"""
Basic Image Editor
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
from PyQt6.QtCore import QThread, pyqtSignal
from PIL import Image
import rembg
import numpy as np

class BackgroundRemoverWorker(QThread):
    finished = pyqtSignal(object) # Emit PIL Image
    error = pyqtSignal(str)

    def __init__(self, image: Image.Image):
        super().__init__()
        self.image = image

    def run(self):
        try:
            # rembg expects PIL image or bytes.
            # It returns a PIL image by default if input is PIL.
            output_image = rembg.remove(self.image)
            self.finished.emit(output_image)
        except Exception as e:
            self.error.emit(str(e))
