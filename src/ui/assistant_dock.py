"""
Basic Image Editor - Smart Reveal Assistant Dock
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal

from src.processing.preset_engine import get_preset_metadata


class RevealAssistantDock(QDockWidget):
    """
    Smart Assistant panel that analyzes the open photo (histogram, dynamic range,
    shadows/highlights, sharpness, and scene type) and provides 1-click actions:
    - Auto-Develop Photo (EV + Shadows + Denoise + Recommended Preset)
    - Apply Recommended Preset
    - Smart Square 1:1 Crop for Instagram
    - Strip AI Watermarks / C2PA & Swirl Noise
    """

    auto_develop_requested = pyqtSignal(bool)
    recommended_preset_requested = pyqtSignal(str)
    smart_crop_1x1_requested = pyqtSignal()
    clean_ai_watermark_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Asistente de Revelado", parent)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self.recommended_preset_id = "electric_chroma_hd"
        self.last_analysis = None

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Asistente Inteligente de Revelado")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #ffffff;")
        layout.addWidget(title)

        # Diagnostic Card
        diag_frame = QFrame()
        diag_frame.setStyleSheet(
            "QFrame { background-color: #22252a; border: 1px solid #353a42; border-radius: 6px; padding: 6px; }"
        )
        diag_layout = QVBoxLayout(diag_frame)
        diag_layout.setContentsMargins(6, 6, 6, 6)
        diag_layout.setSpacing(4)

        self.scene_lbl = QLabel("Escena: Sin imagen cargada")
        self.scene_lbl.setWordWrap(True)
        self.scene_lbl.setStyleSheet("color: #6cb6ff; font-weight: bold; font-size: 12px; border: none;")
        diag_layout.addWidget(self.scene_lbl)

        self.metrics_lbl = QLabel("Carga una foto RAW o estándar para analizar su histograma.")
        self.metrics_lbl.setWordWrap(True)
        self.metrics_lbl.setStyleSheet("color: #cccccc; font-size: 11px; border: none;")
        diag_layout.addWidget(self.metrics_lbl)

        self.tips_lbl = QLabel("")
        self.tips_lbl.setWordWrap(True)
        self.tips_lbl.setStyleSheet("color: #a8d5a2; font-size: 11px; border: none;")
        diag_layout.addWidget(self.tips_lbl)

        layout.addWidget(diag_frame)

        # Action Buttons
        self.btn_auto_reveal = QPushButton("✨ Auto-Revelar Foto (Óptimo)")
        self.btn_auto_reveal.setToolTip(
            "Ajusta automáticamente Exposición (EV), Sombras, Altas Luces, Denoise HD, Nitidez y el Preset ideal."
        )
        self.btn_auto_reveal.setStyleSheet(
            "QPushButton { background-color: #1f883d; font-weight: bold; padding: 8px; }"
            "QPushButton:hover { background-color: #26a148; }"
        )
        self.btn_auto_reveal.clicked.connect(lambda: self.auto_develop_requested.emit(True))
        layout.addWidget(self.btn_auto_reveal)

        self.btn_auto_base_only = QPushButton("☀️ Auto-Exposición y Luz (Sin Preset)")
        self.btn_auto_base_only.setToolTip(
            "Corrige únicamente Exposición, Sombras, Altas Luces y Nitidez manteniendo el color original."
        )
        self.btn_auto_base_only.clicked.connect(lambda: self.auto_develop_requested.emit(False))
        layout.addWidget(self.btn_auto_base_only)

        self.btn_apply_recommended = QPushButton("🎨 Aplicar Preset Sugerido")
        self.btn_apply_recommended.clicked.connect(
            lambda: self.recommended_preset_requested.emit(self.recommended_preset_id)
        )
        layout.addWidget(self.btn_apply_recommended)

        self.btn_insta_1x1 = QPushButton("📐 Encuadre Inteligente Insta 1:1")
        self.btn_insta_1x1.setToolTip(
            "Recorta la imagen en formato cuadrado 1:1 centrando automáticamente la zona de mayor peso visual."
        )
        self.btn_insta_1x1.clicked.connect(self.smart_crop_1x1_requested.emit)
        layout.addWidget(self.btn_insta_1x1)

        self.btn_clean_ai = QPushButton("🛡️ Limpiar Marca de Agua IA / C2PA")
        self.btn_clean_ai.setToolTip(
            "Elimina patrones esteganográficos de alta frecuencia en zonas planas y limpia metadatos C2PA."
        )
        self.btn_clean_ai.clicked.connect(self.clean_ai_watermark_requested.emit)
        layout.addWidget(self.btn_clean_ai)

        layout.addStretch()
        self.setWidget(container)

    def update_analysis(self, analysis: dict | None):
        """Updates the diagnostic labels and recommended preset button from `analyze_image` output."""
        self.last_analysis = analysis
        if not analysis:
            self.scene_lbl.setText("Escena: Sin imagen cargada")
            self.metrics_lbl.setText("Carga una foto RAW o estándar para analizar su histograma.")
            self.tips_lbl.setText("")
            return

        self.recommended_preset_id = analysis["recommended_preset"]
        rec_meta = get_preset_metadata(self.recommended_preset_id)
        alt_meta = get_preset_metadata(analysis["alternative_preset"])

        self.scene_lbl.setText(f"Escena: {analysis['scene_type']}")
        self.metrics_lbl.setText(
            f"• Exposición: {analysis['exposure_status']} (Luma media: {analysis['mean_luma']:.2f})\n"
            f"• Sombras: {int(analysis['shadow_ratio'] * 100)}% | Altas luces: {int(analysis['highlight_ratio'] * 100)}%\n"
            f"• Rango dinámico: {analysis['dynamic_range']:.2f} | Nitidez: {analysis['sharpness_score']:.0f}\n"
            f"• Formato: {analysis['width']}×{analysis['height']} {'(1:1 Cuadrado)' if analysis['is_square'] else ''}\n"
            f"• Sugerido: {rec_meta['name']} (Alt: {alt_meta['name']})"
        )
        tips_html = "<br>".join(f"💡 {t}" for t in analysis.get("tips", []))
        self.tips_lbl.setText(tips_html)
        self.btn_apply_recommended.setText(f"🎨 Aplicar Sugerido: {rec_meta['name']}")
