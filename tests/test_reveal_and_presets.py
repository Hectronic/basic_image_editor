"""
Basic Image Editor - Unit & UI Tests for RAW Developer, Presets, and Reveal Assistant
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me
"""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from PIL import Image

from src.processing.raw_developer import (
    is_raw_file,
    pil_to_float,
    float_to_pil,
    load_raw_16bit,
    protect_gamut_and_highlights,
    denoise_ultra_clean,
    sharpen_hd_modern,
    apply_s_curve_luminance,
    develop_base_image,
)
from src.processing.preset_engine import (
    PRESET_DEFINITIONS,
    get_preset_names,
    get_preset_metadata,
    apply_preset,
    generate_preset_thumbnail,
)
from src.processing.reveal_assistant import (
    analyze_image,
    compute_auto_develop_params,
    compute_smart_square_crop,
    strip_ai_watermarks_and_swirl,
)
from src.model.image_model import ImageModel
from src.ui.preset_gallery_dock import PresetGalleryDock
from src.ui.assistant_dock import RevealAssistantDock
from src.ui.main_window import ImageEditorApp


@pytest.fixture
def synthetic_rgb_float():
    """Creates a synthetic 64x80 RGB float32 test image with gradients and colors."""
    y = np.linspace(0.05, 0.95, 64, dtype=np.float32)[:, None]
    x = np.linspace(0.05, 0.95, 80, dtype=np.float32)[None, :]
    r = np.clip(x * 0.9 + 0.05, 0.0, 1.0) * np.ones((64, 1), dtype=np.float32)
    g = np.clip(y * 0.8 + 0.10, 0.0, 1.0) * np.ones((1, 80), dtype=np.float32)
    b = np.clip(1.0 - 0.5 * (x + y), 0.0, 1.0)
    return np.stack([r, g, b], axis=-1).astype(np.float32)


def test_is_raw_file():
    assert is_raw_file("/photos/DSC04808.ARW") is True
    assert is_raw_file("/photos/img.cr2") is True
    assert is_raw_file("/photos/img.nef") is True
    assert is_raw_file("/photos/img.jpg") is False
    assert is_raw_file("") is False


def test_pil_float_roundtrip(synthetic_rgb_float):
    pil_rgba = float_to_pil(synthetic_rgb_float)
    assert pil_rgba.mode == "RGBA"
    rgb_f, alpha = pil_to_float(pil_rgba)
    assert rgb_f.shape == synthetic_rgb_float.shape
    assert alpha is not None
    assert np.allclose(rgb_f, synthetic_rgb_float, atol=1.0 / 255.0 + 1e-3)

    # Roundtrip with explicit non-opaque alpha
    custom_alpha = np.full(synthetic_rgb_float.shape[:2], 0.5, dtype=np.float32)
    pil_semi = float_to_pil(synthetic_rgb_float, custom_alpha)
    assert pil_semi.mode == "RGBA"

    pil_rgb = pil_rgba.convert("RGB")
    rgb_f2, alpha2 = pil_to_float(pil_rgb)
    assert alpha2 is None
    assert rgb_f2.shape == synthetic_rgb_float.shape


def test_load_raw_16bit_mocked():
    fake_raw_obj = MagicMock()
    fake_raw_obj.__enter__.return_value = fake_raw_obj
    fake_raw_obj.postprocess.return_value = np.full((32, 48, 3), 65000, dtype=np.uint16)

    with patch("src.processing.raw_developer.rawpy") as mock_rawpy:
        mock_rawpy.HighlightMode.Blend = 2
        mock_rawpy.HighlightMode.Clip = 0
        mock_rawpy.imread.return_value = fake_raw_obj

        arr = load_raw_16bit("/tmp/fake.ARW", unclipped=True, wb_gains=(1.10, 0.95))
        assert arr.shape == (32, 48, 3)
        assert arr.dtype == np.float32
        assert 0.0 <= arr.min() <= arr.max() <= 1.0

    with patch("src.processing.raw_developer.rawpy", None):
        with pytest.raises(RuntimeError):
            load_raw_16bit("/tmp/fake.ARW")


def test_denoise_sharpen_and_develop(synthetic_rgb_float):
    dn = denoise_ultra_clean(synthetic_rgb_float, chroma_strength=10.0, luma_strength=3.0)
    assert dn.shape == synthetic_rgb_float.shape
    assert np.all((dn >= 0.0) & (dn <= 1.0))

    # Zero-strength branches & large (>256px) multiscale branches
    assert np.allclose(denoise_ultra_clean(synthetic_rgb_float, 0.0, 0.0), synthetic_rgb_float)
    assert np.allclose(sharpen_hd_modern(synthetic_rgb_float, 0.0), synthetic_rgb_float)
    assert np.allclose(apply_s_curve_luminance(synthetic_rgb_float, 0.0), synthetic_rgb_float)
    assert apply_s_curve_luminance(synthetic_rgb_float, 0.2).shape == synthetic_rgb_float.shape

    large_rgb = np.full((300, 300, 3), 0.5, dtype=np.float32)
    assert denoise_ultra_clean(large_rgb, 10.0, 3.0).shape == (300, 300, 3)
    assert apply_preset(large_rgb, "cinestill_800t", 1.0).shape == (300, 300, 3)
    from src.processing.raw_developer import build_gamma_s_curve_lut
    assert build_gamma_s_curve_lut(gamma=0.9, gain=1.1, s_contrast=0.1, highlight_rolloff=0.1).shape == (256,)

    sh = sharpen_hd_modern(synthetic_rgb_float, strength=0.4)
    assert sh.shape == synthetic_rgb_float.shape

    prot = protect_gamut_and_highlights(synthetic_rgb_float, red_tame=0.2, highlight_rolloff=0.2)
    assert prot.shape == synthetic_rgb_float.shape

    dev = develop_base_image(
        synthetic_rgb_float,
        ev=0.35,
        shadows=0.40,
        highlights=0.25,
        wb_temp=0.10,
        wb_tint=-0.05,
        denoise=0.40,
        sharpen=0.40,
    )
    assert dev.shape == synthetic_rgb_float.shape
    assert float(dev.mean()) > float(synthetic_rgb_float.mean())

    # Negative EV branch
    dev_neg = develop_base_image(synthetic_rgb_float, ev=-0.4)
    assert float(dev_neg.mean()) < float(synthetic_rgb_float.mean())


def test_all_presets_and_thumbnails(synthetic_rgb_float):
    names = get_preset_names()
    assert "electric_chroma_hd" in names
    assert "moderna_definida_hd" in names
    assert "editorial_viva_hd" in names
    assert "kodachrome_64" in names
    assert "blancoynegro_platino_hd" in names
    assert "cinestill_800t" in names
    assert "selectivo_platino_hd" in names

    for pid in names:
        meta = get_preset_metadata(pid)
        assert "name" in meta and "description" in meta
        out_full = apply_preset(synthetic_rgb_float, pid, intensity=1.0)
        assert out_full.shape == synthetic_rgb_float.shape
        assert np.all((out_full >= 0.0) & (out_full <= 1.0))

        out_half = apply_preset(synthetic_rgb_float, pid, intensity=0.5)
        assert out_half.shape == synthetic_rgb_float.shape

        thumb = generate_preset_thumbnail(synthetic_rgb_float, pid, size=(48, 32))
        assert thumb.shape == (32, 48, 3)
        assert thumb.dtype == np.uint8


def test_reveal_assistant_analysis_and_auto_params(synthetic_rgb_float):
    # 1. Standard synthetic image
    metrics = analyze_image(synthetic_rgb_float)
    assert "recommended_preset" in metrics
    assert "scene_type" in metrics
    assert len(metrics["tips"]) >= 1

    # 2. Dark neon scene
    dark_neon = np.full((64, 64, 3), 0.06, dtype=np.float32)
    dark_neon[20:30, 20:30, 0] = 0.95
    dark_neon[20:30, 20:30, 1] = 0.15
    m_neon = analyze_image(dark_neon)
    assert m_neon["recommended_preset"] == "electric_chroma_hd"

    # 3. Green nature scene
    green_park = np.full((64, 64, 3), 0.35, dtype=np.float32)
    green_park[..., 1] = 0.65
    m_green = analyze_image(green_park)
    assert m_green["recommended_preset"] == "moderna_definida_hd"

    # 4. Shaded portrait scene
    portrait_shade = np.full((64, 64, 3), 0.12, dtype=np.float32)
    portrait_shade[..., 0] = 0.16
    portrait_shade[..., 2] = 0.10
    m_portrait = analyze_image(portrait_shade)
    assert m_portrait["recommended_preset"] == "editorial_viva_hd"

    # 5. Documentary / low saturation neutral scene with large dimensions (>512) and bright highlights
    doc_scene = np.full((540, 540, 3), 0.50, dtype=np.float32)
    doc_scene[:60, :, :] = 0.96
    m_doc = analyze_image(doc_scene)
    assert m_doc["recommended_preset"] == "kodachrome_64"
    assert m_doc["exposure_status"] == "Altas Luces Fuertes"

    # 5b. Documentary / low saturation neutral scene with balanced midtones
    doc_mid = np.full((64, 64, 3), 0.45, dtype=np.float32)
    m_doc_mid = analyze_image(doc_mid)
    assert m_doc_mid["recommended_preset"] == "kodachrome_64"
    assert m_doc_mid["exposure_status"] == "Equilibrada"

    # 5c. Vibrant urban mural scene (high saturation, non-green)
    urban_mural = np.full((64, 64, 3), 0.45, dtype=np.float32)
    urban_mural[..., 0] = 0.80
    urban_mural[..., 2] = 0.20
    m_urban = analyze_image(urban_mural)
    assert m_urban["recommended_preset"] == "electric_chroma_hd"

    # 6. Auto-develop parameter calculation across dark, bright, and balanced images
    auto_params = compute_auto_develop_params(dark_neon)
    assert auto_params["ev"] > 0.0
    assert auto_params["shadows"] > 0.0
    assert auto_params["recommended_preset"] in PRESET_DEFINITIONS

    bright_img = np.full((64, 64, 3), 0.72, dtype=np.float32)
    auto_bright = compute_auto_develop_params(bright_img)
    assert auto_bright["ev"] < 0.0

    mid_img = np.full((64, 64, 3), 0.50, dtype=np.float32)
    auto_mid = compute_auto_develop_params(mid_img)
    assert auto_mid["ev"] == 0.08


def test_smart_square_crop_and_ai_watermark_strip(synthetic_rgb_float):
    # Horizontal (64x80) -> (64x64)
    x, y, side, _ = compute_smart_square_crop(synthetic_rgb_float)
    assert side == 64
    assert y == 0
    assert 0 <= x <= 16

    # Vertical (80x64) -> (64x64)
    vert = np.transpose(synthetic_rgb_float, (1, 0, 2)).copy()
    xv, yv, side_v, _ = compute_smart_square_crop(vert)
    assert side_v == 64
    assert xv == 0
    assert 0 <= yv <= 16

    # Already square
    sq = synthetic_rgb_float[:, :64, :].copy()
    assert compute_smart_square_crop(sq) == (0, 0, 64, 64)

    # AI watermark & swirl cleaner
    cleaned = strip_ai_watermarks_and_swirl(synthetic_rgb_float)
    assert cleaned.shape == synthetic_rgb_float.shape
    assert np.all((cleaned >= 0.0) & (cleaned <= 1.0))


def test_image_model_preset_auto_develop_and_undo(tmp_path, synthetic_rgb_float):
    img_path = tmp_path / "sample.png"
    float_to_pil(synthetic_rgb_float).save(str(img_path))

    model = ImageModel()
    assert model.load_image(str(img_path))
    assert model.original_image.size == (80, 64)

    # Apply preset
    model.set_preset("electric_chroma_hd", intensity=0.8)
    assert model.active_preset == "electric_chroma_hd"
    assert len(model.history) == 2

    # Undo preset
    assert model.undo()
    assert model.active_preset == "none"

    # Redo preset
    assert model.redo()
    assert model.active_preset == "electric_chroma_hd"

    # Auto-develop
    params = model.auto_develop(apply_recommended_preset=True)
    assert params is not None
    assert model.ev == params["ev"]

    # Smart 1:1 crop
    assert model.smart_crop_square_1x1()
    assert model.original_image.size == (64, 64)

    # Clean AI watermark
    assert model.clean_ai_watermark()


def test_ui_docks_and_main_window_integration(qtbot, tmp_path, synthetic_rgb_float):
    img_path = tmp_path / "ui_test.png"
    float_to_pil(synthetic_rgb_float).save(str(img_path))

    window = ImageEditorApp()
    qtbot.addWidget(window)

    window.create_editor_tab(str(img_path))
    current_tab = window.tabs.currentWidget()
    assert current_tab.model.original_image is not None

    # Exercise PresetGalleryDock UI widgets directly
    window.preset_dock.update_thumbnails(None)
    window.preset_dock.list_widget.setCurrentRow(2)
    window.preset_dock.intensity_slider.setValue(75)
    assert pytest.approx(current_tab.model.preset_intensity, 0.01) == 0.75

    # Exercise RevealAssistantDock UI widgets directly
    window.assistant_dock.update_analysis(None)
    window.assistant_dock.update_analysis(current_tab.model.analyze_current_image())
    window.assistant_dock.btn_apply_recommended.click()

    # Test preset selection via dock signal
    window.on_preset_selected("moderna_definida_hd", 0.9)
    assert current_tab.model.active_preset == "moderna_definida_hd"
    assert pytest.approx(current_tab.model.preset_intensity, 0.01) == 0.9

    # Test intensity slider update
    window.on_preset_intensity_changed("moderna_definida_hd", 0.6)
    assert pytest.approx(current_tab.model.preset_intensity, 0.01) == 0.6

    # Test auto-develop action
    window.trigger_auto_develop(True)
    assert current_tab.model.sharpen > 0.0

    # Test smart 1:1 crop action
    window.trigger_smart_crop_1x1()
    assert current_tab.model.original_image.size == (64, 64)

    # Test clean AI watermark action
    window.trigger_clean_ai_watermark()

    # Test reveal sliders
    window.sl_ev.setValue(25)
    assert pytest.approx(current_tab.model.ev, 0.01) == 0.25

    # Test reset adjustments
    window.reset_adjustments()
    assert current_tab.model.active_preset == "none"
    assert current_tab.model.ev == 0.0

    # Test Qwen AI Chat integration & Custom Preset creation via chat
    with patch("src.ui.assistant_dock.query_qwen_agent") as mock_qwen:
        mock_qwen.return_value = {
            "reply": "He aplicado CineStill 800T al 80%, subido sombras y guardado el preset Nocturno Custom.",
            "action": "update",
            "preset": "cinestill_800t",
            "preset_intensity": 0.80,
            "adjustments": {
                "ev": 0.25,
                "shadows": 0.35,
                "highlights": 0.20,
                "wb_temp": 0.15,
                "denoise": 0.30,
                "sharpen": 0.40,
                "brightness": 1.05,
                "contrast": 1.10,
                "saturation": 1.15,
            },
            "save_preset_as": "Nocturno Custom",
        }
        window.assistant_dock.send_chat_message("Pon cinestill al 80%, abre sombras y guárdalo como Nocturno Custom", run_sync=True)
        assert current_tab.model.active_preset == "custom_nocturno_custom"
        assert "custom_nocturno_custom" in PRESET_DEFINITIONS

    # Test chat global actions (auto_develop, smart_crop_1x1, clean_ai, undo, reset)
    window.on_chat_command_executed({"action": "auto_develop"})
    window.on_chat_command_executed({"action": "smart_crop_1x1"})
    window.on_chat_command_executed({"action": "clean_ai"})
    window.on_chat_command_executed({"action": "undo"})
    window.on_chat_command_executed({"action": "reset"})
    window.on_chat_command_executed({"action": "update"})  # no-op empty update


def test_custom_presets_and_llm_chat_agent(tmp_path, synthetic_rgb_float):
    import json
    from src.processing.preset_engine import (
        register_custom_preset,
        save_custom_presets,
        load_custom_presets,
    )
    from src.processing.llm_chat_agent import (
        list_embedded_qwen_models,
        resolve_model_path,
        ensure_model_downloaded,
        get_embedded_llama,
        build_system_prompt,
        _extract_json_dict,
        parse_natural_language_fallback,
        normalize_agent_response,
        query_qwen_agent,
    )

    # 1. Custom preset registration, persistence, and grading
    custom_file = str(tmp_path / "custom_presets.json")
    pid = register_custom_preset(
        name="Mi Dorado Cálido",
        recipe={
            "base_preset": "editorial_viva_hd",
            "ev": 0.2,
            "shadows": 0.3,
            "highlights": 0.1,
            "wb_temp": 0.2,
            "denoise": 0.2,
            "sharpen": 0.3,
            "brightness": 1.05,
            "contrast": 1.1,
            "saturation": 1.15,
        },
        persist=False,
    )
    assert pid == "custom_mi_dorado_c_lido"
    graded = apply_preset(synthetic_rgb_float, pid, intensity=1.0)
    assert graded.shape == synthetic_rgb_float.shape
    assert save_custom_presets(custom_file) is True
    assert load_custom_presets(custom_file) >= 1
    assert load_custom_presets(str(tmp_path / "nonexistent.json")) == 0

    # 2. Natural language fallback coverage across all branches
    state = {
        "active_preset": "electric_chroma_hd",
        "preset_intensity": 0.9,
        "ev": 0.0,
        "shadows": 0.0,
        "highlights": 0.0,
        "wb_temp": 0.0,
        "denoise": 0.0,
        "sharpen": 0.0,
        "brightness": 1.0,
        "contrast": 1.0,
        "saturation": 1.0,
        "scene_type": "Urbano",
        "recommended_preset": "electric_chroma_hd",
    }

    assert parse_natural_language_fallback("deshacer cambio", state)["action"] == "undo"
    assert parse_natural_language_fallback("reinicia todo de cero", state)["action"] == "reset"
    assert parse_natural_language_fallback("auto revela la foto", state)["action"] == "auto_develop"
    assert parse_natural_language_fallback("recorta formato cuadrado 1:1", state)["action"] == "smart_crop_1x1"
    assert parse_natural_language_fallback("limpiar ia y marca de agua", state)["action"] == "clean_ai"

    r_mod = parse_natural_language_fallback(
        "aplica el preset recomendado al 70%, más luz, abre sombras, protege altas luces, "
        "más cálida, sin grano, más nitidez, más contraste, más saturación y guárdalo como Super Urbano",
        state,
    )
    assert r_mod["preset"] == "electric_chroma_hd"
    assert r_mod["preset_intensity"] == 0.70
    assert r_mod["save_preset_as"] == "Super Urbano"
    assert r_mod["adjustments"]["ev"] > 0
    assert r_mod["adjustments"]["shadows"] > 0
    assert r_mod["adjustments"]["highlights"] > 0
    assert r_mod["adjustments"]["wb_temp"] > 0
    assert r_mod["adjustments"]["denoise"] > 0
    assert r_mod["adjustments"]["sharpen"] > 0
    assert r_mod["adjustments"]["contrast"] > 1.0
    assert r_mod["adjustments"]["saturation"] > 1.0

    r_inv = parse_natural_language_fallback(
        "pon kodachrome, suaviza el preset, exposición a -0.4, oscurece sombras, más fría, menos contraste y menos saturación",
        state,
    )
    assert r_inv["preset"] == "kodachrome_64"
    assert r_inv["adjustments"]["ev"] == -0.4
    assert r_inv["adjustments"]["shadows"] < 0
    assert r_inv["adjustments"]["wb_temp"] < 0
    assert r_inv["adjustments"]["contrast"] < 1.0
    assert r_inv["adjustments"]["saturation"] < 1.0

    r_dark = parse_natural_language_fallback("menos luz", state)
    assert r_dark["adjustments"]["ev"] < 0

    r_help = parse_natural_language_fallback("hola qué tal", state)
    assert "Puedo aplicar" in r_help["reply"]

    # 3. JSON extraction & normalization
    assert _extract_json_dict("") is None
    assert _extract_json_dict("<think>pensando</think>```json\n{\"reply\": \"ok\", \"action\": \"update\"}\n```")["reply"] == "ok"

    norm = normalize_agent_response(
        {
            "reply": "Listo",
            "action": "invalid_action",
            "preset": "cinestill_800t",
            "preset_intensity": 85,  # 0..100 scale auto-normalized to 0.85
            "adjustments": {"ev": 0.5, "shadows": "0.3"},
            "save_preset_as": "Mi Cine",
        },
        "pon cinestill",
        state,
    )
    assert norm["preset"] == "cinestill_800t"
    assert norm["preset_intensity"] == 0.85
    assert norm["adjustments"]["ev"] == 0.5
    assert norm["save_preset_as"] == "Mi Cine"

    # 4. Embedded in-process llama_cpp GGUF queries (mocked & live fallback)
    assert "PRESETS DISPONIBLES" in build_system_prompt(state)

    models = list_embedded_qwen_models()
    assert len(models) >= 2
    assert resolve_model_path("qwen2.5:0.5b").endswith("qwen2.5-0.5b-instruct.gguf")
    assert resolve_model_path("qwen2.5:1.5b").endswith("qwen2.5-1.5b-instruct.gguf")

    fake_llama = MagicMock()
    fake_llama.create_chat_completion.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "reply": "Aplicado blanco y negro platino.",
                            "action": "update",
                            "preset": "blancoynegro_platino_hd",
                            "preset_intensity": 0.9,
                            "adjustments": {"contrast": 1.15},
                            "save_preset_as": None,
                        }
                    )
                }
            }
        ]
    }
    with patch("src.processing.llm_chat_agent.get_embedded_llama", return_value=fake_llama):
        res = query_qwen_agent(
            "pon blanco y negro",
            state,
            model_name="Qwen 2.5 1.5B (Integrado Preciso)",
            history=[{"role": "user", "content": "hola"}],
        )
        assert res["preset"] == "blancoynegro_platino_hd"
        assert res["model_used"] == "qwen2.5-1.5b-instruct.gguf"

    # Test automatic on-demand GGUF download when file is absent in models_dir
    dl_dir = tmp_path / "models_dl"
    progress_calls = []

    class _FakeResp:
        headers = {"Content-Length": "16"}

        def __init__(self):
            self._chunks = [b"GGUF_FAKE_chunk1", b""]

        def read(self, _n):
            return self._chunks.pop(0)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        dl_path = ensure_model_downloaded(
            "Qwen 2.5 0.5B (Integrado Rápido)",
            models_dir=str(dl_dir),
            progress_callback=lambda d, t: progress_calls.append((d, t)),
        )
        assert dl_path.endswith("qwen2.5-0.5b-instruct.gguf")
        assert len(progress_calls) == 1
        assert progress_calls[0] == (16, 16)
        # Second call returns cached file without downloading again
        assert ensure_model_downloaded("qwen2.5:0.5b", models_dir=str(dl_dir)) == dl_path

    # Test download failure cleans up .part file and raises
    dl_fail_dir = tmp_path / "models_fail"
    with patch("urllib.request.urlopen", side_effect=OSError("Network unreachable")):
        with pytest.raises(OSError):
            ensure_model_downloaded("qwen2.5:1.5b", models_dir=str(dl_fail_dir))

    # Test missing model fallback to built-in NLU
    res_fallback = query_qwen_agent(
        "pon cinestill al 75%",
        state,
        model_name="nonexistent.gguf",
        models_dir=str(tmp_path),
    )
    assert res_fallback["preset"] == "cinestill_800t"
    assert res_fallback["preset_intensity"] == 0.75
    assert res_fallback["model_used"] == "fallback-nlu"


def test_interactive_history_jump_and_decluttered_ui(qtbot, tmp_path, synthetic_rgb_float):
    img_path = tmp_path / "history_jump.png"
    float_to_pil(synthetic_rgb_float).save(str(img_path))

    window = ImageEditorApp()
    qtbot.addWidget(window)
    window.show()

    window.create_editor_tab(str(img_path))
    tab = window.tabs.currentWidget()
    model = tab.model

    # 1. Verify decluttered defaults (secondary toolbar, classic sliders, diagnostic details hidden)
    assert window.draw_toolbar.isVisible() is False
    assert window.classic_container.isVisible() is False
    assert window.assistant_dock.details_container.isVisible() is False

    # Toggling collapsible UI elements works cleanly
    window.toggle_draw_toolbar_act.setChecked(True)
    assert window.draw_toolbar.isVisible() is True
    window.toggle_draw_toolbar_act.setChecked(False)
    assert window.draw_toolbar.isVisible() is False

    window.btn_toggle_classic.setChecked(True)
    assert window.classic_container.isVisible() is True
    window.assistant_dock.btn_toggle_details.setChecked(True)
    assert window.assistant_dock.details_container.isVisible() is True

    # 2. Build a 4-step history timeline:
    #    [0] Load Image (80x64, preset='none', ev=0.0)
    #    [1] Preset: CineStill 800T (80x64, preset='cinestill_800t', ev=0.0)
    #    [2] Ajuste: Exposición (80x64, preset='cinestill_800t', ev=0.45)
    #    [3] Smart Crop 1:1 (64x64, preset='cinestill_800t', ev=0.45)
    orig_pixels = np.array(model.display_image).copy()

    window.on_preset_selected("cinestill_800t", 0.85)
    preset_pixels = np.array(model.display_image).copy()
    assert not np.array_equal(orig_pixels, preset_pixels)

    window.sl_ev.setValue(45)
    window.sl_ev.sliderReleased.emit()
    ev_pixels = np.array(model.display_image).copy()
    assert pytest.approx(model.ev, 0.01) == 0.45
    assert not np.array_equal(preset_pixels, ev_pixels)

    window.trigger_smart_crop_1x1()
    assert model.original_image.size == (64, 64)
    assert len(model.get_history_timeline()) == 4
    assert window.history_list.count() == 4
    assert model.current_history_index == 3

    # 3. Select history point [0] ("Load Image") in the UI list -> restores original image & sliders!
    window.history_list.setCurrentRow(0)
    assert model.current_history_index == 0
    assert model.original_image.size == (80, 64)
    assert model.active_preset == "none"
    assert model.ev == 0.0
    assert window.sl_ev.value() == 0
    assert window.preset_dock.current_preset_id == "none"
    assert np.array_equal(np.array(model.display_image), orig_pixels)
    # Full timeline of 4 items remains visible in history_list so user can jump forward again
    assert window.history_list.count() == 4

    # 4. Select history point [1] ("Preset: CineStill 800T") -> restores exact preset state!
    window.history_list.setCurrentRow(1)
    assert model.current_history_index == 1
    assert model.active_preset == "cinestill_800t"
    assert pytest.approx(model.preset_intensity, 0.01) == 0.85
    assert model.ev == 0.0
    assert np.array_equal(np.array(model.display_image), preset_pixels)

    # 5. Select history point [3] ("Smart Crop 1:1") -> jumps all the way forward!
    window.history_list.setCurrentRow(3)
    assert model.current_history_index == 3
    assert model.original_image.size == (64, 64)
    assert pytest.approx(model.ev, 0.01) == 0.45
    assert window.sl_ev.value() == 45

    # 6. Uncommitted live tweak reverted by clicking the currently active history item
    model.set_reveal_params(ev=-0.50)
    assert pytest.approx(model.ev, 0.01) == -0.50
    window._on_history_item_clicked(window.history_list.item(3))
    assert pytest.approx(model.ev, 0.01) == 0.45

    # 7. Reset Adjustments stores the reset state (not the pre-reset state) and out-of-bounds jump returns False
    window.reset_adjustments()
    assert model.active_preset == "none"
    assert model.ev == 0.0
    assert model.history[-1]["active_preset"] == "none"
    assert model.history[-1]["ev"] == 0.0
    assert model.jump_to_history(-1) is False
    assert model.jump_to_history(999) is False
    assert model.commit_adjustments("No-op") is False

    # 8. Preset intensity slider release commits a history entry when changed
    prev_len = len(model.history)
    window.on_preset_selected("kodachrome_64", 1.0)
    assert len(model.history) == prev_len + 1
    window.preset_dock.intensity_slider.setValue(60)
    window.preset_dock.intensity_slider.sliderReleased.emit()
    assert len(model.history) == prev_len + 2
    assert pytest.approx(model.history[-1]["preset_intensity"], 0.01) == 0.60

