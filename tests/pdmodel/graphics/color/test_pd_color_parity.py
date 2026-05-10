from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation

# ---------- get_components / set_components round-trip ----------


def test_get_components_round_trip() -> None:
    color = PDColor([0.1, 0.2, 0.3], PDDeviceRGB.INSTANCE)
    assert color.get_components() == [0.1, 0.2, 0.3]


def test_set_components_replaces_values() -> None:
    color = PDColor([0.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    color.set_components([0.5, 0.6, 0.7])
    assert color.get_components() == [0.5, 0.6, 0.7]


def test_set_components_defensively_copies_input() -> None:
    color = PDColor([0.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    src = [0.1, 0.2, 0.3]
    color.set_components(src)
    src[0] = 99.0
    assert color.get_components() == [0.1, 0.2, 0.3]


def test_set_components_coerces_to_float() -> None:
    color = PDColor([0.0], PDDeviceGray.INSTANCE)
    color.set_components([1])  # int gets coerced
    components = color.get_components()
    assert components == [1.0]
    assert isinstance(components[0], float)


# ---------- get_color_space_name ----------


def test_get_color_space_name_device_rgb() -> None:
    color = PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    assert color.get_color_space_name() == "DeviceRGB"


def test_get_color_space_name_device_gray() -> None:
    color = PDColor([0.5], PDDeviceGray.INSTANCE)
    assert color.get_color_space_name() == "DeviceGray"


def test_get_color_space_name_device_cmyk() -> None:
    color = PDColor([0.0, 0.0, 0.0, 1.0], PDDeviceCMYK.INSTANCE)
    assert color.get_color_space_name() == "DeviceCMYK"


def test_get_color_space_name_pattern() -> None:
    color = PDColor([], PDPattern(), COSName.get_pdf_name("P1"))
    assert color.get_color_space_name() == "Pattern"


# ---------- to_cos_array ----------


def test_to_cos_array_contains_cos_float_entries() -> None:
    color = PDColor([0.25, 0.5, 0.75], PDDeviceRGB.INSTANCE)
    array = color.to_cos_array()
    assert isinstance(array, COSArray)
    assert array.size() == 3
    for index in range(array.size()):
        assert isinstance(array.get(index), COSFloat)


def test_to_cos_array_includes_pattern_name_after_components() -> None:
    pattern_name = COSName.get_pdf_name("P1")
    color = PDColor([0.5, 0.5, 0.5], PDDeviceRGB.INSTANCE, pattern_name)
    array = color.to_cos_array()
    assert array.size() == 4
    assert isinstance(array.get(0), COSFloat)
    assert isinstance(array.get(1), COSFloat)
    assert isinstance(array.get(2), COSFloat)
    assert isinstance(array.get(3), COSName)
    assert array.get(3) is pattern_name


# ---------- is_pattern ----------


def test_is_pattern_true_for_pattern_color_space_with_name() -> None:
    color = PDColor([], PDPattern(), COSName.get_pdf_name("P1"))
    assert color.is_pattern() is True


def test_is_pattern_true_for_pattern_color_space_without_name() -> None:
    # Even without an explicit pattern name, a Pattern color space alone
    # should report as pattern (upstream PDFBox semantics).
    color = PDColor([], PDPattern())
    assert color.is_pattern() is True


def test_is_pattern_false_for_device_rgb() -> None:
    color = PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    assert color.is_pattern() is False


# ---------- equality / hashing ----------


def test_equal_with_same_components_and_same_color_space() -> None:
    a = PDColor([0.5, 0.25, 0.75], PDDeviceRGB.INSTANCE)
    b = PDColor([0.5, 0.25, 0.75], PDDeviceRGB.INSTANCE)
    assert a == b
    assert hash(a) == hash(b)


def test_not_equal_with_different_components() -> None:
    a = PDColor([0.5, 0.25, 0.75], PDDeviceRGB.INSTANCE)
    b = PDColor([0.5, 0.25, 0.5], PDDeviceRGB.INSTANCE)
    assert a != b


def test_not_equal_with_different_color_space() -> None:
    a = PDColor([0.5], PDDeviceGray.INSTANCE)
    b = PDColor([0.5], PDDeviceGray.INSTANCE)
    assert a == b
    c = PDColor([0.5, 0.25, 0.75], PDDeviceRGB.INSTANCE)
    assert a != c


def test_not_equal_to_non_pdcolor() -> None:
    a = PDColor([0.5], PDDeviceGray.INSTANCE)
    assert a != "not a pdcolor"
    assert a != [0.5]


def test_equal_with_same_pattern_name() -> None:
    name = COSName.get_pdf_name("P1")
    a = PDColor([0.5, 0.25, 0.75], PDDeviceRGB.INSTANCE, name)
    b = PDColor([0.5, 0.25, 0.75], PDDeviceRGB.INSTANCE, name)
    assert a == b
    assert hash(a) == hash(b)


# ---------- to_rgb_image / to_raw_image ----------


def test_to_rgb_image_returns_pillow_image() -> None:
    from PIL import Image

    color = PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    img = color.to_rgb_image(2, 3)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"
    assert img.size == (2, 3)
    assert img.getpixel((0, 0)) == (255, 0, 0)


def test_to_raw_image_uses_native_mode_for_device_spaces() -> None:
    from PIL import Image

    img = PDColor([0.5], PDDeviceGray.INSTANCE).to_raw_image(1, 1)
    assert isinstance(img, Image.Image)
    assert img.mode == "L"
    img = PDColor(
        [0.0, 1.0, 1.0, 0.0], PDDeviceCMYK.INSTANCE
    ).to_raw_image(1, 1)
    assert img.mode == "CMYK"


# ---------- is_separation / is_device_n predicates ----------


def test_is_separation_true_for_separation_color_space() -> None:
    color = PDColor([1.0], PDSeparation())
    assert color.is_separation() is True
    assert color.is_device_n() is False


def test_is_device_n_true_for_device_n_color_space() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["Cyan", "Magenta"])
    color = PDColor([1.0, 1.0], cs)
    assert color.is_device_n() is True
    assert color.is_separation() is False


def test_is_separation_and_is_device_n_false_for_device_rgb() -> None:
    color = PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    assert color.is_separation() is False
    assert color.is_device_n() is False
    assert color.is_pattern() is False
