## ADDED Requirements

### Requirement: Automated Scene Diagnostics and Auto-Develop
The system SHALL analyze the open image's luminance histogram, dynamic range, shadow/highlight ratios, color warmth, saturation, and central Laplacian sharpness (`analyze_image`) to classify the scene type, recommend an optimal preset, and compute 1-click auto-develop parameters (`compute_auto_develop_params`).

#### Scenario: 1-Click Auto-Develop Photo
- **WHEN** the user clicks `✨ Auto-Revelar Foto (Óptimo)` or triggers `Ctrl+R`
- **THEN** the system applies optimal EV, shadow recovery, highlight protection, white balance, denoise, sharpen, and the recommended preset for the detected scene

### Requirement: Smart 1:1 Saliency Square Crop and AI Watermark Cleaner
The system SHALL provide a 1-click Smart Square 1:1 Crop (`compute_smart_square_crop`) maximizing Sobel gradient and chromatic saliency energy, and an AI/C2PA Watermark & Swirl Cleaner (`strip_ai_watermarks_and_swirl`) using edge-guided bilateral filtering and sub-pixel Lanczos4 resampling.

#### Scenario: Smart 1:1 Crop for Instagram
- **WHEN** the user triggers `📐 Insta 1:1` on a non-square image
- **THEN** the system crops the image to `min(width, height) × min(width, height)` centered on the highest visual saliency region
