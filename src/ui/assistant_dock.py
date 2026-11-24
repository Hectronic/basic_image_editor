"""
Basic Image Editor - Smart Reveal Assistant & Qwen AI Chat Dock
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
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTextBrowser,
    QLineEdit,
    QComboBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from src.processing.preset_engine import get_preset_metadata
from src.processing.llm_chat_agent import (
    list_embedded_qwen_models,
    query_qwen_agent,
)


class LLMChatWorker(QThread):
    """Background worker thread so embedded Qwen GGUF auto-download & inference never block the Qt GUI."""

    response_ready = pyqtSignal(dict)
    download_progress = pyqtSignal(int, int)

    def __init__(self, user_message: str, state: dict, model_name: str, history: list[dict], parent=None):
        super().__init__(parent)
        self.user_message = user_message
        self.state = state
        self.model_name = model_name
        self.history = list(history)
        self._last_pct = -1

    def _on_progress(self, downloaded: int, total: int):
        pct = int((downloaded * 100) // total) if total > 0 else 0
        if pct != self._last_pct:
            self._last_pct = pct
            self.download_progress.emit(downloaded, total)

    def run(self):
        result = query_qwen_agent(
            user_message=self.user_message,
            state=self.state,
            model_name=self.model_name,
            history=self.history,
            progress_callback=self._on_progress,
        )
        self.response_ready.emit(result)


class RevealAssistantDock(QDockWidget):
    """
    Smart Assistant & 100% Embedded Qwen AI Panel:
    - Compact scene summary with on-demand collapsible histogram diagnostics
    - Calm 1-click actions (Auto-Develop CTA + subtle 2x2 quick actions)
    - Spacious embedded in-process Qwen Chat (0.5B / 1.5B GGUF via llama-cpp-python)
    """

    auto_develop_requested = pyqtSignal(bool)
    recommended_preset_requested = pyqtSignal(str)
    smart_crop_1x1_requested = pyqtSignal()
    clean_ai_watermark_requested = pyqtSignal()
    chat_command_executed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__("💬 Asistente IA", parent)
        self.setMinimumWidth(275)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self.recommended_preset_id = "electric_chroma_hd"
        self.last_analysis = None
        self.chat_history: list[dict] = []
        self._active_worker: LLMChatWorker | None = None
        self._state_provider = None

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # --- Compact Scene Summary Card (Collapsible Details) ---
        diag_frame = QFrame()
        diag_frame.setStyleSheet(
            "QFrame#diagCard { background-color: #181b20; border: 1px solid #262b33; border-radius: 8px; }"
        )
        diag_frame.setObjectName("diagCard")
        diag_layout = QVBoxLayout(diag_frame)
        diag_layout.setContentsMargins(10, 8, 10, 8)
        diag_layout.setSpacing(4)

        top_diag_row = QHBoxLayout()
        self.scene_lbl = QLabel("Sin imagen cargada")
        self.scene_lbl.setWordWrap(True)
        self.scene_lbl.setStyleSheet("color: #e6edf3; font-weight: 600; font-size: 12px; border: none;")
        top_diag_row.addWidget(self.scene_lbl, stretch=1)

        self.btn_toggle_details = QPushButton("Detalles ▾")
        self.btn_toggle_details.setCheckable(True)
        self.btn_toggle_details.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_details.setStyleSheet(
            "QPushButton { background: transparent; color: #58a6ff; border: none; font-size: 11px; padding: 2px 4px; }"
            "QPushButton:hover { color: #79c0ff; }"
        )
        self.btn_toggle_details.toggled.connect(self._toggle_details)
        top_diag_row.addWidget(self.btn_toggle_details)
        diag_layout.addLayout(top_diag_row)

        self.summary_lbl = QLabel("Abre una foto para recibir sugerencias automáticas.")
        self.summary_lbl.setWordWrap(True)
        self.summary_lbl.setStyleSheet("color: #8b949e; font-size: 11px; border: none;")
        diag_layout.addWidget(self.summary_lbl)

        self.details_container = QWidget()
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(0, 6, 0, 2)
        details_layout.setSpacing(4)

        self.metrics_lbl = QLabel("")
        self.metrics_lbl.setWordWrap(True)
        self.metrics_lbl.setStyleSheet("color: #b1bac4; font-size: 11px; border: none;")
        details_layout.addWidget(self.metrics_lbl)

        self.tips_lbl = QLabel("")
        self.tips_lbl.setWordWrap(True)
        self.tips_lbl.setStyleSheet("color: #7ee787; font-size: 11px; border: none;")
        details_layout.addWidget(self.tips_lbl)

        self.details_container.setVisible(False)
        diag_layout.addWidget(self.details_container)
        layout.addWidget(diag_frame)

        # --- Primary Action + Subtle 2x2 Quick Tools ---
        self.btn_auto_reveal = QPushButton("✨ Auto-Revelar Foto")
        self.btn_auto_reveal.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_auto_reveal.setToolTip(
            "Ajusta automáticamente Exposición (EV), Sombras, Altas Luces, Denoise HD, Nitidez y el Preset ideal."
        )
        self.btn_auto_reveal.setStyleSheet(
            "QPushButton { background-color: #238636; color: #ffffff; font-weight: 600; "
            "font-size: 12px; padding: 8px 12px; border-radius: 6px; border: 1px solid #2ea043; }"
            "QPushButton:hover { background-color: #2ea043; }"
        )
        self.btn_auto_reveal.clicked.connect(lambda: self.auto_develop_requested.emit(True))
        layout.addWidget(self.btn_auto_reveal)

        grid = QGridLayout()
        grid.setSpacing(6)

        self.btn_apply_recommended = QPushButton("🎨 Preset Sugerido")
        self.btn_apply_recommended.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply_recommended.setToolTip("Aplicar el preset recomendado por el análisis de escena.")
        self.btn_apply_recommended.clicked.connect(
            lambda: self.recommended_preset_requested.emit(self.recommended_preset_id)
        )
        grid.addWidget(self.btn_apply_recommended, 0, 0)

        self.btn_auto_base_only = QPushButton("☀️ Solo Luz")
        self.btn_auto_base_only.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_auto_base_only.setToolTip(
            "Corrige Exposición, Sombras, Altas Luces y Nitidez manteniendo el color original."
        )
        self.btn_auto_base_only.clicked.connect(lambda: self.auto_develop_requested.emit(False))
        grid.addWidget(self.btn_auto_base_only, 0, 1)

        self.btn_insta_1x1 = QPushButton("📐 Encuadre 1:1")
        self.btn_insta_1x1.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_insta_1x1.setToolTip(
            "Recorta en formato cuadrado 1:1 centrando automáticamente el sujeto principal."
        )
        self.btn_insta_1x1.clicked.connect(self.smart_crop_1x1_requested.emit)
        grid.addWidget(self.btn_insta_1x1, 1, 0)

        self.btn_clean_ai = QPushButton("🛡️ Limpiar IA")
        self.btn_clean_ai.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clean_ai.setToolTip(
            "Elimina patrones esteganográficos de alta frecuencia en zonas planas y limpia metadatos C2PA."
        )
        self.btn_clean_ai.clicked.connect(self.clean_ai_watermark_requested.emit)
        grid.addWidget(self.btn_clean_ai, 1, 1)

        layout.addLayout(grid)

        # --- Conversational Qwen AI Chat Section (Spacious) ---
        chat_header_row = QHBoxLayout()
        chat_lbl = QLabel("Chat Qwen IA")
        chat_lbl.setStyleSheet("font-weight: 600; font-size: 12px; color: #8b949e;")
        chat_header_row.addWidget(chat_lbl)
        chat_header_row.addStretch()

        self.model_combo = QComboBox()
        self.model_combo.setToolTip("Modelo Qwen GGUF integrado (100% local en proceso, auto-descargable)")
        self.model_combo.setStyleSheet(
            "QComboBox { background: #181b20; color: #c9d1d9; border: 1px solid #2d333b; "
            "border-radius: 5px; padding: 3px 8px; font-size: 11px; }"
        )
        for m in list_embedded_qwen_models():
            self.model_combo.addItem(m)
        chat_header_row.addWidget(self.model_combo)
        layout.addLayout(chat_header_row)

        self.chat_browser = QTextBrowser()
        self.chat_browser.setOpenExternalLinks(False)
        self.chat_browser.setMinimumHeight(180)
        self.chat_browser.setStyleSheet(
            "QTextBrowser { background-color: #16191e; color: #d0d7de; "
            "border: 1px solid #262b33; border-radius: 8px; padding: 10px; font-size: 12px; }"
        )
        self.chat_browser.append(
            "<div style='margin-bottom:6px;'><span style='color:#58a6ff;font-weight:600;'>Qwen IA</span><br>"
            "<span style='color:#8b949e;'>Pídeme ajustes o presets en lenguaje natural. Por ejemplo:<br>"
            "• <i>«Pon CineStill al 80% y abre las sombras»</i><br>"
            "• <i>«Más cálida, sin grano y guárdalo como Mi Retrato»</i></span></div>"
        )
        layout.addWidget(self.chat_browser, stretch=1)

        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Pide un ajuste o preset...")
        self.chat_input.setStyleSheet(
            "QLineEdit { background-color: #16191e; color: #f0f3f6; border: 1px solid #2d333b; "
            "border-radius: 6px; padding: 7px 10px; font-size: 12px; }"
            "QLineEdit:focus { border: 1px solid #388bfd; }"
        )
        self.chat_input.returnPressed.connect(self.send_chat_message)
        input_row.addWidget(self.chat_input, stretch=1)

        self.btn_send_chat = QPushButton("Enviar")
        self.btn_send_chat.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send_chat.setStyleSheet(
            "QPushButton { background-color: #2f81f7; color: #ffffff; font-weight: 600; "
            "padding: 7px 14px; border-radius: 6px; border: none; }"
            "QPushButton:hover { background-color: #388bfd; }"
            "QPushButton:disabled { background-color: #21262d; color: #8b949e; }"
        )
        self.btn_send_chat.clicked.connect(self.send_chat_message)
        input_row.addWidget(self.btn_send_chat)
        layout.addLayout(input_row)

        self.setWidget(container)

    def _toggle_details(self, checked: bool):
        self.details_container.setVisible(checked)
        self.btn_toggle_details.setText("Detalles ▴" if checked else "Detalles ▾")

    def set_state_provider(self, provider_callable):
        """Registers a callable returning the active photo's current state dict for the LLM."""
        self._state_provider = provider_callable

    def get_current_state(self) -> dict:
        if callable(self._state_provider):
            state = self._state_provider()
            if isinstance(state, dict):
                return state
        base = {
            "active_preset": "none",
            "preset_intensity": 1.0,
            "ev": 0.0,
            "shadows": 0.0,
            "highlights": 0.0,
            "wb_temp": 0.0,
            "denoise": 0.0,
            "sharpen": 0.0,
            "brightness": 1.0,
            "contrast": 1.0,
            "saturation": 1.0,
            "scene_type": "Desconocida",
            "recommended_preset": self.recommended_preset_id,
        }
        if self.last_analysis:
            base["scene_type"] = self.last_analysis.get("scene_type", "Desconocida")
            base["recommended_preset"] = self.last_analysis.get("recommended_preset", self.recommended_preset_id)
        return base

    def send_chat_message(self, text: str | None = None, run_sync: bool = False):
        """Sends a user message from the input box (or passed directly) to the Qwen agent."""
        msg = (text if isinstance(text, str) else self.chat_input.text()).strip()
        if not msg:
            return
        if not isinstance(text, str):
            self.chat_input.clear()

        self.chat_browser.append(
            f"<div style='margin-top:6px;'><span style='color:#d29922;font-weight:600;'>Tú:</span> {msg}</div>"
        )
        state = self.get_current_state()
        model_name = self.model_combo.currentText() or "Qwen 2.5 0.5B (Integrado Rápido)"

        if run_sync:
            res = query_qwen_agent(
                user_message=msg,
                state=state,
                model_name=model_name,
                history=self.chat_history,
            )
            self._on_agent_response(msg, res)
            return

        self.btn_send_chat.setEnabled(False)
        self.chat_input.setEnabled(False)
        self.btn_send_chat.setText("...")
        self._active_worker = LLMChatWorker(msg, state, model_name, self.chat_history, self)
        self._active_worker.download_progress.connect(self._on_download_progress)
        self._active_worker.response_ready.connect(lambda res: self._on_agent_response(msg, res))
        self._active_worker.start()

    def _on_download_progress(self, downloaded: int, total: int):
        mb_done = downloaded / (1024 * 1024)
        if total > 0:
            pct = int((downloaded * 100) // total)
            mb_tot = total / (1024 * 1024)
            self.btn_send_chat.setText(f"⬇ {pct}%")
            self.chat_input.setPlaceholderText(f"Descargando modelo Qwen ({mb_done:.0f}/{mb_tot:.0f} MB)...")
        else:
            self.btn_send_chat.setText(f"⬇ {mb_done:.0f}M")

    def _on_agent_response(self, user_msg: str, result: dict):
        self.btn_send_chat.setEnabled(True)
        self.btn_send_chat.setText("Enviar")
        self.chat_input.setEnabled(True)
        self.chat_input.setPlaceholderText("Pide un ajuste o preset...")
        self.chat_input.setFocus()

        reply = result.get("reply", "Ajustes aplicados.")
        self.chat_history.append({"role": "user", "content": user_msg})
        self.chat_history.append({"role": "assistant", "content": reply})

        self.chat_browser.append(
            f"<div style='margin-top:4px;margin-bottom:4px;'><span style='color:#58a6ff;font-weight:600;'>Qwen IA:</span> {reply}</div>"
        )
        self.chat_command_executed.emit(result)

    def update_analysis(self, analysis: dict | None):
        """Updates the compact summary and collapsible diagnostic labels from `analyze_image` output."""
        self.last_analysis = analysis
        if not analysis:
            self.scene_lbl.setText("Sin imagen cargada")
            self.summary_lbl.setText("Abre una foto para recibir sugerencias automáticas.")
            self.metrics_lbl.setText("")
            self.tips_lbl.setText("")
            self.btn_apply_recommended.setText("🎨 Preset Sugerido")
            return

        self.recommended_preset_id = analysis["recommended_preset"]
        rec_meta = get_preset_metadata(self.recommended_preset_id)
        alt_meta = get_preset_metadata(analysis["alternative_preset"])

        self.scene_lbl.setText(analysis["scene_type"])
        self.summary_lbl.setText(
            f"{analysis['exposure_status']} · Sugerido: {rec_meta['name']}"
        )
        self.metrics_lbl.setText(
            f"• Luma media: {analysis['mean_luma']:.2f} | Rango dinámico: {analysis['dynamic_range']:.2f}\n"
            f"• Sombras: {int(analysis['shadow_ratio'] * 100)}% | Altas luces: {int(analysis['highlight_ratio'] * 100)}%\n"
            f"• Nitidez: {analysis['sharpness_score']:.0f} | {analysis['width']}×{analysis['height']}\n"
            f"• Alternativa: {alt_meta['name']}"
        )
        tips_html = "<br>".join(f"💡 {t}" for t in analysis.get("tips", []))
        self.tips_lbl.setText(tips_html)
        self.btn_apply_recommended.setText(f"🎨 {rec_meta['name']}")
