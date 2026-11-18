# Tasks: RAW 16-bit Developer, Curated Preset Studio, Smart Reveal Assistant & Qwen Conversational Agent

## 1. 16-bit RAW Developer & Multi-Level Caching

- [x] 1.1 Implement 16-bit RAW loading (`load_raw_16bit`, `is_raw_file`) and float32 RGB conversion in `src/processing/raw_developer.py`.
- [x] 1.2 Implement 256-entry OpenCV LUT tone curves (`build_gamma_s_curve_lut`, `apply_lut_curve_float`), soft-knee highlight protection, LAB edge-guided Denoise HD (`denoise_ultra_clean`), and structural HD sharpening (`sharpen_hd_modern`).
- [x] 1.3 Integrate multi-level caching (`_cached_base_rgb`, `_cached_dev_rgb`, `_preset_graded_cache`) and Undo/Redo state preservation in `src/model/image_model.py`.

## 2. Photographic Preset Engine & Custom Preset Persistence

- [x] 2.1 Implement curated photographic presets (`electric_chroma_hd`, `moderna_definida_hd`, `editorial_viva_hd`, `kodachrome_64`, `blancoynegro_platino_hd`, `cinestill_800t`, `selectivo_platino_hd`) and thumbnail generator in `src/processing/preset_engine.py`.
- [x] 2.2 Implement dynamic custom preset creation, recipe compilation, and JSON persistence (`register_custom_preset`, `save_custom_presets`, `load_custom_presets`).
- [x] 2.3 Build `PresetGalleryDock` (`src/ui/preset_gallery_dock.py`) with live 96×64 previews, 0–100% intensity slider, and dynamic list refresh.

## 3. Smart Reveal Assistant & Conversational Qwen Chat Agent

- [x] 3.1 Implement scene histogram/sharpness diagnostics (`analyze_image`), 1-click Auto-Develop (`compute_auto_develop_params`), Smart 1:1 Saliency Square Crop (`compute_smart_square_crop`), and AI/C2PA Watermark & Swirl Cleaner (`strip_ai_watermarks_and_swirl`) in `src/processing/reveal_assistant.py`.
- [x] 3.2 Implement 100% embedded Qwen GGUF agent (`src/processing/llm_chat_agent.py`) supporting `models/qwen2.5-0.5b-instruct.gguf` and `models/qwen2.5-1.5b-instruct.gguf` in-process via `llama-cpp-python` (`response_format={"type": "json_object"}`), hybrid parameter validation (`normalize_agent_response`), and deterministic NLU (`parse_natural_language_fallback`) with zero external services.
- [x] 3.3 Embed conversational Qwen chat UI and background `LLMChatWorker` (`QThread`) in `RevealAssistantDock` (`src/ui/assistant_dock.py`) and wire `on_chat_command_executed` in `ImageEditorApp` (`src/ui/main_window.py`).

## 4. Testing, Documentation & OpenSpec Validation

- [x] 4.1 Write comprehensive unit and UI tests in `tests/test_reveal_and_presets.py` and verify 100% test pass rate with `pytest`.
- [x] 4.2 Sync OpenSpec delta specs to main `openspec/specs/` and include executable Spanish BDD Gherkin contracts (`.feature`).
- [x] 4.3 Update `README.md`, `README_ES.md`, `README_AST.md`, and `HISTORY.md` to reflect all capabilities.
