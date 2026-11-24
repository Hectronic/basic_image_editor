# Spec: Image Editor Core (`image-editor-core`)

## Purpose

Defines the core non-destructive image editing canvas, multi-tab workspace, geometric transformations, vector shape annotations, background removal, and multi-level Undo/Redo history in Basic Image Editor.

## Requirements

### Requirement: Multi-Tab Image Loading, Saving, and Geometric Transformations
The system SHALL allow opening standard raster images (`.png`, `.jpg`, `.jpeg`, `.bmp`, `.tif`, `.tiff`) and camera RAW files in independent closable tabs (`EditorTab`), supporting non-destructive zoom/pan, 90° left/right rotation, horizontal/vertical flipping, interactive rectangle cropping, and saving to PNG/JPG with vector annotations rendered.

#### Scenario: Open, Rotate, and Save an Image
- **WHEN** the user opens an image file, rotates it 90°, and saves it
- **THEN** the system updates the geometric base image, invalidates intermediate caches, records the rotation in Undo/Redo history, and exports the final composite image to disk

### Requirement: Vector Annotations and AI Background Removal
The system SHALL provide interactive drawing tools (`SELECT_SHAPE`, `DRAW_PEN`, `DRAW_ERASER`, `DRAW_LINE`, `DRAW_ARROW`, `DRAW_RECT`, `DRAW_ELLIPSE`, `DRAW_TEXT`) with configurable color and stroke width, as well as asynchronous AI background removal (`rembg`) executed in a background thread (`BackgroundRemoverWorker`).

#### Scenario: Add Vector Shape and Undo
- **WHEN** the user draws a shape on the canvas and triggers `Ctrl+Z` (Undo)
- **THEN** the shape state is pushed to `ImageModel.history` and restored accurately on Undo/Redo

### Requirement: Interactive History Timeline Point Selection
The system SHALL expose the full chronological edit timeline (`history` + undone `redo_stack`) in the History panel (`history_list`) and allow the user to select/click any point in the timeline (`jump_to_history(index)`) to immediately restore the image, parametric reveal sliders, preset selection/intensity, geometric state, and vector shapes at that exact point without discarding subsequent timeline states until a new edit is committed.

#### Scenario: Jump Backward and Forward Across History Points
- **WHEN** the user applies multiple edits (e.g., preset selection, EV slider adjustment, 1:1 crop) and clicks an earlier entry in `history_list`
- **THEN** the canvas image, sliders, and active preset immediately revert to that exact historical state while keeping later steps selectable (displayed as future states) so clicking a later entry restores it again

### Requirement: Decluttered Dark-Studio Workspace Layout
The system SHALL present a spacious dark-studio UI by tabifying left-side panels (`🎨 Presets` and `💬 Asistente IA`), hiding secondary annotation tools (`Drawing Toolbar`) behind an on-demand `"✏️ Anotar"` toggle, collapsing classic adjustments (`Brillo`, `Contraste`, `Saturación`) and detailed histogram diagnostics by default, and displaying live formatted value readouts next to every slider.

#### Scenario: Spacious Default Photo Reveal Workspace
- **WHEN** the user opens a RAW or standard photo in the editor
- **THEN** only the single main toolbar is shown at the top, left docks share full vertical height via tabs, and collapsible sections remain folded until explicitly expanded
