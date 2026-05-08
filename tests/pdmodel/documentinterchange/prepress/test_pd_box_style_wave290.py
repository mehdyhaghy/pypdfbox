from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.prepress import PDBoxStyle
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _array(*values: float) -> COSArray:
    array = COSArray()
    for value in values:
        if value.is_integer():
            array.add(COSInteger.get(int(value)))
        else:
            array.add(COSFloat(value))
    return array


def test_wave290_presence_helpers_report_valid_box_style_entries() -> None:
    style = PDBoxStyle()
    style.set_guideline_color(PDColor([0.2, 0.4, 0.6], PDDeviceRGB.INSTANCE))
    style.set_guideline_width(2.5)
    style.set_guideline_style(PDBoxStyle.GUIDELINE_STYLE_DASHED)
    style.set_line_dash_pattern(_array(4.0, 2.5))

    assert style.has_guideline_color() is True
    assert style.has_guideline_width() is True
    assert style.has_guideline_style() is True
    assert style.has_line_dash_pattern() is True


def test_wave290_clear_helpers_remove_entries_and_defaults_resume() -> None:
    style = PDBoxStyle()
    style.set_guideline_color(PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE))
    style.set_guideline_width(3.0)
    style.set_guideline_style(PDBoxStyle.GUIDELINE_STYLE_DASHED)
    style.set_line_dash_pattern(_array(6.0))

    style.clear_guideline_color()
    style.clear_guideline_width()
    style.clear_guideline_style()
    style.clear_line_dash_pattern()

    dictionary = style.get_cos_object()
    assert not dictionary.contains_key(_name("C"))
    assert not dictionary.contains_key(_name("W"))
    assert not dictionary.contains_key(_name("S"))
    assert not dictionary.contains_key(_name("D"))
    assert style.has_guideline_color() is False
    assert style.has_guideline_width() is False
    assert style.has_guideline_style() is False
    assert style.has_line_dash_pattern() is False
    assert tuple(style.get_guideline_color().get_components()) == (0.0, 0.0, 0.0)
    assert style.get_guideline_width() == 1.0
    assert style.get_guideline_style() == PDBoxStyle.GUIDELINE_STYLE_SOLID
    assert style.get_line_dash_pattern().get_dash_array() == [3.0]


def test_wave290_malformed_entries_do_not_report_present() -> None:
    dictionary = COSDictionary()
    dictionary.set_item(_name("C"), COSString("not an array"))
    dictionary.set_item(_name("W"), COSName.get_pdf_name("wide"))
    dictionary.set_item(_name("S"), COSString("D"))
    dictionary.set_item(_name("D"), COSString("not an array"))

    style = PDBoxStyle(dictionary)

    assert style.has_guideline_color() is False
    assert style.has_guideline_width() is False
    assert style.has_guideline_style() is False
    assert style.has_line_dash_pattern() is False
    assert tuple(style.get_guideline_color().get_components()) == (0.0, 0.0, 0.0)
    assert style.get_guideline_width() == 1.0
    assert style.get_guideline_style() == PDBoxStyle.GUIDELINE_STYLE_SOLID
    assert style.get_line_dash_pattern().get_dash_array() == [3.0]

