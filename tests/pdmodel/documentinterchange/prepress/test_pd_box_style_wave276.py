from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.prepress import PDBoxStyle
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _array(*items: object) -> COSArray:
    out = COSArray()
    for item in items:
        if isinstance(item, int):
            out.add(COSInteger.get(item))
        elif isinstance(item, float):
            out.add(COSFloat(item))
        elif isinstance(item, str):
            out.add(COSString(item))
        else:
            out.add(item)  # type: ignore[arg-type]
    return out


def test_wave276_defaults_are_accessor_specific() -> None:
    style = PDBoxStyle()
    dictionary = style.get_cos_object()

    assert style.get_guideline_width() == 1.0
    assert style.get_guideline_style() == PDBoxStyle.GUIDELINE_STYLE_SOLID
    assert not dictionary.contains_key(_name("W"))
    assert not dictionary.contains_key(_name("S"))

    assert tuple(style.get_guideline_color().get_components()) == (0.0, 0.0, 0.0)
    assert style.get_line_dash_pattern().get_dash_array() == [3.0]
    assert dictionary.get_cos_array(_name("C")) is not None
    assert dictionary.get_cos_array(_name("D")) is not None


def test_wave276_all_setters_clear_and_defaults_resume() -> None:
    style = PDBoxStyle()
    style.set_guideline_color(PDColor([0.1, 0.2, 0.3], PDDeviceRGB.INSTANCE))
    style.set_guideline_width(2.25)
    style.set_guideline_style(PDBoxStyle.GUIDELINE_STYLE_DASHED)
    style.set_line_dash_pattern(_array(4, 2))

    dictionary = style.get_cos_object()
    assert dictionary.contains_key(_name("C"))
    assert dictionary.contains_key(_name("W"))
    assert dictionary.contains_key(_name("S"))
    assert dictionary.contains_key(_name("D"))

    style.set_guideline_color(None)
    style.set_guideline_width(None)
    style.set_guideline_style(None)
    style.set_line_dash_pattern(None)

    assert not dictionary.contains_key(_name("C"))
    assert not dictionary.contains_key(_name("W"))
    assert not dictionary.contains_key(_name("S"))
    assert not dictionary.contains_key(_name("D"))
    assert style.get_guideline_width() == 1.0
    assert style.get_guideline_style() == PDBoxStyle.GUIDELINE_STYLE_SOLID


def test_wave276_cos_round_trip_uses_existing_dictionary() -> None:
    dictionary = COSDictionary()
    dictionary.set_item(_name("C"), _array(0.125, 0.25, 0.5))
    dictionary.set_item(_name("W"), COSInteger.get(7))
    dictionary.set_name(_name("S"), PDBoxStyle.GUIDELINE_STYLE_DASHED)
    dictionary.set_item(_name("D"), _array(6, 3, 1))

    style = PDBoxStyle(dictionary)
    assert tuple(style.get_guideline_color().get_components()) == (0.125, 0.25, 0.5)
    assert style.get_guideline_width() == 7.0
    assert style.get_guideline_style() == PDBoxStyle.GUIDELINE_STYLE_DASHED
    assert style.get_line_dash_pattern().get_dash_array() == [6.0, 3.0, 1.0]

    dash = _array(9, 4)
    style.set_guideline_color(PDColor([0.875, 0.75, 0.625], PDDeviceRGB.INSTANCE))
    style.set_guideline_width(0.5)
    style.set_guideline_style(PDBoxStyle.GUIDELINE_STYLE_SOLID)
    style.set_line_dash_pattern(dash)

    other = PDBoxStyle(dictionary)
    assert tuple(other.get_guideline_color().get_components()) == (0.875, 0.75, 0.625)
    assert other.get_guideline_width() == 0.5
    assert other.get_guideline_style() == PDBoxStyle.GUIDELINE_STYLE_SOLID
    assert other.get_line_dash_pattern().get_dash_array() == [9.0, 4.0]
    assert dictionary.get_cos_array(_name("D")) is dash


def test_wave276_malformed_non_array_or_scalar_entries_fall_back() -> None:
    dictionary = COSDictionary()
    dictionary.set_item(_name("C"), COSString("not an array"))
    dictionary.set_item(_name("W"), COSName.get_pdf_name("wide"))
    dictionary.set_item(_name("S"), COSString("D"))
    dictionary.set_item(_name("D"), COSString("not an array"))

    style = PDBoxStyle(dictionary)
    assert tuple(style.get_guideline_color().get_components()) == (0.0, 0.0, 0.0)
    assert style.get_guideline_width() == 1.0
    assert style.get_guideline_style() == PDBoxStyle.GUIDELINE_STYLE_SOLID
    assert style.get_line_dash_pattern().get_dash_array() == [3.0]
    assert dictionary.get_cos_array(_name("C")).to_float_array() == [0.0, 0.0, 0.0]  # type: ignore[union-attr]
    assert dictionary.get_cos_array(_name("D")).to_float_array() == [3.0]  # type: ignore[union-attr]


def test_wave276_malformed_array_entries_stay_tolerant() -> None:
    dictionary = COSDictionary()
    dictionary.set_item(_name("C"), _array(0.75, "ignored"))
    dictionary.set_item(_name("D"), _array(5, "gap"))

    style = PDBoxStyle(dictionary)
    assert tuple(style.get_guideline_color().get_components()) == (0.75, 0.0, 0.0)
    assert style.get_line_dash_pattern().get_dash_array() == [5.0, 0.0]
