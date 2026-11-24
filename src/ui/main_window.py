"""
Basic Image Editor
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QToolBar,
    QFileDialog,
    QLabel,
    QSlider,
    QPushButton,
    QDockWidget,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QApplication,
    QTabWidget,
    QScrollArea,
    QTabBar,
    QFrame,
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QAction, QIcon, QPalette, QColor, QFont

from src.ui.editor_tab import EditorTab
from src.ui.start_page import StartPageWidget
from src.ui.preset_gallery_dock import PresetGalleryDock
from src.ui.assistant_dock import RevealAssistantDock

import os
import logging

logger = logging.getLogger(__name__)


class ImageEditorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Basic Image Editor — RAW & Preset Studio")

        logo_path = os.path.abspath("logo.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        self.resize(1380, 880)
        self.setDockOptions(
            QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks
        )
        self.setTabPosition(
            Qt.DockWidgetArea.LeftDockWidgetArea, QTabWidget.TabPosition.North
        )

        self._updating_history_ui = False
        self._slider_value_labels: dict[QSlider, tuple[QLabel, callable]] = {}
        self._pending_slider_desc = "Ajuste de Revelado"
        self._slider_commit_timer = QTimer(self)
        self._slider_commit_timer.setSingleShot(True)
        self._slider_commit_timer.setInterval(350)
        self._slider_commit_timer.timeout.connect(self._commit_pending_slider_change)

        # Central Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabs.setStyleSheet(
            """
            QTabWidget::pane { border: 0; background: #141619; }
            QTabBar { background: #181b20; }
            QTabBar::tab {
                background: #181b20;
                color: #8b949e;
                padding: 8px 18px;
                margin-right: 1px;
                border-bottom: 2px solid transparent;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #141619;
                color: #f0f3f6;
                font-weight: 600;
                border-bottom: 2px solid #2f81f7;
            }
            QTabBar::tab:hover:!selected {
                background: #1f242c;
                color: #c9d1d9;
            }
            """
        )
        self.setCentralWidget(self.tabs)

        # Actions References (to enable/disable)
        self.actions = {}

        # Setup UI & Styling
        self.setup_ui()
        self.setup_styling()

        self.recent_files = self.load_recents()

        # Open Start Page
        self.open_start_page()

        logger.info("Application started, main window initialized.")

    def setup_ui(self):
        # --- Single Clean Main Toolbar ---
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        self.main_toolbar = toolbar

        open_act = QAction(QIcon.fromTheme("document-open"), "Abrir", self)
        open_act.setShortcut("Ctrl+O")
        open_act.setToolTip("Abrir imagen o archivo RAW (Ctrl+O)")
        open_act.triggered.connect(self.open_image_dialog)
        toolbar.addAction(open_act)

        save_act = QAction(QIcon.fromTheme("document-save"), "Guardar", self)
        save_act.setShortcut("Ctrl+S")
        save_act.setToolTip("Exportar imagen revelada (Ctrl+S)")
        save_act.triggered.connect(self.save_image)
        toolbar.addAction(save_act)
        self.actions["save"] = save_act

        toolbar.addSeparator()

        # Undo / Redo (Icon-compact to keep toolbar calm)
        undo_act = QAction(QIcon.fromTheme("edit-undo"), "Deshacer", self)
        undo_act.setShortcut("Ctrl+Z")
        undo_act.setToolTip("Deshacer último cambio (Ctrl+Z)")
        undo_act.triggered.connect(self.undo_action)
        undo_act.setEnabled(False)
        toolbar.addAction(undo_act)
        self.actions["undo"] = undo_act

        redo_act = QAction(QIcon.fromTheme("edit-redo"), "Rehacer", self)
        redo_act.setShortcut("Ctrl+Shift+Z")
        redo_act.setToolTip("Rehacer cambio (Ctrl+Shift+Z)")
        redo_act.triggered.connect(self.redo_action)
        redo_act.setEnabled(False)
        toolbar.addAction(redo_act)
        self.actions["redo"] = redo_act

        toolbar.addSeparator()

        # Zoom & Geometry (Icon-only for clean visual rhythm)
        zoom_in_act = QAction(QIcon.fromTheme("zoom-in"), "+", self)
        zoom_in_act.setShortcut("Ctrl++")
        zoom_in_act.setToolTip("Acercar vista (Ctrl++)")
        zoom_in_act.triggered.connect(lambda: self.zoom(1.1))
        toolbar.addAction(zoom_in_act)
        self.actions["zoom_in"] = zoom_in_act

        zoom_out_act = QAction(QIcon.fromTheme("zoom-out"), "−", self)
        zoom_out_act.setShortcut("Ctrl+-")
        zoom_out_act.setToolTip("Alejar vista (Ctrl+-)")
        zoom_out_act.triggered.connect(lambda: self.zoom(0.9))
        toolbar.addAction(zoom_out_act)
        self.actions["zoom_out"] = zoom_out_act

        rot_left_act = QAction(QIcon.fromTheme("object-rotate-left"), "⟲", self)
        rot_left_act.setToolTip("Rotar 90° a la izquierda")
        rot_left_act.triggered.connect(lambda: self.rotate_image(90))
        toolbar.addAction(rot_left_act)
        self.actions["rotate_left"] = rot_left_act

        rot_right_act = QAction(QIcon.fromTheme("object-rotate-right"), "⟳", self)
        rot_right_act.setToolTip("Rotar 90° a la derecha")
        rot_right_act.triggered.connect(lambda: self.rotate_image(-90))
        toolbar.addAction(rot_right_act)
        self.actions["rotate_right"] = rot_right_act

        flip_h_act = QAction(QIcon.fromTheme("object-flip-horizontal"), "⇆", self)
        flip_h_act.setToolTip("Voltear horizontalmente")
        flip_h_act.triggered.connect(lambda: self.flip_image(True))
        toolbar.addAction(flip_h_act)
        self.actions["flip_h"] = flip_h_act

        flip_v_act = QAction(QIcon.fromTheme("object-flip-vertical"), "⇅", self)
        flip_v_act.setToolTip("Voltear verticalmente")
        flip_v_act.triggered.connect(lambda: self.flip_image(False))
        toolbar.addAction(flip_v_act)
        self.actions["flip_v"] = flip_v_act

        self.crop_act = QAction(QIcon.fromTheme("crop"), "Recortar", self)
        self.crop_act.setCheckable(True)
        self.crop_act.setToolTip("Recorte libre en lienzo (Enter para aplicar, Esc para cancelar)")
        self.crop_act.triggered.connect(self.toggle_crop)
        toolbar.addAction(self.crop_act)
        self.actions["crop"] = self.crop_act

        toolbar.addSeparator()

        # Smart Reveal Quick Actions
        auto_reveal_act = QAction("✨ Auto-Revelar", self)
        auto_reveal_act.setShortcut("Ctrl+R")
        auto_reveal_act.setToolTip("Auto-Revelar foto con asistente inteligente (Ctrl+R)")
        auto_reveal_act.triggered.connect(lambda: self.trigger_auto_develop(True))
        toolbar.addAction(auto_reveal_act)
        self.actions["auto_reveal"] = auto_reveal_act

        insta_crop_act = QAction("📐 1:1", self)
        insta_crop_act.setToolTip("Encuadre cuadrado inteligente 1:1")
        insta_crop_act.triggered.connect(self.trigger_smart_crop_1x1)
        toolbar.addAction(insta_crop_act)
        self.actions["insta_1x1"] = insta_crop_act

        clean_ai_act = QAction("🛡️ Limpiar IA", self)
        clean_ai_act.setToolTip("Eliminar marcas de agua IA / C2PA")
        clean_ai_act.triggered.connect(self.trigger_clean_ai_watermark)
        toolbar.addAction(clean_ai_act)
        self.actions["clean_ai"] = clean_ai_act

        rembg_act = QAction("✂️ Fondo", self)
        rembg_act.setToolTip("Eliminar fondo de la imagen con IA")
        rembg_act.triggered.connect(self.remove_background)
        toolbar.addAction(rembg_act)
        self.actions["rembg"] = rembg_act

        toolbar.addSeparator()

        # Collapsible Annotation Bar Toggle (keeps UI uncluttered by default)
        self.toggle_draw_toolbar_act = QAction("✏️ Anotar", self)
        self.toggle_draw_toolbar_act.setCheckable(True)
        self.toggle_draw_toolbar_act.setChecked(False)
        self.toggle_draw_toolbar_act.setToolTip("Mostrar u ocultar herramientas de dibujo y anotación")
        self.toggle_draw_toolbar_act.toggled.connect(self._on_toggle_draw_toolbar)
        toolbar.addAction(self.toggle_draw_toolbar_act)
        self.actions["toggle_annotate"] = self.toggle_draw_toolbar_act

        # --- Secondary Drawing Toolbar (Hidden by default until user clicks '✏️ Anotar') ---
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        draw_toolbar = QToolBar("Drawing Toolbar")
        draw_toolbar.setMovable(False)
        draw_toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, draw_toolbar)
        draw_toolbar.setVisible(False)
        self.draw_toolbar = draw_toolbar

        self.select_act = QAction(QIcon.fromTheme("input-mouse"), "Seleccionar", self)
        self.select_act.setCheckable(True)
        self.select_act.setChecked(True)
        self.select_act.triggered.connect(lambda: self.set_draw_mode("SELECT_SHAPE"))
        draw_toolbar.addAction(self.select_act)
        self.actions["draw_select"] = self.select_act

        self.draw_pen_act = QAction(QIcon.fromTheme("draw-freehand"), "Trazo", self)
        self.draw_pen_act.setCheckable(True)
        self.draw_pen_act.triggered.connect(lambda: self.set_draw_mode("DRAW_PEN"))
        draw_toolbar.addAction(self.draw_pen_act)
        self.actions["draw_pen"] = self.draw_pen_act

        self.draw_eraser_act = QAction(QIcon.fromTheme("draw-eraser"), "Borrador", self)
        if self.draw_eraser_act.icon().isNull():
            self.draw_eraser_act.setIcon(QIcon.fromTheme("edit-clear"))
        self.draw_eraser_act.setCheckable(True)
        self.draw_eraser_act.triggered.connect(lambda: self.set_draw_mode("DRAW_ERASER"))
        draw_toolbar.addAction(self.draw_eraser_act)
        self.actions["draw_eraser"] = self.draw_eraser_act

        draw_toolbar.addSeparator()

        self.draw_line_act = QAction(QIcon.fromTheme("draw-line"), "Línea", self)
        self.draw_line_act.setCheckable(True)
        self.draw_line_act.triggered.connect(lambda: self.set_draw_mode("DRAW_LINE"))
        draw_toolbar.addAction(self.draw_line_act)
        self.actions["draw_line"] = self.draw_line_act

        self.draw_arrow_act = QAction(QIcon.fromTheme("draw-arrow"), "Flecha", self)
        self.draw_arrow_act.setCheckable(True)
        self.draw_arrow_act.triggered.connect(lambda: self.set_draw_mode("DRAW_ARROW"))
        draw_toolbar.addAction(self.draw_arrow_act)
        self.actions["draw_arrow"] = self.draw_arrow_act

        self.draw_rect_act = QAction(QIcon.fromTheme("draw-rectangle"), "Rectángulo", self)
        self.draw_rect_act.setCheckable(True)
        self.draw_rect_act.triggered.connect(lambda: self.set_draw_mode("DRAW_RECT"))
        draw_toolbar.addAction(self.draw_rect_act)
        self.actions["draw_rect"] = self.draw_rect_act

        self.draw_ellipse_act = QAction(QIcon.fromTheme("draw-ellipse"), "Elipse", self)
        self.draw_ellipse_act.setCheckable(True)
        self.draw_ellipse_act.triggered.connect(lambda: self.set_draw_mode("DRAW_ELLIPSE"))
        draw_toolbar.addAction(self.draw_ellipse_act)
        self.actions["draw_ellipse"] = self.draw_ellipse_act

        self.draw_text_act = QAction(QIcon.fromTheme("draw-text"), "Texto", self)
        self.draw_text_act.setCheckable(True)
        self.draw_text_act.triggered.connect(lambda: self.set_draw_mode("DRAW_TEXT"))
        draw_toolbar.addAction(self.draw_text_act)
        self.actions["draw_text"] = self.draw_text_act

        draw_toolbar.addSeparator()

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(22, 22)
        self.color_btn.setToolTip("Color de anotación")
        self.color_btn.setStyleSheet("background-color: #ff4d4f; border: 1px solid #484f58; border-radius: 4px;")
        self.color_btn.clicked.connect(self.choose_color)
        draw_toolbar.addWidget(self.color_btn)
        self.current_color = QColor(255, 77, 79)

        width_lbl = QLabel(" Grosor: ")
        width_lbl.setStyleSheet("color: #8b949e; font-size: 11px; margin-left: 6px;")
        draw_toolbar.addWidget(width_lbl)

        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(1, 20)
        self.width_slider.setValue(3)
        self.width_slider.setFixedWidth(84)
        self.width_slider.valueChanged.connect(self.width_changed)
        draw_toolbar.addWidget(self.width_slider)
        self.current_width = 3

        # --- Left Docks: Tabified (Presets | Asistente IA) for spacious full-height panels ---
        self.preset_dock = PresetGalleryDock(self)
        self.preset_dock.preset_selected.connect(self.on_preset_selected)
        self.preset_dock.intensity_changed.connect(self.on_preset_intensity_changed)
        self.preset_dock.intensity_committed.connect(self.on_preset_intensity_committed)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.preset_dock)

        self.assistant_dock = RevealAssistantDock(self)
        self.assistant_dock.set_state_provider(self.get_active_photo_state)
        self.assistant_dock.auto_develop_requested.connect(self.trigger_auto_develop)
        self.assistant_dock.recommended_preset_requested.connect(self.on_recommended_preset_clicked)
        self.assistant_dock.smart_crop_1x1_requested.connect(self.trigger_smart_crop_1x1)
        self.assistant_dock.clean_ai_watermark_requested.connect(self.trigger_clean_ai_watermark)
        self.assistant_dock.chat_command_executed.connect(self.on_chat_command_executed)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.assistant_dock)

        # Tabify left docks so they never crush each other vertically
        self.tabifyDockWidget(self.preset_dock, self.assistant_dock)
        self.preset_dock.raise_()

        # --- Right Sidebar: Interactive History & Parametric Reveal ---
        dock = QDockWidget("Revelado & Historial", self)
        dock.setMinimumWidth(285)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        dock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        sidebar = QWidget()
        scroll.setWidget(sidebar)
        dock.setWidget(scroll)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.dock = dock

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Interactive History Card ---
        hist_header = QHBoxLayout()
        history_lbl = QLabel("Historial")
        history_lbl.setStyleSheet("font-weight: 600; font-size: 13px; color: #f0f3f6;")
        hist_header.addWidget(history_lbl)
        hist_header.addStretch()

        self.reset_btn = QPushButton("Reiniciar")
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.setToolTip("Restablecer todos los parámetros y presets al estado base")
        self.reset_btn.setStyleSheet(
            "QPushButton { background: #21262d; color: #c9d1d9; border: 1px solid #30363d; "
            "border-radius: 5px; padding: 3px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #292f38; border-color: #8b949e; }"
        )
        self.reset_btn.clicked.connect(self.reset_adjustments)
        hist_header.addWidget(self.reset_btn)
        layout.addLayout(hist_header)

        hist_hint = QLabel("Selecciona cualquier estado para volver a ese punto")
        hist_hint.setStyleSheet("color: #6e7681; font-size: 11px;")
        layout.addWidget(hist_hint)

        self.history_list = QListWidget()
        self.history_list.setMinimumHeight(135)
        self.history_list.setMaximumHeight(195)
        self.history_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.history_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.history_list.setStyleSheet(
            """
            QListWidget {
                background-color: #16191e;
                border: 1px solid #262b33;
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 5px;
                color: #c9d1d9;
                font-size: 12px;
            }
            QListWidget::item:hover {
                background-color: #21262d;
            }
            QListWidget::item:selected {
                background-color: #1f2d3d;
                color: #ffffff;
                border: 1px solid #388bfd;
            }
            """
        )
        self.history_list.currentRowChanged.connect(self.on_history_row_selected)
        self.history_list.itemClicked.connect(self._on_history_item_clicked)
        layout.addWidget(self.history_list)

        # Subtle section divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setStyleSheet("color: #262b33; background-color: #262b33; max-height: 1px; border: none;")
        layout.addWidget(div1)

        # --- RAW / Reveal Parametric Sliders ---
        reveal_lbl = QLabel("Revelado Fotográfico")
        reveal_lbl.setStyleSheet("font-weight: 600; font-size: 13px; color: #f0f3f6; margin-top: 2px;")
        layout.addWidget(reveal_lbl)

        self.sl_ev = self.create_reveal_slider(
            layout, "Exposición", -1.5, 1.5, 0.0, fmt=lambda v: f"{v:+.2f} EV"
        )
        self.sl_shadows = self.create_reveal_slider(
            layout, "Sombras", -1.0, 1.0, 0.0, fmt=lambda v: f"{int(round(v * 100)):+d}%"
        )
        self.sl_highlights = self.create_reveal_slider(
            layout, "Altas Luces", -1.0, 1.0, 0.0, fmt=lambda v: f"{int(round(v * 100)):+d}%"
        )
        self.sl_wb_temp = self.create_reveal_slider(
            layout, "Temperatura WB", -1.0, 1.0, 0.0, fmt=lambda v: f"{int(round(v * 100)):+d}%"
        )
        self.sl_denoise = self.create_reveal_slider(
            layout, "Reducción de Ruido", 0.0, 1.0, 0.0, fmt=lambda v: f"{int(round(v * 100))}%"
        )
        self.sl_sharpen = self.create_reveal_slider(
            layout, "Nitidez HD", 0.0, 1.0, 0.0, fmt=lambda v: f"{int(round(v * 100))}%"
        )

        # Subtle section divider
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet("color: #262b33; background-color: #262b33; max-height: 1px; border: none;")
        layout.addWidget(div2)

        # --- Collapsible Classic Adjustments (collapsed by default to reduce density) ---
        self.btn_toggle_classic = QPushButton("▸ Ajustes Clásicos (Brillo, Contraste, Saturación)")
        self.btn_toggle_classic.setCheckable(True)
        self.btn_toggle_classic.setChecked(False)
        self.btn_toggle_classic.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_classic.setStyleSheet(
            "QPushButton { background: transparent; color: #8b949e; border: none; "
            "text-align: left; font-weight: 600; font-size: 12px; padding: 4px 0px; }"
            "QPushButton:hover { color: #c9d1d9; }"
        )
        self.btn_toggle_classic.toggled.connect(self._on_toggle_classic_section)
        layout.addWidget(self.btn_toggle_classic)

        self.classic_container = QWidget()
        classic_layout = QVBoxLayout(self.classic_container)
        classic_layout.setContentsMargins(0, 4, 0, 0)
        classic_layout.setSpacing(8)

        self.sl_brightness = self.create_slider(
            classic_layout, "Brillo", 0.0, 2.0, 1.0, fmt=lambda v: f"{int(round(v * 100))}%"
        )
        self.sl_contrast = self.create_slider(
            classic_layout, "Contraste", 0.0, 2.0, 1.0, fmt=lambda v: f"{int(round(v * 100))}%"
        )
        self.sl_saturation = self.create_slider(
            classic_layout, "Saturación", 0.0, 2.0, 1.0, fmt=lambda v: f"{int(round(v * 100))}%"
        )
        self.classic_container.setVisible(False)
        layout.addWidget(self.classic_container)

        layout.addStretch()

    def _build_labeled_slider(
        self,
        parent_layout,
        label_text: str,
        min_val: float,
        max_val: float,
        default_val: float,
        on_change_slot,
        fmt=None,
    ) -> QSlider:
        if fmt is None:
            fmt = lambda v: f"{v:.2f}"

        block = QVBoxLayout()
        block.setContentsMargins(0, 2, 0, 2)
        block.setSpacing(3)

        header = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #c9d1d9; font-size: 12px;")
        header.addWidget(lbl)
        header.addStretch()

        val_lbl = QLabel(fmt(default_val))
        val_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-family: monospace;")
        header.addWidget(val_lbl)
        block.addLayout(header)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(round(min_val * 100)), int(round(max_val * 100)))
        slider.setValue(int(round(default_val * 100)))
        self._slider_value_labels[slider] = (val_lbl, fmt)

        def _handle_value_changed(_raw_val: int):
            val_lbl.setText(fmt(slider.value() / 100.0))
            on_change_slot()
            self._pending_slider_desc = f"Ajuste: {label_text}"
            if not slider.isSliderDown():
                self._slider_commit_timer.start()

        def _handle_released():
            self._slider_commit_timer.stop()
            current = self.tabs.currentWidget()
            if isinstance(current, EditorTab):
                current.commit_slider_change(f"Ajuste: {label_text}")

        slider.valueChanged.connect(_handle_value_changed)
        slider.sliderPressed.connect(self.slider_pressed)
        slider.sliderReleased.connect(_handle_released)

        block.addWidget(slider)
        parent_layout.addLayout(block)
        return slider

    def create_slider(self, parent_layout, label_text, min_val, max_val, default_val, fmt=None):
        return self._build_labeled_slider(
            parent_layout,
            label_text,
            min_val,
            max_val,
            default_val,
            self.adjustments_changed,
            fmt=fmt,
        )

    def create_reveal_slider(self, parent_layout, label_text, min_val, max_val, default_val, fmt=None):
        return self._build_labeled_slider(
            parent_layout,
            label_text,
            min_val,
            max_val,
            default_val,
            self.reveal_sliders_changed,
            fmt=fmt,
        )

    def _refresh_slider_labels(self):
        for slider, (val_lbl, fmt) in self._slider_value_labels.items():
            val_lbl.setText(fmt(slider.value() / 100.0))

    def _commit_pending_slider_change(self):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.commit_slider_change(self._pending_slider_desc)

    def _on_toggle_classic_section(self, checked: bool):
        self.classic_container.setVisible(checked)
        self.btn_toggle_classic.setText(
            "▾ Ajustes Clásicos (Brillo, Contraste, Saturación)"
            if checked
            else "▸ Ajustes Clásicos (Brillo, Contraste, Saturación)"
        )

    def _on_toggle_draw_toolbar(self, checked: bool):
        is_editor = isinstance(self.tabs.currentWidget(), EditorTab)
        self.draw_toolbar.setVisible(checked and is_editor)

    def setup_styling(self):
        """Sets a calm, modern dark-studio theme with subtle surfaces and clean contrast."""
        self.setAutoFillBackground(True)
        app = QApplication.instance()

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#1c2026"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#e6edf3"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#141619"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1c2026"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#21262d"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f0f3f6"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#e6edf3"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#21262d"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#c9d1d9"))
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff7b72"))
        palette.setColor(QPalette.ColorRole.Link, QColor("#58a6ff"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#2f81f7"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))

        app.setPalette(palette)

        app.setStyleSheet(
            """
            QMainWindow {
                background-color: #141619;
            }
            QMainWindow::separator {
                background-color: #262b33;
                width: 1px;
                height: 1px;
            }
            QToolTip {
                color: #f0f3f6;
                background-color: #21262d;
                border: 1px solid #30363d;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QToolBar {
                background-color: #181b20;
                border-bottom: 1px solid #262b33;
                spacing: 4px;
                padding: 4px 8px;
            }
            QToolBar::separator {
                background-color: #2d333b;
                width: 1px;
                margin: 4px 6px;
            }
            QToolButton {
                background: transparent;
                color: #c9d1d9;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 12px;
            }
            QToolButton:hover {
                background-color: #21262d;
                border-color: #30363d;
                color: #ffffff;
            }
            QToolButton:checked {
                background-color: #1f2d3d;
                border-color: #388bfd;
                color: #58a6ff;
            }
            QToolButton:disabled {
                color: #484f58;
            }
            QDockWidget {
                color: #e6edf3;
                font-size: 12px;
            }
            QDockWidget::title {
                background: #181b20;
                color: #8b949e;
                padding: 7px 12px;
                border-bottom: 1px solid #262b33;
                font-weight: 600;
            }
            QTabBar::tab {
                background: #181b20;
                color: #8b949e;
                padding: 7px 14px;
                border-bottom: 2px solid transparent;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #1c2026;
                color: #f0f3f6;
                font-weight: 600;
                border-bottom: 2px solid #2f81f7;
            }
            QSlider::groove:horizontal {
                border: none;
                height: 4px;
                background: #2d333b;
                margin: 4px 0;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #2f81f7;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #e6edf3;
                border: 2px solid #2f81f7;
                width: 12px;
                height: 12px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #ffffff;
                border-color: #58a6ff;
            }
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border-radius: 6px;
                padding: 6px 10px;
                border: 1px solid #30363d;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #292f38;
                border-color: #484f58;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #16191e;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #30363d;
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #484f58;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )

    def open_start_page(self):
        start_page = StartPageWidget(self.recent_files)
        start_page.file_opened.connect(self.handle_file_opened)
        index = self.tabs.addTab(start_page, "Inicio")
        self.tabs.setCurrentWidget(start_page)
        self.tabs.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, None)
        self.tab_ui_update()

    def open_image_dialog(self):
        file_filter = (
            "All Supported Photos (*.png *.jpg *.jpeg *.bmp *.tif *.tiff "
            "*.arw *.ARW *.cr2 *.CR2 *.cr3 *.CR3 *.nef *.NEF *.dng *.DNG *.raf *.RAF *.orf *.ORF);;"
            "RAW Photos (*.arw *.ARW *.cr2 *.CR2 *.cr3 *.CR3 *.nef *.NEF *.dng *.DNG *.raf *.RAF *.orf *.ORF);;"
            "Standard Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Photo / RAW", "", file_filter
        )
        if file_path:
            self.create_editor_tab(file_path)
            logger.info(f"Opened image: {file_path}")

    def handle_file_opened(self, path):
        if not path:
            self.open_image_dialog()
        else:
            self.create_editor_tab(path)

    def create_editor_tab(self, file_path):
        tab = EditorTab()
        if tab.load_image(file_path):
            filename = os.path.basename(file_path)
            index = self.tabs.addTab(tab, filename)
            self.tabs.setCurrentIndex(index)
            self.update_recents(file_path)

            tab.history_updated.connect(lambda: self.update_history_ui(tab))
            self.update_history_ui(tab)
            self.refresh_reveal_panels(tab)
        else:
            QMessageBox.warning(self, "Error", "Failed to load image.")

    def refresh_reveal_panels(self, tab: EditorTab):
        """Updates Preset Gallery thumbnails and Smart Assistant diagnosis for `tab`."""
        if not isinstance(tab, EditorTab):
            return
        base_rgb = tab.model.get_base_float_rgb()
        self.preset_dock.update_thumbnails(base_rgb)
        self.preset_dock.sync_from_model(tab.model.active_preset, tab.model.preset_intensity)
        analysis = tab.model.analyze_current_image()
        self.assistant_dock.update_analysis(analysis)

    def _sync_all_panels_from_tab(self, tab: EditorTab):
        """Synchronizes sliders, preset selection, thumbnails, analysis, and history list after state restoration."""
        if not isinstance(tab, EditorTab):
            return
        self.update_adjustments_ui(tab)
        self.refresh_reveal_panels(tab)
        self.update_history_ui(tab)

    def update_recents(self, path):
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:10]
        self.save_recents()

        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, StartPageWidget):
                widget.add_recent(path)
                break

    def load_recents(self):
        import json
        recents_path = os.path.expanduser("~/.image_editor_recents.json")
        if os.path.exists(recents_path):
            try:
                with open(recents_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load recent files: {e}")
                return []
        return []

    def save_recents(self):
        import json
        recents_path = os.path.expanduser("~/.image_editor_recents.json")
        try:
            with open(recents_path, "w") as f:
                json.dump(self.recent_files, f)
        except Exception as e:
            logger.warning(f"Failed to save recent files: {e}")

    def close_tab(self, index):
        widget = self.tabs.widget(index)
        if isinstance(widget, StartPageWidget):
            return

        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.open_start_page()

    def tab_ui_update(self):
        current = self.tabs.currentWidget()
        is_editor = isinstance(current, EditorTab)

        for _name, action in self.actions.items():
            action.setEnabled(is_editor)

        self.dock.setVisible(is_editor)
        self.preset_dock.setVisible(is_editor)
        self.assistant_dock.setVisible(is_editor)
        self.draw_toolbar.setVisible(is_editor and self.toggle_draw_toolbar_act.isChecked())

        if is_editor:
            self.preset_dock.raise_()
            self.update_adjustments_ui(current)
            self.update_history_ui(current)
            self.refresh_reveal_panels(current)
            self.actions["crop"].setChecked(current.canvas.mode == "CROP")
            self.update_drawing_toolbar(current.canvas.mode)

    def update_drawing_toolbar(self, mode):
        mode_map = {
            "SELECT_SHAPE": "draw_select",
            "DRAW_LINE": "draw_line",
            "DRAW_ARROW": "draw_arrow",
            "DRAW_RECT": "draw_rect",
            "DRAW_ELLIPSE": "draw_ellipse",
            "DRAW_TEXT": "draw_text",
            "DRAW_PEN": "draw_pen",
            "DRAW_ERASER": "draw_eraser",
            "CROP": "crop",
        }

        for key, act in self.actions.items():
            if key.startswith("draw_") or key == "crop":
                act.blockSignals(True)
                act.setChecked(False)
                act.blockSignals(False)

        target_key = mode_map.get(mode)
        if target_key and target_key in self.actions:
            self.actions[target_key].blockSignals(True)
            self.actions[target_key].setChecked(True)
            self.actions[target_key].blockSignals(False)

    def save_image(self):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Image", "", "PNG Files (*.png);;JPG Files (*.jpg)"
            )
            if file_path:
                if current.save_image(file_path):
                    logger.info(f"Saved image to: {file_path}")
                    QMessageBox.information(self, "Success", "Image saved successfully.")
                else:
                    logger.error(f"Failed to save image to: {file_path}")
                    QMessageBox.warning(self, "Error", "Failed to save image.")

    # --- Interactive History Navigation (Undo, Redo & Direct Point Selection) ---
    def undo_action(self):
        self._slider_commit_timer.stop()
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            if current.undo():
                self._sync_all_panels_from_tab(current)

    def redo_action(self):
        self._slider_commit_timer.stop()
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            if current.redo():
                self._sync_all_panels_from_tab(current)

    def on_history_row_selected(self, row: int):
        """Restores the image and all parameters to the selected history point."""
        if self._updating_history_ui or row < 0:
            return
        self._slider_commit_timer.stop()
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            if current.jump_to_history(row):
                self._sync_all_panels_from_tab(current)

    def _on_history_item_clicked(self, item: QListWidgetItem):
        """Allows clicking even the already-selected row to discard any uncommitted live drag."""
        if self._updating_history_ui or item is None:
            return
        row = self.history_list.row(item)
        if row >= 0:
            self._slider_commit_timer.stop()
            current = self.tabs.currentWidget()
            if isinstance(current, EditorTab):
                needs_jump = row != current.model.current_history_index or (
                    bool(current.model.history)
                    and not current.model._state_matches_current(current.model.history[-1])
                )
                if needs_jump and current.jump_to_history(row):
                    self._sync_all_panels_from_tab(current)

    def zoom(self, factor):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.zoom(factor)

    def rotate_image(self, angle):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.rotate(angle)
            self.update_history_ui(current)
            self.refresh_reveal_panels(current)

    def flip_image(self, horizontal):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.flip(horizontal)
            self.update_history_ui(current)
            self.refresh_reveal_panels(current)

    def remove_background(self):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.remove_background()

    # --- Preset & Assistant Handlers ---
    def on_preset_selected(self, preset_id: str, intensity: float):
        self._slider_commit_timer.stop()
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.apply_preset(preset_id, intensity=intensity, push_history=True)
            self.update_history_ui(current)

    def on_preset_intensity_changed(self, preset_id: str, intensity: float):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.apply_preset(preset_id, intensity=intensity, push_history=False)

    def on_preset_intensity_committed(self, _preset_id: str, _intensity: float):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.commit_slider_change("Intensidad de Preset")

    def on_recommended_preset_clicked(self, preset_id: str):
        self._slider_commit_timer.stop()
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.apply_preset(preset_id, intensity=1.0, push_history=True)
            self.preset_dock.sync_from_model(preset_id, 1.0)
            self.update_history_ui(current)

    def trigger_auto_develop(self, apply_recommended_preset: bool = True):
        self._slider_commit_timer.stop()
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.auto_develop(apply_recommended_preset=apply_recommended_preset)
            self.update_adjustments_ui(current)
            self.preset_dock.sync_from_model(
                current.model.active_preset, current.model.preset_intensity
            )
            self.update_history_ui(current)

    def trigger_smart_crop_1x1(self):
        self._slider_commit_timer.stop()
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            if current.smart_crop_square_1x1():
                self.update_history_ui(current)
                self.refresh_reveal_panels(current)

    def trigger_clean_ai_watermark(self):
        self._slider_commit_timer.stop()
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            if current.clean_ai_watermark():
                self.update_history_ui(current)
                self.refresh_reveal_panels(current)

    def get_active_photo_state(self) -> dict:
        """Returns the current photo state dictionary for the Qwen chat agent."""
        current = self.tabs.currentWidget()
        if not isinstance(current, EditorTab):
            return {}
        m = current.model
        analysis = m.analyze_current_image() or {}
        return {
            "active_preset": m.active_preset,
            "preset_intensity": m.preset_intensity,
            "ev": m.ev,
            "shadows": m.shadows,
            "highlights": m.highlights,
            "wb_temp": m.wb_temp,
            "denoise": m.denoise,
            "sharpen": m.sharpen,
            "brightness": m.brightness,
            "contrast": m.contrast,
            "saturation": m.saturation,
            "scene_type": analysis.get("scene_type", "Desconocida"),
            "recommended_preset": analysis.get("recommended_preset", "electric_chroma_hd"),
        }

    def on_chat_command_executed(self, cmd: dict):
        """Applies the structured preset/adjustment/custom-preset command returned by the Qwen chat agent."""
        self._slider_commit_timer.stop()
        current = self.tabs.currentWidget()
        if not isinstance(current, EditorTab) or not isinstance(cmd, dict):
            return

        action = cmd.get("action", "update")
        if action == "undo":
            self.undo_action()
            return
        if action == "reset":
            self.reset_adjustments()
            return
        if action == "auto_develop":
            self.trigger_auto_develop(True)
            return
        if action == "smart_crop_1x1":
            self.trigger_smart_crop_1x1()
            return
        if action == "clean_ai":
            self.trigger_clean_ai_watermark()
            return

        m = current.model
        preset_id = cmd.get("preset")
        intensity = cmd.get("preset_intensity")
        adj = cmd.get("adjustments") or {}
        save_as = cmd.get("save_preset_as")

        has_changes = bool(preset_id is not None or intensity is not None or adj or save_as)
        if not has_changes:
            return

        if preset_id is not None:
            m.active_preset = preset_id
        if intensity is not None:
            m.preset_intensity = float(intensity)

        if adj.get("ev") is not None:
            m.ev = float(adj["ev"])
        if adj.get("shadows") is not None:
            m.shadows = float(adj["shadows"])
        if adj.get("highlights") is not None:
            m.highlights = float(adj["highlights"])
        if adj.get("wb_temp") is not None:
            m.wb_temp = float(adj["wb_temp"])
        if adj.get("denoise") is not None:
            m.denoise = float(adj["denoise"])
        if adj.get("sharpen") is not None:
            m.sharpen = float(adj["sharpen"])

        if adj.get("brightness") is not None:
            m.brightness = float(adj["brightness"])
        if adj.get("contrast") is not None:
            m.contrast = float(adj["contrast"])
        if adj.get("saturation") is not None:
            m.saturation = float(adj["saturation"])

        if save_as:
            from src.processing.preset_engine import register_custom_preset
            recipe = {
                "base_preset": m.active_preset if not str(m.active_preset).startswith("custom_") else "none",
                "ev": m.ev,
                "shadows": m.shadows,
                "highlights": m.highlights,
                "wb_temp": m.wb_temp,
                "wb_tint": m.wb_tint,
                "denoise": m.denoise,
                "sharpen": m.sharpen,
                "brightness": m.brightness,
                "contrast": m.contrast,
                "saturation": m.saturation,
            }
            new_pid = register_custom_preset(
                name=save_as,
                recipe=recipe,
                description=f"Preset personalizado ({save_as}) creado por chat IA.",
            )
            m._reset_parameters()
            m.active_preset = new_pid
            m.preset_intensity = 1.0
            m._invalidate_caches()
            self.preset_dock.refresh_preset_list(m.get_base_float_rgb())

        m._update_display_image()
        current.update_canvas()
        m.push_state("Ajuste por Chat IA")
        self.update_adjustments_ui(current)
        self.preset_dock.sync_from_model(m.active_preset, m.preset_intensity)
        self.update_history_ui(current)

    def set_draw_mode(self, mode):
        draw_actions = [
            self.actions["draw_select"],
            self.actions["draw_line"],
            self.actions["draw_arrow"],
            self.actions["draw_rect"],
            self.actions["draw_ellipse"],
            self.actions["draw_text"],
            self.actions["draw_pen"],
            self.actions["draw_eraser"],
        ]

        mode_map = {
            "SELECT_SHAPE": "draw_select",
            "DRAW_LINE": "draw_line",
            "DRAW_ARROW": "draw_arrow",
            "DRAW_RECT": "draw_rect",
            "DRAW_ELLIPSE": "draw_ellipse",
            "DRAW_TEXT": "draw_text",
            "DRAW_PEN": "draw_pen",
            "DRAW_ERASER": "draw_eraser",
        }

        target_key = mode_map.get(mode)

        for act in draw_actions:
            act.blockSignals(True)
            act.setChecked(False)
            act.blockSignals(False)

        if target_key:
            self.actions[target_key].blockSignals(True)
            self.actions[target_key].setChecked(True)
            self.actions[target_key].blockSignals(False)

        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.set_draw_mode(mode)
            if mode != "CROP":
                self.actions["crop"].setChecked(False)

    def choose_color(self):
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(self.current_color, self, "Choose Color")
        if color.isValid():
            self.current_color = color
            self.color_btn.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid #484f58; border-radius: 4px;"
            )
            self.update_tool_properties()

    def width_changed(self, value):
        self.current_width = value
        self.update_tool_properties()

    def update_tool_properties(self):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.set_tool_properties(self.current_color, self.current_width)

    def toggle_crop(self, checked):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            if checked:
                current.set_draw_mode("CROP")
                self.set_draw_mode("CROP")
                self.actions["crop"].setChecked(True)
            else:
                current.set_draw_mode("SELECT_SHAPE")
                self.set_draw_mode("SELECT_SHAPE")

    def on_tab_changed(self):
        self._slider_commit_timer.stop()
        self.tab_ui_update()
        self.update_tool_properties()

    def slider_pressed(self):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.slider_pressed()

    def adjustments_changed(self):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            b = self.sl_brightness.value() / 100.0
            c = self.sl_contrast.value() / 100.0
            s = self.sl_saturation.value() / 100.0
            current.set_adjustments(b, c, s)

    def reveal_sliders_changed(self):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.set_reveal_params(
                ev=self.sl_ev.value() / 100.0,
                shadows=self.sl_shadows.value() / 100.0,
                highlights=self.sl_highlights.value() / 100.0,
                wb_temp=self.sl_wb_temp.value() / 100.0,
                denoise=self.sl_denoise.value() / 100.0,
                sharpen=self.sl_sharpen.value() / 100.0,
            )

    def reset_adjustments(self):
        self._slider_commit_timer.stop()
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.reset_adjustments()
            self.reset_adjustments_ui()
            self.preset_dock.sync_from_model("none", 1.0)
            self.update_history_ui(current)

    def update_history_ui(self, tab):
        self._updating_history_ui = True
        try:
            self.history_list.clear()
            if not tab or not isinstance(tab, EditorTab):
                return

            timeline = tab.model.get_history_timeline()
            active_idx = tab.model.current_history_index

            for i, state in enumerate(timeline):
                desc = state.get("description", "Paso")
                is_current = i == active_idx
                is_future = i > active_idx

                prefix = "● " if is_current else "   "
                item = QListWidgetItem(f"{prefix}{i + 1}. {desc}")
                item.setData(Qt.ItemDataRole.UserRole, i)

                if is_current:
                    f = QFont()
                    f.setBold(True)
                    item.setFont(f)
                    item.setForeground(QColor("#ffffff"))
                elif is_future:
                    f = QFont()
                    f.setItalic(True)
                    item.setFont(f)
                    item.setForeground(QColor("#6e7681"))
                    item.setToolTip("Estado posterior — haz clic para volver a avanzar a este punto")
                else:
                    item.setForeground(QColor("#c9d1d9"))
                    item.setToolTip("Haz clic para restaurar la imagen en este punto")

                self.history_list.addItem(item)

            if 0 <= active_idx < self.history_list.count():
                self.history_list.setCurrentRow(active_idx)

            self.actions["undo"].setEnabled(active_idx > 0)
            self.actions["redo"].setEnabled(len(tab.model.redo_stack) > 0)
        finally:
            self._updating_history_ui = False

    def update_adjustments_ui(self, tab):
        if not tab:
            return
        sliders = [
            self.sl_brightness,
            self.sl_contrast,
            self.sl_saturation,
            self.sl_ev,
            self.sl_shadows,
            self.sl_highlights,
            self.sl_wb_temp,
            self.sl_denoise,
            self.sl_sharpen,
        ]
        for sl in sliders:
            sl.blockSignals(True)

        self.sl_brightness.setValue(int(round(tab.model.brightness * 100)))
        self.sl_contrast.setValue(int(round(tab.model.contrast * 100)))
        self.sl_saturation.setValue(int(round(tab.model.saturation * 100)))
        self.sl_ev.setValue(int(round(tab.model.ev * 100)))
        self.sl_shadows.setValue(int(round(tab.model.shadows * 100)))
        self.sl_highlights.setValue(int(round(tab.model.highlights * 100)))
        self.sl_wb_temp.setValue(int(round(tab.model.wb_temp * 100)))
        self.sl_denoise.setValue(int(round(tab.model.denoise * 100)))
        self.sl_sharpen.setValue(int(round(tab.model.sharpen * 100)))

        for sl in sliders:
            sl.blockSignals(False)

        self._refresh_slider_labels()

    def reset_adjustments_ui(self):
        sliders = [
            (self.sl_brightness, 100),
            (self.sl_contrast, 100),
            (self.sl_saturation, 100),
            (self.sl_ev, 0),
            (self.sl_shadows, 0),
            (self.sl_highlights, 0),
            (self.sl_wb_temp, 0),
            (self.sl_denoise, 0),
            (self.sl_sharpen, 0),
        ]
        for sl, val in sliders:
            sl.blockSignals(True)
            sl.setValue(val)
            sl.blockSignals(False)

        self._refresh_slider_labels()
