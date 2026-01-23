"""
Basic Image Editor
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal
from src.model.image_model import ImageModel
from src.ui.canvas_widget import CanvasWidget

class EditorTab(QWidget):
    """
    Encapsulates a single open image session.
    Contains its own ImageModel and CanvasWidget.
    """
    history_updated = pyqtSignal()

    def __init__(self):
        super().__init__()
        
        self.model = ImageModel()
        self.canvas = CanvasWidget()
        
        # Connect internal signals
        self.canvas.crop_completed = self.perform_crop

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
    
    def load_image(self, filepath):
        if self.model.load_image(filepath):
            self.update_canvas()
            # Pass shapes ref
            self.canvas.set_shapes_ref(self.model.shapes)
            # Connect Callbacks
            self.canvas.shape_added = self.on_shape_added
            self.canvas.shape_updated = self.on_shape_updated
            return True
        return False
        
    def save_image(self, filepath):
        return self.model.save_image(filepath)

    def update_canvas(self):
        qt_img = self.model.get_qt_image()
        self.canvas.set_image(qt_img)

    def perform_crop(self, rect, scale, offset_x, offset_y):
        self.model.crop(rect, scale, offset_x, offset_y)
        self.update_canvas()
        # Notify others? The Main Window needs to know history changed.
        # But Main Window listens to active tab.
        # We need a signal here to bubble up change events?
        # Or Main Window connects directly to self.model.
        # Or Main Window connects directly to self.model.
        self.canvas.crop_mode = False
        self.history_updated.emit()

    def rotate(self, angle):
        self.model.rotate(angle)
        self.update_canvas()
        self.history_updated.emit()

    def flip(self, horizontal):
        self.model.flip(horizontal)
        self.update_canvas()
        self.history_updated.emit()

    def zoom(self, factor):
        self.canvas.set_zoom(self.canvas.zoom_factor * factor)
    
    def slider_pressed(self):
         self.model.push_state("Adjustment")
         # Main Window should update history UI when this happens
         self.history_updated.emit()

    def set_adjustments(self, b, c, s):
        self.model.set_adjustments(b, c, s)
        self.update_canvas()

    def reset_adjustments(self):
        self.model.reset_adjustments()
        self.update_canvas()
        self.history_updated.emit()

    def undo(self):
        res = self.model.undo()
        if res:
             self.update_canvas()
             self.canvas.set_shapes_ref(self.model.shapes)
             self.history_updated.emit()
        return res

    def redo(self):
        res = self.model.redo()
        if res:
             self.update_canvas()
             self.canvas.set_shapes_ref(self.model.shapes)
             self.history_updated.emit()
        return res

    # --- Drawing ---
    def set_draw_mode(self, mode):
        self.canvas.set_mode(mode)

    def set_tool_properties(self, color, width):
        self.canvas.set_tool_properties(color, width)

    def on_shape_added(self, shape):
        self.model.push_state(f"Add {shape.type}")
        self.history_updated.emit()

    def on_shape_updated(self, shape):
        action = "Update Shape" if shape else "Remove Shape"
        self.model.push_state(action)
        self.history_updated.emit()

    def remove_background(self):
        """Starts the background removal process in a separate thread."""
        if not self.model.original_image:
            return
            
        from src.utils.background_remover import BackgroundRemoverWorker
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt

        # Create Progress Dialog
        self.progress = QProgressDialog("Removing Background... (This may take a while)", "Cancel", 0, 0, self)
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.show()

        # Start Worker
        self.worker = BackgroundRemoverWorker(self.model.original_image.copy())
        self.worker.finished.connect(self.on_bg_removed)
        self.worker.error.connect(self.on_bg_error)
        self.worker.start()
    
    def on_bg_removed(self, new_image):
        self.progress.close()
        self.model.set_new_image(new_image, "Remove Background")
        self.update_canvas()
        self.history_updated.emit()
    
    def on_bg_error(self, error_msg):
        self.progress.close()
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Error", f"Failed to remove background:\n{error_msg}")

