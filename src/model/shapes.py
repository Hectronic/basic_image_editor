"""
Basic Image Editor
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt6.QtCore import QRectF, QPointF
from PyQt6.QtGui import QColor

class Shape:
    def __init__(self):
        self.rect = QRectF()
        self.color = QColor(255, 0, 0) # Default Red
        self.width = 3
        self.selected = False
        self.type = "shape"

    def copy(self):
        # Shallow copy is risky if we have mutable children, but mostly we store value types.
        # But rect and color are objects.
        import copy
        return copy.deepcopy(self)

    def contains(self, point):
        return self.rect.contains(point)

    def move(self, delta):
        self.rect.translate(delta)

    def normalize(self):
        self.rect = self.rect.normalized()

class LineShape(Shape):
    def __init__(self):
        super().__init__()
        self.type = "line"
        self.start_pos = QPointF()
        self.end_pos = QPointF()

    def set_points(self, p1, p2):
        self.start_pos = p1
        self.end_pos = p2
        # Update bounding rect for selection
        self.rect = QRectF(p1, p2).normalized()

    def move(self, delta):
        self.start_pos += delta
        self.end_pos += delta
        super().move(delta)
    
    def contains(self, point):
        # Hit test line with tolerance
        # Simple distance check
        import math
        p1 = self.start_pos
        p2 = self.end_pos
        
        # Distance from point to line segment
        nom = abs((p2.y() - p1.y()) * point.x() - (p2.x() - p1.x()) * point.y() + p2.x() * p1.y() - p2.y() * p1.x())
        denom = math.sqrt((p2.y() - p1.y())**2 + (p2.x() - p1.x())**2)
        if denom == 0: return False
        dist = nom / denom
        
        # Check if within bounding box too (segment, not infinite line)
        expanded_rect = self.rect.adjusted(-5, -5, 5, 5)
        if not expanded_rect.contains(point): return False

        return dist <= (self.width / 2 + 5) # Tolerance

class RectShape(Shape):
    def __init__(self):
        super().__init__()
        self.type = "rect"

class EllipseShape(Shape):
    def __init__(self):
        super().__init__()
        self.type = "ellipse"

    def contains(self, point):
        # Ellipse hit test is mathy. 
        # For simplicity, we can check bounding rect or use QPainterPath
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        path.addEllipse(self.rect)
        return path.contains(point)

class ArrowShape(LineShape):
    def __init__(self):
        super().__init__()
        self.type = "arrow"

class TextShape(Shape):
    def __init__(self):
        super().__init__()
        self.type = "text"
        self.text = ""
        self.font_size = 20

class PenShape(Shape):
    def __init__(self):
        super().__init__()
        self.type = "pen"
        self.points = []

    def set_points(self, p_start, p_end):
        # Used for initial creation compatibility, but pen usually appends
        if not self.points:
            self.points.append(p_start)
        self.points.append(p_end)
        self._update_rect()

    def add_point(self, point):
        self.points.append(point)
        self._update_rect()

    def _update_rect(self):
        if not self.points:
            self.rect = QRectF()
            return
        
        # Calculate bounding box
        xs = [p.x() for p in self.points]
        ys = [p.y() for p in self.points]
        self.rect = QRectF(min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys)).normalized()

    def move(self, delta):
        # Move all points
        self.points = [p + delta for p in self.points]
        super().move(delta)
    
    def copy(self):
        import copy
        new_shape = super().copy()
        new_shape.points = [QPointF(p) for p in self.points] # Ensure deep copy of points
        return new_shape

    def contains(self, point):
        # Simple bounding box check for now, accurate path checking is expensive
        expanded = self.rect.adjusted(-5, -5, 5, 5)
        return expanded.contains(point)
