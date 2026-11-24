# Proposal: RAW 16-bit Developer, Curated Preset Studio, Smart Reveal Assistant & Qwen Conversational Agent

## Why

Basic Image Editor originally supported only basic 8-bit operations (rotate, flip, crop, brightness, contrast, saturation). To serve as a high-definition, non-destructive photographic studio for camera RAW files (`.ARW`, `.CR2`, `.NEF`, `.DNG`, etc.) and urban/travel photography without the overhead of heavy editors, the application needed:
1. A 16-bit linear/unclipped RAW development pipeline with SIMD/LUT hardware acceleration.
2. A curated photographic preset engine with real-time thumbnail previews and custom preset creation.
3. An automated scene-diagnostic assistant (auto-develop, smart 1:1 saliency crop for Instagram, and AI/C2PA watermark & swirl cleaner).
4. A 100% embedded in-process conversational AI chat agent powered by lightweight **Qwen (`qwen2.5-0.5b-instruct.gguf` / `qwen2.5-1.5b-instruct.gguf`)** models executed directly inside Python via `llama-cpp-python` (with zero external services or daemons) capable of applying presets, modifying parametric adjustments, and saving new custom presets through natural language.

## What Changes

- **16-bit RAW Developer (`src/processing/raw_developer.py`)**:
  - Support for camera RAW formats (`.arw`, `.cr2`, `.cr3`, `.nef`, `.dng`, `.raf`, `.orf`, `.rw2`, `.pef`, `.srw`) via `rawpy` in 16-bit precision with highlight blend recovery.
  - Combined 256-entry float32 OpenCV LUT curves for Exposure (EV), Shadows, Highlights, Soft-Knee highlight protection, White Balance (Temp/Tint), multiscale LAB edge-guided Denoise HD (zero grain), and Unsharp Mask HD structural sharpening.
- **Photographic Preset Engine & Custom Presets (`src/processing/preset_engine.py`, `src/ui/preset_gallery_dock.py`)**:
  - 7 curated photographic presets (`electric_chroma_hd`, `moderna_definida_hd`, `editorial_viva_hd`, `kodachrome_64`, `blancoynegro_platino_hd`, `cinestill_800t`, `selectivo_platino_hd`) + `none`.
  - Dynamic registration, modification, and JSON persistence (`~/.image_editor_custom_presets.json`) of user/chat-defined custom presets (`register_custom_preset`, `save_custom_presets`, `load_custom_presets`).
  - Interactive `PresetGalleryDock` with live 96×64 thumbnails and continuous 0–100% intensity blending.
- **Smart Reveal Assistant (`src/processing/reveal_assistant.py`)**:
  - Histogram, dynamic range, shadow/highlight ratio, warmth, saturation, and Laplacian sharpness analysis with automatic scene classification and preset recommendation.
  - 1-click Auto-Develop (`compute_auto_develop_params`), Smart 1:1 Saliency Square Crop (`compute_smart_square_crop`), and AI/C2PA Steganographic Watermark & Swirl Remover (`strip_ai_watermarks_and_swirl`).
- **Conversational Qwen LLM Chat Agent (`src/processing/llm_chat_agent.py`, `src/ui/assistant_dock.py`)**:
  - 100% self-contained in-process inference using `llama_cpp.Llama` and local GGUF weights (`models/qwen2.5-0.5b-instruct.gguf` and `models/qwen2.5-1.5b-instruct.gguf`) with structured JSON output (`response_format={"type": "json_object"}`) in a non-blocking `QThread` (`LLMChatWorker`). No Ollama or external daemon required.
  - Hybrid deterministic NLU validation and offline fallback (`parse_natural_language_fallback`, `normalize_agent_response`) so natural Spanish/English prompts reliably apply presets, adjust percentages/sliders, trigger global actions (`auto_develop`, `smart_crop_1x1`, `clean_ai`, `undo`, `reset`), and save custom presets.

## Capabilities

### New Capabilities
- `raw-developer`: 16-bit camera RAW decoding and SIMD/LUT parametric development (EV, Shadows, Highlights, WB Temp/Tint, Denoise HD, Structural Sharpen HD).
- `preset-engine`: Curated photographic grading presets, live gallery dock with 0–100% intensity slider, and persistent custom preset creation/modification.
- `smart-reveal-assistant`: Automated scene diagnostics, 1-click optimal auto-development, saliency-guided 1:1 square cropping, and AI/C2PA watermark/swirl removal.
- `qwen-chat-agent`: Local Qwen (0.5B / 1.5B) conversational chat interface in the assistant dock to apply/modify presets and development parameters via natural language.

### Modified Capabilities
- `image-editor-core`: Extended `ImageModel`, `EditorTab`, and `ImageEditorApp` with multi-level float32 caching, non-destructive preset/reveal state history (Undo/Redo), and dock synchronization.

## Impact

- **Codebase**: Adds `src/processing/raw_developer.py`, `src/processing/preset_engine.py`, `src/processing/reveal_assistant.py`, `src/processing/llm_chat_agent.py`, `src/ui/preset_gallery_dock.py`, `src/ui/assistant_dock.py`, and updates `src/model/image_model.py`, `src/ui/editor_tab.py`, `src/ui/main_window.py`.
- **Tests**: Comprehensive unit and Qt UI test suite in `tests/test_reveal_and_presets.py` covering all processing pipelines, docks, custom presets, and Qwen LLM chat agent interactions.
