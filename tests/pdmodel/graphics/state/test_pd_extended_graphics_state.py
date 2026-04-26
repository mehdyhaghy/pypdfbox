from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState


def test_fresh_has_type_ext_g_state() -> None:
    gs = PDExtendedGraphicsState()
    cos = gs.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_name("Type") == "ExtGState"


def test_existing_dictionary_is_preserved() -> None:
    d = COSDictionary()
    d.set_name("Type", "ExtGState")
    d.set_int("LC", 2)
    gs = PDExtendedGraphicsState(d)
    assert gs.get_cos_object() is d
    assert gs.get_line_cap_style() == 2


def test_get_cos_object_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_cos_object() is gs.get_cos_object()


def test_round_trip_line_width() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_line_width() is None
    gs.set_line_width(2.0)
    assert gs.get_line_width() == 2.0


def test_round_trip_line_cap_style() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_line_cap_style() is None
    gs.set_line_cap_style(1)
    assert gs.get_line_cap_style() == 1


def test_round_trip_line_join_style() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_line_join_style() is None
    gs.set_line_join_style(2)
    assert gs.get_line_join_style() == 2


def test_round_trip_miter_limit() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_miter_limit() is None
    gs.set_miter_limit(10.0)
    assert gs.get_miter_limit() == 10.0


def test_round_trip_stroking_alpha_constant() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_stroking_alpha_constant() is None
    gs.set_stroking_alpha_constant(0.5)
    # 0.5 is exactly representable in IEEE-754 single precision.
    assert gs.get_stroking_alpha_constant() == 0.5


def test_round_trip_non_stroking_alpha_constant() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_non_stroking_alpha_constant() is None
    gs.set_non_stroking_alpha_constant(0.7)
    # COSFloat stores in IEEE-754 single precision (Java float parity);
    # 0.7 is not exactly representable, so use approx.
    assert gs.get_non_stroking_alpha_constant() == pytest.approx(0.7)


def test_round_trip_rendering_intent() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_rendering_intent() is None
    gs.set_rendering_intent("Perceptual")
    assert gs.get_rendering_intent() == "Perceptual"


def test_round_trip_blend_mode_cosname() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_blend_mode() is None
    multiply = COSName.get_pdf_name("Multiply")
    gs.set_blend_mode(multiply)
    bm = gs.get_blend_mode()
    assert isinstance(bm, COSName)
    assert bm is multiply
    assert bm.get_name() == "Multiply"


def test_round_trip_blend_mode_string_stored_as_name() -> None:
    gs = PDExtendedGraphicsState()
    gs.set_blend_mode("Screen")
    bm = gs.get_blend_mode()
    assert isinstance(bm, COSName)
    assert bm.get_name() == "Screen"


def test_round_trip_alpha_source_flag() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_alpha_source_flag() is False
    gs.set_alpha_source_flag(True)
    assert gs.get_alpha_source_flag() is True
    gs.set_alpha_source_flag(False)
    assert gs.get_alpha_source_flag() is False


def test_round_trip_text_knockout_flag() -> None:
    gs = PDExtendedGraphicsState()
    # Upstream default for /TK when absent is True.
    assert gs.get_text_knockout_flag() is True
    gs.set_text_knockout_flag(False)
    assert gs.get_text_knockout_flag() is False
    gs.set_text_knockout_flag(True)
    assert gs.get_text_knockout_flag() is True


def test_round_trip_stroke_adjustment() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_stroke_adjustment() is False
    gs.set_stroke_adjustment(True)
    assert gs.get_stroke_adjustment() is True
    gs.set_stroke_adjustment(False)
    assert gs.get_stroke_adjustment() is False


def test_set_line_width_none_removes_entry() -> None:
    gs = PDExtendedGraphicsState()
    gs.set_line_width(3.5)
    assert gs.get_line_width() == 3.5
    gs.set_line_width(None)
    assert gs.get_line_width() is None
    assert gs.get_cos_object().get_item("LW") is None


def test_overprint_mode_default_is_zero() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_overprint_mode() == 0
    gs.set_overprint_mode(1)
    assert gs.get_overprint_mode() == 1
    gs.set_overprint_mode(None)
    assert gs.get_overprint_mode() == 0
    assert gs.get_cos_object().get_item("OPM") is None


def test_stroke_overprint_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_strokeOverprint() is False
    gs.set_stroke_overprint(True)
    assert gs.get_strokeOverprint() is True


def test_non_stroking_overprint_falls_back_to_stroking() -> None:
    gs = PDExtendedGraphicsState()
    # When /op is absent, upstream falls back to /OP.
    gs.set_stroke_overprint(True)
    assert gs.get_non_stroking_overprint() is True
    gs.set_non_stroking_overprint(False)
    assert gs.get_non_stroking_overprint() is False


def test_smoothness_and_flatness_defaults_and_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_smoothness() == 0.0
    assert gs.get_flatness() == 1.0
    gs.set_smoothness(0.25)
    gs.set_flatness(2.0)
    assert gs.get_smoothness() == 0.25
    assert gs.get_flatness() == 2.0


def test_line_dash_pattern_round_trip_raw_array() -> None:
    from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern

    gs = PDExtendedGraphicsState()
    assert gs.get_line_dash_pattern() is None
    arr = COSArray()
    inner = COSArray()
    arr._items.append(inner)  # noqa: SLF001 - test exercises raw array shape
    arr._items.append(COSFloat(0.0))  # noqa: SLF001
    gs.set_line_dash_pattern(arr)
    rt = gs.get_line_dash_pattern()
    assert isinstance(rt, PDLineDashPattern)
    assert rt.get_phase() == 0.0
    gs.set_line_dash_pattern(None)
    assert gs.get_line_dash_pattern() is None


def test_font_size_helper() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_font_size() is None
    gs.set_font_size(12.5)
    assert gs.get_font_size() == 12.5
    # Setting again should overwrite the size slot, not append.
    gs.set_font_size(8.0)
    assert gs.get_font_size() == 8.0
