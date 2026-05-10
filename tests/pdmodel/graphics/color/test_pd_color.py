from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern

# ---------- device singletons ----------


def test_device_gray_singleton_metadata() -> None:
    cs = PDDeviceGray.INSTANCE
    assert cs.get_name() == "DeviceGray"
    assert cs.get_number_of_components() == 1
    assert PDDeviceGray.INSTANCE is cs


def test_device_rgb_singleton_metadata() -> None:
    cs = PDDeviceRGB.INSTANCE
    assert cs.get_name() == "DeviceRGB"
    assert cs.get_number_of_components() == 3
    assert PDDeviceRGB.INSTANCE is cs


def test_device_cmyk_singleton_metadata() -> None:
    cs = PDDeviceCMYK.INSTANCE
    assert cs.get_name() == "DeviceCMYK"
    assert cs.get_number_of_components() == 4
    assert PDDeviceCMYK.INSTANCE is cs


def test_device_color_spaces_extend_pd_color_space() -> None:
    assert isinstance(PDDeviceGray.INSTANCE, PDColorSpace)
    assert isinstance(PDDeviceRGB.INSTANCE, PDColorSpace)
    assert isinstance(PDDeviceCMYK.INSTANCE, PDColorSpace)


# ---------- initial colors (black) ----------


def test_device_gray_initial_color_is_black() -> None:
    assert PDDeviceGray.INSTANCE.get_initial_color().get_components() == [0.0]


def test_device_rgb_initial_color_is_black() -> None:
    assert PDDeviceRGB.INSTANCE.get_initial_color().get_components() == [0.0, 0.0, 0.0]


def test_device_cmyk_initial_color_is_black() -> None:
    assert PDDeviceCMYK.INSTANCE.get_initial_color().get_components() == [
        0.0,
        0.0,
        0.0,
        1.0,
    ]


# ---------- device color space CO surface ----------


def test_device_color_space_cos_object_is_name() -> None:
    cos = PDDeviceRGB.INSTANCE.get_cos_object()
    assert isinstance(cos, COSName)
    assert cos.get_name() == "DeviceRGB"


# ---------- PDColor accessors ----------


def test_pd_color_basic_accessors() -> None:
    color = PDColor([1.0, 0.5, 0.0], PDDeviceRGB.INSTANCE)
    assert color.get_components() == [1.0, 0.5, 0.0]
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    assert color.get_pattern_name() is None
    assert color.is_pattern() is False


def test_pd_color_components_are_defensively_copied() -> None:
    src = [1.0, 0.5, 0.0]
    color = PDColor(src, PDDeviceRGB.INSTANCE)
    src[0] = 99.0
    assert color.get_components() == [1.0, 0.5, 0.0]
    out = color.get_components()
    out[0] = 42.0
    assert color.get_components() == [1.0, 0.5, 0.0]


# ---------- PDColor round-trips ----------


def test_pd_color_to_cos_array_round_trip() -> None:
    original = PDColor([1.0, 0.5, 0.0], PDDeviceRGB.INSTANCE)
    array = original.to_cos_array()
    assert isinstance(array, COSArray)
    assert array.size() == 3
    assert isinstance(array.get(0), COSFloat)
    assert array.to_float_array() == [1.0, 0.5, 0.0]

    restored = PDColor.from_cos_array(array, PDDeviceRGB.INSTANCE)
    assert restored.get_components() == [1.0, 0.5, 0.0]
    assert restored.get_color_space() is PDDeviceRGB.INSTANCE
    assert restored.get_pattern_name() is None


def test_pd_color_with_pattern_name_round_trip() -> None:
    pattern = COSName.get_pdf_name("P1")
    original = PDColor([0.25, 0.75, 0.5], PDDeviceRGB.INSTANCE, pattern)
    assert original.is_pattern() is True

    array = original.to_cos_array()
    assert array.size() == 4
    assert isinstance(array.get(3), COSName)

    restored = PDColor.from_cos_array(array, PDDeviceRGB.INSTANCE)
    assert restored.get_components() == [0.25, 0.75, 0.5]
    assert restored.get_pattern_name() == pattern
    assert restored.is_pattern() is True


def test_pd_color_cmyk_round_trip() -> None:
    # values exact in IEEE-754 float32 to survive COSFloat truncation
    original = PDColor([0.125, 0.25, 0.5, 0.75], PDDeviceCMYK.INSTANCE)
    array = original.to_cos_array()
    restored = PDColor.from_cos_array(array, PDDeviceCMYK.INSTANCE)
    assert restored.get_components() == original.get_components()
    assert restored.get_color_space() is PDDeviceCMYK.INSTANCE


def test_pd_color_gray_round_trip() -> None:
    original = PDColor([0.5], PDDeviceGray.INSTANCE)
    array = original.to_cos_array()
    restored = PDColor.from_cos_array(array, PDDeviceGray.INSTANCE)
    assert restored.get_components() == original.get_components()
    assert restored.get_color_space() is PDDeviceGray.INSTANCE


# ---------- PDColor.to_rgb ----------


def test_to_rgb_device_gray_midtone() -> None:
    rgb = PDColor([0.5], PDDeviceGray.INSTANCE).to_rgb()
    assert rgb == (0.5, 0.5, 0.5)


def test_to_rgb_device_rgb_pure_red() -> None:
    rgb = PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE).to_rgb()
    assert rgb == (1.0, 0.0, 0.0)


def test_to_rgb_device_cmyk_pure_red() -> None:
    rgb = PDColor([0.0, 1.0, 1.0, 0.0], PDDeviceCMYK.INSTANCE).to_rgb()
    assert rgb[0] == pytest.approx(1.0, abs=1e-6)
    assert rgb[1] == pytest.approx(0.0, abs=1e-6)
    assert rgb[2] == pytest.approx(0.0, abs=1e-6)


def test_to_rgb_device_cmyk_pure_black_via_k() -> None:
    rgb = PDColor([0.0, 0.0, 0.0, 1.0], PDDeviceCMYK.INSTANCE).to_rgb()
    assert rgb == (0.0, 0.0, 0.0)


def test_to_rgb_lab_white_round_trip() -> None:
    rgb = PDColor([100.0, 0.0, 0.0], PDLab()).to_rgb()
    assert rgb[0] == pytest.approx(1.0, abs=0.05)
    assert rgb[1] == pytest.approx(1.0, abs=0.05)
    assert rgb[2] == pytest.approx(1.0, abs=0.05)


def test_to_rgb_pattern_raises_not_implemented() -> None:
    color = PDColor([], PDPattern(), COSName.get_pdf_name("P1"))
    with pytest.raises(NotImplementedError):
        color.to_rgb()


# ---------- PDColor.to_rgba ----------


def test_to_rgba_default_alpha_is_opaque() -> None:
    rgba = PDColor([1.0, 0.5, 0.0], PDDeviceRGB.INSTANCE).to_rgba()
    assert rgba == (1.0, 0.5, 0.0, 1.0)


def test_to_rgba_explicit_alpha_round_trip() -> None:
    color = PDColor([0.25, 0.5, 0.75], PDDeviceRGB.INSTANCE)
    rgba = color.to_rgba(0.4)
    assert rgba[:3] == color.to_rgb()
    assert rgba[3] == pytest.approx(0.4, abs=1e-12)


def test_to_rgba_alpha_zero_and_one_boundaries() -> None:
    color = PDColor([0.5], PDDeviceGray.INSTANCE)
    assert color.to_rgba(0.0) == (0.5, 0.5, 0.5, 0.0)
    assert color.to_rgba(1.0) == (0.5, 0.5, 0.5, 1.0)


def test_to_rgba_alpha_below_zero_raises() -> None:
    color = PDColor([0.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    with pytest.raises(ValueError):
        color.to_rgba(-0.01)


def test_to_rgba_alpha_above_one_raises() -> None:
    color = PDColor([0.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    with pytest.raises(ValueError):
        color.to_rgba(1.01)


def test_to_rgba_alpha_nan_raises() -> None:
    color = PDColor([0.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    with pytest.raises(ValueError):
        color.to_rgba(float("nan"))


def test_to_rgba_cmyk_uses_to_rgb_then_appends() -> None:
    color = PDColor([0.0, 1.0, 1.0, 0.0], PDDeviceCMYK.INSTANCE)
    rgba = color.to_rgba(0.5)
    assert rgba[0] == pytest.approx(1.0, abs=1e-6)
    assert rgba[1] == pytest.approx(0.0, abs=1e-6)
    assert rgba[2] == pytest.approx(0.0, abs=1e-6)
    assert rgba[3] == pytest.approx(0.5, abs=1e-12)


# ---------- PDColor.composite_over ----------


def test_composite_over_full_alpha_returns_top() -> None:
    out = PDColor.composite_over((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 1.0)
    assert out == (1.0, 0.0, 0.0)


def test_composite_over_zero_alpha_returns_bottom() -> None:
    out = PDColor.composite_over((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.0)
    assert out == (0.0, 0.0, 1.0)


def test_composite_over_half_alpha_blends_evenly() -> None:
    out = PDColor.composite_over((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.5)
    assert out[0] == pytest.approx(0.5, abs=1e-12)
    assert out[1] == pytest.approx(0.0, abs=1e-12)
    assert out[2] == pytest.approx(0.5, abs=1e-12)


def test_composite_over_quarter_alpha_blends_proportionally() -> None:
    out = PDColor.composite_over((0.8, 0.4, 0.2), (0.0, 0.0, 0.0), 0.25)
    assert out[0] == pytest.approx(0.2, abs=1e-12)
    assert out[1] == pytest.approx(0.1, abs=1e-12)
    assert out[2] == pytest.approx(0.05, abs=1e-12)


def test_composite_over_clamps_inputs() -> None:
    # Out-of-range components are clamped to [0,1] before blending.
    out = PDColor.composite_over((2.0, -0.5, 0.5), (0.0, 0.0, 0.0), 1.0)
    assert out == (1.0, 0.0, 0.5)


def test_composite_over_supports_cmyk_arity() -> None:
    out = PDColor.composite_over(
        (0.0, 1.0, 1.0, 0.0), (1.0, 0.0, 0.0, 0.0), 0.5
    )
    assert out[0] == pytest.approx(0.5, abs=1e-12)
    assert out[1] == pytest.approx(0.5, abs=1e-12)
    assert out[2] == pytest.approx(0.5, abs=1e-12)
    assert out[3] == pytest.approx(0.0, abs=1e-12)


def test_composite_over_mismatched_arities_raises() -> None:
    with pytest.raises(ValueError):
        PDColor.composite_over((1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), 0.5)


def test_composite_over_alpha_out_of_range_raises() -> None:
    with pytest.raises(ValueError):
        PDColor.composite_over((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), -0.1)
    with pytest.raises(ValueError):
        PDColor.composite_over((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 1.1)


def test_composite_over_alpha_nan_raises() -> None:
    with pytest.raises(ValueError):
        PDColor.composite_over(
            (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), float("nan")
        )


# ---------- constructor variants (upstream parity) ----------


def test_constructor_variant_components_and_color_space() -> None:
    color = PDColor([0.1, 0.2, 0.3], PDDeviceRGB.INSTANCE)
    assert color.get_components() == [0.1, 0.2, 0.3]
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    assert color.get_pattern_name() is None


def test_constructor_variant_upstream_pattern_name_then_cs() -> None:
    # Upstream signature: PDColor(components, patternName, colorSpace).
    name = COSName.get_pdf_name("P1")
    pattern_cs = PDPattern()
    color = PDColor([0.5, 0.25], name, pattern_cs)
    assert color.get_components() == [0.5, 0.25]
    assert color.get_color_space() is pattern_cs
    assert color.get_pattern_name() is name


def test_constructor_variant_legacy_cs_then_pattern_name() -> None:
    # Legacy pypdfbox positional order — also still supported.
    name = COSName.get_pdf_name("P2")
    color = PDColor([0.5, 0.25, 0.75], PDDeviceRGB.INSTANCE, name)
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    assert color.get_pattern_name() is name


def test_constructor_variant_pattern_keyword() -> None:
    name = COSName.get_pdf_name("P3")
    color = PDColor([0.5], PDDeviceGray.INSTANCE, pattern=name)
    assert color.get_pattern_name() is name


def test_constructor_variant_cos_array_round_trip() -> None:
    # Upstream signature: PDColor(COSArray, PDColorSpace) parses both
    # components and an optional trailing pattern name.
    src = PDColor([0.25, 0.5, 0.75], PDDeviceRGB.INSTANCE)
    array = src.to_cos_array()
    rebuilt = PDColor(array, PDDeviceRGB.INSTANCE)
    assert rebuilt.get_components() == [0.25, 0.5, 0.75]
    assert rebuilt.get_color_space() is PDDeviceRGB.INSTANCE
    assert rebuilt.get_pattern_name() is None


def test_constructor_variant_cos_array_keeps_pattern_name() -> None:
    # Uncolored tiling form: 3 tint components + pattern name, against a
    # Pattern color space whose underlying is DeviceRGB. Using DeviceRGB
    # arity (3) avoids the PDFBOX-4279 pad-to-N reshape inside
    # ``get_components()``.
    from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern

    pattern_cs = PDPattern(PDDeviceRGB.INSTANCE)
    name = COSName.get_pdf_name("P1")
    src = PDColor([0.5, 0.25, 0.75], pattern_cs, name)
    array = src.to_cos_array()
    rebuilt = PDColor(array, pattern_cs)
    assert rebuilt.get_components() == [0.5, 0.25, 0.75]
    assert rebuilt.get_pattern_name() == name


def test_constructor_variant_cos_array_disallows_extra_args() -> None:
    src = PDColor([0.5], PDDeviceGray.INSTANCE)
    array = src.to_cos_array()
    with pytest.raises(TypeError):
        PDColor(array, PDDeviceGray.INSTANCE, COSName.get_pdf_name("P"))
    with pytest.raises(TypeError):
        PDColor(
            array,
            PDDeviceGray.INSTANCE,
            pattern=COSName.get_pdf_name("P"),
        )


def test_constructor_variant_pattern_name_requires_third_color_space() -> None:
    # PDColor(components, COSName) without a third PDColorSpace is invalid.
    with pytest.raises(TypeError):
        PDColor([0.5], COSName.get_pdf_name("P"))


def test_constructor_variant_pattern_keyword_conflict_raises() -> None:
    name = COSName.get_pdf_name("P1")
    with pytest.raises(TypeError):
        PDColor(
            [0.5],
            PDDeviceGray.INSTANCE,
            COSName.get_pdf_name("P2"),
            pattern=name,
        )


# ---------- get_java_color (AWT replacement) ----------


def test_get_java_color_matches_to_rgb_for_device_rgb() -> None:
    color = PDColor([0.25, 0.5, 0.75], PDDeviceRGB.INSTANCE)
    assert color.get_java_color() == color.to_rgb()


def test_get_java_color_returns_three_floats_in_unit_range() -> None:
    color = PDColor([0.0, 1.0, 1.0, 0.0], PDDeviceCMYK.INSTANCE)
    rgb = color.get_java_color()
    assert isinstance(rgb, tuple)
    assert len(rgb) == 3
    for component in rgb:
        assert 0.0 <= component <= 1.0


# ---------- to_rgb_image / to_raw_image (Pillow) ----------


def test_to_rgb_image_default_size_is_one_by_one() -> None:
    from PIL import Image

    color = PDColor([1.0, 0.5, 0.0], PDDeviceRGB.INSTANCE)
    img = color.to_rgb_image()
    assert isinstance(img, Image.Image)
    assert img.size == (1, 1)
    assert img.mode == "RGB"


def test_to_rgb_image_custom_size_round_trip() -> None:
    color = PDColor([0.0, 1.0, 0.0], PDDeviceRGB.INSTANCE)
    img = color.to_rgb_image(4, 5)
    assert img.size == (4, 5)
    assert img.getpixel((2, 3)) == (0, 255, 0)


def test_to_raw_image_for_device_gray_uses_l_mode() -> None:
    img = PDColor([0.25], PDDeviceGray.INSTANCE).to_raw_image(2, 2)
    assert img.mode == "L"
    assert img.size == (2, 2)


def test_to_raw_image_for_device_cmyk_uses_cmyk_mode() -> None:
    img = PDColor(
        [0.0, 1.0, 1.0, 0.0], PDDeviceCMYK.INSTANCE
    ).to_raw_image(1, 1)
    assert img.mode == "CMYK"


def test_to_raw_image_for_lab_falls_through_to_srgb() -> None:
    img = PDColor([100.0, 0.0, 0.0], PDLab()).to_raw_image(1, 1)
    assert img.mode == "RGB"


# ---------- Indexed lookup parity ----------


def test_indexed_to_rgb_reads_n_bytes_from_lookup_table() -> None:
    from pypdfbox.cos import COSArray, COSInteger, COSString
    from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed

    # 3-entry palette: white, red, blue (DeviceRGB base, 1 byte/component).
    palette = bytes([255, 255, 255, 255, 0, 0, 0, 0, 255])
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(2))
    arr.add(COSString(palette))
    indexed = PDIndexed(arr)

    assert PDColor([0], indexed).to_rgb() == (1.0, 1.0, 1.0)
    assert PDColor([1], indexed).to_rgb() == (1.0, 0.0, 0.0)
    assert PDColor([2], indexed).to_rgb() == (0.0, 0.0, 1.0)


def test_indexed_to_rgb_clamps_index_to_hival() -> None:
    from pypdfbox.cos import COSArray, COSInteger, COSString
    from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed

    palette = bytes([255, 0, 0, 0, 255, 0])  # 2 entries
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(1))
    arr.add(COSString(palette))
    indexed = PDIndexed(arr)

    # Index 99 is clamped to hival=1 -> green palette entry.
    assert PDColor([99], indexed).to_rgb() == (0.0, 1.0, 0.0)


def test_indexed_to_rgb_with_device_gray_base_reads_one_byte_per_entry() -> None:
    from pypdfbox.cos import COSArray, COSInteger, COSString
    from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
    from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed

    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceGray.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(2))
    arr.add(COSString(bytes([0, 128, 255])))
    indexed = PDIndexed(arr)

    assert PDColor([0], indexed).to_rgb() == (0.0, 0.0, 0.0)
    rgb_mid = PDColor([1], indexed).to_rgb()
    assert rgb_mid[0] == pytest.approx(128 / 255.0, abs=1e-6)
    assert rgb_mid[0] == rgb_mid[1] == rgb_mid[2]
    assert PDColor([2], indexed).to_rgb() == (1.0, 1.0, 1.0)
