"""Upstream-parity port for ``PDAnnotationFreeText``.

Mirrors ``PDAnnotationFreeText.java`` (PDFBox 3.0.x). Upstream ships no
JUnit test for the free-text wrapper — this module ports the source's
behavioural contract: SUB_TYPE stamp, /DA default appearance, /DS default
style, /Q quadding, /CL callout 4-/6-element line, /LE line ending
defaulting to ``None``, /RD rect differences, and /BE border-effect
typed wrapper.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)

_SUBTYPE = COSName.get_pdf_name("Subtype")


def test_default_constructor_stamps_subtype():
    ann = PDAnnotationFreeText()
    assert ann.get_subtype() == "FreeText"
    assert ann.get_cos_object().get_name(_SUBTYPE) == "FreeText"


def test_default_appearance_get_set_round_trip():
    ann = PDAnnotationFreeText()
    assert ann.get_default_appearance() is None
    ann.set_default_appearance("/Helv 12 Tf 0 g")
    assert ann.get_default_appearance() == "/Helv 12 Tf 0 g"


def test_default_style_string_get_set_round_trip():
    ann = PDAnnotationFreeText()
    assert ann.get_default_style_string() is None
    ann.set_default_style_string("font: 12pt Helvetica")
    assert ann.get_default_style_string() == "font: 12pt Helvetica"


def test_q_default_zero_round_trip():
    # Upstream returns 0 (left) when /Q is absent.
    ann = PDAnnotationFreeText()
    assert ann.get_q() == 0
    ann.set_q(1)
    assert ann.get_q() == 1
    ann.set_q(2)
    assert ann.get_q() == 2


def test_quadding_constants_match_spec():
    assert PDAnnotationFreeText.JUSTIFICATION_LEFT == 0
    assert PDAnnotationFreeText.JUSTIFICATION_CENTER == 1
    assert PDAnnotationFreeText.JUSTIFICATION_RIGHT == 2


def test_callout_get_set_4_element_round_trip():
    ann = PDAnnotationFreeText()
    assert ann.get_callout() is None
    ann.set_callout([10.0, 20.0, 30.0, 40.0])
    assert ann.get_callout() == [10.0, 20.0, 30.0, 40.0]


def test_callout_get_set_6_element_round_trip():
    # Upstream allows /CL as a 4- or 6-element array (the 6-form
    # includes a knee-point).
    ann = PDAnnotationFreeText()
    ann.set_callout([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
    assert ann.get_callout() == [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]


def test_line_ending_style_default_none():
    ann = PDAnnotationFreeText()
    assert ann.get_line_ending_style() == "None"


def test_set_line_ending_style_round_trip():
    ann = PDAnnotationFreeText()
    ann.set_line_ending_style("OpenArrow")
    assert ann.get_line_ending_style() == "OpenArrow"


def test_rect_differences_default_empty_array():
    # Upstream returns ``new float[]{}`` when /RD is absent.
    ann = PDAnnotationFreeText()
    assert ann.get_rect_differences() == []


def test_set_rect_differences_writes_four_element_array():
    ann = PDAnnotationFreeText()
    ann.set_rect_differences(1.0, 2.0, 3.0, 4.0)
    assert ann.get_rect_differences() == [1.0, 2.0, 3.0, 4.0]


def test_border_effect_get_set_round_trip():
    ann = PDAnnotationFreeText()
    assert ann.get_border_effect() is None
    be = PDBorderEffectDictionary()
    be.set_intensity(2.0)
    ann.set_border_effect(be)
    fetched = ann.get_border_effect()
    assert isinstance(fetched, PDBorderEffectDictionary)
    assert fetched.get_intensity() == 2.0


def test_it_constants_match_spec():
    assert PDAnnotationFreeText.IT_FREE_TEXT == "FreeText"
    assert PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT == "FreeTextCallout"
    assert PDAnnotationFreeText.IT_FREE_TEXT_TYPE_WRITER == "FreeTextTypeWriter"


def test_sub_type_constant_equals_free_text():
    assert PDAnnotationFreeText.SUB_TYPE == "FreeText"


def test_existing_dict_constructor_no_overwrite():
    # Upstream's COSDictionary ctor calls only super(field) — no subtype
    # stamping. A dict with mismatched /Subtype is preserved.
    d = COSDictionary()
    d.set_name(_SUBTYPE, "FreeText")
    d.set_string(COSName.get_pdf_name("DA"), "/F1 10 Tf 1 0 0 rg")
    ann = PDAnnotationFreeText(d)
    assert ann.get_default_appearance() == "/F1 10 Tf 1 0 0 rg"
