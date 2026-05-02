"""Wave 190 — small parity round-out for annotation subclasses.

Covers:

- ``PDAnnotationLine`` ``/IC`` interior-color accessors (line endings).
- ``PDAnnotationStamp`` snake_case-only naming (no camelCase aliases).
- ``PDAnnotationPolyline`` ``/LE`` start/end-point ending-style accessors.
- ``PDAnnotationFreeText``/``Polygon``/``Polyline`` typed
  :class:`PDBorderEffectDictionary` returns from ``get_border_effect``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polygon import (
    PDAnnotationPolygon,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polyline import (
    PDAnnotationPolyline,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_stamp import (
    PDAnnotationStamp,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)

_IC = COSName.get_pdf_name("IC")
_LE = COSName.get_pdf_name("LE")
_BE = COSName.get_pdf_name("BE")


# ---------- PDAnnotationLine /IC ----------


def test_line_interior_color_default_none() -> None:
    ann = PDAnnotationLine()
    assert ann.get_interior_color() is None


def test_line_interior_color_round_trip_rgb() -> None:
    ann = PDAnnotationLine()
    ann.set_interior_color([0.25, 0.5, 0.75])
    assert ann.get_interior_color() == [0.25, 0.5, 0.75]


def test_line_interior_color_round_trip_gray() -> None:
    ann = PDAnnotationLine()
    ann.set_interior_color([0.5])  # exactly representable
    assert ann.get_interior_color() == [0.5]


def test_line_interior_color_round_trip_cmyk() -> None:
    ann = PDAnnotationLine()
    ann.set_interior_color((0.0, 1.0, 1.0, 0.25))
    assert ann.get_interior_color() == [0.0, 1.0, 1.0, 0.25]


def test_line_interior_color_clear_via_none_removes_entry() -> None:
    ann = PDAnnotationLine()
    ann.set_interior_color([0.5, 0.5, 0.5])
    ann.set_interior_color(None)
    assert ann.get_interior_color() is None
    assert not ann.get_cos_object().contains_key(_IC)


def test_line_interior_color_writes_cosfloat_array() -> None:
    ann = PDAnnotationLine()
    ann.set_interior_color([0.1, 0.2, 0.3])
    raw = ann.get_cos_object().get_dictionary_object(_IC)
    assert isinstance(raw, COSArray)
    assert raw.size() == 3
    for item in raw:
        assert isinstance(item, COSFloat)


def test_line_interior_color_returns_none_for_non_array_entry() -> None:
    ann = PDAnnotationLine()
    # Stuff a non-array under /IC; accessor must tolerate and return None.
    ann.get_cos_object().set_name(_IC, "Garbage")
    assert ann.get_interior_color() is None


# ---------- PDAnnotationStamp — snake_case only ----------


def test_stamp_has_no_camelcase_aliases() -> None:
    """Wave 190 strips ``getName``/``setName`` per the no-camelCase rule.

    Memory: ``feedback_no_camelcase_aliases.md`` — strict snake_case only;
    no Java-name aliases on ported surfaces.
    """
    assert not hasattr(PDAnnotationStamp, "getName")
    assert not hasattr(PDAnnotationStamp, "setName")


def test_stamp_snake_case_name_round_trip_still_works() -> None:
    ann = PDAnnotationStamp()
    ann.set_name(PDAnnotationStamp.NAME_FINAL)
    assert ann.get_name() == "Final"
    ann.set_name(None)
    assert ann.get_name() == PDAnnotationStamp.NAME_DRAFT


# ---------- PDAnnotationPolyline /LE individual endpoint accessors ----------


def test_polyline_endings_default_le_none() -> None:
    ann = PDAnnotationPolyline()
    assert ann.get_start_point_ending_style() == PDAnnotationLine.LE_NONE
    assert ann.get_end_point_ending_style() == PDAnnotationLine.LE_NONE


def test_polyline_set_start_point_ending_style_round_trip() -> None:
    ann = PDAnnotationPolyline()
    ann.set_start_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    assert ann.get_start_point_ending_style() == "OpenArrow"
    # End is normalised to LE_NONE during initialisation.
    assert ann.get_end_point_ending_style() == "None"


def test_polyline_set_end_point_ending_style_round_trip() -> None:
    ann = PDAnnotationPolyline()
    ann.set_end_point_ending_style(PDAnnotationLine.LE_CLOSED_ARROW)
    assert ann.get_end_point_ending_style() == "ClosedArrow"
    assert ann.get_start_point_ending_style() == "None"


def test_polyline_set_both_endings_via_individual_accessors() -> None:
    ann = PDAnnotationPolyline()
    ann.set_start_point_ending_style(PDAnnotationLine.LE_DIAMOND)
    ann.set_end_point_ending_style(PDAnnotationLine.LE_SQUARE)
    assert ann.get_start_point_ending_style() == "Diamond"
    assert ann.get_end_point_ending_style() == "Square"


def test_polyline_set_start_endings_with_none_uses_le_none() -> None:
    """Mirror upstream: ``setStartPointEndingStyle(null)`` writes ``LE_NONE``."""
    ann = PDAnnotationPolyline()
    ann.set_start_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    ann.set_start_point_ending_style(None)
    assert ann.get_start_point_ending_style() == "None"


def test_polyline_individual_accessor_writes_two_element_le() -> None:
    """``/LE`` is always written as a 2-element array even when only one
    endpoint style is supplied."""
    ann = PDAnnotationPolyline()
    ann.set_start_point_ending_style(PDAnnotationLine.LE_BUTT)
    raw = ann.get_cos_object().get_dictionary_object(_LE)
    assert isinstance(raw, COSArray)
    assert raw.size() == 2
    assert isinstance(raw.get(0), COSName) and raw.get(0).name == "Butt"
    assert isinstance(raw.get(1), COSName) and raw.get(1).name == "None"


def test_polyline_individual_setter_overwrites_existing_le() -> None:
    """Setting one endpoint must not destroy the other when ``/LE`` is
    already populated — mirroring upstream ``array.setName(index, …)``."""
    ann = PDAnnotationPolyline()
    ann.set_line_ending_styles("OpenArrow", "ClosedArrow")
    ann.set_start_point_ending_style(PDAnnotationLine.LE_BUTT)
    assert ann.get_start_point_ending_style() == "Butt"
    assert ann.get_end_point_ending_style() == "ClosedArrow"


def test_polyline_get_endings_handles_short_le_array() -> None:
    """Defensive: a malformed 1-element ``/LE`` falls back to ``LE_NONE``."""
    ann = PDAnnotationPolyline()
    arr = COSArray([COSName.get_pdf_name("OpenArrow")])
    ann.get_cos_object().set_item(_LE, arr)
    assert ann.get_start_point_ending_style() == "None"
    assert ann.get_end_point_ending_style() == "None"


# ---------- /BE typed return — FreeText / Polygon / Polyline ----------


@pytest.mark.parametrize(
    "cls",
    [PDAnnotationFreeText, PDAnnotationPolygon, PDAnnotationPolyline],
)
def test_border_effect_default_none(cls: type) -> None:
    assert cls().get_border_effect() is None


@pytest.mark.parametrize(
    "cls",
    [PDAnnotationFreeText, PDAnnotationPolygon, PDAnnotationPolyline],
)
def test_border_effect_typed_wrapper(cls: type) -> None:
    ann = cls()
    be_dict = COSDictionary()
    be_dict.set_name(COSName.get_pdf_name("S"), "C")
    be_dict.set_float(COSName.get_pdf_name("I"), 2.0)
    ann.set_border_effect(be_dict)
    fetched = ann.get_border_effect()
    assert isinstance(fetched, PDBorderEffectDictionary)
    assert fetched.get_cos_object() is be_dict
    assert fetched.get_style() == PDBorderEffectDictionary.STYLE_CLOUDY
    assert fetched.get_intensity() == 2.0


@pytest.mark.parametrize(
    "cls",
    [PDAnnotationFreeText, PDAnnotationPolygon, PDAnnotationPolyline],
)
def test_border_effect_accepts_typed_wrapper_input(cls: type) -> None:
    ann = cls()
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    be.set_intensity(1.5)
    ann.set_border_effect(be)
    fetched = ann.get_border_effect()
    assert isinstance(fetched, PDBorderEffectDictionary)
    # Same underlying COSDictionary, not a new wrapper of a copy.
    assert fetched.get_cos_object() is be.get_cos_object()


@pytest.mark.parametrize(
    "cls",
    [PDAnnotationFreeText, PDAnnotationPolygon, PDAnnotationPolyline],
)
def test_border_effect_set_none_removes_entry(cls: type) -> None:
    ann = cls()
    ann.set_border_effect(COSDictionary())
    assert ann.get_cos_object().contains_key(_BE)
    ann.set_border_effect(None)
    assert ann.get_border_effect() is None
    assert not ann.get_cos_object().contains_key(_BE)


@pytest.mark.parametrize(
    "cls",
    [PDAnnotationFreeText, PDAnnotationPolygon, PDAnnotationPolyline],
)
def test_border_effect_default_style_solid(cls: type) -> None:
    """Default ``/S`` per spec is ``S`` (solid). Wrapper must surface it."""
    ann = cls()
    ann.set_border_effect(COSDictionary())
    fetched = ann.get_border_effect()
    assert fetched is not None
    assert fetched.get_style() == PDBorderEffectDictionary.STYLE_SOLID
    assert fetched.get_intensity() == 0.0
