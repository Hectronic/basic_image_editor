# Design: RAW Developer, Preset Engine, Smart Assistant & Qwen Chat Architecture

## Context

Basic Image Editor is a desktop PyQt6 application designed for responsiveness and simplicity. Adding 16-bit RAW processing, multi-preset grading, scene diagnostics, and conversational LLM control requires non-blocking execution and sub-15ms interactive slider/preset response times on standard CPU hardware.

## Goals / Non-Goals

**Goals:**
- Achieve real-time (60 FPS) slider and preset switching using multi-level caching and OpenCV 256-entry LUT vectorization.
- Provide non-destructive parametric RAW development and preset blending with full Undo/Redo support.
- Enable natural language photo editing and custom preset creation via lightweight 100% embedded Qwen GGUF models (`models/qwen2.5-0.5b-instruct.gguf` and `models/qwen2.5-1.5b-instruct.gguf`) running directly in-process via `llama-cpp-python`, with zero external daemons and zero UI freezing.

**Non-Goals:**
- Replacing layer-based raster editors like GIMP or Photoshop.
- External LLM daemons (such as Ollama) or cloud-only LLM dependencies.

## Decisions

### 1. Multi-Level Caching & SIMD LUT Pipeline (`ImageModel`, `raw_developer.py`, `preset_engine.py`)
- **Decision**: Cap interactive working resolution at `MAX_WORKING_DIMENSION = 1440` and cache three distinct stages in `ImageModel`:
  1. `_cached_base_rgb`: Normalized `float32` RGB `[0, 1]` from the geometric base image.
  2. `_cached_dev_rgb`: Result of `develop_base_image()` keyed by `(img_id, ev, shadows, highlights, wb_temp, wb_tint, denoise, sharpen)`.
  3. `_preset_graded_cache`: Result of 100% preset grading keyed by `(dev_key, preset_id)`, allowing the 0–100% intensity slider to perform a single `cv2.addWeighted` call in `<2ms`.
- **Rationale**: Avoids recomputing bilateral denoise or RAW tone curves when switching presets or dragging the preset intensity slider.

### 2. Hybrid 100% Embedded Qwen GGUF (`llama-cpp-python`) + Deterministic NLU Validation (`llm_chat_agent.py`, `assistant_dock.py`)
- **Decision**: Load `models/qwen2.5-0.5b-instruct.gguf` (380 MB) and `models/qwen2.5-1.5b-instruct.gguf` (941 MB) directly in Python memory using `llama_cpp.Llama` (`response_format={"type": "json_object"}`, `temperature=0.15`) inside a `QThread` (`LLMChatWorker`), and pass the output through `normalize_agent_response()`, which merges and validates it against `parse_natural_language_fallback()`.
- **Rationale**: Eliminates any dependency on Ollama or external processes while keeping inference fast (~0.3–1.1s on CPU) and guaranteeing valid preset IDs and clamped slider bounds.

### 3. Dynamic Custom Presets (`register_custom_preset`)
- **Decision**: Represent custom presets as composable recipes (`base_preset` + parametric adjustments + classic adjustments) compiled into a fast callable in `_PRESET_FUNCTIONS` and persisted in `~/.image_editor_custom_presets.json`.
- **Rationale**: Allows users to say *"pon CineStill al 80%, sube sombras, hazla más cálida y guárdalo como Mi Nocturno"* and immediately see `Mi Nocturno` in the Preset Gallery with its live thumbnail.
