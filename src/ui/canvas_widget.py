"""
Basic Image Editor
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt6.QtWidgets import QWidget, QSizePolicy, QInputDialog
from PyQt6.QtGui import QPainter, QPen, QColor, QCursor, QFont
from PyQt6.QtCore import Qt, QRect, QPoint, QRectF, QPointF, QSize, QSizeF

from src.model.shapes import LineShape, RectShape, EllipseShape, ArrowShape, TextShape, PenShape

class CanvasWidget(QWidget):
    """
    Displays the image and handles crop selection and vector drawing.
    """
    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus) # Accept key events
        self.setMouseTracking(True)
        
        self.qt_image = None
        self.zoom_factor = 1.0
        self.pan_offset = QPoint(0, 0)
        
        # Modes: 'NONE', 'CROP', 'SELECT_SHAPE', 'DRAW_LINE', 'DRAW_RECT', 'DRAW_ELLIPSE', 'DRAW_ARROW', 'DRAW_TEXT'
        self.mode = 'NONE'
        
        # Tools Properties
        self.current_color = QColor(255, 0, 0)
        self.current_width = 3
        
        self.shapes = [] # Reference to model's shapes
        self.selected_shape = None
        
        self.selection_rect = QRect() # For Crop
        
        # Interaction State
        self.is_creating = False 
        self.is_moving = False
        self.is_resizing = False
        self.is_panning = False
        self.resize_handle = None 
        self.start_point = QPoint()     # For Crop (Int)
        self.start_point_f = QPointF()  # For Shapes (Float)
        self.last_mouse_pos = QPoint()

        # Layout details
        self.img_draw_rect = QRect()
        self.scale_factor = 1.0

        # Signals
        self.crop_completed = None 
        self.shape_added = None # callback(shape)
        self.shape_updated = None # callback(shape)
        
        self.handle_size = 10

    @property
    def crop_mode(self):
        return self.mode == 'CROP'

    @crop_mode.setter
    def crop_mode(self, value):
        self.set_mode('CROP' if value else 'SELECT_SHAPE')

    def set_image(self, qt_image):
        self.qt_image = qt_image
        self.selection_rect = QRect()
        self.update()

    def set_shapes_ref(self, shapes_list):
        self.shapes = shapes_list
        self.selected_shape = None
        self.update()
        
    def set_zoom(self, factor):
        self.zoom_factor = factor
        self.update()

    def zoom_in(self):
        self.zoom_factor *= 1.1
        self.update()

    def zoom_out(self):
        self.zoom_factor /= 1.1
        if self.zoom_factor < 0.1: self.zoom_factor = 0.1
        self.update()

    def set_mode(self, mode):
        self.mode = mode
        self.selection_rect = QRect() 
        self.is_creating = False
        self.is_moving = False
        self.is_resizing = False
        self.selected_shape = None
        self.update()
        
        if mode == 'CROP':
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode.startswith('DRAW_'):
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_tool_properties(self, color, width):
        self.current_color = color
        self.current_width = width
        if self.selected_shape:
            self.selected_shape.color = color
            self.selected_shape.width = width
            if self.shape_updated: self.shape_updated(self.selected_shape)
            self.update()

    # --- Coordinate Mapping ---
    def map_to_image(self, pos):
        """Maps widget coordinate to image coordinate (QPointF)."""
        offset_x = self.img_draw_rect.x()
        offset_y = self.img_draw_rect.y()
        x = (pos.x() - offset_x) / self.scale_factor
        y = (pos.y() - offset_y) / self.scale_factor
        return QPointF(x, y)

    def map_from_image(self, pos_f):
        """Maps image coordinate (QPointF) to widget coordinate."""
        offset_x = self.img_draw_rect.x()
        offset_y = self.img_draw_rect.y()
        x = pos_f.x() * self.scale_factor + offset_x
        y = pos_f.y() * self.scale_factor + offset_y
        return QPointF(x, y)
        
    def map_rect_from_image(self, rect_f):
        tl = self.map_from_image(rect_f.topLeft())
        br = self.map_from_image(rect_f.bottomRight())
        return QRectF(tl, br)

    # --- Handles ---

    def get_handles_for_rect(self, rect):
        """Returns dict of handle rects (in widget coords) for a given widget-space rect."""
        if rect.isEmpty(): return {}
        s = self.handle_size
        hs = s // 2
        r = rect
        return {
            'TL': QRectF(r.left() - hs, r.top() - hs, s, s),
            'TM': QRectF(r.center().x() - hs, r.top() - hs, s, s),
            'TR': QRectF(r.right() - hs, r.top() - hs, s, s),
            'ML': QRectF(r.left() - hs, r.center().y() - hs, s, s),
            'MR': QRectF(r.right() - hs, r.center().y() - hs, s, s),
            'BL': QRectF(r.left() - hs, r.bottom() - hs, s, s),
            'BM': QRectF(r.center().x() - hs, r.bottom() - hs, s, s),
            'BR': QRectF(r.right() - hs, r.bottom() - hs, s, s),
        }

    def get_shape_handles(self, shape):
        if not shape: return {}
        # Special case for Line/Arrow? They just have Start/End
        if shape.type in ['line', 'arrow']:
             p1 = self.map_from_image(shape.start_pos)
             p2 = self.map_from_image(shape.end_pos)
             s = self.handle_size
             hs = s / 2
             return {
                 'START': QRectF(p1.x() - hs, p1.y() - hs, s, s),
                 'END':   QRectF(p2.x() - hs, p2.y() - hs, s, s)
             }
        
        # For Rect/Ellipse/Text, use bounding box
        widget_rect = self.map_rect_from_image(shape.rect)
        return self.get_handles_for_rect(widget_rect)

    def hit_test(self, pos):
        """Returns ('TYPE', payload)."""
        # 1. Check Crop handles if cropping
        if self.mode == 'CROP':
             # ... (Same logic as before but adapted) ...
             # Reusing generic handle logic? 
             # Let's keep existing CROP logic separate or unified.
             # For simplicity, let's just create 'CROP_HANDLE' logic here or rely on old impl style.
             pass 

        # 2. Check Shape Handles (Selected)
        if self.selected_shape and self.mode in ['SELECT_SHAPE', 'NONE']:
            handles = self.get_shape_handles(self.selected_shape)
            pos_f = QPointF(pos)
            for name, rect in handles.items():
                if rect.contains(pos_f):
                    return ('HANDLE', name)
        
        # 3. Check Crop Rect (Inside)
        if self.mode == 'CROP' and not self.selection_rect.isEmpty():
             # Basic rect check
             pass # Implemented inline in MousePress for crop legacy

        # 4. Check Shapes (Hit)
        if self.mode in ['SELECT_SHAPE', 'NONE']:
            # Check in reverse (topmost first)
            img_pos = self.map_to_image(pos)
            for shape in reversed(self.shapes):
                if shape.contains(img_pos):
                    return ('SHAPE', shape)

        return ('NONE', None)

    # --- Paint ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#141619"))

        if not self.qt_image or self.qt_image.isNull():
            return

        # Calc Transforms with subtle studio breathing margin
        canvas_size = self.size()
        img_size = self.qt_image.size()
        pad = 24 if (canvas_size.width() > 160 and canvas_size.height() > 160) else 0
        avail_w = max(1, canvas_size.width() - pad * 2)
        avail_h = max(1, canvas_size.height() - pad * 2)
        scale_w = avail_w / img_size.width()
        scale_h = avail_h / img_size.height()
        base_scale = min(scale_w, scale_h)
        self.scale_factor = base_scale * self.zoom_factor

        display_w = int(img_size.width() * self.scale_factor)
        display_h = int(img_size.height() * self.scale_factor)
        center_x = canvas_size.width() // 2
        center_y = canvas_size.height() // 2
        offset_x = center_x - (display_w // 2) + self.pan_offset.x()
        offset_y = center_y - (display_h // 2) + self.pan_offset.y()

        self.img_draw_rect = QRect(offset_x, offset_y, display_w, display_h)

        # Draw Image & subtle frame
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(self.img_draw_rect, self.qt_image)
        painter.setPen(QPen(QColor("#282d37"), 1))
        painter.drawRect(self.img_draw_rect.adjusted(-1, -1, 0, 0))

        # Draw Shapes
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for shape in self.shapes:
            self.draw_shape(painter, shape)

        # Draw Overlays (Handles/Selection)
        if self.selected_shape and self.mode in ['SELECT_SHAPE', 'NONE', 'DRAW_TEXT']: # Allow editing text after creation
            self.draw_handles(painter, self.selected_shape)

        # Draw Crop Selection
        if self.mode == 'CROP':
            self.draw_crop_ui(painter)

    def draw_shape(self, painter, shape):
        # Coordinates must be mapped from Image Space to Widget Space
        pen = QPen(shape.color, shape.width * self.scale_factor) # Scale width too? Maybe. Or keep constant visual width?
        # Typically line width scales with zoom, but here shape.width is in Image Pixels.
        pen.setWidthF(shape.width * self.scale_factor)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if shape.type in ['line', 'arrow']:
            p1 = self.map_from_image(shape.start_pos)
            p2 = self.map_from_image(shape.end_pos)
            painter.drawLine(p1, p2)
            if shape.type == 'arrow':
                # Draw Arrowhead
                import math
                line_vec = p2 - p1
                angle = math.atan2(line_vec.y(), line_vec.x())
                arrow_len = 15 # Constant visual size? Or scaled? Scaled matches image content.
                arrow_len *= self.scale_factor 
                arrow_angle = math.radians(30)
                
                tip1 = p2 - QPointF(arrow_len * math.cos(angle - arrow_angle), arrow_len * math.sin(angle - arrow_angle))
                tip2 = p2 - QPointF(arrow_len * math.cos(angle + arrow_angle), arrow_len * math.sin(angle + arrow_angle))
                painter.drawLine(p2, tip1)
                painter.drawLine(p2, tip2)

        elif shape.type == 'pen' or shape.type == 'eraser':
             if shape.type == 'eraser':
                 painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                 # Ensure we have a thick enough pen for eraser
                 pen.setWidthF(shape.width * self.scale_factor * 2) # Eraser often larger
                 painter.setPen(pen)
             
             if len(shape.points) > 1:
                 # Need to map points
                 mapped_points = [self.map_from_image(p) for p in shape.points]
                 from PyQt6.QtGui import QPolygonF
                 painter.drawPolyline(QPolygonF(mapped_points))
             
             if shape.type == 'eraser':
                 # Restore composition mode
                 painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        elif shape.type == 'rect':
            r = self.map_rect_from_image(shape.rect)
            painter.drawRect(r)
        elif shape.type == 'ellipse':
            r = self.map_rect_from_image(shape.rect)
            painter.drawEllipse(r)
        elif shape.type == 'text':
             r = self.map_rect_from_image(shape.rect)
             font = QFont("Arial", int(shape.font_size * self.scale_factor))
             painter.setFont(font)
             painter.setPen(shape.color)
             painter.drawText(r, Qt.AlignmentFlag.AlignLeft, shape.text)
             painter.drawText(r, Qt.AlignmentFlag.AlignLeft, shape.text)
             # Draw dashed box if selected?
             

             
    def draw_handles(self, painter, shape):
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QColor("#0078d4"))
        handles = self.get_shape_handles(shape)
        for rect in handles.values():
             painter.drawRect(rect)
        
        # Bounding box for non-rect shapes to make it clear?
        if shape.type == 'text':
            r = self.map_rect_from_image(shape.rect)
            pen = QPen(Qt.GlobalColor.lightGray, 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)

    def draw_crop_ui(self, painter):
        if self.selection_rect.isEmpty(): return
        
        painter.setBrush(QColor(0, 0, 0, 150))
        painter.setPen(Qt.PenStyle.NoPen)
        r = self.selection_rect
        w, h = self.width(), self.height()
        painter.drawRect(0, 0, w, r.top())
        painter.drawRect(0, r.bottom() + 1, w, h - r.bottom())
        painter.drawRect(0, r.top(), r.left(), r.height())
        painter.drawRect(r.right() + 1, r.top(), w - r.right(), r.height())

        pen = QPen(QColor("#0078d4"), 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(r)
        
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QColor("#0078d4"))
        handles = self.get_handles_for_rect(QRectF(r)) # Convert to Float for unified handle logic
        for rect in handles.values():
            painter.drawRect(rect)

    # --- Mouse Events ---

    def mousePressEvent(self, event):
        if not self.qt_image: return 
        pos = event.pos()

        # Panning
        if event.button() == Qt.MouseButton.MiddleButton:
            self.is_panning = True
            self.last_mouse_pos = pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        # 1. CROP MODE
        if self.mode == 'CROP':
             # Legacy Crop Logic or Adapted
             # Check handles first
             handles = self.get_handles_for_rect(QRectF(self.selection_rect))
             clicked_handle = None
             for name, rect in handles.items():
                 if rect.contains(QPointF(pos)):
                     clicked_handle = name
                     break
            
             if clicked_handle:
                 self.is_resizing = True
                 self.resize_handle = clicked_handle
                 self.last_mouse_pos = pos
             elif self.selection_rect.contains(pos):
                 self.is_moving = True
                 self.last_mouse_pos = pos
             else:
                 self.is_creating = True
                 self.start_point = pos
                 self.selection_rect = QRect()
             self.update()
             return

        # 2. DRAWING MODES
        if self.mode.startswith('DRAW_'):
             self.is_creating = True
             img_pos = self.map_to_image(pos)
             self.start_point_f = img_pos
             
             # Create Shape
             if self.mode == 'DRAW_LINE': shape = LineShape()
             elif self.mode == 'DRAW_ARROW': shape = ArrowShape()
             elif self.mode == 'DRAW_ELLIPSE': shape = EllipseShape()
             elif self.mode == 'DRAW_RECT': shape = RectShape()
             elif self.mode == 'DRAW_TEXT': shape = TextShape()
             elif self.mode == 'DRAW_PEN': shape = PenShape()
             elif self.mode == 'DRAW_ERASER':
                  shape = PenShape()
                  shape.type = 'eraser'
                  shape.width = self.current_width * 2 # Default thicker eraser
             
             shape.color = self.current_color
             shape.width = self.current_width
             
             if hasattr(shape, 'set_points'):
                 shape.set_points(img_pos, img_pos)
             else:
                 shape.rect = QRectF(img_pos, QSizeF(1,1)) # Tiny start
                 
             self.selected_shape = shape
             self.shapes.append(shape) # Temporary add
             self.update()
             return

        # 3. SELECT MODE
        if self.mode in ['SELECT_SHAPE', 'NONE']:
             hit_type, payload = self.hit_test(pos)
             
             if hit_type == 'HANDLE':
                 self.is_resizing = True
                 self.resize_handle = payload
                 self.last_mouse_pos = pos
             elif hit_type == 'SHAPE':
                 self.selected_shape = payload
                 self.is_moving = True
                 self.last_mouse_pos = pos
                 self.update()
             else:
                 self.selected_shape = None
                 self.update()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        
        if self.is_panning:
            delta = pos - self.last_mouse_pos
            self.last_mouse_pos = pos
            self.pan_offset += delta
            self.update()
            return

        # CROP Logic
        if self.mode == 'CROP':
             if not (self.is_creating or self.is_moving or self.is_resizing):
                 # Hover Cursor Update
                 handles = self.get_handles_for_rect(QRectF(self.selection_rect))
                 cursor_set = False
                 for name, rect in handles.items():
                     if rect.contains(QPointF(pos)):
                         if name in ['TL', 'BR']: self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                         elif name in ['TR', 'BL']: self.setCursor(Qt.CursorShape.SizeBDiagCursor)
                         elif name in ['TM', 'BM']: self.setCursor(Qt.CursorShape.SizeVerCursor)
                         elif name in ['ML', 'MR']: self.setCursor(Qt.CursorShape.SizeHorCursor)
                         cursor_set = True
                         break
                 if not cursor_set:
                     if self.selection_rect.contains(pos):
                         self.setCursor(Qt.CursorShape.SizeAllCursor)
                     else:
                         self.setCursor(Qt.CursorShape.CrossCursor)

             elif self.is_creating:
                 rect = QRect(self.start_point, pos).normalized().intersected(self.img_draw_rect)
                 self.selection_rect = rect
             elif self.is_moving:
                 delta = pos - self.last_mouse_pos
                 self.last_mouse_pos = pos
                 self.selection_rect = self.selection_rect.translated(delta).intersected(self.img_draw_rect)
             elif self.is_resizing:
                 delta = pos - self.last_mouse_pos
                 self.last_mouse_pos = pos
                 r = self.selection_rect
                 x, y, w, h = r.x(), r.y(), r.width(), r.height()
                 dx = delta.x()
                 dy = delta.y()

                 if 'L' in self.resize_handle: 
                     x += dx
                     w -= dx
                 if 'R' in self.resize_handle: 
                     w += dx
                 if 'T' in self.resize_handle: 
                     y += dy
                     h -= dy
                 if 'B' in self.resize_handle: 
                     h += dy
                 
                 self.selection_rect = QRect(x, y, w, h).normalized().intersected(self.img_draw_rect)

             self.update()
             return

        # DRAWING Logic
        if self.is_creating:
             img_pos = self.map_to_image(pos)
             shape = self.selected_shape
             
             if shape.type == 'text':
                 return # Text doesn't drag-resize on creation usually, or drags box?
                 
             if shape.type in ['line', 'arrow']:
                 shape.set_points(self.start_point_f, img_pos)
             elif shape.type == 'pen' or shape.type == 'eraser':
                 shape.add_point(img_pos)
             else:
                 shape.rect = QRectF(self.start_point_f, img_pos).normalized()
             self.update()

        # EDITING Logic
        elif self.selected_shape:
             img_pos = self.map_to_image(pos)
             last_img_pos = self.map_to_image(self.last_mouse_pos)
             delta = img_pos - last_img_pos
             
             if self.is_moving:
                 self.selected_shape.move(delta)
                 self.last_mouse_pos = pos
                 self.update()
             elif self.is_resizing:
                 self.handle_shape_resize(self.selected_shape, self.resize_handle, delta)
                 self.last_mouse_pos = pos
                 self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if self.is_creating:
            if self.mode == 'DRAW_TEXT':
                 # Prompt for text
                 text, ok = QInputDialog.getText(self, "Text Input", "Enter text:")
                 if ok and text:
                     self.selected_shape.text = text
                     # Estimate size?
                     self.selected_shape.rect.setWidth(len(text) * 15) 
                     self.selected_shape.rect.setHeight(30)
                     if self.shape_added: self.shape_added(self.selected_shape)
                 else:
                     self.shapes.remove(self.selected_shape)
            elif self.mode != 'CROP':
                 if self.shape_added and self.selected_shape: self.shape_added(self.selected_shape)
            
            # Switch back to select mode? Only for drawing shapes, not crop
            if self.mode != 'CROP':
                self.mode = 'SELECT_SHAPE'
                self.setCursor(Qt.CursorShape.ArrowCursor)

        if self.is_moving or self.is_resizing:
             if self.shape_updated and self.selected_shape:
                 self.shape_updated(self.selected_shape)

        self.is_creating = False
        self.is_moving = False
        self.is_resizing = False
        self.resize_handle = None
        self.update()

    def mouseDoubleClickEvent(self, event):
         if self.mode == 'CROP':
             if self.crop_completed:
                 self.crop_completed(self.selection_rect, self.scale_factor, self.img_draw_rect.x(), self.img_draw_rect.y())
                 self.selection_rect = QRect()
         elif self.selected_shape and self.selected_shape.type == 'text':
             # Edit Text
             text, ok = QInputDialog.getText(self, "Edit Text", "Edit text:", text=self.selected_shape.text)
             if ok:
                 self.selected_shape.text = text
                 if self.shape_updated: self.shape_updated(self.selected_shape)
                 self.update()
    
    def keyPressEvent(self, event):
         if self.mode == 'CROP':
             if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                 if self.crop_completed:
                      self.crop_completed(self.selection_rect, self.scale_factor, self.img_draw_rect.x(), self.img_draw_rect.y())
                      self.selection_rect = QRect()
                      self.update()
             elif event.key() == Qt.Key.Key_Escape:
                  self.set_mode('NONE')
         
         elif event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
              if self.selected_shape:
                   self.shapes.remove(self.selected_shape)
                   self.selected_shape = None
                   # Commit deletion
                   if self.shape_updated: self.shape_updated(None) # Force push
                   self.update()

    def handle_shape_resize(self, shape, handle, delta):
         # Delta is in Image Coordinates
         if shape.type in ['line', 'arrow']:
             if handle == 'START':
                 shape.start_pos += delta
             elif handle == 'END':
                 shape.end_pos += delta
             # Update rect
             shape.rect = QRectF(shape.start_pos, shape.end_pos).normalized()
         else:
             r = shape.rect
             l, t, w, h = r.x(), r.y(), r.width(), r.height()
             
             if 'L' in handle: l += delta.x(); w -= delta.x()
             if 'R' in handle: w += delta.x()
             if 'T' in handle: t += delta.y(); h -= delta.y()
             if 'B' in handle: h += delta.y()
             
             shape.rect = QRectF(l, t, w, h).normalized()

