from __future__ import annotations

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.shading import PDShadingType2


def _float_array(*values: float) -> COSArray:
    array = COSArray()
    for value in values:
        array.add(COSFloat(value))
    return array


def test_color_space_presence_uses_short_form_and_clear_removes_both_keys() -> None:
    shading = PDShadingType2()
    cs = COSName.get_pdf_name("DeviceRGB")
    shading.get_cos_object().set_item("CS", cs)

    assert shading.has_color_space() is True
    assert shading.get_color_space() is cs

    shading.clear_color_space()

    assert shading.has_color_space() is False
    assert shading.get_color_space() is None
    assert shading.get_color_space_object() is None
    assert shading.get_cos_object().get_dictionary_object("CS") is None


def test_color_space_prefers_long_form_over_short_form() -> None:
    shading = PDShadingType2()
    color_space = COSName.get_pdf_name("DeviceRGB")
    cs = COSName.get_pdf_name("DeviceCMYK")
    shading.get_cos_object().set_item("ColorSpace", color_space)
    shading.get_cos_object().set_item("CS", cs)

    assert shading.get_color_space() is color_space


def test_numeric_array_presence_helpers_reject_malformed_entries() -> None:
    shading = PDShadingType2()
    shading.set_background(_float_array(0.1, 0.2, 0.3))
    shading.set_b_box(_float_array(0.0, 0.0, 100.0, 200.0))

    assert shading.has_background() is True
    assert shading.has_b_box() is True

    bad_background = _float_array(0.1, 0.2)
    bad_background.add(COSName.get_pdf_name("Bad"))
    shading.get_cos_object().set_item("Background", bad_background)
    shading.get_cos_object().set_item("BBox", _float_array(0.0, 0.0, 100.0))

    assert shading.has_background() is False
    assert shading.has_b_box() is False
    assert shading.get_background() is bad_background
    assert shading.get_b_box_rect() is None


def test_clear_helpers_remove_shading_optional_entries() -> None:
    shading = PDShadingType2()
    shading.set_background(_float_array(0.1))
    shading.set_b_box(_float_array(0.0, 0.0, 100.0, 200.0))
    shading.set_anti_alias(True)
    shading.get_cos_object().set_item("Function", COSDictionary())

    shading.clear_background()
    shading.clear_b_box()
    shading.clear_anti_alias()
    shading.clear_function()

    assert shading.has_background() is False
    assert shading.has_b_box() is False
    assert shading.has_anti_alias() is False
    assert shading.has_function() is False


def test_typed_presence_helpers_ignore_malformed_scalar_entries() -> None:
    shading = PDShadingType2()
    shading.get_cos_object().set_item("AntiAlias", COSName.get_pdf_name("yes"))
    shading.get_cos_object().set_item("Function", COSName.get_pdf_name("F1"))

    assert shading.get_anti_alias() is False
    assert shading.has_anti_alias() is False
    assert shading.has_function() is False

    shading.get_cos_object().set_item("AntiAlias", COSBoolean.TRUE)
    shading.get_cos_object().set_item("Function", COSArray())

    assert shading.has_anti_alias() is True
    assert shading.has_function() is True
