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
    - Analyzes the open photo (histogram, dynamic range, shadows/highlights, sharpness, scene type)
    - Provides 1-click quick actions (Auto-Develop, Recommended Preset, 1:1 Crop, Clean AI Watermark)
    - Embedded in-process Qwen Chat (0.5B / 1.5B GGUF via llama-cpp-python + NLU engine) to apply,
      tweak, or create/save custom presets via natural language with zero external services.
    """

    auto_develop_requested = pyqtSignal(bool)
    recommended_preset_requested = pyqtSignal(str)
    smart_crop_1x1_requested = pyqtSignal()
    clean_ai_watermark_requested = pyqtSignal()
    chat_command_executed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__("Asistente & Chat IA (Qwen)", parent)
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
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Asistente Inteligente & Chat Qwen")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #ffffff;")
        layout.addWidget(title)

        # Diagnostic Card
        diag_frame = QFrame()
        diag_frame.setStyleSheet(
            "QFrame { background-color: #22252a; border: 1px solid #353a42; border-radius: 6px; padding: 5px; }"
        )
        diag_layout = QVBoxLayout(diag_frame)
        diag_layout.setContentsMargins(6, 5, 6, 5)
        diag_layout.setSpacing(3)

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
            "QPushButton { background-color: #1f883d; font-weight: bold; padding: 6px; }"
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

        row_tools = QHBoxLayout()
        self.btn_insta_1x1 = QPushButton("📐 Insta 1:1")
        self.btn_insta_1x1.setToolTip(
            "Recorta la imagen en formato cuadrado 1:1 centrando automáticamente la zona de mayor peso visual."
        )
        self.btn_insta_1x1.clicked.connect(self.smart_crop_1x1_requested.emit)
        row_tools.addWidget(self.btn_insta_1x1)

        self.btn_clean_ai = QPushButton("🛡️ Limpiar IA")
        self.btn_clean_ai.setToolTip(
            "Elimina patrones esteganográficos de alta frecuencia en zonas planas y limpia metadatos C2PA."
        )
        self.btn_clean_ai.clicked.connect(self.clean_ai_watermark_requested.emit)
        row_tools.addWidget(self.btn_clean_ai)
        layout.addLayout(row_tools)

        # --- Conversational Qwen AI Chat Section ---
        chat_header_row = QHBoxLayout()
        chat_lbl = QLabel("💬 Chat con Qwen:")
        chat_lbl.setStyleSheet("font-weight: bold; font-size: 12px; color: #6cb6ff;")
        chat_header_row.addWidget(chat_lbl)

        self.model_combo = QComboBox()
        self.model_combo.setToolTip("Selecciona el modelo Qwen GGUF integrado (100% en proceso, sin servicios externos)")
        self.model_combo.setStyleSheet(
            "QComboBox { background: #252525; color: #ffffff; border: 1px solid #3A3939; border-radius: 4px; padding: 2px 6px; font-size: 11px; }"
        )
        models = list_embedded_qwen_models()
        for m in models:
            self.model_combo.addItem(m)
        chat_header_row.addWidget(self.model_combo)
        layout.addLayout(chat_header_row)

        self.chat_browser = QTextBrowser()
        self.chat_browser.setOpenExternalLinks(False)
        self.chat_browser.setMinimumHeight(140)
        self.chat_browser.setStyleSheet(
            "QTextBrowser { background-color: #1c1e22; color: #e6e6e6; border: 1px solid #353a42; border-radius: 6px; padding: 6px; font-size: 11px; }"
        )
        self.chat_browser.append(
            "<span style='color:#6cb6ff;'><b>Qwen IA:</b></span> ¡Hola! Pídeme que aplique o modifique "
            "cualquier preset o parámetro. Ejemplos:<br>"
            "• <i>«Pon CineStill al 80% y abre las sombras»</i><br>"
            "• <i>«Hazla más cálida, sube nitidez y guárdalo como Mi Retrato»</i>"
        )
        layout.addWidget(self.chat_browser, stretch=1)

        input_row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Escribe un ajuste o preset (ej. 'más cálida y abre sombras')...")
        self.chat_input.setStyleSheet(
            "QLineEdit { background-color: #252525; color: #ffffff; border: 1px solid #3A3939; border-radius: 4px; padding: 6px; font-size: 12px; }"
        )
        self.chat_input.returnPressed.connect(self.send_chat_message)
        input_row.addWidget(self.chat_input, stretch=1)

        self.btn_send_chat = QPushButton("Enviar")
        self.btn_send_chat.setStyleSheet(
            "QPushButton { background-color: #2a82da; font-weight: bold; padding: 6px 10px; }"
        )
        self.btn_send_chat.clicked.connect(self.send_chat_message)
        input_row.addWidget(self.btn_send_chat)
        layout.addLayout(input_row)

        self.setWidget(container)

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

        self.chat_browser.append(f"<span style='color:#ffcf6b;'><b>Tú:</b></span> {msg}")
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
        self.chat_input.setPlaceholderText("Escribe un ajuste o preset (ej. 'más cálida y abre sombras')...")
        self.chat_input.setFocus()

        reply = result.get("reply", "Ajustes aplicados.")
        self.chat_history.append({"role": "user", "content": user_msg})
        self.chat_history.append({"role": "assistant", "content": reply})

        self.chat_browser.append(f"<span style='color:#6cb6ff;'><b>Qwen IA:</b></span> {reply}")
        self.chat_command_executed.emit(result)

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
