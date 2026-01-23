"""
Basic Image Editor
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from src.ui.main_window import ImageEditorApp
from src.ui.editor_tab import EditorTab
from PyQt6.QtWidgets import QTabWidget

def test_editor_tab_init(qtbot):
    tab = EditorTab()
    qtbot.addWidget(tab)
    assert tab.model is not None
    assert tab.canvas is not None

def test_editor_tab_interactions(qtbot, sample_image_path):
    tab = EditorTab()
    qtbot.addWidget(tab)
    
    assert tab.load_image(sample_image_path)
    # Check canvas received image
    assert tab.canvas.qt_image is not None

def test_main_window_init(qtbot):
    window = ImageEditorApp()
    qtbot.addWidget(window)
    
    # Check tabs exist
    tabs = window.centralWidget()
    assert isinstance(tabs, QTabWidget)
    assert tabs.count() > 0 # Start page
