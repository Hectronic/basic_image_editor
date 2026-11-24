## ADDED Requirements

### Requirement: Curated Photographic Presets with Live Thumbnails and Intensity Blending
The system SHALL provide curated photographic presets (`none`, `electric_chroma_hd`, `moderna_definida_hd`, `editorial_viva_hd`, `kodachrome_64`, `blancoynegro_platino_hd`, `cinestill_800t`, `selectivo_platino_hd`) rendered as live 96×64 miniature previews in `PresetGalleryDock` and blended linearly according to a continuous intensity slider (`0.0` to `1.0`).

#### Scenario: Apply Preset and Adjust Intensity
- **WHEN** the user selects `electric_chroma_hd` in the Preset Gallery and moves the intensity slider to `75%`
- **THEN** the system blends the developed base image with the cached graded image at `0.75` weight and records the state in Undo/Redo history

### Requirement: Dynamic Custom Preset Creation and Persistence
The system SHALL allow registering, modifying, and persisting custom presets (`register_custom_preset`) composed of a base preset and parametric/classic adjustments in `~/.image_editor_custom_presets.json`, updating the Preset Gallery immediately.

#### Scenario: Register Custom Preset from Recipe
- **WHEN** a custom preset named `Mi Dorado Cálido` is registered with a recipe (`base_preset`, `ev`, `shadows`, `wb_temp`, `saturation`)
- **THEN** the preset is added to `PRESET_DEFINITIONS` and `_PRESET_FUNCTIONS`, persisted to disk, and selectable in the UI gallery
