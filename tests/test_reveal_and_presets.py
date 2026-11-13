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
