"""Hand-written tests for ``PDPageXYZDestination`` (``/XYZ``).

Covers the unset-slot predicates, the ``UNSET`` sentinel constant,
``is_complete()``, and the ``clear_*`` convenience helpers added to
mirror upstream's ``-1`` "use current viewer value" semantics from
``org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageXYZDestination``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSNull
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageDestination,
    PDPageXYZDestination,
)


# ---------- class-level constants ----------


def test_type_constant_is_xyz() -> None:
    assert PDPageXYZDestination.TYPE == "XYZ"


def test_unset_constant_is_minus_one() -> None:
    """Upstream parity: the sentinel for 'use current viewer value' is -1."""
    assert PDPageXYZDestination.UNSET == -1


def test_slot_indices_are_two_three_four() -> None:
    """The /D array layout is [page /XYZ left top zoom]; slots 2..4
    hold the geometry. The constants pin that layout."""
    assert PDPageXYZDestination._SLOT_LEFT == 2
    assert PDPageXYZDestination._SLOT_TOP == 3
    assert PDPageXYZDestination._SLOT_ZOOM == 4


# ---------- inheritance & default construction ----------


def test_inherits_pd_page_destination() -> None:
    dest = PDPageXYZDestination()
    assert isinstance(dest, PDPageDestination)


def test_default_construction_writes_xyz_type() -> None:
    dest = PDPageXYZDestination()
    assert dest.get_type() == "XYZ"


# ---------- is_*_unset predicates ----------


def test_is_left_unset_true_on_default_construction() -> None:
    dest = PDPageXYZDestination()
    assert dest.is_left_unset() is True


def test_is_top_unset_true_on_default_construction() -> None:
    dest = PDPageXYZDestination()
    assert dest.is_top_unset() is True


def test_is_zoom_unset_true_on_default_construction() -> None:
    dest = PDPageXYZDestination()
    assert dest.is_zoom_unset() is True


def test_is_left_unset_false_after_set_left() -> None:
    dest = PDPageXYZDestination()
    dest.set_left(72.5)
    assert dest.is_left_unset() is False


def test_is_top_unset_false_after_set_top() -> None:
    dest = PDPageXYZDestination()
    dest.set_top(540.0)
    assert dest.is_top_unset() is False


def test_is_zoom_unset_false_after_set_zoom() -> None:
    dest = PDPageXYZDestination()
    dest.set_zoom(1.5)
    assert dest.is_zoom_unset() is False


def test_is_zoom_unset_false_when_zoom_is_zero() -> None:
    """Zero is a valid (if unusual) zoom value — it isn't a missing slot.
    Upstream stores it verbatim and our predicate respects that."""
    dest = PDPageXYZDestination()
    dest.set_zoom(0.0)
    assert dest.is_zoom_unset() is False
    assert dest.get_zoom() == 0.0


def test_predicates_flip_back_to_true_after_clearing_with_none() -> None:
    """``set_*(None)`` writes ``COSNull`` and the unset predicates report
    that as 'unset' again."""
    dest = PDPageXYZDestination()
    dest.set_left(10.0)
    dest.set_top(20.0)
    dest.set_zoom(2.0)

    dest.set_left(None)
    dest.set_top(None)
    dest.set_zoom(None)

    assert dest.is_left_unset() is True
    assert dest.is_top_unset() is True
    assert dest.is_zoom_unset() is True


def test_unset_predicates_handle_short_array() -> None:
    """If the ``/D`` array is shorter than the slot index, the predicate
    treats the slot as unset rather than raising ``IndexError``."""
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("XYZ")])
    dest = PDPageXYZDestination(arr)

    assert dest.is_left_unset() is True
    assert dest.is_top_unset() is True
    assert dest.is_zoom_unset() is True


def test_unset_predicates_recognise_explicit_cos_null() -> None:
    """An array with explicit ``COSNull`` entries in the geometry slots
    behaves the same as a short/missing array."""
    arr = COSArray([
        COSInteger.get(0),
        COSName.get_pdf_name("XYZ"),
        COSNull.NULL,
        COSNull.NULL,
        COSNull.NULL,
    ])
    dest = PDPageXYZDestination(arr)

    assert dest.is_left_unset() is True
    assert dest.is_top_unset() is True
    assert dest.is_zoom_unset() is True


# ---------- is_complete() ----------


def test_is_complete_false_on_default_construction() -> None:
    """A fresh destination has no coordinates set — ``is_complete()`` is False."""
    dest = PDPageXYZDestination()
    assert dest.is_complete() is False


def test_is_complete_true_when_all_three_coordinates_set() -> None:
    dest = PDPageXYZDestination()
    dest.set_left(10.0)
    dest.set_top(20.0)
    dest.set_zoom(1.0)
    assert dest.is_complete() is True


def test_is_complete_false_when_only_two_set() -> None:
    dest = PDPageXYZDestination()
    dest.set_left(10.0)
    dest.set_top(20.0)
    # zoom omitted
    assert dest.is_complete() is False


def test_is_complete_false_when_left_missing() -> None:
    dest = PDPageXYZDestination()
    dest.set_top(20.0)
    dest.set_zoom(1.0)
    assert dest.is_complete() is False


def test_is_complete_false_when_top_missing() -> None:
    dest = PDPageXYZDestination()
    dest.set_left(10.0)
    dest.set_zoom(1.0)
    assert dest.is_complete() is False


def test_is_complete_false_when_zoom_missing() -> None:
    dest = PDPageXYZDestination()
    dest.set_left(10.0)
    dest.set_top(20.0)
    assert dest.is_complete() is False


def test_is_complete_true_with_zoom_zero() -> None:
    """Zoom 0 is still a written value, so ``is_complete()`` is True."""
    dest = PDPageXYZDestination()
    dest.set_left(10.0)
    dest.set_top(20.0)
    dest.set_zoom(0.0)
    assert dest.is_complete() is True


# ---------- clear_*() helpers ----------


def test_clear_left_writes_cos_null_at_slot_two() -> None:
    dest = PDPageXYZDestination()
    dest.set_left(10.0)
    assert dest.is_left_unset() is False

    dest.clear_left()

    assert dest.is_left_unset() is True
    assert dest.get_left() is None
    assert dest.get_cos_array().get(2) is COSNull.NULL


def test_clear_top_writes_cos_null_at_slot_three() -> None:
    dest = PDPageXYZDestination()
    dest.set_top(20.0)
    assert dest.is_top_unset() is False

    dest.clear_top()

    assert dest.is_top_unset() is True
    assert dest.get_top() is None
    assert dest.get_cos_array().get(3) is COSNull.NULL


def test_clear_zoom_writes_cos_null_at_slot_four() -> None:
    dest = PDPageXYZDestination()
    dest.set_zoom(1.5)
    assert dest.is_zoom_unset() is False

    dest.clear_zoom()

    assert dest.is_zoom_unset() is True
    assert dest.get_zoom() is None
    assert dest.get_cos_array().get(4) is COSNull.NULL


def test_clear_left_grows_array_when_short() -> None:
    """``clear_left`` on a too-short array still works — it grows the
    underlying array to fit slot 2 and writes ``COSNull``."""
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("XYZ")])
    dest = PDPageXYZDestination(arr)

    dest.clear_left()

    assert dest.get_cos_array().size() >= 3
    assert dest.is_left_unset() is True


def test_clear_zoom_does_not_clear_other_slots() -> None:
    """``clear_zoom()`` only touches slot 4 — left/top remain set."""
    dest = PDPageXYZDestination()
    dest.set_left(10.0)
    dest.set_top(20.0)
    dest.set_zoom(1.5)

    dest.clear_zoom()

    assert dest.is_left_unset() is False
    assert dest.is_top_unset() is False
    assert dest.is_zoom_unset() is True
    assert dest.get_left() == 10.0
    assert dest.get_top() == 20.0


def test_clear_helpers_idempotent() -> None:
    """Clearing a slot that's already null is a no-op (stays null)."""
    dest = PDPageXYZDestination()
    dest.clear_left()
    dest.clear_left()
    dest.clear_top()
    dest.clear_top()
    dest.clear_zoom()
    dest.clear_zoom()

    assert dest.is_left_unset() is True
    assert dest.is_top_unset() is True
    assert dest.is_zoom_unset() is True


# ---------- interaction with existing accessors ----------


def test_unset_predicates_match_get_returns_none() -> None:
    """Predicate parity: ``is_*_unset()`` ↔ ``get_*() is None``."""
    dest = PDPageXYZDestination()
    assert dest.is_left_unset() == (dest.get_left() is None)
    assert dest.is_top_unset() == (dest.get_top() is None)
    assert dest.is_zoom_unset() == (dest.get_zoom() is None)

    dest.set_left(0.0)
    dest.set_top(0.0)
    dest.set_zoom(0.0)
    assert dest.is_left_unset() == (dest.get_left() is None)
    assert dest.is_top_unset() == (dest.get_top() is None)
    assert dest.is_zoom_unset() == (dest.get_zoom() is None)


def test_unset_predicates_preserve_for_int_value() -> None:
    """A ``COSInteger`` in the geometry slot counts as set, not unset."""
    arr = COSArray([
        COSInteger.get(0),
        COSName.get_pdf_name("XYZ"),
        COSInteger.get(50),
        COSInteger.get(60),
        COSInteger.get(2),
    ])
    dest = PDPageXYZDestination(arr)

    assert dest.is_left_unset() is False
    assert dest.is_top_unset() is False
    assert dest.is_zoom_unset() is False
    assert dest.is_complete() is True


def test_unset_predicates_preserve_for_float_value() -> None:
    arr = COSArray([
        COSInteger.get(0),
        COSName.get_pdf_name("XYZ"),
        COSFloat(50.5),
        COSFloat(60.25),
        COSFloat(2.0),
    ])
    dest = PDPageXYZDestination(arr)

    assert dest.is_left_unset() is False
    assert dest.is_top_unset() is False
    assert dest.is_zoom_unset() is False
