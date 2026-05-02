from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.documentinterchange.prepress import PDBoxStyle
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern


# ---------- constructors / COS surface ----------


def test_default_constructor_is_empty_dictionary() -> None:
    style = PDBoxStyle()
    assert isinstance(style.get_cos_object(), COSDictionary)
    assert style.get_cos_object().is_empty()
    # Pypdfbox-style alias resolves to the same object.
    assert style.get_cos_dictionary() is style.get_cos_object()


def test_existing_dictionary_constructor_keeps_identity() -> None:
    dic = COSDictionary()
    style = PDBoxStyle(dic)
    assert style.get_cos_object() is dic


def test_constants_match_pdf32000_box_style_names() -> None:
    assert PDBoxStyle.GUIDELINE_STYLE_SOLID == "S"
    assert PDBoxStyle.GUIDELINE_STYLE_DASHED == "D"


# ---------- /C — guideline colour ----------


def test_get_guideline_color_default_materializes_zero_zero_zero() -> None:
    style = PDBoxStyle()
    color = style.get_guideline_color()
    assert isinstance(color, PDColor)
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    assert tuple(color.get_components()) == (0.0, 0.0, 0.0)
    # Upstream behaviour: the default colour is written into the dict.
    stored = style.get_cos_object().get_cos_array(COSName.get_pdf_name("C"))
    assert stored is not None
    assert stored.size() == 3


def test_get_guideline_color_round_trip_existing_array() -> None:
    style = PDBoxStyle()
    inner = COSArray()
    inner.add(COSFloat(0.25))
    inner.add(COSFloat(0.5))
    inner.add(COSFloat(0.75))
    style.get_cos_object().set_item(COSName.get_pdf_name("C"), inner)
    color = style.get_guideline_color()
    assert tuple(color.get_components()) == (0.25, 0.5, 0.75)


def test_set_guideline_color_writes_components() -> None:
    style = PDBoxStyle()
    color = PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    style.set_guideline_color(color)
    stored = style.get_cos_object().get_cos_array(COSName.get_pdf_name("C"))
    assert stored is not None
    assert stored.size() == 3
    # Round-trip.
    refetched = style.get_guideline_color()
    assert tuple(refetched.get_components()) == (1.0, 0.0, 0.0)


def test_set_guideline_color_none_removes_entry() -> None:
    style = PDBoxStyle()
    style.set_guideline_color(PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE))
    assert style.get_cos_object().contains_key(COSName.get_pdf_name("C"))
    style.set_guideline_color(None)
    assert not style.get_cos_object().contains_key(COSName.get_pdf_name("C"))


def test_set_guide_line_color_alias_matches_upstream() -> None:
    style = PDBoxStyle()
    color = PDColor([0.5, 0.5, 0.5], PDDeviceRGB.INSTANCE)
    # Upstream method is ``setGuideLineColor`` — surface mirror should exist.
    style.set_guide_line_color(color)
    refetched = style.get_guideline_color()
    assert tuple(refetched.get_components()) == (0.5, 0.5, 0.5)


# ---------- /W — guideline width ----------


def test_get_guideline_width_default_is_one() -> None:
    style = PDBoxStyle()
    assert style.get_guideline_width() == 1.0


def test_guideline_width_round_trip() -> None:
    style = PDBoxStyle()
    style.set_guideline_width(2.5)
    assert style.get_guideline_width() == 2.5
    style.set_guideline_width(0.0)
    assert style.get_guideline_width() == 0.0


def test_guideline_width_accepts_int_arg_and_returns_float() -> None:
    style = PDBoxStyle()
    style.set_guideline_width(3)
    width = style.get_guideline_width()
    assert width == 3.0
    assert isinstance(width, float)


# ---------- /S — guideline style ----------


def test_get_guideline_style_default_is_solid() -> None:
    style = PDBoxStyle()
    assert style.get_guideline_style() == PDBoxStyle.GUIDELINE_STYLE_SOLID


def test_guideline_style_round_trip_dashed() -> None:
    style = PDBoxStyle()
    style.set_guideline_style(PDBoxStyle.GUIDELINE_STYLE_DASHED)
    assert style.get_guideline_style() == "D"


def test_guideline_style_none_removes_entry_and_falls_back_to_default() -> None:
    style = PDBoxStyle()
    style.set_guideline_style(PDBoxStyle.GUIDELINE_STYLE_DASHED)
    style.set_guideline_style(None)
    assert not style.get_cos_object().contains_key(COSName.get_pdf_name("S"))
    # Reading again returns the default solid style.
    assert style.get_guideline_style() == "S"


# ---------- /D — line dash pattern ----------


def test_get_line_dash_pattern_default_is_three() -> None:
    style = PDBoxStyle()
    pattern = style.get_line_dash_pattern()
    assert isinstance(pattern, PDLineDashPattern)
    assert pattern.get_dash_array() == [3.0]
    assert pattern.get_phase() == 0
    # Upstream behaviour: the default ``[3]`` is materialised into ``/D``.
    stored = style.get_cos_object().get_cos_array(COSName.get_pdf_name("D"))
    assert stored is not None
    assert stored.size() == 1


def test_set_line_dash_pattern_round_trip() -> None:
    style = PDBoxStyle()
    dash = COSArray()
    dash.add(COSInteger.get(2))
    dash.add(COSInteger.get(1))
    style.set_line_dash_pattern(dash)
    pattern = style.get_line_dash_pattern()
    assert pattern.get_dash_array() == [2.0, 1.0]


def test_set_line_dash_pattern_none_removes_entry() -> None:
    style = PDBoxStyle()
    dash = COSArray()
    dash.add(COSInteger.get(5))
    style.set_line_dash_pattern(dash)
    assert style.get_cos_object().contains_key(COSName.get_pdf_name("D"))
    style.set_line_dash_pattern(None)
    assert not style.get_cos_object().contains_key(COSName.get_pdf_name("D"))


# ---------- whole-dictionary round-trip ----------


def test_full_round_trip_through_existing_dictionary() -> None:
    """A ``PDBoxStyle`` constructed over a dictionary and configured by
    setters should reflect every entry on a freshly-wrapped instance
    that shares the same dictionary."""
    dic = COSDictionary()
    style = PDBoxStyle(dic)
    # Use exactly-representable binary fractions so float round-trip is bit-stable.
    style.set_guideline_color(PDColor([0.125, 0.25, 0.5], PDDeviceRGB.INSTANCE))
    style.set_guideline_width(0.75)
    style.set_guideline_style(PDBoxStyle.GUIDELINE_STYLE_DASHED)
    dash = COSArray()
    dash.add(COSInteger.get(4))
    style.set_line_dash_pattern(dash)

    # Re-wrap the same dictionary.
    other = PDBoxStyle(dic)
    assert tuple(other.get_guideline_color().get_components()) == (0.125, 0.25, 0.5)
    assert other.get_guideline_width() == 0.75
    assert other.get_guideline_style() == "D"
    assert other.get_line_dash_pattern().get_dash_array() == [4.0]
