"""
Basic Image Editor - 100% Embedded In-Process Qwen GGUF & NLU Photographic Chat Agent
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import logging
import os
import re
import threading
import urllib.request
from typing import Callable
import numpy as np

try:
    from llama_cpp import Llama
except ImportError:  # pragma: no cover
    Llama = None

from src.processing.preset_engine import PRESET_DEFINITIONS, get_preset_metadata

logger = logging.getLogger(__name__)

# Directory containing the self-contained embedded GGUF model weights (gitignored; auto-downloaded on demand)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELS_DIR = os.path.join(REPO_ROOT, "models")

EMBEDDED_QWEN_MODELS = {
    "Qwen 2.5 0.5B (Integrado Rápido)": "qwen2.5-0.5b-instruct.gguf",
    "Qwen 2.5 1.5B (Integrado Preciso)": "qwen2.5-1.5b-instruct.gguf",
}

MODEL_DOWNLOAD_URLS = {
    "qwen2.5-0.5b-instruct.gguf": (
        "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/"
        "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    ),
    "qwen2.5-1.5b-instruct.gguf": (
        "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
        "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    ),
}

# Aliases so callers passing short names resolve to the embedded GGUF files
MODEL_FILENAME_ALIASES = {
    "qwen2.5:0.5b": "qwen2.5-0.5b-instruct.gguf",
    "qwen2.5-0.5b": "qwen2.5-0.5b-instruct.gguf",
    "qwen2.5-0.5b-instruct.gguf": "qwen2.5-0.5b-instruct.gguf",
    "Qwen 2.5 0.5B (Integrado Rápido)": "qwen2.5-0.5b-instruct.gguf",
    "qwen2.5:1.5b": "qwen2.5-1.5b-instruct.gguf",
    "qwen2.5-1.5b": "qwen2.5-1.5b-instruct.gguf",
    "qwen2.5-1.5b-instruct.gguf": "qwen2.5-1.5b-instruct.gguf",
    "Qwen 2.5 1.5B (Integrado Preciso)": "qwen2.5-1.5b-instruct.gguf",
}

_LOADED_LLAMA_INSTANCES: dict[str, object] = {}
_LLAMA_LOCK = threading.Lock()
_DOWNLOAD_LOCK = threading.Lock()

PRESET_KEYWORDS = {
    "electric_chroma_hd": [
        "electric chroma",
        "electric",
        "chroma",
        "vibrante",
        "urbano",
        "zafiro",
        "favorito",
    ],
    "moderna_definida_hd": [
        "moderna definida",
        "moderna",
        "definida",
        "naturaleza",
        "cristalino",
    ],
    "editorial_viva_hd": [
        "editorial viva",
        "editorial",
        "retrato",
        "piel",
        "revista",
    ],
    "kodachrome_64": [
        "kodachrome",
        "kodak",
        "documental",
        "analogico",
        "analógico",
        "vintage",
        "retro",
    ],
    "blancoynegro_platino_hd": [
        "blanco y negro",
        "byn",
        "b&n",
        "monocromo",
        "platino",
        "black and white",
    ],
    "cinestill_800t": [
        "cinestill",
        "800t",
        "halacion",
        "halación",
        "nocturno",
        "tungsteno",
        "neon",
        "neón",
        "cyberpunk",
        "cine",
    ],
    "selectivo_platino_hd": [
        "selectivo",
        "desaturado selectivo",
        "color selectivo",
    ],
    "none": [
        "sin preset",
        "quitar preset",
        "original",
        "ninguno",
    ],
}


def resolve_model_path(model_name: str, models_dir: str = MODELS_DIR) -> str:
    """Resolves a UI model label or alias to an absolute `.gguf` file path inside `models_dir`."""
    filename = MODEL_FILENAME_ALIASES.get(model_name, model_name)
    if os.path.isabs(filename) and os.path.exists(filename):
        return filename
    return os.path.join(models_dir, filename)


def list_embedded_qwen_models(models_dir: str = MODELS_DIR) -> list[str]:
    """
    Returns the list of supported embedded Qwen models (auto-downloaded on first use if absent).
    """
    return list(EMBEDDED_QWEN_MODELS.keys())


def ensure_model_downloaded(
    model_name: str,
    models_dir: str = MODELS_DIR,
    progress_callback: Callable[[int, int], None] | None = None,
) -> str:
    """
    Ensures the requested GGUF model exists in `models_dir`.
    If missing and a known official Hugging Face GGUF URL exists, downloads it atomically
    via a `.part` temporary file while reporting `(downloaded_bytes, total_bytes)`.
    """
    model_path = resolve_model_path(model_name, models_dir=models_dir)
    if os.path.exists(model_path) and os.path.getsize(model_path) > 0:
        return model_path

    filename = os.path.basename(model_path)
    url = MODEL_DOWNLOAD_URLS.get(filename)
    if not url:
        raise FileNotFoundError(f"Embedded GGUF model not found and no download URL registered: {model_path}")

    with _DOWNLOAD_LOCK:
        if os.path.exists(model_path) and os.path.getsize(model_path) > 0:
            return model_path

        os.makedirs(models_dir, exist_ok=True)
        part_path = f"{model_path}.part"
        logger.info(f"Downloading Qwen GGUF model '{filename}' from {url} ...")

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "BasicImageEditor/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp, open(part_path, "wb") as out_f:
                total_header = resp.headers.get("Content-Length")
                total_bytes = int(total_header) if total_header and total_header.isdigit() else 0
                downloaded = 0
                chunk_size = 1024 * 1024  # 1 MB chunks
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback is not None:
                        progress_callback(downloaded, total_bytes)
            os.replace(part_path, model_path)
            logger.info(f"Successfully downloaded model to {model_path} ({downloaded} bytes)")
            return model_path
        except Exception:
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except OSError:
                    pass
            raise


def get_embedded_llama(
    model_name: str,
    models_dir: str = MODELS_DIR,
    auto_download: bool = True,
    progress_callback: Callable[[int, int], None] | None = None,
):
    """
    Loads and caches the in-process `llama_cpp.Llama` model instance from `models/*.gguf`.
    Automatically downloads the GGUF file on first use when `auto_download=True`.
    """
    if Llama is None:
        raise RuntimeError("llama-cpp-python is not installed.")
    if auto_download:
        model_path = ensure_model_downloaded(
            model_name,
            models_dir=models_dir,
            progress_callback=progress_callback,
        )
    else:
        model_path = resolve_model_path(model_name, models_dir=models_dir)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Embedded GGUF model not found: {model_path}")

    with _LLAMA_LOCK:
        instance = _LOADED_LLAMA_INSTANCES.get(model_path)
        if instance is None:
            threads = max(2, min(8, (os.cpu_count() or 4) // 2))
            instance = Llama(
                model_path=model_path,
                n_ctx=2048,
                n_threads=threads,
                verbose=False,
            )
            _LOADED_LLAMA_INSTANCES[model_path] = instance
        return instance


def build_system_prompt(state: dict) -> str:
    """Builds a compact, deterministic system prompt for embedded Qwen 0.5B / 1.5B."""
    presets_summary = "\n".join(
        f"- `{pid}`: {meta['name']} ({meta['category']}) — {meta['description']}"
        for pid, meta in PRESET_DEFINITIONS.items()
    )
    current_json = json.dumps(
        {
            "active_preset": state.get("active_preset", "none"),
            "preset_intensity": round(float(state.get("preset_intensity", 1.0)), 2),
            "ev": round(float(state.get("ev", 0.0)), 2),
            "shadows": round(float(state.get("shadows", 0.0)), 2),
            "highlights": round(float(state.get("highlights", 0.0)), 2),
            "wb_temp": round(float(state.get("wb_temp", 0.0)), 2),
            "denoise": round(float(state.get("denoise", 0.0)), 2),
            "sharpen": round(float(state.get("sharpen", 0.0)), 2),
            "brightness": round(float(state.get("brightness", 1.0)), 2),
            "contrast": round(float(state.get("contrast", 1.0)), 2),
            "saturation": round(float(state.get("saturation", 1.0)), 2),
            "scene_type": state.get("scene_type", "Desconocida"),
            "recommended_preset": state.get("recommended_preset", "electric_chroma_hd"),
        },
        ensure_ascii=False,
    )

    return (
        "Eres el Asistente Fotográfico IA integrado en Basic Image Editor (basado en Qwen).\n"
        "Tu tarea es conversar con el usuario en español y traducir sus peticiones a comandos de revelado y presets.\n\n"
        "PRESETS DISPONIBLES:\n"
        f"{presets_summary}\n\n"
        f"ESTADO ACTUAL DE LA FOTO:\n{current_json}\n\n"
        "RANGOS DE PARÁMETROS:\n"
        "- preset: ID de uno de los presets disponibles (ej. 'electric_chroma_hd', 'cinestill_800t', 'none') o null si no cambia.\n"
        "- preset_intensity: float de 0.0 a 1.0 (ej. 0.8 para 80%).\n"
        "- ev (Exposición): float de -1.5 a 1.5 (0.0 es neutro).\n"
        "- shadows (Sombras): float de -1.0 a 1.0 (>0 abre/aclara sombras, <0 oscurece sombras).\n"
        "- highlights (Altas luces): float de -1.0 a 1.0 (>0 recupera/protege luces altas).\n"
        "- wb_temp (Temperatura cálido/frío): float de -1.0 (frío/azul) a 1.0 (cálido/dorado).\n"
        "- denoise (Reducción ruido sin grano): float de 0.0 a 1.0.\n"
        "- sharpen (Nitidez HD): float de 0.0 a 1.0.\n"
        "- brightness (Brillo): float de 0.5 a 1.5 (1.0 es neutro).\n"
        "- contrast (Contraste): float de 0.5 a 1.5 (1.0 es neutro).\n"
        "- saturation (Saturación): float de 0.0 a 2.0 (1.0 es neutro).\n"
        "- save_preset_as: string con el nombre si el usuario pide guardar/crear un nuevo preset con los ajustes actuales, o null.\n"
        "- action: una de ['update', 'auto_develop', 'smart_crop_1x1', 'clean_ai', 'reset', 'undo'] (por defecto 'update').\n\n"
        "RESPONDE ÚNICAMENTE CON UN OBJETO JSON VÁLIDO CON ESTA ESTRUCTURA EXACTA:\n"
        "{\n"
        '  "reply": "Explicación breve y amable en español de los cambios aplicados",\n'
        '  "action": "update",\n'
        '  "preset": null,\n'
        '  "preset_intensity": null,\n'
        '  "adjustments": {\n'
        '    "ev": null, "shadows": null, "highlights": null, "wb_temp": null,\n'
        '    "denoise": null, "sharpen": null, "brightness": null, "contrast": null, "saturation": null\n'
        "  },\n"
        '  "save_preset_as": null\n'
        "}"
    )


def _extract_json_dict(raw_text: str) -> dict | None:
    """Extracts a JSON object from LLM text (handling markdown code fences or <think> tags)."""
    if not raw_text:
        return None
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return None


def parse_natural_language_fallback(user_message: str, state: dict) -> dict:
    """
    Fast, deterministic NLU parser for Spanish/English photographic instructions.
    Used both to enrich/validate Qwen's response and as an instant fallback.
    """
    text = user_message.lower().strip()
    result = {
        "reply": "",
        "action": "update",
        "preset": None,
        "preset_intensity": None,
        "adjustments": {},
        "save_preset_as": None,
    }
    applied_notes = []

    # 1. Special global actions
    if any(re.search(rf"\b{re.escape(k)}\b", text) for k in ["deshacer", "undo", "paso atrás", "volver atras", "volver atrás"]):
        result["action"] = "undo"
        result["reply"] = "He deshecho el último cambio."
        return result

    if any(re.search(rf"\b{re.escape(k)}\b", text) for k in ["reset", "reinicia", "restablece", "valores originales", "de cero"]):
        result["action"] = "reset"
        result["reply"] = "He restablecido todos los ajustes y el preset a la imagen original."
        return result

    if any(re.search(rf"\b{re.escape(k)}\b", text) for k in ["auto revela", "auto-revela", "autorevela", "revelado automatico", "revelado automático", "optimiza la foto", "mejora automatica"]):
        result["action"] = "auto_develop"
        result["reply"] = "He ejecutado el Auto-Revelado Inteligente ajustando exposición, sombras, nitidez y el preset óptimo."
        return result

    if any(re.search(rf"\b{re.escape(k)}\b", text) for k in ["1:1", "cuadrado", "instagram", "recorta", "encuadre inteligente"]):
        result["action"] = "smart_crop_1x1"
        result["reply"] = "He aplicado el recorte cuadrado inteligente 1:1 centrado en la zona de mayor interés visual."
        return result

    if any(re.search(rf"\b{re.escape(k)}\b", text) for k in ["marca de agua", "c2pa", "limpiar ia", "remolino"]):
        result["action"] = "clean_ai"
        result["reply"] = "He limpiado las marcas de agua esteganográficas IA y el patrón de remolino."
        return result

    # 2. Save / modify custom preset detection
    save_match = re.search(
        r"(?:guarda(?:r|lo)?|gu[aá]rdalo|crea(?:r)?|salvar|ll[aá]malo|como preset)\s+(?:este\s+preset\s+)?(?:como\s+|llamado\s+)?[\"']?([a-zA-Z0-9áéíóúñÁÉÍÓÚÑ _\-]{2,30})[\"']?",
        user_message,
        flags=re.IGNORECASE,
    )
    if save_match and any(w in text for w in ["guarda", "guárdalo", "guardalo", "crea", "nuevo preset", "como preset", "llamado", "llámalo"]):
        cand = save_match.group(1).strip(" .,:;\"'")
        if cand and cand.lower() not in ("preset", "el preset", "un preset"):
            result["save_preset_as"] = cand.title()
            applied_notes.append(f"guardado como preset «{result['save_preset_as']}»")

    # 3. Preset selection (including custom presets)
    if "recomendado" in text or "sugerido" in text:
        rec = state.get("recommended_preset", "electric_chroma_hd")
        result["preset"] = rec
        meta = get_preset_metadata(rec)
        applied_notes.append(f"preset recomendado «{meta['name']}»")
    else:
        for pid, meta in PRESET_DEFINITIONS.items():
            if meta["name"].lower() in text or pid.lower() in text:
                result["preset"] = pid
                applied_notes.append(f"preset «{meta['name']}»")
                break
        if result["preset"] is None:
            for pid, kw_list in PRESET_KEYWORDS.items():
                if any(kw in text for kw in kw_list):
                    result["preset"] = pid
                    meta = get_preset_metadata(pid)
                    applied_notes.append(f"preset «{meta['name']}»")
                    break

    # 4. Percentage / intensity detection (e.g., "al 70%", "intensidad 60%")
    pct_match = re.search(r"(\d{1,3})\s*%", text)
    if pct_match and (result["preset"] is not None or "intensidad" in text or "preset" in text or "suaviza el preset" in text):
        pct_val = float(np.clip(int(pct_match.group(1)) / 100.0, 0.0, 1.0))
        result["preset_intensity"] = round(pct_val, 2)
        if result["preset"] is None and state.get("active_preset", "none") != "none":
            result["preset"] = state.get("active_preset")
        applied_notes.append(f"intensidad al {int(pct_val * 100)}%")
    elif "suaviza el preset" in text or "menos intenso" in text or "baja el preset" in text:
        cur_int = float(state.get("preset_intensity", 1.0))
        new_int = round(float(np.clip(cur_int - 0.25, 0.1, 1.0)), 2)
        result["preset_intensity"] = new_int
        result["preset"] = result["preset"] or state.get("active_preset", "electric_chroma_hd")
        applied_notes.append(f"intensidad del preset reducida al {int(new_int * 100)}%")

    # 5. Parametric adjustments (relative or explicit)
    adj = result["adjustments"]
    cur_ev = float(state.get("ev", 0.0))
    cur_sh = float(state.get("shadows", 0.0))
    cur_hl = float(state.get("highlights", 0.0))
    cur_wb = float(state.get("wb_temp", 0.0))
    cur_dn = float(state.get("denoise", 0.0))
    cur_sp = float(state.get("sharpen", 0.0))
    cur_con = float(state.get("contrast", 1.0))
    cur_sat = float(state.get("saturation", 1.0))

    # Exposure / Brightness
    ev_num = re.search(r"(?:exposicion|exposición|ev)\s*(?:a|en|de)\s*([+\-]?\d+(?:[\.,]\d+)?)", text)
    if ev_num:
        val = float(ev_num.group(1).replace(",", "."))
        adj["ev"] = round(float(np.clip(val, -1.5, 1.5)), 2)
        applied_notes.append(f"exposición EV {adj['ev']:+.2f}")
    elif any(k in text for k in ["mas luz", "más luz", "sube la exposicion", "sube la exposición", "mas clara", "más clara", "aclara", "ilumina", "sube el brillo", "mas brillante"]):
        adj["ev"] = round(float(np.clip(cur_ev + 0.30, -1.5, 1.5)), 2)
        applied_notes.append(f"exposición aumentada ({adj['ev']:+.2f} EV)")
    elif any(k in text for k in ["menos luz", "baja la exposicion", "baja la exposición", "mas oscura", "más oscura", "oscurece", "baja el brillo"]):
        adj["ev"] = round(float(np.clip(cur_ev - 0.30, -1.5, 1.5)), 2)
        applied_notes.append(f"exposición reducida ({adj['ev']:+.2f} EV)")

    # Shadows
    if any(k in text for k in ["abre sombras", "abrir sombras", "sube sombras", "sube las sombras", "levanta sombras", "levantar sombras", "aclara sombras", "mas sombras"]):
        adj["shadows"] = round(float(np.clip(max(cur_sh, 0.0) + 0.35, -1.0, 1.0)), 2)
        applied_notes.append(f"sombras abiertas ({adj['shadows']:+.2f})")
    elif any(k in text for k in ["baja sombras", "oscurece sombras", "sombras densas", "cierra sombras"]):
        adj["shadows"] = round(float(np.clip(cur_sh - 0.30, -1.0, 1.0)), 2)
        applied_notes.append(f"sombras más profundas ({adj['shadows']:+.2f})")

    # Highlights
    if any(k in text for k in ["protege altas luces", "baja altas luces", "recupera altas luces", "recupera el cielo", "baja las luces", "altas luces"]):
        adj["highlights"] = round(float(np.clip(max(cur_hl, 0.0) + 0.35, -1.0, 1.0)), 2)
        applied_notes.append(f"altas luces protegidas ({adj['highlights']:+.2f})")

    # White Balance (Warm / Cool)
    if any(k in text for k in ["mas calid", "más cálid", "mas calida", "más cálida", "calido", "cálido", "dorado", "atardecer", "sube temperatura"]):
        adj["wb_temp"] = round(float(np.clip(cur_wb + 0.25, -1.0, 1.0)), 2)
        applied_notes.append(f"balance más cálido ({adj['wb_temp']:+.2f})")
    elif any(k in text for k in ["mas fri", "más frí", "frio", "frío", "azulado", "baja temperatura"]):
        adj["wb_temp"] = round(float(np.clip(cur_wb - 0.25, -1.0, 1.0)), 2)
        applied_notes.append(f"balance más frío ({adj['wb_temp']:+.2f})")

    # Denoise
    if any(k in text for k in ["quita ruido", "quitar ruido", "sin ruido", "sin grano", "denoise", "limpia el ruido", "suaviza ruido"]):
        adj["denoise"] = round(float(np.clip(max(cur_dn, 0.2) + 0.35, 0.0, 1.0)), 2)
        applied_notes.append(f"reducción de ruido HD ({int(adj['denoise'] * 100)}%)")

    # Sharpen
    if any(k in text for k in ["mas nitidez", "más nitidez", "enfoca", "mas definida", "más definida", "nitidez", "sharpen", "detalle"]):
        adj["sharpen"] = round(float(np.clip(max(cur_sp, 0.2) + 0.35, 0.0, 1.0)), 2)
        applied_notes.append(f"nitidez estructural HD ({int(adj['sharpen'] * 100)}%)")

    # Contrast
    if any(k in text for k in ["mas contraste", "más contraste", "sube el contraste", "sube contraste"]):
        adj["contrast"] = round(float(np.clip(cur_con + 0.18, 0.5, 1.5)), 2)
        applied_notes.append(f"contraste aumentado ({adj['contrast']:.2f})")
    elif any(k in text for k in ["menos contraste", "baja el contraste", "baja contraste", "suave"]):
        adj["contrast"] = round(float(np.clip(cur_con - 0.15, 0.5, 1.5)), 2)
        applied_notes.append(f"contraste suavizado ({adj['contrast']:.2f})")

    # Saturation
    if any(k in text for k in ["mas saturacion", "más saturación", "mas color", "más color", "colores vivos", "sube saturacion", "sube la saturación"]):
        adj["saturation"] = round(float(np.clip(cur_sat + 0.22, 0.0, 2.0)), 2)
        applied_notes.append(f"saturación aumentada ({adj['saturation']:.2f})")
    elif any(k in text for k in ["menos saturacion", "menos saturación", "desatura", "menos color", "apagado"]):
        adj["saturation"] = round(float(np.clip(cur_sat - 0.22, 0.0, 2.0)), 2)
        applied_notes.append(f"saturación reducida ({adj['saturation']:.2f})")

    if applied_notes:
        result["reply"] = "He aplicado: " + ", ".join(applied_notes) + "."
    else:
        rec_id = state.get("recommended_preset", "electric_chroma_hd")
        rec_name = get_preset_metadata(rec_id)["name"]
        result["reply"] = (
            f"Puedo aplicar o modificar cualquier preset y parámetro por ti. "
            f"Para esta foto ({state.get('scene_type', 'actual')}) te recomiendo «{rec_name}». "
            f"Prueba a decirme: «aplica {rec_name} al 80% y abre las sombras» o «hazla más cálida y guárdalo como Mi Preset»."
        )
    return result


def normalize_agent_response(raw_dict: dict | None, user_message: str, state: dict) -> dict:
    """
    Validates, clamps, and merges the embedded Qwen LLM JSON output with deterministic NLU rules
    so that small 0.5B/1.5B models never hallucinate invalid preset IDs or out-of-range sliders.
    """
    fallback = parse_natural_language_fallback(user_message, state)
    if not isinstance(raw_dict, dict):
        return fallback

    action = str(raw_dict.get("action") or fallback["action"] or "update").lower()
    if action not in ("update", "auto_develop", "smart_crop_1x1", "clean_ai", "reset", "undo"):
        action = fallback["action"]

    # Validate preset
    preset = raw_dict.get("preset")
    if isinstance(preset, str):
        preset_clean = preset.strip().lower()
        if preset_clean in PRESET_DEFINITIONS:
            preset = preset_clean
        else:
            preset = fallback["preset"]
    else:
        preset = fallback["preset"]

    # Validate intensity (prefer explicit percentage from user text if present)
    intensity = raw_dict.get("preset_intensity")
    if fallback["preset_intensity"] is not None and "%" in user_message:
        intensity = fallback["preset_intensity"]
    elif intensity is not None:
        try:
            intensity = float(intensity)
            if intensity > 1.0 and intensity <= 100.0:
                intensity = intensity / 100.0
            intensity = round(float(np.clip(intensity, 0.0, 1.0)), 2)
        except Exception:
            intensity = fallback["preset_intensity"]
    else:
        intensity = fallback["preset_intensity"]

    # Validate adjustments
    raw_adj = raw_dict.get("adjustments") if isinstance(raw_dict.get("adjustments"), dict) else {}
    merged_adj = dict(fallback["adjustments"])
    bounds = {
        "ev": (-1.5, 1.5),
        "shadows": (-1.0, 1.0),
        "highlights": (-1.0, 1.0),
        "wb_temp": (-1.0, 1.0),
        "denoise": (0.0, 1.0),
        "sharpen": (0.0, 1.0),
        "brightness": (0.2, 2.0),
        "contrast": (0.2, 2.0),
        "saturation": (0.0, 2.0),
    }
    for key, (low, high) in bounds.items():
        val = raw_adj.get(key)
        if val is not None:
            try:
                fval = round(float(np.clip(float(val), low, high)), 2)
                merged_adj[key] = fval
            except Exception:
                pass

    save_as = raw_dict.get("save_preset_as")
    if not isinstance(save_as, str) or not save_as.strip():
        save_as = fallback["save_preset_as"]
    else:
        save_as = save_as.strip()

    reply = raw_dict.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        reply = fallback["reply"]

    return {
        "reply": reply.strip(),
        "action": action,
        "preset": preset,
        "preset_intensity": intensity,
        "adjustments": merged_adj,
        "save_preset_as": save_as,
    }


def query_qwen_agent(
    user_message: str,
    state: dict,
    model_name: str = "Qwen 2.5 0.5B (Integrado Rápido)",
    history: list[dict] | None = None,
    models_dir: str = MODELS_DIR,
    auto_download: bool = True,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    """
    Runs 100% embedded in-process inference using `llama_cpp.Llama` and the local GGUF weights
    (`models/qwen2.5-0.5b-instruct.gguf` or `models/qwen2.5-1.5b-instruct.gguf`), automatically
    downloading the GGUF file on first use if not yet present in `models_dir`.
    """
    messages = [{"role": "system", "content": build_system_prompt(state)}]
    if history:
        for msg in history[-4:]:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    try:
        llm = get_embedded_llama(
            model_name,
            models_dir=models_dir,
            auto_download=auto_download,
            progress_callback=progress_callback,
        )
        with _LLAMA_LOCK:
            completion = llm.create_chat_completion(
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.15,
                max_tokens=256,
            )
        content = (
            completion.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = _extract_json_dict(content)
        res = normalize_agent_response(parsed, user_message, state)
        res["model_used"] = os.path.basename(resolve_model_path(model_name, models_dir=models_dir))
        return res
    except Exception as e:
        logger.warning(f"Embedded Qwen GGUF inference error ({model_name}), using built-in NLU engine: {e}")
        res = parse_natural_language_fallback(user_message, state)
        res["model_used"] = "fallback-nlu"
        return res
