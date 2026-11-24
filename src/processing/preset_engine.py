"""
Basic Image Editor - Curated Photographic Preset Engine (SIMD / LUT Accelerated)
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import re
from collections import OrderedDict
import cv2
import numpy as np

from src.processing.raw_developer import (
    apply_lut_curve_float,
    build_gamma_s_curve_lut,
    develop_base_image,
    protect_gamut_and_highlights,
    sharpen_hd_modern,
)


CUSTOM_PRESETS_PATH = os.path.expanduser("~/.image_editor_custom_presets.json")
_CUSTOM_RECIPES: dict[str, dict] = {}


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

# Precomputed 256-entry RGB split-toning & curve LUTs for ultra-fast preset grading
_X256 = np.linspace(0.0, 1.0, 256, dtype=np.float32)

# Precompute Hue (0..255) blue boost LUT for Electric Chroma
_HUE_IDX = np.arange(256, dtype=np.float32)
_BLUE_HUE_WEIGHT_LUT = np.exp(-0.5 * ((_HUE_IDX - 112.0) / 22.0) ** 2).astype(np.float32)


def _apply_3channel_lut_float(
    img_float: np.ndarray,
    lut_r: np.ndarray,
    lut_g: np.ndarray,
    lut_b: np.ndarray,
) -> np.ndarray:
    """Applies independent R, G, B 256-entry float32 [0, 1] LUTs in a single OpenCV pass."""
    u8 = np.clip(img_float * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
    lut_rgb = np.stack(
        [
            np.clip(lut_r * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8),
            np.clip(lut_g * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8),
            np.clip(lut_b * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8),
        ],
        axis=-1,
    ).reshape(256, 1, 3)
    out_u8 = cv2.LUT(u8, lut_rgb)
    return out_u8.astype(np.float32) * (1.0 / 255.0)


def get_preset_names() -> list[str]:
    """Returns ordered list of available preset IDs."""
    return list(PRESET_DEFINITIONS.keys())


def get_preset_metadata(preset_id: str) -> dict:
    """Returns metadata dictionary for a preset ID."""
    return PRESET_DEFINITIONS.get(preset_id, PRESET_DEFINITIONS["none"])


def _grade_electric_chroma_hd(img: np.ndarray) -> np.ndarray:
    # 1. Combined gamma + S-curve + split-toning + soft-knee in a single 3-channel LUT!
    base_curve = build_gamma_s_curve_lut(gamma=0.93, s_contrast=0.22, highlight_rolloff=0.16)
    sh_w = (1.0 - base_curve) ** 1.8
    hi_w = base_curve ** 1.6

    lut_r = np.clip(base_curve - 0.035 * sh_w + 0.045 * hi_w, 0.0, 1.0)
    lut_g = np.clip(base_curve - 0.010 * sh_w + 0.020 * hi_w, 0.0, 1.0)
    lut_b = np.clip(base_curve + 0.055 * sh_w - 0.030 * hi_w, 0.0, 1.0)
    out = _apply_3channel_lut_float(img, lut_r, lut_g, lut_b)

    # 2. Fast HSV saturation & sapphire blue boost using 1D Hue LUT
    u8 = np.clip(out * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
    hsv = cv2.cvtColor(u8, cv2.COLOR_RGB2HSV)
    h_u8, s_u8, v_u8 = cv2.split(hsv)

    blue_w = cv2.LUT(h_u8, _BLUE_HUE_WEIGHT_LUT)
    s_f = s_u8.astype(np.float32) * (1.24 + 0.12 * blue_w)
    s_new = np.clip(s_f, 0.0, 255.0).astype(np.uint8)
    v_f = v_u8.astype(np.float32) * (1.0 - 0.05 * blue_w * (s_new.astype(np.float32) * (1.0 / 255.0)))
    v_new = np.clip(v_f, 0.0, 255.0).astype(np.uint8)

    out_u8 = cv2.cvtColor(cv2.merge([h_u8, s_new, v_new]), cv2.COLOR_HSV2RGB)
    out = out_u8.astype(np.float32) * (1.0 / 255.0)

    out = protect_gamut_and_highlights(out, red_tame=0.18, highlight_rolloff=0.0)
    return sharpen_hd_modern(out, strength=0.35)


def _saturation_matrix(sat: float) -> np.ndarray:
    """Builds a 3x3 luminance-preserving saturation matrix for fast cv2.transform."""
    w_r, w_g, w_b = 0.299, 0.587, 0.114
    s = float(sat)
    return np.array(
        [
            [(1.0 - s) * w_r + s, (1.0 - s) * w_g, (1.0 - s) * w_b],
            [(1.0 - s) * w_r, (1.0 - s) * w_g + s, (1.0 - s) * w_b],
            [(1.0 - s) * w_r, (1.0 - s) * w_g, (1.0 - s) * w_b + s],
        ],
        dtype=np.float32,
    )


_MODERNA_SAT_MAT = _saturation_matrix(1.16)
_EDITORIAL_SAT_MAT = _saturation_matrix(1.12)


def _grade_moderna_definida_hd(img: np.ndarray) -> np.ndarray:
    lut = build_gamma_s_curve_lut(gamma=0.95, s_contrast=0.22, highlight_rolloff=0.14)
    out = apply_lut_curve_float(img, lut)
    out = np.clip(cv2.transform(out, _MODERNA_SAT_MAT), 0.0, 1.0)
    out = protect_gamut_and_highlights(out, red_tame=0.14, highlight_rolloff=0.0)
    return sharpen_hd_modern(out, strength=0.44)


def _grade_editorial_viva_hd(img: np.ndarray) -> np.ndarray:
    # Combine gamma 0.91 + shadow lift + warm golden balance + S-curve in 3-channel LUT!
    x = np.power(_X256, 0.91)
    x = np.clip(x + 0.14 * ((1.0 - x) ** 2) * (1.0 - x), 0.0, 1.0)

    def _s_and_knee(c):
        c = np.clip(c, 0.0, 1.0)
        c = c - 0.14 * 0.22 * np.sin(2.0 * np.pi * c)
        knee = 0.78
        above = np.maximum(0.0, c - knee)
        c = np.where(c > knee, knee + above / (1.0 + 0.16 * 3.5 * (above / 0.22)), c)
        return np.clip(c, 0.0, 1.0).astype(np.float32)

    lut_r = _s_and_knee(x * 1.035)
    lut_g = _s_and_knee(x * 1.010)
    lut_b = _s_and_knee(x * 0.965)
    out = _apply_3channel_lut_float(img, lut_r, lut_g, lut_b)
    out = np.clip(cv2.transform(out, _EDITORIAL_SAT_MAT), 0.0, 1.0)
    out = protect_gamut_and_highlights(out, red_tame=0.18, highlight_rolloff=0.0)
    return sharpen_hd_modern(out, strength=0.30)


_KODACHROME_MATRIX = np.array(
    [
        [1.06, 0.02, -0.03],
        [0.01, 1.01, -0.01],
        [-0.02, 0.03, 0.95],
    ],
    dtype=np.float32,
)


def _grade_kodachrome_64(img: np.ndarray) -> np.ndarray:
    lut = build_gamma_s_curve_lut(gamma=0.94, s_contrast=0.24, highlight_rolloff=0.15)
    out = apply_lut_curve_float(img, lut)
    out = cv2.transform(out, _KODACHROME_MATRIX)
    out = np.clip(out, 0.0, 1.0)
    out = protect_gamut_and_highlights(out, red_tame=0.16, highlight_rolloff=0.0)
    return sharpen_hd_modern(out, strength=0.32)


def _grade_blancoynegro_platino_hd(img: np.ndarray) -> np.ndarray:
    luma = 0.36 * img[..., 0] + 0.53 * img[..., 1] + 0.11 * img[..., 2]
    lut = build_gamma_s_curve_lut(gamma=0.93, s_contrast=0.25)
    luma_u8 = np.clip(luma * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
    lut_u8 = np.clip(lut * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
    luma = cv2.LUT(luma_u8, lut_u8).astype(np.float32) * (1.0 / 255.0)

    local_mean = cv2.GaussianBlur(luma, (0, 0), 3.5)
    luma = np.clip(luma + (luma - local_mean) * 0.24, 0.0, 1.0)

    r = np.clip(luma * 1.008, 0.0, 1.0)
    g = np.clip(luma * 1.002, 0.0, 1.0)
    b = np.clip(luma * 0.990 + 0.008 * (1.0 - luma), 0.0, 1.0)
    bw = np.stack([r, g, b], axis=-1)
    return sharpen_hd_modern(bw, strength=0.40)


def _grade_cinestill_800t(img: np.ndarray) -> np.ndarray:
    base = build_gamma_s_curve_lut(gamma=0.94, s_contrast=0.20, highlight_rolloff=0.16)
    sh_w = (1.0 - base) ** 1.5
    lut_r = np.clip(base - 0.040 * sh_w, 0.0, 1.0)
    lut_g = np.clip(base + 0.015 * sh_w, 0.0, 1.0)
    lut_b = np.clip(base + 0.055 * sh_w, 0.0, 1.0)
    out = _apply_3channel_lut_float(img, lut_r, lut_g, lut_b)

    # Fast halation glow computed at 1/4 resolution then upsampled!
    h, w, _ = out.shape
    luma = 0.299 * out[..., 0] + 0.587 * out[..., 1] + 0.114 * out[..., 2]
    bright_mask = np.clip((luma - 0.72) * (1.0 / 0.28), 0.0, 1.0)
    if max(h, w) > 256:
        gw, gh = max(1, w // 4), max(1, h // 4)
        bm_small = cv2.resize(bright_mask, (gw, gh), interpolation=cv2.INTER_AREA)
        glow_small = cv2.GaussianBlur(bm_small, (0, 0), 2.0)
        glow = cv2.resize(glow_small, (w, h), interpolation=cv2.INTER_LINEAR)
    else:
        glow = cv2.GaussianBlur(bright_mask, (0, 0), 4.0)

    out[..., 0] += glow * 0.18
    out[..., 1] += glow * 0.05
    out[..., 2] -= glow * 0.02

    out = protect_gamut_and_highlights(np.clip(out, 0.0, 1.0), red_tame=0.14, highlight_rolloff=0.0)
    return sharpen_hd_modern(out, strength=0.30)


def _grade_selectivo_platino_hd(img: np.ndarray) -> np.ndarray:
    bw = _grade_blancoynegro_platino_hd(img)
    vibrant = _grade_electric_chroma_hd(img)

    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    warm_dominance = np.clip((r - 0.55 * g - 0.45 * b) * 3.2, 0.0, 1.0)
    mask = cv2.GaussianBlur(warm_dominance, (5, 5), 1.5)[..., np.newaxis]
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


def _build_custom_preset_fn(recipe: dict):
    """Builds a fast grading function from a custom preset recipe dict."""
    base_preset = recipe.get("base_preset", "none")
    base_fn = _PRESET_FUNCTIONS.get(base_preset)
    ev = float(recipe.get("ev", 0.0))
    shadows = float(recipe.get("shadows", 0.0))
    highlights = float(recipe.get("highlights", 0.0))
    wb_temp = float(recipe.get("wb_temp", 0.0))
    wb_tint = float(recipe.get("wb_tint", 0.0))
    denoise = float(recipe.get("denoise", 0.0))
    sharpen = float(recipe.get("sharpen", 0.0))
    brightness = float(recipe.get("brightness", 1.0))
    contrast = float(recipe.get("contrast", 1.0))
    saturation = float(recipe.get("saturation", 1.0))

    has_dev = any(
        abs(x) > 1e-4 for x in (ev, shadows, highlights, wb_temp, wb_tint, denoise, sharpen)
    )
    sat_mat = _saturation_matrix(saturation) if abs(saturation - 1.0) > 1e-3 else None

    def _grade_custom(img: np.ndarray) -> np.ndarray:
        out = base_fn(img) if base_fn is not None else img.copy()
        if has_dev:
            out = develop_base_image(
                out,
                ev=ev,
                shadows=shadows,
                highlights=highlights,
                wb_temp=wb_temp,
                wb_tint=wb_tint,
                denoise=denoise,
                sharpen=sharpen,
            )
        if abs(brightness - 1.0) > 1e-3 or abs(contrast - 1.0) > 1e-3:
            out = np.clip((out - 0.5) * contrast + 0.5 + (brightness - 1.0) * 0.5, 0.0, 1.0)
        if sat_mat is not None:
            out = np.clip(cv2.transform(out.astype(np.float32), sat_mat), 0.0, 1.0)
        return out.astype(np.float32)

    return _grade_custom


def register_custom_preset(
    name: str,
    recipe: dict,
    description: str = "Preset personalizado creado con el asistente de chat.",
    preset_id: str | None = None,
    persist: bool = True,
) -> str:
    """
    Registers or updates a custom preset in `PRESET_DEFINITIONS` and `_PRESET_FUNCTIONS`.
    Returns the `preset_id`.
    """
    if not preset_id:
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "custom"
        preset_id = f"custom_{slug}"

    clean_recipe = {
        "name": name,
        "description": description,
        "base_preset": recipe.get("base_preset", "none"),
        "ev": float(recipe.get("ev", 0.0)),
        "shadows": float(recipe.get("shadows", 0.0)),
        "highlights": float(recipe.get("highlights", 0.0)),
        "wb_temp": float(recipe.get("wb_temp", 0.0)),
        "wb_tint": float(recipe.get("wb_tint", 0.0)),
        "denoise": float(recipe.get("denoise", 0.0)),
        "sharpen": float(recipe.get("sharpen", 0.0)),
        "brightness": float(recipe.get("brightness", 1.0)),
        "contrast": float(recipe.get("contrast", 1.0)),
        "saturation": float(recipe.get("saturation", 1.0)),
    }

    PRESET_DEFINITIONS[preset_id] = {
        "id": preset_id,
        "name": name,
        "badge": "★ Custom IA",
        "category": "Personalizado",
        "description": description,
        "best_for": ["Edición por Chat", "Personalizado"],
        "is_custom": True,
        "recipe": clean_recipe,
    }
    _PRESET_FUNCTIONS[preset_id] = _build_custom_preset_fn(clean_recipe)
    _CUSTOM_RECIPES[preset_id] = clean_recipe

    if persist:
        save_custom_presets()
    return preset_id


def save_custom_presets(filepath: str = CUSTOM_PRESETS_PATH) -> bool:
    """Saves all custom preset recipes to disk as JSON."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(_CUSTOM_RECIPES, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def load_custom_presets(filepath: str = CUSTOM_PRESETS_PATH) -> int:
    """Loads custom preset recipes from disk and registers them."""
    if not os.path.exists(filepath):
        return 0
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        count = 0
        if isinstance(data, dict):
            for pid, recipe in data.items():
                if isinstance(recipe, dict):
                    register_custom_preset(
                        name=recipe.get("name", pid),
                        recipe=recipe,
                        description=recipe.get("description", "Preset personalizado."),
                        preset_id=pid,
                        persist=False,
                    )
                    count += 1
        return count
    except Exception:
        return 0


# Load any saved custom presets on module import
load_custom_presets()


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
    return cv2.addWeighted(base, 1.0 - intensity, graded, intensity, 0.0)


def generate_preset_thumbnail(
    img_float: np.ndarray,
    preset_id: str,
    size: tuple[int, int] = (112, 76),
) -> np.ndarray:
    """
    Downsamples `img_float` (if not already at target `size`) and renders a fast
    preview thumbnail (uint8 RGB) with `preset_id` applied.
    """
    target_w, target_h = size
    h, w, _ = img_float.shape
    if w == target_w and h == target_h:
        small_f = img_float
    else:
        small_f = cv2.resize(img_float, (target_w, target_h), interpolation=cv2.INTER_AREA)
    graded_f = apply_preset(small_f, preset_id, intensity=1.0)
    return np.clip(graded_f * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
