"""
Basic Image Editor - Interactive Preset Gallery Dock
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
    QListWidget,
    QListWidgetItem,
    QSlider,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QIcon, QImage, QPixmap
import numpy as np

from src.processing.preset_engine import (
    PRESET_DEFINITIONS,
    generate_preset_thumbnail,
)


class PresetGalleryDock(QDockWidget):
    """
    Dockable visual gallery of photographic presets with live miniature previews
    and a continuous intensity slider (0% - 100%).
    """

    preset_selected = pyqtSignal(str, float)      # (preset_id, intensity)
    intensity_changed = pyqtSignal(str, float)    # (preset_id, intensity)
    intensity_committed = pyqtSignal(str, float)  # (preset_id, intensity)

    def __init__(self, parent=None):
        super().__init__("🎨 Presets", parent)
        self.setMinimumWidth(260)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self.current_preset_id = "none"
        self._updating_ui = False
        self._last_thumb_img_id = None

        self._commit_timer = QTimer(self)
        self._commit_timer.setSingleShot(True)
        self._commit_timer.setInterval(350)
        self._commit_timer.timeout.connect(self._emit_intensity_committed)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Intensity Control Header
        int_row = QHBoxLayout()
        int_title = QLabel("Intensidad del preset")
        int_title.setStyleSheet("color: #8b949e; font-size: 12px; font-weight: 500;")
        int_row.addWidget(int_title)
        int_row.addStretch()

        self.intensity_lbl = QLabel("100%")
        self.intensity_lbl.setStyleSheet(
            "color: #e6edf3; font-size: 12px; font-weight: 600; "
            "background: #262c36; padding: 2px 8px; border-radius: 4px;"
        )
        int_row.addWidget(self.intensity_lbl)
        layout.addLayout(int_row)

        self.intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self.intensity_slider.setRange(0, 100)
        self.intensity_slider.setValue(100)
        self.intensity_slider.valueChanged.connect(self._on_intensity_changed)
        self.intensity_slider.sliderReleased.connect(self._on_intensity_released)
        layout.addWidget(self.intensity_slider)

        # Preset List with Live Thumbnails
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(88, 58))
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setSpacing(6)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_widget.setStyleSheet(
            """
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 10px;
                color: #c9d1d9;
                background-color: #181b20;
                border: 1px solid #262b33;
                border-radius: 8px;
            }
            QListWidget::item:hover {
                background-color: #21262d;
                border: 1px solid #353c47;
            }
            QListWidget::item:selected {
                background-color: #1f2d3d;
                color: #ffffff;
                border: 1px solid #388bfd;
            }
            """
        )
        self.list_widget.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list_widget, stretch=1)

        # Active preset description box (calm, minimal)
        self.desc_label = QLabel("Selecciona un preset para previsualizar su estética.")
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet(
            "color: #8b949e; font-size: 11px; background: #181b20; "
            "border: 1px solid #262b33; padding: 8px 10px; border-radius: 6px;"
        )
        layout.addWidget(self.desc_label)

        self.setWidget(container)
        self._populate_default_items()

    def _populate_default_items(self):
        self._updating_ui = True
        self.list_widget.clear()
        placeholder = np.full((58, 88, 3), 42, dtype=np.uint8)
        qimg = QImage(placeholder.data, 88, 58, 88 * 3, QImage.Format.Format_RGB888)
        default_icon = QIcon(QPixmap.fromImage(qimg.copy()))

        for preset_id, meta in PRESET_DEFINITIONS.items():
            title = f"{meta['name']}\n{meta['category']}"
            item = QListWidgetItem(default_icon, title)
            item.setData(Qt.ItemDataRole.UserRole, preset_id)
            item.setToolTip(f"{meta['description']}\nIdeal para: {', '.join(meta['best_for'])}")
            self.list_widget.addItem(item)

        self.list_widget.setCurrentRow(0)
        self._updating_ui = False

    def refresh_preset_list(self, base_rgb_float: np.ndarray | None = None):
        """Rebuilds the preset list when a custom preset is added or modified."""
        self._populate_default_items()
        self._last_thumb_img_id = None
        if base_rgb_float is not None:
            self.update_thumbnails(base_rgb_float)

    def update_thumbnails(self, base_rgb_float: np.ndarray | None):
        """Renders live preview thumbnails for every preset using a single 88x58 downsample."""
        if base_rgb_float is None:
            return
        img_id = id(base_rgb_float)
        if self._last_thumb_img_id == img_id:
            return
        self._last_thumb_img_id = img_id

        import cv2
        small_f = cv2.resize(base_rgb_float, (88, 58), interpolation=cv2.INTER_AREA)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            preset_id = item.data(Qt.ItemDataRole.UserRole)
            thumb_u8 = generate_preset_thumbnail(small_f, preset_id, size=(88, 58))
            h, w, _ = thumb_u8.shape
            qimg = QImage(thumb_u8.data, w, h, w * 3, QImage.Format.Format_RGB888)
            item.setIcon(QIcon(QPixmap.fromImage(qimg.copy())))

    def sync_from_model(self, preset_id: str, intensity: float):
        """Synchronizes selection and slider state from active tab's ImageModel."""
        self._updating_ui = True
        self._commit_timer.stop()
        self.current_preset_id = preset_id
        pct = int(round(np.clip(intensity, 0.0, 1.0) * 100))
        self.intensity_slider.setValue(pct)
        self.intensity_lbl.setText(f"{pct}%")

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == preset_id:
                self.list_widget.setCurrentRow(i)
                meta = PRESET_DEFINITIONS.get(preset_id)
                if meta:
                    self.desc_label.setText(
                        f"<span style='color:#e6edf3;font-weight:600;'>{meta['name']}</span> — {meta['description']}"
                    )
                break
        self._updating_ui = False

    def _on_item_changed(self, current: QListWidgetItem, _previous: QListWidgetItem):
        if self._updating_ui or current is None:
            return
        preset_id = current.data(Qt.ItemDataRole.UserRole)
        self.current_preset_id = preset_id
        meta = PRESET_DEFINITIONS.get(preset_id, PRESET_DEFINITIONS["none"])
        self.desc_label.setText(
            f"<span style='color:#e6edf3;font-weight:600;'>{meta['name']}</span> — {meta['description']}"
        )
        intensity = self.intensity_slider.value() / 100.0
        self.preset_selected.emit(preset_id, intensity)

    def _on_intensity_changed(self, value: int):
        self.intensity_lbl.setText(f"{value}%")
        if self._updating_ui:
            return
        intensity = value / 100.0
        self.intensity_changed.emit(self.current_preset_id, intensity)
        if not self.intensity_slider.isSliderDown():
            self._commit_timer.start()

    def _on_intensity_released(self):
        if self._updating_ui:
            return
        self._commit_timer.stop()
        self._emit_intensity_committed()

    def _emit_intensity_committed(self):
        if self._updating_ui:
            return
        intensity = self.intensity_slider.value() / 100.0
        self.intensity_committed.emit(self.current_preset_id, intensity)
