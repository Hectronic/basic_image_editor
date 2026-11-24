# Editor de Imágenes Básico

Una aplicación de escritorio de edición de imágenes minimalista, rápida y ligera, construida con Python y PyQt6.

Este proyecto nació de la necesidad de tener un editor simple que haga las cosas rápidas que suelo necesitar. No quiero usar GIMP para tareas sencillas, ni aspiro a que esto sea un reemplazo de GIMP.

## Características

-   **Lienzo Responsivo y Estudio Multi-Pestaña**: Visualización y edición fluida con caché multinivel e historial completo de Deshacer/Rehacer.
-   **Revelador RAW de 16 bits**: Soporte nativo para `.ARW`, `.CR2`, `.CR3`, `.NEF`, `.DNG`, `.RAF`, `.ORF` acelerado por LUTs SIMD de 256 entradas (Exposición EV, Sombras, Altas Luces, Temperatura WB, Denoise HD sin grano y Nitidez Estructural HD).
-   **Galería de Presets Fotográficos HD**: 7 presets curados (`Electric Chroma HD`, `Moderna Definida HD`, `Editorial Viva HD`, `Kodachrome 64 Cine`, `Blanco y Negro Platino HD`, `CineStill 800T Halación`, `Desaturado Selectivo Platino`) con miniaturas en vivo, deslizador de intensidad 0–100% y creación de presets personalizados.
-   **Asistente Inteligente de Revelado**: Diagnóstico automático de escena e histograma, Auto-Revelado en 1 clic (`Ctrl+R`), Encuadre Inteligente 1:1 para Instagram y Limpiador de marcas de agua IA / C2PA y remolino.
-   **Chat IA Conversacional 100% Integrado con Qwen (`0.5B` / `1.5B`)**: Agente ejecutado directamente en proceso mediante `llama-cpp-python` y modelos GGUF locales (`models/qwen2.5-0.5b-instruct.gguf` y `models/qwen2.5-1.5b-instruct.gguf`, descargados automáticamente por la propia herramienta en el primer uso si no están presentes), sin necesidad de Ollama ni servicios externos.
-   **Transformaciones, Dibujo Vectorial y Eliminación de Fondo IA**: Rotar, voltear, recortar, anotar (lápiz, flechas, formas, texto) y eliminar el fondo con `rembg`.
-   **Tema Oscuro**: Interfaz de usuario moderna y limpia.

## Capturas de Pantalla

![Página de Inicio](screenshots/home.png)
![Vista del Editor](screenshots/editor.png)

## Instalación y Uso

Clona el repositorio y ejecuta el script proporcionado:

```bash
./run.sh
```

Este script automáticamente:
1.  Creará un entorno virtual (`venv`).
2.  Instalará las dependencias necesarias desde `requirements.txt`.
3.  Iniciará la aplicación.

### Instalación Manual

Si prefieres ejecutarlo manualmente:

1.  Crea un entorno virtual:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
2.  Instala las dependencias:
    ```bash
    pip install -r requirements.txt
    ```
3.  Ejecuta la aplicación:
    ```bash
    python3 main.py
    ```

## Requisitos

-   Python 3.10+
-   PyQt6
-   Pillow

## Licencia

Este proyecto está licenciado bajo la Licencia GPL-3.0-o-posterior. Consulta el archivo [LICENSE](LICENSE) para más detalles.

---

> Esta aplicación ha sido vibecodeada usando **Antigravity** en Diciembre - Enero de 2026.

