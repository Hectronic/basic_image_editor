"""
Basic Image Editor
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QToolBar, QFileDialog, QLabel, QSlider, 
    QPushButton, QDockWidget, QMessageBox, QListWidget, QApplication, QTabWidget,
    QScrollArea, QTabBar
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QIcon, QPalette, QColor

from src.ui.editor_tab import EditorTab
from src.ui.start_page import StartPageWidget

import os

class ImageEditorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Basic Image Editor")
        
        # Set Window Icon
        import os
        logo_path = os.path.abspath("logo.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        self.resize(1100, 800)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 0; }
            QTabBar::tab { background: #252525; color: #888888; padding: 8px 16px; margin-right: 2px; }
            QTabBar::tab:selected { background: #353535; color: white; border-top: 2px solid #2a82da; }
            QTabBar::tab:hover { background: #303030; }
        """)
        self.setCentralWidget(self.tabs)
        
        # Actions References (to enable/disable)
        self.actions = {}

        # Setup UI
        self.setup_ui()
        self.setup_styling()

        self.recent_files = self.load_recents()
        
        # Open Start Page
        self.open_start_page()

    def setup_ui(self):
        # Toolbar
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        # Actions
        open_act = QAction(QIcon.fromTheme("document-open"), "Open", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_image_dialog)
        toolbar.addAction(open_act)

        save_act = QAction(QIcon.fromTheme("document-save"), "Save", self)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_image)
        toolbar.addAction(save_act)
        self.actions['save'] = save_act

        toolbar.addSeparator()

        # Undo / Redo
        undo_act = QAction(QIcon.fromTheme("edit-undo"), "Undo", self)
        undo_act.setShortcut("Ctrl+Z")
        undo_act.triggered.connect(self.undo_action)
        undo_act.setEnabled(False)
        toolbar.addAction(undo_act)
        self.actions['undo'] = undo_act

        redo_act = QAction(QIcon.fromTheme("edit-redo"), "Redo", self)
        redo_act.setShortcut("Ctrl+Shift+Z") # Or Ctrl+Y
        redo_act.triggered.connect(self.redo_action)
        redo_act.setEnabled(False)
        toolbar.addAction(redo_act)
        self.actions['redo'] = redo_act

        toolbar.addSeparator()

        # Zoom
        zoom_in_act = QAction(QIcon.fromTheme("zoom-in"), "Zoom In", self)
        zoom_in_act.setShortcut("Ctrl++")
        zoom_in_act.triggered.connect(lambda: self.zoom(1.1))
        toolbar.addAction(zoom_in_act)
        self.actions['zoom_in'] = zoom_in_act

        zoom_out_act = QAction(QIcon.fromTheme("zoom-out"), "Zoom Out", self)
        zoom_out_act.setShortcut("Ctrl+-")
        zoom_out_act.triggered.connect(lambda: self.zoom(0.9))
        toolbar.addAction(zoom_out_act)
        self.actions['zoom_out'] = zoom_out_act

        toolbar.addSeparator()

        rot_left_act = QAction(QIcon.fromTheme("object-rotate-left"), "Rotate Left", self)
        rot_left_act.triggered.connect(lambda: self.rotate_image(90))
        toolbar.addAction(rot_left_act)
        self.actions['rotate_left'] = rot_left_act

        rot_right_act = QAction(QIcon.fromTheme("object-rotate-right"), "Rotate Right", self)
        rot_right_act.triggered.connect(lambda: self.rotate_image(-90))
        toolbar.addAction(rot_right_act)
        self.actions['rotate_right'] = rot_right_act

        flip_h_act = QAction(QIcon.fromTheme("object-flip-horizontal"), "Flip H", self)
        flip_h_act.triggered.connect(lambda: self.flip_image(True))
        toolbar.addAction(flip_h_act)
        self.actions['flip_h'] = flip_h_act

        flip_v_act = QAction(QIcon.fromTheme("object-flip-vertical"), "Flip V", self)
        flip_v_act.triggered.connect(lambda: self.flip_image(False))
        toolbar.addAction(flip_v_act)
        self.actions['flip_v'] = flip_v_act

        toolbar.addSeparator()

        self.crop_act = QAction(QIcon.fromTheme("crop"), "Crop", self)
        self.crop_act.setCheckable(True)
        self.crop_act.triggered.connect(self.toggle_crop)
        toolbar.addAction(self.crop_act)
        self.actions['crop'] = self.crop_act

        rembg_act = QAction(QIcon.fromTheme("photo"), "Remove BG", self) # Changed to photo generic
        if rembg_act.icon().isNull():
             rembg_act.setIcon(QIcon.fromTheme("image-x-generic"))
        rembg_act.triggered.connect(self.remove_background)
        toolbar.addAction(rembg_act)
        self.actions['rembg'] = rembg_act

        # --- Drawing Toolbar ---
        draw_toolbar = QToolBar("Drawing Toolbar")
        draw_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, draw_toolbar)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea) 

        # Pointer (Select)
        self.select_act = QAction(QIcon.fromTheme("input-mouse"), "Select", self) # Changed icon
        self.select_act.setCheckable(True)
        self.select_act.setChecked(True) # Default
        self.select_act.triggered.connect(lambda: self.set_draw_mode('SELECT_SHAPE'))
        draw_toolbar.addAction(self.select_act)
        self.actions['draw_select'] = self.select_act
        
        # Pen
        self.draw_pen_act = QAction(QIcon.fromTheme("draw-freehand"), "Pen", self)
        self.draw_pen_act.setCheckable(True)
        self.draw_pen_act.triggered.connect(lambda: self.set_draw_mode('DRAW_PEN'))
        draw_toolbar.addAction(self.draw_pen_act)
        self.actions['draw_pen'] = self.draw_pen_act

        # Eraser
        self.draw_eraser_act = QAction(QIcon.fromTheme("draw-eraser"), "Eraser", self)
        if self.draw_eraser_act.icon().isNull():
             self.draw_eraser_act.setIcon(QIcon.fromTheme("edit-clear")) # Fallback
        self.draw_eraser_act.setCheckable(True)
        self.draw_eraser_act.triggered.connect(lambda: self.set_draw_mode('DRAW_ERASER'))
        draw_toolbar.addAction(self.draw_eraser_act)
        self.actions['draw_eraser'] = self.draw_eraser_act

        draw_toolbar.addSeparator()

        # Shapes
        self.draw_line_act = QAction(QIcon.fromTheme("draw-line"), "Line", self)
        self.draw_line_act.setCheckable(True)
        self.draw_line_act.triggered.connect(lambda: self.set_draw_mode('DRAW_LINE'))
        draw_toolbar.addAction(self.draw_line_act)
        self.actions['draw_line'] = self.draw_line_act

        self.draw_arrow_act = QAction(QIcon.fromTheme("draw-arrow"), "Arrow", self)
        self.draw_arrow_act.setCheckable(True)
        self.draw_arrow_act.triggered.connect(lambda: self.set_draw_mode('DRAW_ARROW'))
        draw_toolbar.addAction(self.draw_arrow_act)
        self.actions['draw_arrow'] = self.draw_arrow_act

        self.draw_rect_act = QAction(QIcon.fromTheme("draw-rectangle"), "Rect", self)
        self.draw_rect_act.setCheckable(True)
        self.draw_rect_act.triggered.connect(lambda: self.set_draw_mode('DRAW_RECT'))
        draw_toolbar.addAction(self.draw_rect_act)
        self.actions['draw_rect'] = self.draw_rect_act

        self.draw_ellipse_act = QAction(QIcon.fromTheme("draw-ellipse"), "Circle", self)
        self.draw_ellipse_act.setCheckable(True)
        self.draw_ellipse_act.triggered.connect(lambda: self.set_draw_mode('DRAW_ELLIPSE'))
        draw_toolbar.addAction(self.draw_ellipse_act)
        self.actions['draw_ellipse'] = self.draw_ellipse_act

        self.draw_text_act = QAction(QIcon.fromTheme("draw-text"), "Text", self)
        self.draw_text_act.setCheckable(True)
        self.draw_text_act.triggered.connect(lambda: self.set_draw_mode('DRAW_TEXT'))
        draw_toolbar.addAction(self.draw_text_act)
        self.actions['draw_text'] = self.draw_text_act

        draw_toolbar.addSeparator()

        # Properties
        # Color Button
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(24, 24)
        self.color_btn.setStyleSheet("background-color: red; border: 1px solid #555;")
        self.color_btn.clicked.connect(self.choose_color)
        draw_toolbar.addWidget(self.color_btn)
        self.current_color = QColor(255, 0, 0)

        draw_toolbar.addSeparator()

        # Width Slider
        width_lbl = QLabel("W:")
        width_lbl.setStyleSheet("margin-left: 5px;")
        draw_toolbar.addWidget(width_lbl)
        
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(1, 20)
        self.width_slider.setValue(3)
        self.width_slider.setFixedWidth(80)
        self.width_slider.valueChanged.connect(self.width_changed)
        draw_toolbar.addWidget(self.width_slider)
        
        self.current_width = 3

        # Sidebar (Dock Widget)
        dock = QDockWidget("Adjustments", self)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable | QDockWidget.DockWidgetFeature.DockWidgetMovable)
        dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        
        sidebar = QWidget()
        dock.setWidget(sidebar)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.dock = dock # To hide/show

        layout = QVBoxLayout(sidebar)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # History List
        history_lbl = QLabel("History")
        history_lbl.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(history_lbl)

        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(200) # Limit height
        self.history_list.setStyleSheet("""
            QListWidget {
                background-color: #252525;
                border: 1px solid #3A3939;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 4px;
                color: #cccccc;
            }
            QListWidget::item:selected {
                background-color: #2a82da;
                color: white;
            }
        """)
        layout.addWidget(self.history_list)
        layout.addSpacing(10)

        # Reset Button
        reset_btn = QPushButton("Reset All")
        reset_btn.clicked.connect(self.reset_adjustments)
        layout.addWidget(reset_btn)
        
        layout.addSpacing(20)

        # Sliders
        self.sl_brightness = self.create_slider(layout, "Brightness", 0.0, 2.0, 1.0)
        self.sl_contrast = self.create_slider(layout, "Contrast", 0.0, 2.0, 1.0)
        self.sl_saturation = self.create_slider(layout, "Saturation", 0.0, 2.0, 1.0)

        # Spacer
        layout.addStretch()

    def create_slider(self, parent_layout, label_text, min_val, max_val, default_val):
        lbl = QLabel(label_text)
        parent_layout.addWidget(lbl)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(min_val * 100), int(max_val * 100))
        slider.setValue(int(default_val * 100))
        slider.valueChanged.connect(self.adjustments_changed)
        slider.sliderPressed.connect(self.slider_pressed) # Track start of adjustment
        parent_layout.addWidget(slider)
        return slider

    def setup_styling(self):
        """Sets a dark theme palette suitable for Ubuntu/Gnome."""
        self.setAutoFillBackground(True)
        app = QApplication.instance()
        
        # Dark Palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        
        app.setPalette(palette)
        
        # Stylesheet for sliders and specific widgets to look crisp
        app.setStyleSheet("""
            QToolTip { 
                color: #ffffff; 
                background-color: #2a82da; 
                border: 1px solid white; 
            }
            QDockWidget::title {
                background: #353535;
                text-align: center;
            }
            QSlider::groove:horizontal {
                border: 1px solid #3A3939;
                height: 8px;
                background: #201F1F;
                margin: 2px 0;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #2a82da;
                border: 1px solid #2a82da;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QToolBar {
                background: #353535;
                border-bottom: 1px solid #201F1F;
            }
            QPushButton {
                background-color: #2a82da;
                color: white;
                border-radius: 4px;
                padding: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #3294f0;
            }
        """)

    def open_start_page(self):
        start_page = StartPageWidget(self.recent_files)
        start_page.file_opened.connect(self.handle_file_opened)
        index = self.tabs.addTab(start_page, "Start")
        self.tabs.setCurrentWidget(start_page)
        # Lock the tab (remove close button)
        self.tabs.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, None)
        self.tab_ui_update()

    def open_image_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.create_editor_tab(file_path)

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
            # Add to recents (Mock for now, or find the start page)
            self.update_recents(file_path)
            
            # Connect History Signal
            tab.history_updated.connect(lambda: self.update_history_ui(tab))
            self.update_history_ui(tab)
        else:
            QMessageBox.warning(self, "Error", "Failed to load image.")

    def update_recents(self, path):
        # Update internal list
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:10] # Keep last 10
        self.save_recents()

        # Update Start Page UI if it exists
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
                with open(recents_path, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_recents(self):
        import json
        recents_path = os.path.expanduser("~/.image_editor_recents.json")
        try:
             with open(recents_path, 'w') as f:
                json.dump(self.recent_files, f)
        except:
            pass

    def close_tab(self, index):
        widget = self.tabs.widget(index)
        if isinstance(widget, StartPageWidget):
            return # Don't close start page

        self.tabs.removeTab(index)
        # If no tabs left (shouldn't happen if Start Page is locked, but just in case)
        if self.tabs.count() == 0:
            self.open_start_page()

    def on_tab_changed(self):
        self.tab_ui_update()

    def tab_ui_update(self):
        current = self.tabs.currentWidget()
        is_editor = isinstance(current, EditorTab)
        
        # Enable/Disable Actions
        for name, action in self.actions.items():
            action.setEnabled(is_editor)

        self.dock.setVisible(is_editor)
        
        if is_editor:
             # Sync UI from model
             self.update_adjustments_ui(current)
             self.update_history_ui(current)
             # Sync Crop State
             self.actions['crop'].setChecked(current.canvas.mode == 'CROP')
             
             # Sync Drawing Tools State
             # We should also update the drawing toolbar buttons based on mode
             self.update_drawing_toolbar(current.canvas.mode)

    def update_drawing_toolbar(self, mode):
        # Uncheck all first (handled in set_draw_mode usually, but this is visual sync)
        # Actually set_draw_mode updates the action checked state.
        # But if tab changed, we need to reflect the new tab's mode in the UI actions.
        
        # Map mode to action key
        mode_map = {
            'SELECT_SHAPE': 'draw_select',
            'DRAW_LINE': 'draw_line',
            'DRAW_ARROW': 'draw_arrow',
            'DRAW_RECT': 'draw_rect',
            'DRAW_ELLIPSE': 'draw_ellipse',
            'DRAW_TEXT': 'draw_text',
            'DRAW_PEN': 'draw_pen',
            'DRAW_ERASER': 'draw_eraser',
            'CROP': 'crop'
        }
        
        # Block signals to prevent triggering set_draw_mode logic which modifies the model
        for key, act in self.actions.items():
            if key.startswith('draw_') or key == 'crop':
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
                    QMessageBox.information(self, "Success", "Image saved successfully.")
                else:
                    QMessageBox.warning(self, "Error", "Failed to save image.")

    def undo_action(self):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            if current.undo():
                self.update_adjustments_ui(current)
                self.update_history_ui(current)

    def redo_action(self):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
             if current.redo():
                self.update_adjustments_ui(current)
                self.update_history_ui(current)

    def zoom(self, factor):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
             current.zoom(factor)

    def rotate_image(self, angle):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.rotate(angle)
            self.update_history_ui(current)

    def flip_image(self, horizontal):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.flip(horizontal)
            self.update_history_ui(current)

    def remove_background(self):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.remove_background()

    def set_draw_mode(self, mode):
        # Uncheck others
        draw_actions = [
            self.actions['draw_select'], self.actions['draw_line'], self.actions['draw_arrow'],
            self.actions['draw_rect'], self.actions['draw_ellipse'], self.actions['draw_text'],
            self.actions['draw_pen'], self.actions['draw_eraser']
        ]
        
        mode_map = {
            'SELECT_SHAPE': 'draw_select',
            'DRAW_LINE': 'draw_line',
            'DRAW_ARROW': 'draw_arrow',
            'DRAW_RECT': 'draw_rect',
            'DRAW_ELLIPSE': 'draw_ellipse',
            'DRAW_TEXT': 'draw_text',
            'DRAW_PEN': 'draw_pen',
            'DRAW_ERASER': 'draw_eraser'
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

        # Propagate to Tab
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.set_draw_mode(mode)
            if mode != 'CROP':
                 self.actions['crop'].setChecked(False) 
            
    def choose_color(self):
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(self.current_color, self, "Choose Color")
        if color.isValid():
            self.current_color = color
            self.color_btn.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #555;")
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
                current.set_draw_mode('CROP')
                self.set_draw_mode('CROP') 
                self.actions['crop'].setChecked(True)
            else:
                current.set_draw_mode('SELECT_SHAPE')
                self.set_draw_mode('SELECT_SHAPE')
    
    def on_tab_changed(self):
        self.tab_ui_update()
        self.update_tool_properties()

    def slider_pressed(self):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.slider_pressed()
            self.update_history_ui(current)

    def adjustments_changed(self):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            b = self.sl_brightness.value() / 100.0
            c = self.sl_contrast.value() / 100.0
            s = self.sl_saturation.value() / 100.0
            current.set_adjustments(b, c, s)

    def reset_adjustments(self):
        current = self.tabs.currentWidget()
        if isinstance(current, EditorTab):
            current.reset_adjustments()
            self.reset_adjustments_ui()
            self.update_history_ui(current)

    def update_history_ui(self, tab):
        self.history_list.clear()
        if not tab: return
        
        # Populate history
        for i, state in enumerate(tab.model.history): # Access Model via Tab
            self.history_list.addItem(f"{i+1}. {state['description']}")
        
        if tab.model.history:
            self.history_list.setCurrentRow(len(tab.model.history) - 1)
        
        self.actions['undo'].setEnabled(len(tab.model.history) > 1)
        self.actions['redo'].setEnabled(len(tab.model.redo_stack) > 0)

    def update_adjustments_ui(self, tab):
        if not tab: return
        self.sl_brightness.blockSignals(True)
        self.sl_contrast.blockSignals(True)
        self.sl_saturation.blockSignals(True)
        
        self.sl_brightness.setValue(int(tab.model.brightness * 100))
        self.sl_contrast.setValue(int(tab.model.contrast * 100))
        self.sl_saturation.setValue(int(tab.model.saturation * 100))
        
        self.sl_brightness.blockSignals(False)
        self.sl_contrast.blockSignals(False)
        self.sl_saturation.blockSignals(False)

    def reset_adjustments_ui(self):
        self.sl_brightness.blockSignals(True)
        self.sl_contrast.blockSignals(True)
        self.sl_saturation.blockSignals(True)
        
        self.sl_brightness.setValue(100)
        self.sl_contrast.setValue(100)
        self.sl_saturation.setValue(100)
        
        self.sl_brightness.blockSignals(False)
        self.sl_contrast.blockSignals(False)
        self.sl_saturation.blockSignals(False)
