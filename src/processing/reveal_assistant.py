"""
Basic Image Editor - Smart Photographic Reveal Assistant
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import cv2
import numpy as np

from src.processing.raw_developer import denoise_ultra_clean, sharpen_hd_modern


def analyze_image(img_float: np.ndarray) -> dict:
    """
    Analyzes an RGB float32 image [0, 1] and returns diagnostic metrics,
    scene classification, optimal preset recommendation, and human-readable tips.
    """
    arr = np.clip(img_float, 0.0, 1.0).astype(np.float32)
    h, w, _ = arr.shape

    # Downsample for fast analysis if image is huge
    max_dim = 512
    if max(h, w) > max_dim:
        scale = max_dim / float(max(h, w))
        small = cv2.resize(arr, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    else:
        small = arr

    luma = 0.299 * small[..., 0] + 0.587 * small[..., 1] + 0.114 * small[..., 2]
    mean_luma = float(np.mean(luma))
    p02 = float(np.percentile(luma, 2.0))
    p50 = float(np.percentile(luma, 50.0))
    p98 = float(np.percentile(luma, 98.0))
    dynamic_range = float(p98 - p02)

    shadow_ratio = float(np.mean(luma < 0.18))
    highlight_ratio = float(np.mean(luma > 0.90))

    # Color balance & saturation
    mean_r = float(np.mean(small[..., 0]))
    mean_g = float(np.mean(small[..., 1]))
    mean_b = float(np.mean(small[..., 2]))
    warmth = float(mean_r - mean_b)

    sat = np.max(small, axis=-1) - np.min(small, axis=-1)
    mean_sat = float(np.mean(sat))

    # Sharpness (Laplacian variance on central region)
    ch0, ch1 = int(small.shape[0] * 0.15), max(1, int(small.shape[0] * 0.85))
    cw0, cw1 = int(small.shape[1] * 0.15), max(1, int(small.shape[1] * 0.85))
    center_gray = (luma[ch0:ch1, cw0:cw1] * 255.0).astype(np.uint8)
    lap = cv2.Laplacian(center_gray, cv2.CV_32F)
    sharpness_score = float(np.var(lap))

    # Green foliage / skin / neon detection heuristics
    max_c = np.max(small, axis=-1)
    green_dominance = float(np.mean((small[..., 1] > small[..., 0] * 1.05) & (small[..., 1] > small[..., 2] * 1.08)))
    neon_highlights = float(np.mean((max_c > 0.65) & (sat > 0.45)))

    # Scene classification & preset recommendation
    if mean_luma < 0.28 and neon_highlights > 0.015:
        scene_type = "Escena Nocturna / Neones Urbanos"
        recommended_preset = "electric_chroma_hd"
        alternative_preset = "cinestill_800t"
    elif shadow_ratio > 0.38 and warmth > 0.01:
        scene_type = "Retrato / Sombra Abierta o Contraluz"
        recommended_preset = "editorial_viva_hd"
        alternative_preset = "moderna_definida_hd"
    elif green_dominance > 0.22:
        scene_type = "Naturaleza / Parque y Vegetación"
        recommended_preset = "moderna_definida_hd"
        alternative_preset = "editorial_viva_hd"
    elif mean_sat > 0.26:
        scene_type = "Urbano / Color Vibrante y Murales"
        recommended_preset = "electric_chroma_hd"
        alternative_preset = "kodachrome_64"
    else:
        scene_type = "Documental / Calle y Arquitectura"
        recommended_preset = "kodachrome_64"
        alternative_preset = "blancoynegro_platino_hd"

    # Diagnostic messages
    tips = []
    if mean_luma < 0.34 or p50 < 0.28:
        tips.append("Subexposición detectada: conviene levantar exposición (+EV) y abrir sombras.")
        exposure_status = "Subexpuesta (Oscura)"
    elif highlight_ratio > 0.08:
        tips.append("Altas luces intensas: se recomienda compresión soft-knee para proteger texturas.")
        exposure_status = "Altas Luces Fuertes"
    else:
        tips.append("Exposición equilibrada con buen margen tonal.")
        exposure_status = "Equilibrada"

    if dynamic_range < 0.45:
        tips.append("Rango dinámico plano: aplicar micro-contraste y curva S mejorará el volumen.")

    if sharpness_score < 60.0:
        tips.append("Textura suave: se recomienda activar Nitidez Estructural HD.")
    else:
        tips.append(f"Buena nitidez estructural (índice {sharpness_score:.0f}).")

    return {
        "width": w,
        "height": h,
        "is_square": w == h,
        "mean_luma": round(mean_luma, 3),
        "median_luma": round(p50, 3),
        "dynamic_range": round(dynamic_range, 3),
        "shadow_ratio": round(shadow_ratio, 3),
        "highlight_ratio": round(highlight_ratio, 3),
        "warmth": round(warmth, 3),
        "mean_saturation": round(mean_sat, 3),
        "sharpness_score": round(sharpness_score, 1),
        "exposure_status": exposure_status,
        "scene_type": scene_type,
        "recommended_preset": recommended_preset,
        "alternative_preset": alternative_preset,
        "tips": tips,
    }


def compute_auto_develop_params(img_float: np.ndarray) -> dict:
    """
    Calculates optimal non-destructive development parameters (EV, shadows,
    highlights, white balance, denoise, sharpen, and recommended preset)
    based on the image histogram and scene analysis.
    """
    metrics = analyze_image(img_float)
    mean_luma = metrics["mean_luma"]
    shadow_ratio = metrics["shadow_ratio"]
    highlight_ratio = metrics["highlight_ratio"]
    warmth = metrics["warmth"]

    # Target a natural luminous mean luminance around 0.44..0.48
    if mean_luma < 0.44:
        ev = float(np.clip((0.45 - mean_luma) * 1.45, 0.08, 0.65))
    elif mean_luma > 0.62:
        ev = float(np.clip((0.55 - mean_luma) * 0.90, -0.45, -0.05))
    else:
        ev = 0.08

    # Shadow lift proportional to dark pixel fraction
    shadows = float(np.clip(shadow_ratio * 0.85, 0.12, 0.58))

    # Highlight recovery if bright pixels are present
    highlights = float(np.clip(highlight_ratio * 1.8 + 0.10, 0.10, 0.55))

    # Subtle white balance neutralization if strongly cool or overly warm
    wb_temp = float(np.clip(-warmth * 0.25, -0.15, 0.18))
    if mean_luma < 0.35 and wb_temp < 0.04:
        wb_temp = 0.06  # slight golden warmth for shaded portraits

    denoise = 0.45 if mean_luma < 0.35 else 0.30
    sharpen = 0.45

    return {
        "ev": round(ev, 2),
        "shadows": round(shadows, 2),
        "highlights": round(highlights, 2),
        "wb_temp": round(wb_temp, 2),
        "wb_tint": 0.0,
        "denoise": round(denoise, 2),
        "sharpen": round(sharpen, 2),
        "recommended_preset": metrics["recommended_preset"],
        "analysis": metrics,
    }


def compute_smart_square_crop(img_float: np.ndarray) -> tuple[int, int, int, int]:
    """
    Computes an optimal 1:1 square crop box (x, y, side, side) in image pixel
    coordinates by maximizing structural gradient + chromatic saliency energy.
    """
    h, w, _ = img_float.shape
    side = min(h, w)
    if h == w:
        return (0, 0, side, side)

    # Compute saliency map at reduced resolution
    luma = 0.299 * img_float[..., 0] + 0.587 * img_float[..., 1] + 0.114 * img_float[..., 2]
    gx = cv2.Sobel(luma, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(luma, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.sqrt(gx * gx + gy * gy)
    sat = np.max(img_float, axis=-1) - np.min(img_float, axis=-1)
    saliency = grad * 0.70 + sat * 0.30

    if w > h:
        # Horizontal image: slide square horizontally
        col_energy = np.mean(saliency, axis=0)
        kernel = np.ones(side, dtype=np.float32) / float(side)
        scores = np.convolve(col_energy, kernel, mode="valid")
        # Slight center bias to avoid extreme edge crops
        centers = np.linspace(-1.0, 1.0, len(scores))
        bias = 1.0 - 0.15 * (centers ** 2)
        best_x = int(np.argmax(scores * bias))
        return (best_x, 0, side, side)
    else:
        # Vertical image: slide square vertically
        row_energy = np.mean(saliency, axis=1)
        kernel = np.ones(side, dtype=np.float32) / float(side)
        scores = np.convolve(row_energy, kernel, mode="valid")
        centers = np.linspace(-1.0, 1.0, len(scores))
        bias = 1.0 - 0.15 * (centers ** 2)
        best_y = int(np.argmax(scores * bias))
        return (0, best_y, side, side)


def strip_ai_watermarks_and_swirl(img_float: np.ndarray) -> np.ndarray:
    """
    Removes invisible pixel-level AI watermarks (e.g. c2pa.watermarked.unbound
    high-frequency diffusion swirl in flat sky/asphalt areas) using edge-guided
    bilateral filtering + sub-pixel Lanczos4 phase break + HD structural sharpening.
    """
    arr = np.clip(img_float, 0.0, 1.0).astype(np.float32)
    h, w, _ = arr.shape
    u8 = (arr * 255.0 + 0.5).astype(np.uint8)
    bgr = cv2.cvtColor(u8, cv2.COLOR_RGB2BGR)

    bilat_strong = cv2.bilateralFilter(bgr, d=9, sigmaColor=24, sigmaSpace=24)
    bilat_mid = cv2.bilateralFilter(bgr, d=5, sigmaColor=14, sigmaSpace=14)

    gray = cv2.cvtColor(u8, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.sqrt(gx * gx + gy * gy)

    struct_mask = np.clip((grad - 0.035) / 0.14, 0.0, 1.0)
    struct_mask = cv2.GaussianBlur(struct_mask, (0, 0), 1.3)[..., np.newaxis]

    clean_flat = cv2.cvtColor(bilat_strong, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    clean_mid = cv2.cvtColor(bilat_mid, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    blended = clean_flat * (1.0 - struct_mask) + (0.65 * arr + 0.35 * clean_mid) * struct_mask

    blended = denoise_ultra_clean(blended, chroma_strength=10.0, luma_strength=2.5)

    # Sub-pixel Lanczos4 resampling to break frequency-domain steganographic watermarks
    u8_clean = (np.clip(blended, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    up_w, up_h = max(2, int(w * 1.25)), max(2, int(h * 1.25))
    up = cv2.resize(u8_clean, (up_w, up_h), interpolation=cv2.INTER_LANCZOS4)
    back = cv2.resize(up, (w, h), interpolation=cv2.INTER_LANCZOS4)
    res = back.astype(np.float32) / 255.0

    return sharpen_hd_modern(res, strength=0.38)
