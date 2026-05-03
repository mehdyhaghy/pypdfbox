"""Wave 265 — round-out cold gaps for ``PDAnnotationLine``.

Covers parity round-outs for the line annotation:

- Constructor seeds ``/L`` with ``[0, 0, 0, 0]`` matching upstream's
  mandatory-entry seeding.
- Parent class is :class:`PDAnnotationMarkup` (not the bare
  :class:`PDAnnotation`) — markup-level fields (``/Subj``, ``/CreationDate``,
  ``/IT``, ``/CA``, …) are reachable.
- ``set_start_point_ending_style`` / ``set_end_point_ending_style`` accept
  ``None`` and coerce it to :data:`LE_NONE` (mirrors upstream's
  null-coalescing).
- ``/Measure`` typed accessor (get/set/clear) parity with polygon/polyline.
- ``is_line_arrow`` / ``is_line_dimension`` predicates over ``/IT``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)
from pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary import (
    PDMeasureDictionary,
)

_L = COSName.get_pdf_name("L")
_LE = COSName.get_pdf_name("LE")
_MEASURE = COSName.get_pdf_name("Measure")


# ---------- inheritance ----------


def test_line_inherits_from_markup() -> None:
    """Upstream PDAnnotationLine extends PDAnnotationMarkup — Python
    parity should expose the markup-level surface."""
    ann = PDAnnotationLine()
    assert isinstance(ann, PDAnnotationMarkup)


def test_line_exposes_markup_fields() -> None:
    """Markup-level accessors (creation date, subject, intent, opacity)
    must be reachable on the line annotation."""
    ann = PDAnnotationLine()
    ann.set_subject("ruler")
    ann.set_creation_date("D:20260503000000Z")
    ann.set_constant_opacity(0.75)
    assert ann.get_subject() == "ruler"
    assert ann.get_creation_date() == "D:20260503000000Z"
    assert ann.get_constant_opacity() == 0.75


# ---------- /L mandatory seeding ----------


def test_line_default_constructor_seeds_l_to_zeros() -> None:
    """Upstream's no-arg constructor calls ``setLine([0, 0, 0, 0])`` so
    the mandatory ``/L`` entry is present; Python should match."""
    ann = PDAnnotationLine()
    assert ann.get_line() == [0.0, 0.0, 0.0, 0.0]
    raw = ann.get_cos_object().get_dictionary_object(_L)
    assert isinstance(raw, COSArray)
    assert raw.size() == 4


def test_line_dict_constructor_does_not_seed_l() -> None:
    """When wrapping an existing dictionary, the seeding must not
    overwrite caller-supplied state — mirrors upstream's two-arg path."""
    dictionary = COSDictionary()
    ann = PDAnnotationLine(dictionary)
    assert ann.get_line() is None
    assert not ann.get_cos_object().contains_key(_L)


# ---------- /LE setters accept None ----------


def test_line_set_start_point_ending_style_none_coerces_to_le_none() -> None:
    ann = PDAnnotationLine()
    ann.set_start_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    ann.set_start_point_ending_style(None)
    assert ann.get_start_point_ending_style() == PDAnnotationLine.LE_NONE


def test_line_set_end_point_ending_style_none_coerces_to_le_none() -> None:
    ann = PDAnnotationLine()
    ann.set_end_point_ending_style(PDAnnotationLine.LE_CLOSED_ARROW)
    ann.set_end_point_ending_style(None)
    assert ann.get_end_point_ending_style() == PDAnnotationLine.LE_NONE


def test_line_set_endings_none_when_le_absent_creates_array() -> None:
    """Setting None on a fresh annotation must create the LE array
    [None, None] and not raise."""
    ann = PDAnnotationLine()
    ann.set_start_point_ending_style(None)
    ann.set_end_point_ending_style(None)
    raw = ann.get_cos_object().get_dictionary_object(_LE)
    assert isinstance(raw, COSArray)
    assert raw.size() >= 2
    assert ann.get_start_point_ending_style() == PDAnnotationLine.LE_NONE
    assert ann.get_end_point_ending_style() == PDAnnotationLine.LE_NONE


# ---------- /Measure ----------


def test_line_measure_default_none() -> None:
    ann = PDAnnotationLine()
    assert ann.get_measure() is None


def test_line_set_measure_typed_round_trip() -> None:
    ann = PDAnnotationLine()
    measure = PDMeasureDictionary()
    measure.get_cos_object().set_string(
        COSName.get_pdf_name("R"), "1 in = 1 in"
    )
    ann.set_measure(measure)
    out = ann.get_measure()
    assert out is not None
    assert isinstance(out, PDMeasureDictionary)
    # Underlying COSDictionary identity must match — set must not clone.
    assert out.get_cos_object() is measure.get_cos_object()


def test_line_set_measure_raw_dictionary() -> None:
    ann = PDAnnotationLine()
    raw = COSDictionary()
    raw.set_string(COSName.get_pdf_name("R"), "1 cm = 1 cm")
    ann.set_measure(raw)
    stored = ann.get_cos_object().get_dictionary_object(_MEASURE)
    assert stored is raw


def test_line_set_measure_none_clears_entry() -> None:
    ann = PDAnnotationLine()
    ann.set_measure(PDMeasureDictionary())
    ann.set_measure(None)
    assert ann.get_measure() is None
    assert not ann.get_cos_object().contains_key(_MEASURE)


def test_line_get_measure_returns_none_for_non_dictionary_entry() -> None:
    ann = PDAnnotationLine()
    # Stuff a non-dictionary value under /Measure; accessor must tolerate.
    ann.get_cos_object().set_name(_MEASURE, "Garbage")
    assert ann.get_measure() is None


# ---------- /IT intent predicates ----------


def test_line_is_line_arrow_default_false() -> None:
    ann = PDAnnotationLine()
    assert ann.is_line_arrow() is False
    assert ann.is_line_dimension() is False


def test_line_is_line_arrow_true_after_set() -> None:
    ann = PDAnnotationLine()
    ann.set_intent(PDAnnotationLine.IT_LINE_ARROW)
    assert ann.is_line_arrow() is True
    assert ann.is_line_dimension() is False


def test_line_is_line_dimension_true_after_set() -> None:
    ann = PDAnnotationLine()
    ann.set_intent(PDAnnotationLine.IT_LINE_DIMENSION)
    assert ann.is_line_dimension() is True
    assert ann.is_line_arrow() is False


def test_line_intent_predicates_false_for_unrelated_intent() -> None:
    ann = PDAnnotationLine()
    ann.set_intent("SomeOtherIntent")
    assert ann.is_line_arrow() is False
    assert ann.is_line_dimension() is False
