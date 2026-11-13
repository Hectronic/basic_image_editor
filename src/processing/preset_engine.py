"""
Basic Image Editor - Curated Photographic Preset Engine
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from collections import OrderedDict
import cv2
import numpy as np

from src.processing.raw_developer import (
    apply_s_curve_luminance,
    protect_gamut_and_highlights,
    sharpen_hd_modern,
)


PRESET_DEFINITIONS = OrderedDict(
    [
        (
            "none",
            {
                "id": "none",
                "name": "Original / Sin Preset",
                "badge": "RAW Base",
                "category": "Base",
                "description": "Imagen base sin gradación cromática adicional.",
                "best_for": ["Referencia", "Neutral"],
            },
        ),
        (
            "electric_chroma_hd",
            {
                "id": "electric_chroma_hd",
                "name": "Electric Chroma HD",
                "badge": "★ Favorito #1",
                "category": "Vibrante / Urbano",
                "description": (
                    "Separación cromática armónica: azules zafiro/índigo profundos "
                    "y luces cálidas doradas con protección anti-quemado en neones."
                ),
                "best_for": ["Escenas nocturnas", "Murales urbanos", "Cielos y neones", "Arquitectura"],
            },
        ),
        (
            "moderna_definida_hd",
            {
                "id": "moderna_definida_hd",
                "name": "Moderna Definida HD",
                "badge": "★ Nitidez HD",
                "category": "Definición / Naturaleza",
                "description": (
                    "Micro-contraste lineal cristalino, verdes y azules naturales "
                    "y enfoque selectivo en bordes sin grano artificial."
                ),
                "best_for": ["Naturaleza y fauna", "Arquitectura", "Día soleado", "Murales"],
            },
        ),
        (
            "editorial_viva_hd",
            {
                "id": "editorial_viva_hd",
                "name": "Editorial Viva / Retrato HD",
                "badge": "★ Retratos",
                "category": "Retrato / Piel",
                "description": (
                    "Luz dorada envolvente, tonos de piel orgánicos y suaves, "
                    "apertura de sombras en ojos y contraste limpio de revista."
                ),
                "best_for": ["Retratos", "Contraluz", "Escenas cotidianas", "Parques"],
            },
        ),
        (
            "kodachrome_64",
            {
                "id": "kodachrome_64",
                "name": "Kodachrome 64 Cine",
                "badge": "Documental",
                "category": "Analógico Limpio",
                "description": (
                    "Emulación clásica Kodachrome 64: rojos, ámbar y amarillos ricos, "
                    "sombras densas con carácter documental y cero grano."
                ),
                "best_for": ["Fotografía callejera", "Mercados", "Viajes", "Luz de tarde"],
            },
        ),
        (
            "blancoynegro_platino_hd",
            {
                "id": "blancoynegro_platino_hd",
                "name": "Blanco y Negro Platino HD",
                "badge": "Monocromo",
                "category": "Blanco y Negro",
                "description": (
                    "Conversión monocroma al platino-paladio con filtro cálido de luminancia, "
                    "negros profundos, reflejos plateados y cero grano."
                ),
                "best_for": ["Retratos expresivos", "Arquitectura", "Geometría y sombras"],
            },
        ),
        (
            "cinestill_800t",
            {
                "id": "cinestill_800t",
                "name": "CineStill 800T Halación",
                "badge": "Nocturno Cine",
                "category": "Cine / Neón",
                "description": (
                    "Estética cinematográfica de tungsteno con halación cálida rojiza "
                    "alrededor de las altas luces y sombras azul-verdosas."
                ),
                "best_for": ["Noche urbana", "Chinatown / Neones", "Tráfico nocturno"],
            },
        ),
        (
            "selectivo_platino_hd",
            {
                "id": "selectivo_platino_hd",
                "name": "Desaturado Selectivo Platino",
                "badge": "Color Selectivo",
                "category": "Artístico",
                "description": (
                    "Fondo monocromo platino que conserva intactos los tonos cálidos, "
                    "rojos, naranjas y dorados del sujeto principal."
                ),
                "best_for": ["Motos y vehículos", "Neones rojos", "Detalles urbanos"],
            },
        ),
    ]
)


def get_preset_names() -> list[str]:
    """Returns ordered list of available preset IDs."""
    return list(PRESET_DEFINITIONS.keys())


def get_preset_metadata(preset_id: str) -> dict:
    """Returns metadata dictionary for a preset ID."""
    return PRESET_DEFINITIONS.get(preset_id, PRESET_DEFINITIONS["none"])


def _grade_electric_chroma_hd(img: np.ndarray) -> np.ndarray:
    out = np.clip(img, 0.0, 1.0).copy()
    # Lift midtones slightly & apply crisp S-curve
    out = np.power(out, 0.93)
    out = apply_s_curve_luminance(out, contrast_strength=0.22)

    # Split-toning: deep sapphire/indigo shadows & warm golden highlights
    luma = (0.299 * out[..., 0] + 0.587 * out[..., 1] + 0.114 * out[..., 2])[..., np.newaxis]
    shadow_w = np.power(1.0 - luma, 1.8)
    high_w = np.power(luma, 1.6)

    out[..., 0] = out[..., 0] - 0.035 * shadow_w[..., 0] + 0.045 * high_w[..., 0]
    out[..., 1] = out[..., 1] - 0.010 * shadow_w[..., 0] + 0.020 * high_w[..., 0]
    out[..., 2] = out[..., 2] + 0.055 * shadow_w[..., 0] - 0.030 * high_w[..., 0]

    # Harmonic saturation boost in HSV with skin/red protection
    u8 = (np.clip(out, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    hsv = cv2.cvtColor(u8, cv2.COLOR_RGB2HSV).astype(np.float32)
    h, s, v = hsv[..., 0], hsv[..., 1] / 255.0, hsv[..., 2] / 255.0

    # Blues/cyans (hue ~ 90..135 in OpenCV 0..180 scale) get deeper richness
    blue_mask = np.exp(-0.5 * ((h - 112.0) / 22.0) ** 2)
    sat_boost = 1.24 + 0.12 * blue_mask
    s = np.clip(s * sat_boost, 0.0, 1.0)
    v = np.clip(v * (1.0 - 0.05 * blue_mask * s), 0.0, 1.0)

    hsv[..., 1] = s * 255.0
    hsv[..., 2] = v * 255.0
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32) / 255.0

    out = protect_gamut_and_highlights(out, red_tame=0.18, highlight_rolloff=0.16)
    return sharpen_hd_modern(out, strength=0.35)


def _grade_moderna_definida_hd(img: np.ndarray) -> np.ndarray:
    out = np.clip(img, 0.0, 1.0).copy()
    out = np.power(out, 0.95)
    out = apply_s_curve_luminance(out, contrast_strength=0.18)

    # Local micro-contrast (clarity) on luminance
    luma = 0.299 * out[..., 0] + 0.587 * out[..., 1] + 0.114 * out[..., 2]
    local_mean = cv2.GaussianBlur(luma, (0, 0), 4.0)
    clarity = (luma - local_mean) * 0.22
    out = np.clip(out + clarity[..., np.newaxis], 0.0, 1.0)

    # Natural vibrance boost (boosts muted colors more than already-saturated ones)
    mean_rgb = np.mean(out, axis=-1, keepdims=True)
    sat_est = np.max(out, axis=-1, keepdims=True) - np.min(out, axis=-1, keepdims=True)
    vibrance_weight = 1.0 + 0.22 * (1.0 - sat_est)
    out = mean_rgb + (out - mean_rgb) * vibrance_weight

    out = protect_gamut_and_highlights(out, red_tame=0.14, highlight_rolloff=0.14)
    return sharpen_hd_modern(out, strength=0.44)


def _grade_editorial_viva_hd(img: np.ndarray) -> np.ndarray:
    out = np.clip(img, 0.0, 1.0).copy()
    # Gentle shadow & midtone lift for flattering skin tones
    out = np.power(out, 0.91)
    luma = (0.299 * out[..., 0] + 0.587 * out[..., 1] + 0.114 * out[..., 2])[..., np.newaxis]
    shadow_lift = 0.14 * np.power(1.0 - luma, 2.0) * (1.0 - out)
    out = np.clip(out + shadow_lift, 0.0, 1.0)

    # Warm golden editorial balance
    out[..., 0] *= 1.035
    out[..., 1] *= 1.010
    out[..., 2] *= 0.965

    out = apply_s_curve_luminance(np.clip(out, 0.0, 1.0), contrast_strength=0.14)

    # Balanced vibrance
    mean_rgb = np.mean(out, axis=-1, keepdims=True)
    sat_est = np.max(out, axis=-1, keepdims=True) - np.min(out, axis=-1, keepdims=True)
    out = mean_rgb + (out - mean_rgb) * (1.0 + 0.18 * (1.0 - sat_est))

    out = protect_gamut_and_highlights(out, red_tame=0.18, highlight_rolloff=0.16)
    return sharpen_hd_modern(out, strength=0.30)


def _grade_kodachrome_64(img: np.ndarray) -> np.ndarray:
    out = np.clip(img, 0.0, 1.0).copy()
    out = np.power(out, 0.94)
    out = apply_s_curve_luminance(out, contrast_strength=0.24)

    # Characteristic Kodachrome color matrix: warm amber/reds, deep teal-blue skies
    r, g, b = out[..., 0], out[..., 1], out[..., 2]
    new_r = 1.06 * r + 0.02 * g - 0.03 * b
    new_g = 0.01 * r + 1.01 * g - 0.01 * b
    new_b = -0.02 * r + 0.03 * g + 0.95 * b
    out = np.stack([new_r, new_g, new_b], axis=-1)

    out = protect_gamut_and_highlights(out, red_tame=0.16, highlight_rolloff=0.15)
    return sharpen_hd_modern(out, strength=0.32)


def _grade_blancoynegro_platino_hd(img: np.ndarray) -> np.ndarray:
    out = np.clip(img, 0.0, 1.0).copy()
    # Warm panchromatic filter weights (flattering on skin and dramatic on skies)
    luma = 0.36 * out[..., 0] + 0.53 * out[..., 1] + 0.11 * out[..., 2]
    luma = np.power(np.clip(luma, 0.0, 1.0), 0.93)
    luma = apply_s_curve_luminance(luma, contrast_strength=0.25)

    # Local micro-contrast
    local_mean = cv2.GaussianBlur(luma, (0, 0), 4.5)
    luma = np.clip(luma + (luma - local_mean) * 0.24, 0.0, 1.0)

    # Subtle platinum-palladium toning (cool-warm metallic neutrality)
    r = np.clip(luma * 1.008, 0.0, 1.0)
    g = np.clip(luma * 1.002, 0.0, 1.0)
    b = np.clip(luma * 0.990 + 0.008 * (1.0 - luma), 0.0, 1.0)
    bw = np.stack([r, g, b], axis=-1)
    return sharpen_hd_modern(bw, strength=0.40)


def _grade_cinestill_800t(img: np.ndarray) -> np.ndarray:
    out = np.clip(img, 0.0, 1.0).copy()
    out = np.power(out, 0.94)

    # Tungsten cool-teal shadows + warm highlights
    luma = 0.299 * out[..., 0] + 0.587 * out[..., 1] + 0.114 * out[..., 2]
    shadow_w = np.power(1.0 - luma, 1.5)
    out[..., 0] -= 0.04 * shadow_w
    out[..., 1] += 0.015 * shadow_w
    out[..., 2] += 0.055 * shadow_w

    # Warm red-orange halation glow around bright light sources
    bright_mask = np.clip((luma - 0.72) / 0.28, 0.0, 1.0)
    glow = cv2.GaussianBlur(bright_mask, (0, 0), 6.0)
    out[..., 0] += glow * 0.18
    out[..., 1] += glow * 0.05
    out[..., 2] -= glow * 0.02

    out = apply_s_curve_luminance(np.clip(out, 0.0, 1.0), contrast_strength=0.20)
    out = protect_gamut_and_highlights(out, red_tame=0.14, highlight_rolloff=0.16)
    return sharpen_hd_modern(out, strength=0.30)


def _grade_selectivo_platino_hd(img: np.ndarray) -> np.ndarray:
    out = np.clip(img, 0.0, 1.0).copy()
    bw = _grade_blancoynegro_platino_hd(out)
    vibrant = _grade_electric_chroma_hd(out)

    # Detect warm/red/orange/gold hues + strong chromaticity
    r, g, b = out[..., 0], out[..., 1], out[..., 2]
    warm_dominance = np.clip((r - 0.55 * g - 0.45 * b) * 3.2, 0.0, 1.0)
    mask = cv2.GaussianBlur(warm_dominance, (0, 0), 2.0)[..., np.newaxis]
    mask = np.clip(mask * 1.35, 0.0, 1.0)
    return np.clip(bw * (1.0 - mask) + vibrant * mask, 0.0, 1.0)


_PRESET_FUNCTIONS = {
    "electric_chroma_hd": _grade_electric_chroma_hd,
    "moderna_definida_hd": _grade_moderna_definida_hd,
    "editorial_viva_hd": _grade_editorial_viva_hd,
    "kodachrome_64": _grade_kodachrome_64,
    "blancoynegro_platino_hd": _grade_blancoynegro_platino_hd,
    "cinestill_800t": _grade_cinestill_800t,
    "selectivo_platino_hd": _grade_selectivo_platino_hd,
}


def apply_preset(
    img_float: np.ndarray,
    preset_id: str,
    intensity: float = 1.0,
) -> np.ndarray:
    """
    Applies the selected photographic preset to an RGB float32 array in [0, 1],
    blended linearly by `intensity` (0.0 to 1.0).
    """
    base = np.clip(img_float, 0.0, 1.0).astype(np.float32)
    intensity = float(np.clip(intensity, 0.0, 1.0))
    if preset_id == "none" or intensity <= 1e-4 or preset_id not in _PRESET_FUNCTIONS:
        return base.copy()

    graded = _PRESET_FUNCTIONS[preset_id](base)
    if intensity >= 0.999:
        return graded
    return np.clip(base * (1.0 - intensity) + graded * intensity, 0.0, 1.0)


def generate_preset_thumbnail(
    img_float: np.ndarray,
    preset_id: str,
    size: tuple[int, int] = (112, 76),
) -> np.ndarray:
    """
    Downsamples `img_float` and renders a fast preview thumbnail (uint8 RGB)
    with `preset_id` applied.
    """
    target_w, target_h = size
    u8 = (np.clip(img_float, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    small_u8 = cv2.resize(u8, (target_w, target_h), interpolation=cv2.INTER_AREA)
    small_f = small_u8.astype(np.float32) / 255.0
    graded_f = apply_preset(small_f, preset_id, intensity=1.0)
    return (np.clip(graded_f, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
