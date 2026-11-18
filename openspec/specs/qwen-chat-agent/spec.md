# Spec: Conversational Qwen LLM Chat Agent (`qwen-chat-agent`)

## Purpose

Defines the 100% embedded in-process Qwen (`qwen2.5-0.5b-instruct.gguf` and `qwen2.5-1.5b-instruct.gguf` via `llama-cpp-python`) conversational AI agent, automatic on-demand GGUF downloader, and hybrid deterministic NLU parser embedded in `RevealAssistantDock` to apply presets, modify parameters, and create/save custom presets through natural language with zero external services or daemons.

## Requirements

### Requirement: 100% Embedded In-Process Qwen LLM Photo Editing & On-Demand GGUF Auto-Download
The system SHALL provide an embedded chat panel in `RevealAssistantDock` executing local GGUF weights (`models/qwen2.5-0.5b-instruct.gguf` and `models/qwen2.5-1.5b-instruct.gguf`, excluded from Git) directly in-process via `llama_cpp.Llama` inside a background `QThread` (`LLMChatWorker`), automatically downloading missing GGUF weights from official Hugging Face repositories on first use (`ensure_model_downloaded`) with UI progress feedback, and combining LLM output with a deterministic NLU engine (`parse_natural_language_fallback` and `normalize_agent_response`) without requiring Ollama or any external daemon.

#### Scenario: Auto-Download Missing GGUF Model on First Use
- **WHEN** the user clones the repository without `models/*.gguf` and sends a message in the Qwen chat
- **THEN** `ensure_model_downloaded` downloads the selected Qwen 2.5 GGUF file atomically via a `.part` temporary file into `models/`, reports live download progress to the UI, and loads it in-process

#### Scenario: Apply Preset and Modify Parameters via Embedded Qwen Chat
- **WHEN** the user types `"Pon CineStill al 80%, abre las sombras y hazla más cálida"` in the chat input
- **THEN** the in-process Qwen GGUF model returns a structured JSON command that sets `active_preset = "cinestill_800t"`, `preset_intensity = 0.80`, increases `shadows` and `wb_temp`, synchronizes all UI sliders/docks, and replies in the chat log

#### Scenario: Create and Save a Custom Preset via Chat
- **WHEN** the user types `"Aplica el preset recomendado al 70%, sube nitidez y guárdalo como Super Urbano"`
- **THEN** the system registers the new custom preset `custom_super_urbano`, refreshes the Preset Gallery thumbnails, activates the new preset on the canvas, and records the change in history

#### Scenario: Self-Contained Fallback Resilience
- **WHEN** the user sends a chat command while offline and before the GGUF file has been downloaded
- **THEN** `query_qwen_agent` automatically uses the built-in NLU engine (`parse_natural_language_fallback`) and executes the requested preset/parameter changes without error
