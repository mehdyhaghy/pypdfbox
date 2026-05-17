"""Coverage-boost tests for :mod:`pypdfbox.pdmodel.fdf.fdf_annotation`.

Targets the dispatch branches in :meth:`FDFAnnotation.create` (Polygon,
PolyLine/Polyline, Ink, Stamp, Caret, TextMarkup variants, unknown
subtype fallback), plus the rare error paths in
``get_rectangle_as_pd_rectangle``, ``set_rich_contents`` removal, and
``parse_rectangle_attributes``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSString
from pypdfbox.pdmodel.fdf import FDFAnnotation
from pypdfbox.pdmodel.fdf.fdf_annotation_caret import FDFAnnotationCaret
from pypdfbox.pdmodel.fdf.fdf_annotation_ink import FDFAnnotationInk
from pypdfbox.pdmodel.fdf.fdf_annotation_polygon import FDFAnnotationPolygon
from pypdfbox.pdmodel.fdf.fdf_annotation_polyline import FDFAnnotationPolyline
from pypdfbox.pdmodel.fdf.fdf_annotation_stamp import FDFAnnotationStamp
from pypdfbox.pdmodel.fdf.fdf_annotation_text_markup import (
    FDFAnnotationTextMarkup,
)

_SUBTYPE = COSName.get_pdf_name("Subtype")
_RC = COSName.get_pdf_name("RC")
_RECT = COSName.get_pdf_name("Rect")


def _dict_with_subtype(subtype: str) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_SUBTYPE, COSName.get_pdf_name(subtype))
    return d


# ----------------------------------------------------------------------
# create() dispatch — lines 591-615 (Polygon, PolyLine, Polyline, Ink,
# Stamp, Caret, Highlight/Underline/StrikeOut/Squiggly, unknown fallback)
# ----------------------------------------------------------------------


def test_create_dispatches_polygon() -> None:
    annot = FDFAnnotation.create(_dict_with_subtype("Polygon"))
    assert isinstance(annot, FDFAnnotationPolygon)


def test_create_dispatches_polyline_capitalised() -> None:
    annot = FDFAnnotation.create(_dict_with_subtype("PolyLine"))
    assert isinstance(annot, FDFAnnotationPolyline)


def test_create_dispatches_polyline_lowercase_l() -> None:
    """Both ``PolyLine`` and ``Polyline`` (lowercase l) are accepted."""
    annot = FDFAnnotation.create(_dict_with_subtype("Polyline"))
    assert isinstance(annot, FDFAnnotationPolyline)


def test_create_dispatches_ink() -> None:
    annot = FDFAnnotation.create(_dict_with_subtype("Ink"))
    assert isinstance(annot, FDFAnnotationInk)


def test_create_dispatches_stamp() -> None:
    annot = FDFAnnotation.create(_dict_with_subtype("Stamp"))
    assert isinstance(annot, FDFAnnotationStamp)


def test_create_dispatches_caret() -> None:
    annot = FDFAnnotation.create(_dict_with_subtype("Caret"))
    assert isinstance(annot, FDFAnnotationCaret)


@pytest.mark.parametrize(
    "subtype", ["Highlight", "Underline", "StrikeOut", "Squiggly"]
)
def test_create_dispatches_text_markup_variants(subtype: str) -> None:
    annot = FDFAnnotation.create(_dict_with_subtype(subtype))
    assert isinstance(annot, FDFAnnotationTextMarkup)


def test_create_unknown_subtype_falls_back_to_base() -> None:
    """Line 615: an unrecognised ``/Subtype`` returns the bare
    ``FDFAnnotation`` rather than raising."""
    annot = FDFAnnotation.create(_dict_with_subtype("UnknownSubtype"))
    assert type(annot) is FDFAnnotation


def test_create_missing_subtype_falls_back_to_base() -> None:
    """Line 615: a dictionary with no ``/Subtype`` also returns the bare
    ``FDFAnnotation`` — ``sub`` is ``None`` so the dispatch chain falls
    through."""
    annot = FDFAnnotation.create(COSDictionary())
    assert type(annot) is FDFAnnotation


# ----------------------------------------------------------------------
# get_rectangle_as_pd_rectangle TypeError path — lines 186-187
# ----------------------------------------------------------------------


def test_get_rectangle_as_pd_rectangle_returns_none_on_non_numeric_entry() -> None:
    """A /Rect array with a non-numeric entry triggers
    ``PDRectangle.from_cos_array``'s TypeError -> caller swallows it."""
    a = FDFAnnotation()
    bogus = COSArray()
    bogus.add(COSFloat(0.0))
    bogus.add(COSFloat(0.0))
    # Insert a name instead of a number in slot 2 — triggers TypeError
    # in PDRectangle.from_cos_array.
    bogus.add(COSName.get_pdf_name("Bad"))
    bogus.add(COSFloat(10.0))
    a.get_cos_object().set_item(_RECT, bogus)
    assert a.get_rectangle_as_pd_rectangle() is None


def test_get_rectangle_as_pd_rectangle_returns_none_when_absent() -> None:
    """Bottom return (line 188): no ``/Rect`` at all -> ``None``."""
    a = FDFAnnotation()
    assert a.get_rectangle_as_pd_rectangle() is None


def test_get_rectangle_as_pd_rectangle_returns_none_for_wrong_length() -> None:
    """A 3-entry /Rect array doesn't match ``len(v) == 4`` -> ``None``."""
    a = FDFAnnotation()
    short = COSArray()
    for _ in range(3):
        short.add(COSFloat(0.0))
    a.get_cos_object().set_item(_RECT, short)
    assert a.get_rectangle_as_pd_rectangle() is None


# ----------------------------------------------------------------------
# set_rich_contents None removal — lines 469-471
# ----------------------------------------------------------------------


def test_set_rich_contents_none_removes_entry() -> None:
    """Lines 469-471: passing ``None`` deletes ``/RC``."""
    a = FDFAnnotation()
    a.set_rich_contents("<p>hi</p>")
    assert a.get_cos_object().get_dictionary_object(_RC) is not None
    a.set_rich_contents(None)
    assert a.get_cos_object().get_dictionary_object(_RC) is None


def test_set_rich_contents_writes_cos_string() -> None:
    a = FDFAnnotation()
    a.set_rich_contents("<p>hi</p>")
    entry = a.get_cos_object().get_dictionary_object(_RC)
    assert isinstance(entry, COSString)


# ----------------------------------------------------------------------
# parse_rectangle_attributes error paths — lines 521, 527-528
# ----------------------------------------------------------------------


def test_parse_rectangle_attributes_none_raises() -> None:
    """Line 521: a ``None`` rect string raises ``OSError`` with the
    supplied message."""
    a = FDFAnnotation()
    with pytest.raises(OSError, match="missing rect"):
        a.parse_rectangle_attributes(None, "missing rect")  # type: ignore[arg-type]


def test_parse_rectangle_attributes_non_numeric_raises() -> None:
    """Lines 527-528: a non-numeric token wraps the ValueError in OSError."""
    a = FDFAnnotation()
    with pytest.raises(OSError, match="malformed"):
        a.parse_rectangle_attributes("1,2,three,4", "malformed")


def test_parse_rectangle_attributes_wrong_count_raises() -> None:
    """Length-mismatch path also raises OSError."""
    a = FDFAnnotation()
    with pytest.raises(OSError, match="bad count"):
        a.parse_rectangle_attributes("1,2,3", "bad count")


def test_create_rectangle_from_attributes_round_trip() -> None:
    """The error-message-propagating helper also has a happy path."""
    a = FDFAnnotation()
    rect = a.create_rectangle_from_attributes("1.0,2.0,3.0,4.0", "ignored")
    assert rect.get_lower_left_x() == 1.0
    assert rect.get_lower_left_y() == 2.0
    assert rect.get_upper_right_x() == 3.0
    assert rect.get_upper_right_y() == 4.0
