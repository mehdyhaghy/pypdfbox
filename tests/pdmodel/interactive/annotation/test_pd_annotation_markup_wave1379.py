"""Wave 1379 — per-subtype markup annotation accessors closure (agent B).

Adds coverage for the markup-base accessor pairs introduced in wave 1379:
``/IC`` (interior color), ``/Measure`` (measurement dictionary), and the
explicit ``remove_*`` / ``has_*`` predicates for ``/Popup``, ``/RC``,
``/BS``.

These tests pin behaviour at the markup base layer; the per-subtype
specialised accessors on :class:`PDAnnotationLine`,
:class:`PDAnnotationPolyline`, and :class:`PDAnnotationPolygon` continue
to be exercised by their dedicated test modules.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_popup import (
    PDAnnotationPopup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary import (
    PDMeasureDictionary,
)


class _ConcreteMarkup(PDAnnotationMarkup):
    """Tiny concrete subtype — :class:`PDAnnotationMarkup` is abstract in
    upstream; instantiate via a trivial subclass that lets us probe the
    base-class accessor surface without dragging in a real subtype's
    extra fields."""

    SUB_TYPE: str = "TestMarkup"


# ---------------------------------------------------------------------------
# /IC accessor pair
# ---------------------------------------------------------------------------


def test_interior_color_absent_returns_none() -> None:
    markup = _ConcreteMarkup()
    assert markup.get_interior_color() is None
    assert markup.has_interior_color() is False


def test_interior_color_round_trip_rgb() -> None:
    markup = _ConcreteMarkup()
    markup.set_interior_color([0.1, 0.2, 0.3])
    assert markup.get_interior_color() == pytest.approx([0.1, 0.2, 0.3])
    assert markup.has_interior_color() is True


def test_interior_color_round_trip_gray() -> None:
    markup = _ConcreteMarkup()
    markup.set_interior_color([0.5])
    assert markup.get_interior_color() == pytest.approx([0.5])


def test_interior_color_round_trip_cmyk() -> None:
    markup = _ConcreteMarkup()
    markup.set_interior_color([0.1, 0.2, 0.3, 0.4])
    assert markup.get_interior_color() == pytest.approx([0.1, 0.2, 0.3, 0.4])


def test_interior_color_accepts_tuple() -> None:
    markup = _ConcreteMarkup()
    markup.set_interior_color((1.0, 0.5, 0.0))
    assert markup.get_interior_color() == pytest.approx([1.0, 0.5, 0.0])


def test_interior_color_set_none_removes_entry() -> None:
    markup = _ConcreteMarkup()
    markup.set_interior_color([0.5, 0.5, 0.5])
    markup.set_interior_color(None)
    assert markup.get_interior_color() is None
    assert "IC" not in markup.get_cos_object()


def test_interior_color_remove_helper() -> None:
    markup = _ConcreteMarkup()
    markup.set_interior_color([0.1, 0.2, 0.3])
    markup.remove_interior_color()
    assert markup.get_interior_color() is None
    assert markup.has_interior_color() is False


def test_interior_color_ignores_non_array() -> None:
    """A stray ``/IC`` of the wrong COS type yields ``None`` from the
    getter (mirroring the per-subtype accessors' tolerant read)."""
    markup = _ConcreteMarkup()
    markup.get_cos_object().set_item(COSName.get_pdf_name("IC"), COSFloat(0.5))
    assert markup.get_interior_color() is None
    assert markup.has_interior_color() is False


# ---------------------------------------------------------------------------
# /Measure accessor pair
# ---------------------------------------------------------------------------


def test_measure_absent_returns_none() -> None:
    markup = _ConcreteMarkup()
    assert markup.get_measure() is None
    assert markup.has_measure() is False


def test_measure_round_trip_typed_wrapper() -> None:
    markup = _ConcreteMarkup()
    measure = PDMeasureDictionary()
    markup.set_measure(measure)
    fetched = markup.get_measure()
    assert isinstance(fetched, PDMeasureDictionary)
    assert fetched.get_cos_object() is measure.get_cos_object()
    assert markup.has_measure() is True


def test_measure_round_trip_raw_dict() -> None:
    markup = _ConcreteMarkup()
    raw = COSDictionary()
    raw.set_name(COSName.TYPE, "Measure")
    markup.set_measure(raw)
    fetched = markup.get_measure()
    assert isinstance(fetched, PDMeasureDictionary)
    assert fetched.get_cos_object() is raw


def test_measure_set_none_removes_entry() -> None:
    markup = _ConcreteMarkup()
    markup.set_measure(PDMeasureDictionary())
    markup.set_measure(None)
    assert markup.get_measure() is None


def test_measure_remove_helper() -> None:
    markup = _ConcreteMarkup()
    markup.set_measure(PDMeasureDictionary())
    markup.remove_measure()
    assert markup.get_measure() is None
    assert markup.has_measure() is False


def test_measure_ignores_non_dict() -> None:
    """A stray ``/Measure`` whose value is an array yields ``None``."""
    markup = _ConcreteMarkup()
    markup.get_cos_object().set_item(
        COSName.get_pdf_name("Measure"), COSArray()
    )
    assert markup.get_measure() is None
    assert markup.has_measure() is False


# ---------------------------------------------------------------------------
# /Popup remove helper
# ---------------------------------------------------------------------------


def test_remove_popup_clears_entry() -> None:
    markup = _ConcreteMarkup()
    markup.set_popup(PDAnnotationPopup())
    assert markup.has_popup() is True
    markup.remove_popup()
    assert markup.has_popup() is False
    assert markup.get_popup() is None


def test_remove_popup_idempotent_on_absent_entry() -> None:
    markup = _ConcreteMarkup()
    # Should not raise even though /Popup was never set.
    markup.remove_popup()
    assert markup.get_popup() is None


# ---------------------------------------------------------------------------
# /RC remove helper
# ---------------------------------------------------------------------------


def test_remove_rich_contents_clears_entry() -> None:
    markup = _ConcreteMarkup()
    markup.set_rich_contents("<body><p>hi</p></body>")
    assert markup.get_rich_contents() == "<body><p>hi</p></body>"
    markup.remove_rich_contents()
    assert markup.get_rich_contents() is None


def test_remove_rich_contents_idempotent_on_absent_entry() -> None:
    markup = _ConcreteMarkup()
    markup.remove_rich_contents()
    assert markup.get_rich_contents() is None


# ---------------------------------------------------------------------------
# /BS remove + has_border_style helpers
# ---------------------------------------------------------------------------


def test_remove_border_style_clears_entry() -> None:
    markup = _ConcreteMarkup()
    bs = PDBorderStyleDictionary()
    markup.set_border_style(bs)
    assert markup.has_border_style() is True
    markup.remove_border_style()
    assert markup.has_border_style() is False
    assert markup.get_border_style() is None


def test_has_border_style_false_when_value_is_not_dict() -> None:
    markup = _ConcreteMarkup()
    markup.get_cos_object().set_item(COSName.get_pdf_name("BS"), COSArray())
    assert markup.has_border_style() is False


def test_has_border_style_true_after_set() -> None:
    markup = _ConcreteMarkup()
    markup.set_border_style(PDBorderStyleDictionary())
    assert markup.has_border_style() is True


# ---------------------------------------------------------------------------
# Subclass override behaviour — base accessors don't shadow specialised ones
# ---------------------------------------------------------------------------


def test_line_subclass_interior_color_still_works_through_base_accessor() -> None:
    """Subclass overrides return their typed shapes; the base accessor on
    the same instance still produces a list (subclass result is a list
    too in :class:`PDAnnotationLine`)."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
        PDAnnotationLine,
    )

    line = PDAnnotationLine()
    line.set_interior_color([0.2, 0.4, 0.6])
    fetched = line.get_interior_color()
    assert fetched == pytest.approx([0.2, 0.4, 0.6])


def test_polyline_subclass_measure_round_trip_via_base() -> None:
    """The subclass exposes the same ``set_measure`` semantics; verify the
    base-level read path still resolves through the subclass override
    when called via the subclass instance."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polyline import (
        PDAnnotationPolyline,
    )

    poly = PDAnnotationPolyline()
    poly.set_measure(PDMeasureDictionary())
    assert isinstance(poly.get_measure(), PDMeasureDictionary)
    assert poly.has_measure() is True
