"""
Basic Image Editor
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget, 
    QAbstractItemView, QHBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QFont, QPalette

class StartPageWidget(QWidget):
    """
    Welcome screen with Open button, Drag & Drop, and Recents.
    """
    file_opened = pyqtSignal(str)

    def __init__(self, recent_files=None):
        super().__init__()
        self.setAcceptDrops(True)
        # self.recurse = [] # Unused?

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setSpacing(20)

        # Logo
        import os
        from PyQt6.QtGui import QPixmap
        logo_path = os.path.abspath("logo.png")
        if os.path.exists(logo_path):
            logo_lbl = QLabel()
            pixmap = QPixmap(logo_path)
            # Scale if too big
            if pixmap.width() > 150:
                 pixmap = pixmap.scaledToWidth(150, Qt.TransformationMode.SmoothTransformation)
            logo_lbl.setPixmap(pixmap)
            logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(logo_lbl)

        # Hero Title
        title_lbl = QLabel("Basic Image Editor")
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        title_lbl.setFont(font)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_lbl)

        # Open Button
        self.open_btn = QPushButton("Open Image")
        self.open_btn.setIcon(QIcon.fromTheme("document-open"))
        self.open_btn.setIconSize(QSize(32, 32))
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a82da;
                color: white;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 16px;
                border: none;
            }
            QPushButton:hover {
                background-color: #3294f0;
            }
        """)
        self.open_btn.clicked.connect(self.on_open_clicked)
        main_layout.addWidget(self.open_btn)

        # Subtitle / Hint
        hint_lbl = QLabel("or Drag and Drop images here")
        hint_lbl.setStyleSheet("color: #888888; font-size: 14px;")
        hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(hint_lbl)

        # Recent Files
        recents_lbl = QLabel("Recent Files")
        recents_lbl.setStyleSheet("font-weight: bold; margin-top: 20px;")
        main_layout.addWidget(recents_lbl)

        self.recent_list = QListWidget()
        self.recent_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.recent_list.setMaximumWidth(400)
        self.recent_list.setMaximumHeight(200)
        self.recent_list.setStyleSheet("""
            QListWidget {
                background-color: #252525;
                border: 1px solid #3A3939;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 6px;
                color: #cccccc;
            }
            QListWidget::item:hover {
                background-color: #353535;
            }
        """)
        self.recent_list.itemClicked.connect(self.on_recent_clicked)
        main_layout.addWidget(self.recent_list)

        if recent_files:
            for path in recent_files:
                self.add_recent(path)

    def on_open_clicked(self):
        self.file_opened.emit("") 

    def on_recent_clicked(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.file_opened.emit(path)

    def add_recent(self, path):
        from PyQt6.QtWidgets import QListWidgetItem
        
        # Check if exists and remove it to move to top
        for i in range(self.recent_list.count()):
            item = self.recent_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                 self.recent_list.takeItem(i)
                 break

        item = QListWidgetItem(path)
        item.setData(Qt.ItemDataRole.UserRole, path)
        self.recent_list.insertItem(0, item)

    # Drag & Drop
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path:
                self.file_opened.emit(file_path)
