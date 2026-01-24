"""
Basic Image Editor
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PIL import Image, ImageEnhance, ImageQt, ImageDraw
import logging

logger = logging.getLogger(__name__)

class ImageModel:
    """Handles Image Processing using Pillow."""
    def __init__(self):
        # super().__init__() # Not needed unless inheriting from QObject
        self.original_image = None  # The image loaded from disk (or after crop/rotate commits)
        self.display_image = None   # The final image ready for display (with brightness etc.)
        self.preview_image = None   # Intermediate image (Geometric transforms)
        
        # Adjustment parameters
        self.brightness = 1.0
        self.contrast = 1.0
        self.saturation = 1.0
        
        # Vector Objects
        self.shapes = [] 

        # History
        self.history = []     # List of dicts representing state
        self.redo_stack = []  # List of dicts representing state
        self.max_history = 20

    def load_image(self, filepath):
        try:
            # Open and convert to RGBA to ensure consistency
            self.original_image = Image.open(filepath).convert("RGBA")
            self.preview_image = self.original_image.copy()
            self.shapes = []
            self._update_display_image()
            self.history.clear()
            self.redo_stack.clear()
            self.push_state("Load Image")
            logger.info(f"Image loaded successfully: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error loading image {filepath}: {e}")
            print(f"Error loading image: {e}")
            return False

    def save_image(self, filepath):
        if self.display_image:
            try:
                # Bake shapes onto a copy of the display image
                # We need to render the shapes. 
                # Since shapes are Qt based (QRectF), we should probably use QPainter to render them onto QImage,
                # then convert that QImage back to PIL or save directly.
                
                # 1. Get current display image (PIL)
                final_img = self.display_image.copy()
                
                # 2. Convert to QImage to use QPainter (easiest way to draw Qt shapes)
                qimg = ImageQt.ImageQt(final_img)
                
                # We need a QImage that we can paint on. ImageQt might be read-only wrapper?
                # Let's create a full copy.
                from PyQt6.QtGui import QImage, QPainter, QPen, QColor, QFont
                from PyQt6.QtCore import Qt
                
                # Copying qimg to a new QImage to ensure it's writable and valid format
                canvas_img = qimg.copy() 
                
                painter = QPainter(canvas_img)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                for shape in self.shapes:
                    pen = QPen(shape.color, shape.width)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    
                    if shape.type == "line" or shape.type == "arrow":
                        painter.drawLine(shape.start_pos, shape.end_pos)
                        if shape.type == "arrow":
                            # Draw simple arrowhead
                            import math
                            # Vector math
                            line_vec = shape.end_pos - shape.start_pos
                            angle = math.atan2(line_vec.y(), line_vec.x())
                            arrow_len = 15
                            arrow_angle = math.radians(30)
                            
                            p1 = shape.end_pos - QPointF(arrow_len * math.cos(angle - arrow_angle), 
                                                         arrow_len * math.sin(angle - arrow_angle))
                            p2 = shape.end_pos - QPointF(arrow_len * math.cos(angle + arrow_angle), 
                                                         arrow_len * math.sin(angle + arrow_angle))
                            painter.drawLine(shape.end_pos, p1)
                            painter.drawLine(shape.end_pos, p2)

                    elif shape.type == "rect":
                        painter.drawRect(shape.rect)
                    elif shape.type == "ellipse":
                        painter.drawEllipse(shape.rect)
                    elif shape.type == "text":
                         font = QFont("Arial", shape.font_size)
                         painter.setFont(font)
                         painter.setPen(shape.color)
                         painter.drawText(shape.rect, Qt.AlignmentFlag.AlignLeft, shape.text)

                painter.end()
                
                # 3. Save QImage directly
                return canvas_img.save(filepath)

            except Exception as e:
                logger.error(f"Error saving image to {filepath}: {e}")
                print(f"Error saving image: {e}")
                return False
        return False

    def push_state(self, description):
        """Saves current state to history."""
        if not self.original_image:
            return

        # Deep copy shapes
        import copy
        shapes_copy = [s.copy() for s in self.shapes]

        state = {
            "image": self.original_image.copy(),
            "brightness": self.brightness,
            "contrast": self.contrast,
            "saturation": self.saturation,
            "shapes": shapes_copy,
            "description": description
        }
        
        self.history.append(state)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        self.redo_stack.clear()
        
        # logger.debug(f"State pushed: {description}") # Optional debug log

    def undo(self):
        if len(self.history) > 1:
            # Move current state to redo
            current_state = self.history.pop()
            self.redo_stack.append(current_state)

            # Restore previous state
            prev_state = self.history[-1]
            self._restore_state(prev_state)
            return True
        return False

    def redo(self):
        if self.redo_stack:
            # Pop from redo and push to history
            next_state = self.redo_stack.pop()
            self.history.append(next_state)
            
            self._restore_state(next_state)
            return True
        return False

    def _restore_state(self, state):
        self.original_image = state["image"].copy()
        self.brightness = state["brightness"]
        self.contrast = state["contrast"]
        self.saturation = state["saturation"]
        
        # Restore shapes
        import copy
        self.shapes = [s.copy() for s in state.get("shapes", [])]
        
        self.preview_image = self.original_image.copy()
        self._update_display_image()

    def add_shape(self, shape):
        self.shapes.append(shape)
        self.push_state(f"Add {shape.type.capitalize()}")

    def update_shape(self, shape):
        # Push state on finish editing?
        # We might want to just notify change without full push if just dragging, 
        # but for simplicity every release is push.
        pass # push_state handled by controller on interaction end

    def rotate(self, angle):
        """Rotate the geometric image (commits the change to base)."""
        if self.original_image:
            # Rotate
            self.original_image = self.original_image.rotate(angle, expand=True)
            self.preview_image = self.original_image.copy()
            self._update_display_image()
            self.push_state(f"Rotate {angle}°")

    def flip(self, horizontal=True):
        """Flip the geometric image (commits the change to base)."""
        if self.original_image:
            direction = "Horizontal" if horizontal else "Vertical"
            method = Image.FLIP_LEFT_RIGHT if horizontal else Image.FLIP_TOP_BOTTOM
            self.original_image = self.original_image.transpose(method)
            self.preview_image = self.original_image.copy()
            self._update_display_image()
            self.push_state(f"Flip {direction}")

    def crop(self, rect, scale_factor, offset_x, offset_y):
        """
        Crop the image based on the selection rectangle from the UI.
        rect: QRect from the viewport
        scale_factor: The ratio of (displayed_width / actual_width)
        offset_x/y: The padding in the view
        """
        if self.original_image:
            # Convert UI coordinates back to Image coordinates
            # x_img = (x_ui - offset_x) / scale
            x = int((rect.x() - offset_x) / scale_factor)
            y = int((rect.y() - offset_y) / scale_factor)
            w = int(rect.width() / scale_factor)
            h = int(rect.height() / scale_factor)

            # Bounds check
            img_w, img_h = self.original_image.size
            x = max(0, x)
            y = max(0, y)
            w = min(w, img_w - x)
            h = min(h, img_h - y)
            
            if w > 0 and h > 0:
                box = (x, y, x + w, y + h)
                self.original_image = self.original_image.crop(box)
                self.preview_image = self.original_image.copy()
                self._update_display_image()
                self.push_state("Crop")

    def set_adjustments(self, brightness, contrast, saturation):
        self.brightness = brightness
        self.contrast = contrast
        self.saturation = saturation
        self._update_display_image()

    def commit_adjustments(self, description="Adjustments"):
        """Call this when slider is released to save state."""
        # Main logic handled by push_state call in UI
        pass

    def reset_adjustments(self):
        self.push_state("Reset Adjustments")
        self.brightness = 1.0
        self.contrast = 1.0
        self.saturation = 1.0
        self._update_display_image()

    def _update_display_image(self):
        """Applies non-destructive color adjustments to the geometric base."""
        if self.original_image:
            img = self.original_image.copy()
            
            # Apply adjustments sequentially
            if self.brightness != 1.0:
                img = ImageEnhance.Brightness(img).enhance(self.brightness)
            if self.contrast != 1.0:
                img = ImageEnhance.Contrast(img).enhance(self.contrast)
            if self.saturation != 1.0:
                img = ImageEnhance.Color(img).enhance(self.saturation)
            
            self.display_image = img

    def get_qt_image(self):
        """Converts PIL image to QImage for display."""
        if self.display_image:
            return ImageQt.ImageQt(self.display_image)
        return None

    def set_new_image(self, new_image, description="Update Image"):
        """Replaces the current image with a new one (e.g. after background removal)."""
        if new_image:
            self.original_image = new_image.convert("RGBA")
            self.preview_image = self.original_image.copy()
            self._update_display_image()
            self.push_state(description)

