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
