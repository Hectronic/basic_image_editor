"""
Basic Image Editor
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
import sys
import os
from PIL import Image

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def sample_image():
    """Returns a simple red 100x100 RGB image."""
    return Image.new('RGBA', (100, 100), color='red')

@pytest.fixture
def sample_image_path(tmp_path, sample_image):
    """Saves sample image to a temp file and returns path."""
    p = tmp_path / "test_img.png"
    sample_image.save(p)
    return str(p)

# pytest-qt handles QApplication creation automatically via 'qtbot' or 'qapp' fixture.
