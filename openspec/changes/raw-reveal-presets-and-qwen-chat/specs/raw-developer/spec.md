## ADDED Requirements

### Requirement: 16-bit Camera RAW Decoding
The system SHALL decode digital camera RAW files (`.arw`, `.cr2`, `.cr3`, `.nef`, `.dng`, `.raf`, `.orf`, `.rw2`, `.pef`, `.srw`) in 16-bit precision using `rawpy` with camera white balance and unclipped highlight blending, normalizing the output into a `float32` RGB array in `[0.0, 1.0]`.

#### Scenario: Load Sony ARW RAW file without clipping
- **WHEN** the user opens a `.ARW` camera RAW file
- **THEN** the system decodes it in 16-bit mode (`output_bps=16`, `HighlightMode.Blend`) and initializes the non-destructive base `float32` image buffer

### Requirement: Parametric LUT & Edge-Guided RAW Development
The system SHALL apply non-destructive parametric adjustments including Exposure (`ev` in `[-1.5, 1.5]`), Shadows (`[-1.0, 1.0]`), Highlights (`[-1.0, 1.0]`), White Balance Temperature (`[-1.0, 1.0]`), Chroma/Luma Edge-Guided Denoise (`[0.0, 1.0]` with zero artificial grain), and Structural HD Sharpening (`[0.0, 1.0]`) using 256-entry OpenCV LUTs and soft-knee highlight compression.

#### Scenario: Adjust Exposure and Shadows via Reveal Sliders
- **WHEN** the user modifies the Exposure (EV) or Shadows slider in the Adjustments & Revelado dock
- **THEN** the system computes the combined 256-entry LUT with soft-knee highlight protection (`knee = 0.78`) and updates the canvas in real time
