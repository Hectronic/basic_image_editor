"""
Basic Image Editor
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PIL import Image, ImageEnhance, ImageQt
import logging
import numpy as np

from src.processing.raw_developer import (
    is_raw_file,
    load_raw_16bit,
    pil_to_float,
    float_to_pil,
    develop_base_image,
)
from src.processing.preset_engine import apply_preset, get_preset_metadata
from src.processing.reveal_assistant import (
    analyze_image,
    compute_auto_develop_params,
    compute_smart_square_crop,
    strip_ai_watermarks_and_swirl,
)

logger = logging.getLogger(__name__)


class ImageModel:
    """Handles Image Processing, RAW Development, Presets, and Smart Assistant."""

    def __init__(self):
        self.original_image = None  # PIL RGBA image (loaded from disk or after geometric ops)
        self.display_image = None   # Final PIL RGBA image ready for display
        self.preview_image = None   # Intermediate PIL RGBA image
        self.is_raw = False
        self.filepath = None

        # Classic adjustment parameters
        self.brightness = 1.0
        self.contrast = 1.0
        self.saturation = 1.0

        # RAW / Reveal parametric adjustments
        self.ev = 0.0
        self.shadows = 0.0
        self.highlights = 0.0
        self.wb_temp = 0.0
        self.wb_tint = 0.0
        self.denoise = 0.0
        self.sharpen = 0.0

        # Photographic Preset parameters
        self.active_preset = "none"
        self.preset_intensity = 1.0

        # Vector Objects
        self.shapes = []

        # History
        self.history = []     # List of dicts representing state
        self.redo_stack = []  # List of dicts representing state
        self.max_history = 20

    def _reset_parameters(self):
        self.brightness = 1.0
        self.contrast = 1.0
        self.saturation = 1.0
        self.ev = 0.0
        self.shadows = 0.0
        self.highlights = 0.0
        self.wb_temp = 0.0
        self.wb_tint = 0.0
        self.denoise = 0.0
        self.sharpen = 0.0
        self.active_preset = "none"
        self.preset_intensity = 1.0

    def load_image(self, filepath):
        try:
            self.filepath = filepath
            if is_raw_file(filepath):
                rgb_float = load_raw_16bit(filepath, unclipped=True)
                self.original_image = float_to_pil(rgb_float)
                self.is_raw = True
            else:
                self.original_image = Image.open(filepath).convert("RGBA")
                self.is_raw = False

            self._reset_parameters()
            self.preview_image = self.original_image.copy()
            self.shapes = []
            self._update_display_image()
            self.history.clear()
            self.redo_stack.clear()
            self.push_state("Load Image")
            logger.info(f"Image loaded successfully: {filepath} (RAW={self.is_raw})")
            return True
        except Exception as e:
            logger.error(f"Error loading image {filepath}: {e}")
            print(f"Error loading image: {e}")
            return False

    def save_image(self, filepath):
        if self.display_image:
            try:
                final_img = self.display_image.copy()
                qimg = ImageQt.ImageQt(final_img)

                from PyQt6.QtGui import QPainter, QPen, QFont
                from PyQt6.QtCore import Qt, QPointF

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
                            import math
                            line_vec = shape.end_pos - shape.start_pos
                            angle = math.atan2(line_vec.y(), line_vec.x())
                            arrow_len = 15
                            arrow_angle = math.radians(30)

                            p1 = shape.end_pos - QPointF(
                                arrow_len * math.cos(angle - arrow_angle),
                                arrow_len * math.sin(angle - arrow_angle),
                            )
                            p2 = shape.end_pos - QPointF(
                                arrow_len * math.cos(angle + arrow_angle),
                                arrow_len * math.sin(angle + arrow_angle),
                            )
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

        shapes_copy = [s.copy() for s in self.shapes]

        state = {
            "image": self.original_image.copy(),
            "brightness": self.brightness,
            "contrast": self.contrast,
            "saturation": self.saturation,
            "ev": self.ev,
            "shadows": self.shadows,
            "highlights": self.highlights,
            "wb_temp": self.wb_temp,
            "wb_tint": self.wb_tint,
            "denoise": self.denoise,
            "sharpen": self.sharpen,
            "active_preset": self.active_preset,
            "preset_intensity": self.preset_intensity,
            "shapes": shapes_copy,
            "description": description,
        }

        self.history.append(state)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        self.redo_stack.clear()

    def undo(self):
        if len(self.history) > 1:
            current_state = self.history.pop()
            self.redo_stack.append(current_state)

            prev_state = self.history[-1]
            self._restore_state(prev_state)
            return True
        return False

    def redo(self):
        if self.redo_stack:
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
        self.ev = state.get("ev", 0.0)
        self.shadows = state.get("shadows", 0.0)
        self.highlights = state.get("highlights", 0.0)
        self.wb_temp = state.get("wb_temp", 0.0)
        self.wb_tint = state.get("wb_tint", 0.0)
        self.denoise = state.get("denoise", 0.0)
        self.sharpen = state.get("sharpen", 0.0)
        self.active_preset = state.get("active_preset", "none")
        self.preset_intensity = state.get("preset_intensity", 1.0)

        self.shapes = [s.copy() for s in state.get("shapes", [])]

        self.preview_image = self.original_image.copy()
        self._update_display_image()

    def add_shape(self, shape):
        self.shapes.append(shape)
        self.push_state(f"Add {shape.type.capitalize()}")

    def update_shape(self, shape):
        pass

    def rotate(self, angle):
        """Rotate the geometric image (commits the change to base)."""
        if self.original_image:
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
        """
        if self.original_image:
            x = int((rect.x() - offset_x) / scale_factor)
            y = int((rect.y() - offset_y) / scale_factor)
            w = int(rect.width() / scale_factor)
            h = int(rect.height() / scale_factor)

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

    def set_reveal_params(
        self,
        ev=None,
        shadows=None,
        highlights=None,
        wb_temp=None,
        wb_tint=None,
        denoise=None,
        sharpen=None,
    ):
        """Updates parametric RAW/reveal parameters and refreshes display_image."""
        if ev is not None:
            self.ev = float(ev)
        if shadows is not None:
            self.shadows = float(shadows)
        if highlights is not None:
            self.highlights = float(highlights)
        if wb_temp is not None:
            self.wb_temp = float(wb_temp)
        if wb_tint is not None:
            self.wb_tint = float(wb_tint)
        if denoise is not None:
            self.denoise = float(denoise)
        if sharpen is not None:
            self.sharpen = float(sharpen)
        self._update_display_image()

    def set_preset(self, preset_id: str, intensity: float = 1.0, push_history: bool = True):
        """Applies a photographic preset non-destructively."""
        self.active_preset = preset_id
        self.preset_intensity = float(np.clip(intensity, 0.0, 1.0))
        self._update_display_image()
        if push_history and self.original_image:
            meta = get_preset_metadata(preset_id)
            self.push_state(f"Preset: {meta['name']}")

    def commit_adjustments(self, description="Adjustments"):
        """Call this when slider is released to save state."""
        pass

    def reset_adjustments(self):
        self.push_state("Reset Adjustments")
        self._reset_parameters()
        self._update_display_image()

    def _has_reveal_or_preset(self) -> bool:
        return (
            abs(self.ev) > 1e-4
            or abs(self.shadows) > 1e-4
            or abs(self.highlights) > 1e-4
            or abs(self.wb_temp) > 1e-4
            or abs(self.wb_tint) > 1e-4
            or self.denoise > 1e-3
            or self.sharpen > 1e-3
            or (self.active_preset != "none" and self.preset_intensity > 1e-4)
        )

    def get_base_float_rgb(self) -> np.ndarray | None:
        """Returns the current geometric base image as float32 RGB in [0, 1]."""
        if not self.original_image:
            return None
        rgb_f, _ = pil_to_float(self.original_image)
        return rgb_f

    def _update_display_image(self):
        """Applies non-destructive RAW reveal, preset grading, and classic adjustments."""
        if not self.original_image:
            return

        if self._has_reveal_or_preset():
            rgb_f, alpha = pil_to_float(self.original_image)
            rgb_f = develop_base_image(
                rgb_f,
                ev=self.ev,
                shadows=self.shadows,
                highlights=self.highlights,
                wb_temp=self.wb_temp,
                wb_tint=self.wb_tint,
                denoise=self.denoise,
                sharpen=self.sharpen,
            )
            if self.active_preset != "none" and self.preset_intensity > 1e-4:
                rgb_f = apply_preset(rgb_f, self.active_preset, self.preset_intensity)
            img = float_to_pil(rgb_f, alpha)
        else:
            img = self.original_image.copy()

        # Classic adjustments
        if self.brightness != 1.0:
            img = ImageEnhance.Brightness(img).enhance(self.brightness)
        if self.contrast != 1.0:
            img = ImageEnhance.Contrast(img).enhance(self.contrast)
        if self.saturation != 1.0:
            img = ImageEnhance.Color(img).enhance(self.saturation)

        self.display_image = img

    def analyze_current_image(self) -> dict | None:
        """Runs the Smart Reveal Assistant analysis on the base image."""
        rgb_f = self.get_base_float_rgb()
        if rgb_f is None:
            return None
        return analyze_image(rgb_f)

    def auto_develop(self, apply_recommended_preset: bool = True) -> dict | None:
        """
        Automatically calculates and applies optimal exposure, shadow recovery,
        highlight compression, denoise, sharpen, and recommended preset.
        """
        rgb_f = self.get_base_float_rgb()
        if rgb_f is None:
            return None

        params = compute_auto_develop_params(rgb_f)
        self.ev = params["ev"]
        self.shadows = params["shadows"]
        self.highlights = params["highlights"]
        self.wb_temp = params["wb_temp"]
        self.wb_tint = params["wb_tint"]
        self.denoise = params["denoise"]
        self.sharpen = params["sharpen"]
        if apply_recommended_preset:
            self.active_preset = params["recommended_preset"]
            self.preset_intensity = 0.85

        self._update_display_image()
        self.push_state("Auto-Revelado IA")
        return params

    def smart_crop_square_1x1(self) -> bool:
        """Crops the image to an optimal 1:1 square using saliency analysis."""
        rgb_f = self.get_base_float_rgb()
        if rgb_f is None:
            return False
        x, y, side, _ = compute_smart_square_crop(rgb_f)
        self.original_image = self.original_image.crop((x, y, x + side, y + side))
        self.preview_image = self.original_image.copy()
        self._update_display_image()
        self.push_state("Smart Crop 1:1")
        return True

    def clean_ai_watermark(self) -> bool:
        """Removes pixel-level AI watermarks/swirl and strips metadata."""
        if not self.original_image:
            return False
        rgb_f, alpha = pil_to_float(self.original_image)
        cleaned_f = strip_ai_watermarks_and_swirl(rgb_f)
        self.original_image = float_to_pil(cleaned_f, alpha)
        self.preview_image = self.original_image.copy()
        self._update_display_image()
        self.push_state("Limpiar Marca IA")
        return True

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
