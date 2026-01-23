"""
Basic Image Editor
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt6.QtCore import QPointF, QRectF
from src.model.image_model import ImageModel
from src.model.shapes import RectShape, LineShape

def test_shape_creation():
    r = RectShape()
    assert r.type == 'rect'
    r.rect = QRectF(0, 0, 10, 10)
    assert r.contains(QPointF(5, 5))
    assert not r.contains(QPointF(20, 20))

def test_image_model_load(sample_image_path):
    model = ImageModel()
    assert model.load_image(sample_image_path)
    assert model.original_image is not None
    assert len(model.history) == 1

def test_image_model_history(sample_image_path):
    model = ImageModel()
    model.load_image(sample_image_path)
    
    # Push new state
    model.brightness = 1.5
    model.push_state("Brightness Change")
    
    assert len(model.history) == 2
    assert model.history[-1]['brightness'] == 1.5
    
    # Undo
    assert model.undo()
    assert len(model.history) == 1
    assert model.brightness == 1.0 # Restored state logic typically restores properties too
    
    # Redo
    assert model.redo()
    assert len(model.history) == 2
    assert model.brightness == 1.5

def test_model_crop(sample_image_path):
    model = ImageModel()
    model.load_image(sample_image_path)
    orig_size = model.original_image.size
    
    # Mock crop rect (viewport coords, scale 1.0)
    # Center crop 50x50
    crop_rect = QRectF(25, 25, 50, 50)
    model.crop(crop_rect, 1.0, 0, 0)
    
    assert model.original_image.size == (50, 50)
    assert len(model.history) == 2

def test_model_adjustments(sample_image_path):
    model = ImageModel()
    model.load_image(sample_image_path)
    
    model.set_adjustments(1.2, 1.1, 0.5)
    assert model.brightness == 1.2
    assert model.contrast == 1.1
    assert model.saturation == 0.5
    
    # Verify display image is updated (not None)
    assert model.display_image is not None
