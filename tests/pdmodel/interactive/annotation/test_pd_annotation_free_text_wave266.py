"""Wave 266 round-out tests for :class:`PDAnnotationFreeText`.

Covers cold gaps surfaced by the upstream ``PDAnnotationFreeText`` API:

* ``Q_LEFT_JUSTIFIED`` / ``Q_CENTERED`` / ``Q_RIGHT_JUSTIFIED`` constants
* ``QUADDING_*`` aliases mirroring ``PDVariableText``
* Intent predicates: ``is_free_text_plain``, ``is_free_text_callout``,
  ``is_free_text_type_writer``
* Edge cases for ``/Q``, ``/DS``, ``/CL`` (4-vs-6 floats), ``/RD`` round
  trip, ``/BS`` and ``/BE`` typed accessors.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)


# ---------- /Q constants ----------


def test_free_text_q_left_justified_constant() -> None:
    assert PDAnnotationFreeText.Q_LEFT_JUSTIFIED == 0


def test_free_text_q_centered_constant() -> None:
    assert PDAnnotationFreeText.Q_CENTERED == 1


def test_free_text_q_right_justified_constant() -> None:
    assert PDAnnotationFreeText.Q_RIGHT_JUSTIFIED == 2


def test_free_text_quadding_aliases_match_q_constants() -> None:
    assert (
        PDAnnotationFreeText.QUADDING_LEFT
        == PDAnnotationFreeText.Q_LEFT_JUSTIFIED
        == PDAnnotationFreeText.JUSTIFICATION_LEFT
        == 0
    )
    assert (
        PDAnnotationFreeText.QUADDING_CENTERED
        == PDAnnotationFreeText.Q_CENTERED
        == PDAnnotationFreeText.JUSTIFICATION_CENTER
        == 1
    )
    assert (
        PDAnnotationFreeText.QUADDING_RIGHT
        == PDAnnotationFreeText.Q_RIGHT_JUSTIFIED
        == PDAnnotationFreeText.JUSTIFICATION_RIGHT
        == 2
    )


def test_free_text_q_default_when_unset_is_left() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_q() == PDAnnotationFreeText.Q_LEFT_JUSTIFIED


def test_free_text_q_round_trip_through_constants() -> None:
    ann = PDAnnotationFreeText()
    ann.set_q(PDAnnotationFreeText.Q_CENTERED)
    assert ann.get_q() == 1
    ann.set_q(PDAnnotationFreeText.Q_RIGHT_JUSTIFIED)
    assert ann.get_q() == 2


def test_free_text_q_set_coerces_int() -> None:
    ann = PDAnnotationFreeText()
    ann.set_q(True)  # bool is a subclass of int — must coerce cleanly
    assert ann.get_q() == 1


# ---------- /DA (default appearance) ----------


def test_free_text_default_appearance_round_trip() -> None:
    ann = PDAnnotationFreeText()
    ann.set_default_appearance("/Helv 12 Tf 0 0 0 rg")
    assert ann.get_default_appearance() == "/Helv 12 Tf 0 0 0 rg"


def test_free_text_default_appearance_default_is_none() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_default_appearance() is None


# ---------- /DS (default style string) ----------


def test_free_text_default_style_string_round_trip() -> None:
    ann = PDAnnotationFreeText()
    ann.set_default_style_string("font: 12pt Helvetica; color: #000000")
    assert (
        ann.get_default_style_string()
        == "font: 12pt Helvetica; color: #000000"
    )


def test_free_text_default_style_string_clear() -> None:
    ann = PDAnnotationFreeText()
    ann.set_default_style_string("font: 10pt Helvetica")
    ann.set_default_style_string(None)
    assert ann.get_default_style_string() is None


# ---------- /IT predicates ----------


def test_free_text_is_free_text_plain_when_intent_is_free_text() -> None:
    ann = PDAnnotationFreeText()
    ann.set_intent(PDAnnotationFreeText.IT_FREE_TEXT)
    assert ann.is_free_text_plain() is True
    assert ann.is_free_text_callout() is False
    assert ann.is_free_text_type_writer() is False


def test_free_text_is_free_text_callout_when_intent_is_callout() -> None:
    ann = PDAnnotationFreeText()
    ann.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
    assert ann.is_free_text_callout() is True
    assert ann.is_free_text_plain() is False
    assert ann.is_free_text_type_writer() is False


def test_free_text_is_type_writer_when_intent_is_typewriter() -> None:
    ann = PDAnnotationFreeText()
    ann.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_TYPE_WRITER)
    assert ann.is_free_text_type_writer() is True
    assert ann.is_free_text_plain() is False
    assert ann.is_free_text_callout() is False


def test_free_text_predicates_all_false_when_intent_unset() -> None:
    ann = PDAnnotationFreeText()
    assert ann.is_free_text_plain() is False
    assert ann.is_free_text_callout() is False
    assert ann.is_free_text_type_writer() is False


# ---------- /CL (callout line) ----------


def test_free_text_callout_line_4_floats_round_trip() -> None:
    ann = PDAnnotationFreeText()
    ann.set_callout_line([10.0, 20.0, 30.0, 40.0])
    cl = ann.get_callout_line()
    assert cl == [10.0, 20.0, 30.0, 40.0]


def test_free_text_callout_line_6_floats_round_trip() -> None:
    ann = PDAnnotationFreeText()
    ann.set_callout_line([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    cl = ann.get_callout_line()
    assert cl == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_free_text_callout_line_truncates_extra_entries_to_six() -> None:
    """Spec allows 4 or 6 floats; anything beyond 6 is silently truncated."""
    ann = PDAnnotationFreeText()
    ann.set_callout_line([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    cl = ann.get_callout_line()
    assert cl is not None
    assert len(cl) == 6


def test_free_text_callout_line_returns_none_when_too_short() -> None:
    """Three-element ``/CL`` is malformed — accessor should return ``None``."""
    ann = PDAnnotationFreeText()
    cos = ann.get_cos_object()
    cos.set_item(  # type: ignore[attr-defined]
        COSName.get_pdf_name("CL"),
        COSArray([COSFloat(1.0), COSFloat(2.0), COSFloat(3.0)]),
    )
    assert ann.get_callout_line() is None


def test_free_text_callout_alias_round_trip() -> None:
    ann = PDAnnotationFreeText()
    ann.set_callout([5.0, 6.0, 7.0, 8.0])
    assert ann.get_callout() == [5.0, 6.0, 7.0, 8.0]


# ---------- /RD (rectangle differences) ----------


def test_free_text_rect_differences_plural_round_trip() -> None:
    ann = PDAnnotationFreeText()
    ann.set_rect_differences(2.0, 3.0, 4.0, 5.0)
    assert ann.get_rectangle_differences() == [2.0, 3.0, 4.0, 5.0]
    assert ann.get_rect_differences() == [2.0, 3.0, 4.0, 5.0]


def test_free_text_rect_differences_uniform_value() -> None:
    ann = PDAnnotationFreeText()
    ann.set_rect_differences(7.5)
    assert ann.get_rectangle_differences() == [7.5, 7.5, 7.5, 7.5]


def test_free_text_get_rect_differences_empty_when_unset() -> None:
    """Upstream returns ``new float[]{}`` when ``/RD`` is missing."""
    ann = PDAnnotationFreeText()
    assert ann.get_rect_differences() == []


def test_free_text_set_rect_differences_invalid_arity_raises() -> None:
    ann = PDAnnotationFreeText()
    import pytest

    with pytest.raises(TypeError):
        ann.set_rect_differences(1.0, 2.0, 3.0)  # wrong arity


# ---------- /BS (border style) ----------


def test_free_text_border_style_typed_round_trip() -> None:
    ann = PDAnnotationFreeText()
    bs = PDBorderStyleDictionary()
    bs.set_width(1.5)
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    ann.set_border_style(bs)

    rt = ann.get_border_style()
    assert rt is not None
    assert rt.get_width() == 1.5
    assert rt.get_style() == PDBorderStyleDictionary.STYLE_DASHED


def test_free_text_border_style_clear() -> None:
    ann = PDAnnotationFreeText()
    ann.set_border_style(PDBorderStyleDictionary())
    ann.set_border_style(None)
    assert ann.get_border_style() is None


# ---------- /BE (border effect) ----------


def test_free_text_border_effect_typed_round_trip() -> None:
    ann = PDAnnotationFreeText()
    be = PDBorderEffectDictionary()
    be.set_intensity(2.0)
    be.set_style("C")
    ann.set_border_effect(be)

    rt = ann.get_border_effect()
    assert rt is not None
    assert rt.get_intensity() == 2.0
    assert rt.get_style() == "C"


def test_free_text_border_effect_accepts_raw_cos_dictionary() -> None:
    """``set_border_effect`` accepts a bare ``COSDictionary`` for callers
    that build the dict by hand."""
    ann = PDAnnotationFreeText()
    raw = COSDictionary()
    raw.set_float(COSName.get_pdf_name("I"), 1.5)  # type: ignore[attr-defined]
    ann.set_border_effect(raw)

    rt = ann.get_border_effect()
    assert rt is not None
    assert rt.get_intensity() == 1.5


def test_free_text_border_effect_clear() -> None:
    ann = PDAnnotationFreeText()
    ann.set_border_effect(PDBorderEffectDictionary())
    ann.set_border_effect(None)
    assert ann.get_border_effect() is None


# ---------- /LE (line ending) ----------


def test_free_text_line_ending_round_trip_via_upstream_alias() -> None:
    ann = PDAnnotationFreeText()
    ann.set_line_ending_style("OpenArrow")
    assert ann.get_line_ending_style() == "OpenArrow"
    # Local snake_case accessor reads the same entry.
    assert ann.get_line_ending() == "OpenArrow"
