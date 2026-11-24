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
        title_lbl = QLabel("RAW & Preset Studio")
        font = QFont()
        font.setPointSize(22)
        font.setBold(True)
        title_lbl.setFont(font)
        title_lbl.setStyleSheet("color: #f0f3f6; letter-spacing: 0.3px;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_lbl)

        subtitle_lbl = QLabel("Revelado fotográfico 16-bit · Presets HD · Asistente Qwen IA integrado")
        subtitle_lbl.setStyleSheet("color: #8b949e; font-size: 13px; margin-bottom: 8px;")
        subtitle_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(subtitle_lbl)

        # Open Button
        self.open_btn = QPushButton("  Abrir Foto o RAW")
        self.open_btn.setIcon(QIcon.fromTheme("document-open"))
        self.open_btn.setIconSize(QSize(22, 22))
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.setFixedWidth(240)
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #2f81f7;
                color: #ffffff;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
                border: none;
            }
            QPushButton:hover {
                background-color: #388bfd;
            }
        """)
        self.open_btn.clicked.connect(self.on_open_clicked)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.open_btn)
        btn_row.addStretch()
        main_layout.addLayout(btn_row)

        # Subtitle / Hint
        hint_lbl = QLabel("o arrastra tus archivos ARW, CR2, NEF, DNG, PNG o JPG aquí")
        hint_lbl.setStyleSheet("color: #6e7681; font-size: 12px;")
        hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(hint_lbl)

        # Recent Files
        recents_lbl = QLabel("Archivos recientes")
        recents_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        recents_lbl.setStyleSheet("font-weight: 600; font-size: 12px; color: #8b949e; margin-top: 18px;")
        main_layout.addWidget(recents_lbl)

        self.recent_list = QListWidget()
        self.recent_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.recent_list.setMinimumWidth(420)
        self.recent_list.setMaximumWidth(520)
        self.recent_list.setMaximumHeight(190)
        self.recent_list.setStyleSheet("""
            QListWidget {
                background-color: #1c2026;
                border: 1px solid #2d333b;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 10px;
                color: #c9d1d9;
                border-radius: 5px;
            }
            QListWidget::item:hover {
                background-color: #262c36;
            }
        """)
        self.recent_list.itemClicked.connect(self.on_recent_clicked)
        rec_row = QHBoxLayout()
        rec_row.addStretch()
        rec_row.addWidget(self.recent_list)
        rec_row.addStretch()
        main_layout.addLayout(rec_row)

        if recent_files:
            for path in recent_files:
                self.add_recent(path)

    def on_open_clicked(self):
        self.file_opened.emit("") 

    def on_recent_clicked(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        # Import logger locally or at top level if frequent
        import logging
        import os
        from PyQt6.QtWidgets import QMessageBox

        logger = logging.getLogger(__name__)

        if path:
            if os.path.exists(path):
                self.file_opened.emit(path)
            else:
                logger.warning(f"Recent file not found: {path}")
                QMessageBox.warning(self, "File Not Found", f"The file '{path}' no longer exists.")
                # Optional: Remove from list?
                # For now just alert and log.

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
