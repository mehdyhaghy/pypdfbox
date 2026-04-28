"""Parity tests for ``PDExtendedGraphicsState``.

Upstream Apache PDFBox 3.0.x does not ship a dedicated
``PDExtendedGraphicsStateTest`` JUnit class — coverage there is folded
into rendering / content-stream tests. This file therefore mirrors the
*public API surface* exercised by upstream consumers (PDFRenderer,
PDPageContentStream, the ExtGState chapter of the PDF 1.7 spec) so a
future re-sync against an upstream test class — should one appear — has
a stable parity baseline to merge into.

No PROVENANCE row is added because no upstream test source is being
ported; this is a hand-written parity scaffold.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.pdmodel.graphics.state import (
    PDExtendedGraphicsState,
    PDFontSetting,
)


def test_default_dictionary_has_type() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_cos_object().get_name("Type") == "ExtGState"


def test_round_trip_line_metrics_match_spec_defaults() -> None:
    gs = PDExtendedGraphicsState()
    # Per PDF 1.7 §8.4.5, when /LW etc. are absent, the value is
    # inherited from the current graphics state. The wrapper signals
    # absence with ``None`` rather than a default.
    assert gs.get_line_width() is None
    assert gs.get_line_cap_style() is None
    assert gs.get_line_join_style() is None
    assert gs.get_miter_limit() is None
    gs.set_line_width(1.5)
    gs.set_line_cap_style(2)
    gs.set_line_join_style(1)
    gs.set_miter_limit(10.0)
    assert gs.get_line_width() == 1.5
    assert gs.get_line_cap_style() == 2
    assert gs.get_line_join_style() == 1
    assert gs.get_miter_limit() == 10.0


def test_alpha_constants_and_alpha_source_flag() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_stroking_alpha_constant() is None
    assert gs.get_non_stroking_alpha_constant() is None
    assert gs.get_alpha_source_flag() is False
    gs.set_stroking_alpha_constant(0.5)
    gs.set_non_stroking_alpha_constant(0.25)
    gs.set_alpha_source_flag(True)
    assert gs.get_stroking_alpha_constant() == 0.5
    assert gs.get_non_stroking_alpha_constant() == 0.25
    assert gs.get_alpha_source_flag() is True


def test_overprint_controls_with_fallback() -> None:
    gs = PDExtendedGraphicsState()
    # Default OPM per spec is 0.
    assert gs.get_overprint_mode() == 0
    gs.set_overprint_mode(1)
    assert gs.get_overprint_mode() == 1
    # /op falls back to /OP per upstream behaviour and the PDF spec.
    gs.set_stroking_overprint_control(True)
    assert gs.get_non_stroking_overprint_control() is True
    gs.set_non_stroking_overprint_control(False)
    assert gs.get_non_stroking_overprint_control() is False


def test_text_knockout_default_is_true_per_spec() -> None:
    # Per PDF 1.7 §9.3.8 the default value of /TK is true.
    gs = PDExtendedGraphicsState()
    assert gs.get_text_knockout_flag() is True
    gs.set_text_knockout_flag(False)
    assert gs.get_text_knockout_flag() is False


def test_smoothness_and_flatness_tolerances() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_smoothness_tolerance() == 0.0
    assert gs.get_flatness_tolerance() == 1.0
    gs.set_smoothness_tolerance(0.05)
    gs.set_flatness_tolerance(2.0)
    assert gs.get_smoothness_tolerance() == pytest.approx(0.05)
    assert gs.get_flatness_tolerance() == 2.0


def test_blend_mode_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_blend_mode() is None
    gs.set_blend_mode(BlendMode.MULTIPLY)
    assert gs.get_blend_mode() is BlendMode.MULTIPLY


def test_rendering_intent_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_rendering_intent() is None
    gs.set_rendering_intent("RelativeColorimetric")
    assert gs.get_rendering_intent() == "RelativeColorimetric"


def test_font_setting_typed_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    setting = PDFontSetting()
    setting.set_font(COSName.get_pdf_name("F1"))
    setting.set_font_size(11.0)
    gs.set_font_setting(setting)
    rt = gs.get_font_setting()
    assert rt is not None
    assert rt.get_font_size() == 11.0


def test_soft_mask_transfer_halftone_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_soft_mask() is None
    assert gs.get_transfer() is None
    assert gs.get_transfer2() is None
    assert gs.get_halftone() is None

    gs.set_soft_mask(COSName.get_pdf_name("None"))
    gs.set_transfer(COSName.get_pdf_name("Identity"))
    gs.set_transfer2(COSName.get_pdf_name("Default"))
    halftone = COSDictionary()
    halftone.set_int("HalftoneType", 1)
    gs.set_halftone(halftone)
    origin = COSArray()
    origin.add(COSFloat(0.0))
    origin.add(COSFloat(0.0))
    gs.set_halftone_origin(origin)

    assert gs.get_soft_mask() == COSName.get_pdf_name("None")
    assert gs.get_transfer() == COSName.get_pdf_name("Identity")
    assert gs.get_transfer2() == COSName.get_pdf_name("Default")
    assert gs.get_halftone() is halftone
    assert gs.get_halftone_origin() is origin


def test_transfer_array_size_filter_matches_upstream() -> None:
    # Upstream PDExtendedGraphicsState.getTransfer / getTransfer2 explicitly
    # filter out arrays whose size != 4 (returns null). Mirror that contract.
    gs = PDExtendedGraphicsState()
    arr = COSArray()
    arr.add(COSFloat(0.0))  # not even a function — only size matters here
    gs.get_cos_object().set_item("TR", arr)
    assert gs.get_transfer() is None
    gs.get_cos_object().set_item("TR2", arr)
    assert gs.get_transfer2() is None


def test_black_generation_undercolor_removal_round_trip() -> None:
    # PDF 32000-1 Table 58: /BG /BG2 /UCR /UCR2 are function dictionaries
    # (BG2/UCR2 also accept the name /Default). Upstream defers typed
    # accessors; we expose both raw and typed (PDFunction) round-trips.
    gs = PDExtendedGraphicsState()
    assert gs.get_black_generation() is None
    assert gs.get_black_generation2() is None
    assert gs.get_undercolor_removal() is None
    assert gs.get_undercolor_removal2() is None

    fn = COSDictionary()
    fn.set_int("FunctionType", 2)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    fn.set_item("Domain", domain)
    from pypdfbox.cos import COSInteger

    fn.set_item("N", COSInteger.get(1))

    gs.set_black_generation(fn)
    gs.set_undercolor_removal(fn)
    gs.set_black_generation2(COSName.get_pdf_name("Default"))
    gs.set_undercolor_removal2(COSName.get_pdf_name("Default"))

    assert gs.get_black_generation() is fn
    assert gs.get_undercolor_removal() is fn
    assert gs.get_black_generation2() == COSName.get_pdf_name("Default")
    assert gs.get_undercolor_removal2() == COSName.get_pdf_name("Default")


def test_advanced_annotations_round_trip() -> None:
    # Apple-specific /AAPL:AA entry — preserved on round-trip without
    # parsing (mirrors upstream behaviour).
    gs = PDExtendedGraphicsState()
    assert gs.get_advanced_annotations() is None
    aa = COSDictionary()
    aa.set_int("X", 1)
    gs.set_advanced_annotations(aa)
    assert gs.get_advanced_annotations() is aa
