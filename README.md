# Basic Image Editor

A minimalist, fast, and lightweight Desktop Image Editor application built with Python and PyQt6.

This project was born to have a simple editor that does the quick things I usually need. 
I don't want to use GIMP for simple tasks, nor do I aspire for this to be a GIMP replacement.

## Features

-   **Responsive Canvas**: viewing and editing images.
-   **File Operations**: Open and save images.
-   **Transformations**: Rotate and flip images.
-   **Crop Tool**: Easy-to-use cropping functionality.
-   **Adjustments**: Brightness, contrast, and saturation controls.
-   **Dark Theme**: Modern and clean user interface.

## Screenshots

![Start Page](screenshots/home.png)
![Editor View](screenshots/editor.png)

## Installation and Usage

Clone the repository and run the provided script:

```bash
./run.sh
```

This script will automatically:
1.  Create a virtual environment (`venv`).
2.  Install the required dependencies from `requirements.txt`.
3.  Launch the application.

### Manual Installation

If you prefer to run it manually:

1.  Create a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the application:
    ```bash
    python3 main.py
    ```

## Requirements

-   Python 3.10+
-   PyQt6
-   Pillow

## License

This project is licensed under the GPL-3.0-or-later License. See the [LICENSE](LICENSE) file for details.

---

> This application has been vibecoded using **Antigravity** in December - January 2026.

