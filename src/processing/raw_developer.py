"""
Basic Image Editor - RAW 16-bit Developer & High-Definition Pipeline
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import logging
import cv2
import numpy as np
from PIL import Image

try:
    import rawpy
except ImportError:  # pragma: no cover
    rawpy = None

logger = logging.getLogger(__name__)

RAW_EXTENSIONS = (
    ".arw",
    ".cr2",
    ".cr3",
    ".nef",
    ".dng",
    ".raf",
    ".orf",
    ".rw2",
    ".pef",
    ".srw",
)


def is_raw_file(filepath: str) -> bool:
    """Returns True if filepath has a supported digital camera RAW extension."""
    if not filepath:
        return False
    ext = os.path.splitext(filepath)[1].lower()
    return ext in RAW_EXTENSIONS


def pil_to_float(pil_img: Image.Image) -> tuple[np.ndarray, np.ndarray | None]:
    """
    Converts a PIL Image into an RGB float32 array in [0, 1] and an optional alpha channel.
    """
    if pil_img.mode == "RGBA":
        arr = np.asarray(pil_img, dtype=np.float32) / 255.0
        return arr[..., :3].copy(), arr[..., 3].copy()
    rgb = pil_img.convert("RGB")
    arr = np.asarray(rgb, dtype=np.float32) / 255.0
    return arr, None


def float_to_pil(img_float: np.ndarray, alpha: np.ndarray | None = None) -> Image.Image:
    """
    Converts an RGB float32 array in [0, 1] back to an RGBA PIL Image.
    """
    rgb_u8 = (np.clip(img_float, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    if alpha is not None and alpha.shape[:2] == rgb_u8.shape[:2]:
        alpha_u8 = (np.clip(alpha, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
        rgba = np.dstack([rgb_u8, alpha_u8])
        return Image.fromarray(rgba, mode="RGBA")
    pil_rgb = Image.fromarray(rgb_u8, mode="RGB")
    return pil_rgb.convert("RGBA")


def load_raw_16bit(
    filepath: str,
    unclipped: bool = True,
    wb_gains: tuple[float, float] = (1.0, 1.0),
    half_size: bool = False,
) -> np.ndarray:
    """
    Loads a camera RAW file (.ARW, .CR2, .NEF, .DNG, etc.) in 16-bit precision
    without automatic histogram clipping, returning a float32 RGB array in [0, 1].
    """
    if rawpy is None:
        raise RuntimeError("rawpy is not installed; cannot decode RAW file.")

    with rawpy.imread(filepath) as raw:
        hl_mode = (
            rawpy.HighlightMode.Blend
            if unclipped
            else rawpy.HighlightMode.Clip
        )
        rgb16 = raw.postprocess(
            use_camera_wb=True,
            no_auto_bright=True,
            output_bps=16,
            half_size=half_size,
            highlight_mode=hl_mode,
        )

    img = rgb16.astype(np.float32) / 65535.0
    r_gain, b_gain = wb_gains
    if r_gain != 1.0 or b_gain != 1.0:
        img[..., 0] *= r_gain
        img[..., 2] *= b_gain

    # Normalize gently if highlights exceed 1.0 while keeping soft-knee headroom
    peak = float(np.percentile(img, 99.95))
    if peak > 1.0:
        img = img / peak
    return np.clip(img, 0.0, 1.0)


def protect_gamut_and_highlights(
    img_float: np.ndarray,
    red_tame: float = 0.16,
    highlight_rolloff: float = 0.14,
) -> np.ndarray:
    """
    Prevents channel clipping in intense reds/neons and compresses harsh highlights
    using a smooth soft-knee curve so internal texture is preserved.
    """
    out = np.clip(img_float, 0.0, 1.2).copy()

    if red_tame > 0.0:
        r, g, b = out[..., 0], out[..., 1], out[..., 2]
        excess_r = np.maximum(0.0, r - np.maximum(g, b))
        high_r = np.clip((r - 0.65) / 0.35, 0.0, 1.0)
        tame_mask = excess_r * high_r * red_tame
        out[..., 0] = r - tame_mask * 0.65
        out[..., 1] = g + tame_mask * 0.20

    if highlight_rolloff > 0.0:
        knee = 0.78
        above = np.maximum(0.0, out - knee)
        compressed = knee + above / (1.0 + highlight_rolloff * 3.5 * (above / (1.0 - knee + 1e-5)))
        out = np.where(out > knee, compressed, out)

    return np.clip(out, 0.0, 1.0)


def denoise_ultra_clean(
    img_float: np.ndarray,
    chroma_strength: float = 12.0,
    luma_strength: float = 3.5,
) -> np.ndarray:
    """
    Edge-guided noise reduction that removes sensor chroma/luma noise and AI swirl
    patterns in flat regions while keeping 100% of structural edge sharpness.
    Zero artificial grain is ever added.
    """
    if chroma_strength <= 0.0 and luma_strength <= 0.0:
        return np.clip(img_float, 0.0, 1.0)

    u8 = (np.clip(img_float, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    lab = cv2.cvtColor(u8, cv2.COLOR_RGB2LAB)
    l_chan, a_chan, b_chan = cv2.split(lab)

    # 1. Smooth chroma channels (A & B) where color noise lives
    if chroma_strength > 0.0:
        d_chroma = max(5, int(round(chroma_strength * 0.6)) | 1)
        a_chan = cv2.bilateralFilter(a_chan, d=d_chroma, sigmaColor=chroma_strength * 2.2, sigmaSpace=chroma_strength * 1.8)
        b_chan = cv2.bilateralFilter(b_chan, d=d_chroma, sigmaColor=chroma_strength * 2.2, sigmaSpace=chroma_strength * 1.8)

    # 2. Edge-protected luminance smoothing
    if luma_strength > 0.0:
        l_float = l_chan.astype(np.float32) / 255.0
        l_smooth_guide = cv2.GaussianBlur(l_float, (5, 5), 1.0)
        gx = cv2.Sobel(l_smooth_guide, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(l_smooth_guide, cv2.CV_32F, 0, 1, ksize=3)
        grad = np.sqrt(gx * gx + gy * gy)
        edge_mask = np.clip((grad - 0.04) / 0.16, 0.0, 1.0)
        edge_mask = cv2.GaussianBlur(edge_mask, (5, 5), 1.0)

        l_bilat = cv2.bilateralFilter(
            l_chan,
            d=7,
            sigmaColor=luma_strength * 4.5,
            sigmaSpace=luma_strength * 3.5,
        ).astype(np.float32) / 255.0

        l_out = l_bilat * (1.0 - edge_mask) + l_float * edge_mask
        l_chan = (np.clip(l_out, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)

    lab_clean = cv2.merge([l_chan, a_chan, b_chan])
    rgb_clean = cv2.cvtColor(lab_clean, cv2.COLOR_LAB2RGB)
    return rgb_clean.astype(np.float32) / 255.0


def sharpen_hd_modern(img_float: np.ndarray, strength: float = 0.38) -> np.ndarray:
    """
    Selective structural sharpening: enhances true edges and micro-details while
    suppressing sharpening in flat regions (sky, skin, bokeh) to prevent grain.
    """
    if strength <= 0.0:
        return np.clip(img_float, 0.0, 1.0)

    base = np.clip(img_float, 0.0, 1.0)
    luma = 0.299 * base[..., 0] + 0.587 * base[..., 1] + 0.114 * base[..., 2]
    luma_guide = cv2.GaussianBlur(luma, (3, 3), 0.8)
    gx = cv2.Sobel(luma_guide, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(luma_guide, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.sqrt(gx * gx + gy * gy)

    edge_weight = np.clip((grad - 0.03) / 0.18, 0.0, 1.0)
    edge_weight = cv2.GaussianBlur(edge_weight, (5, 5), 1.0)[..., np.newaxis]

    blurred = cv2.GaussianBlur(base, (0, 0), 1.1)
    detail = base - blurred
    sharpened = base + detail * (strength * 1.45) * edge_weight
    return np.clip(sharpened, 0.0, 1.0)


def apply_s_curve_luminance(img_float: np.ndarray, contrast_strength: float = 0.18) -> np.ndarray:
    """Applies a smooth filmic S-curve on luminance while preserving chromaticity."""
    if abs(contrast_strength) < 1e-4:
        return img_float
    x = np.clip(img_float, 0.0, 1.0)
    curved = x - contrast_strength * 0.22 * np.sin(2.0 * np.pi * x)
    return np.clip(curved, 0.0, 1.0)


def develop_base_image(
    img_float: np.ndarray,
    ev: float = 0.0,
    shadows: float = 0.0,
    highlights: float = 0.0,
    wb_temp: float = 0.0,
    wb_tint: float = 0.0,
    denoise: float = 0.0,
    sharpen: float = 0.0,
) -> np.ndarray:
    """
    Applies non-destructive RAW/photo development adjustments:
    - ev: Exposure compensation in stops (-2.0 to +2.0)
    - shadows: Shadow lift (-1.0 to +1.0)
    - highlights: Highlight recovery (-1.0 to +1.0)
    - wb_temp: Warm/Cool white balance shift (-1.0 to +1.0)
    - wb_tint: Green/Magenta tint shift (-1.0 to +1.0)
    - denoise: Edge-preserving noise reduction intensity (0.0 to 1.0)
    - sharpen: Structural HD sharpening intensity (0.0 to 1.0)
    """
    out = np.clip(img_float, 0.0, 1.0).astype(np.float32).copy()

    # 1. White Balance (Temperature & Tint)
    if abs(wb_temp) > 1e-4 or abs(wb_tint) > 1e-4:
        out[..., 0] *= 1.0 + wb_temp * 0.18 + wb_tint * 0.06
        out[..., 1] *= 1.0 - wb_tint * 0.08
        out[..., 2] *= 1.0 - wb_temp * 0.18 + wb_tint * 0.06

    # 2. Exposure Compensation (EV) with highlight protection
    if abs(ev) > 1e-4:
        gain = float(2.0 ** ev)
        # Gamma-assisted lift so midtones open up naturally without blowing highlights
        if ev > 0:
            gamma = max(0.60, 1.0 / (1.0 + ev * 0.55))
            out = np.power(np.clip(out, 0.0, 1.0), gamma) * (1.0 + ev * 0.18)
        else:
            out = out * gain

    # 3. Shadow Recovery
    if abs(shadows) > 1e-4:
        luma = 0.299 * out[..., 0] + 0.587 * out[..., 1] + 0.114 * out[..., 2]
        shadow_mask = np.power(1.0 - np.clip(luma, 0.0, 1.0), 2.2)[..., np.newaxis]
        out = out + shadows * 0.42 * shadow_mask * (1.0 - out)

    # 4. Highlight Recovery / Compression
    if abs(highlights) > 1e-4:
        luma = 0.299 * out[..., 0] + 0.587 * out[..., 1] + 0.114 * out[..., 2]
        hl_mask = np.power(np.clip((luma - 0.50) / 0.50, 0.0, 1.0), 1.6)[..., np.newaxis]
        out = out - highlights * 0.32 * hl_mask * out

    out = protect_gamut_and_highlights(out, red_tame=0.14, highlight_rolloff=0.14)

    # 5. Edge-Guided Denoise
    if denoise > 1e-3:
        out = denoise_ultra_clean(
            out,
            chroma_strength=14.0 * denoise,
            luma_strength=4.5 * denoise,
        )

    # 6. Structural HD Sharpening
    if sharpen > 1e-3:
        out = sharpen_hd_modern(out, strength=0.55 * sharpen)

    return np.clip(out, 0.0, 1.0)
