from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray
from pypdfbox.pdmodel.documentinterchange.taggedpdf import PDFourColours

# ---------- British-spelled (upstream-parity) named accessors ----------


def test_named_colour_round_trip() -> None:
    four = PDFourColours()
    four.set_before_colour((1.0, 0.0, 0.0))
    four.set_after_colour((0.0, 1.0, 0.0))
    four.set_start_colour((0.0, 0.0, 1.0))
    four.set_end_colour((0.25, 0.5, 0.75))
    assert four.get_before_colour() == (1.0, 0.0, 0.0)
    assert four.get_after_colour() == (0.0, 1.0, 0.0)
    assert four.get_start_colour() == (0.0, 0.0, 1.0)
    assert four.get_end_colour() == (0.25, 0.5, 0.75)


# ---------- geometric-edge accessors share storage with British names ----------


def test_geometric_aliases_share_slots() -> None:
    four = PDFourColours()
    # Use exactly-representable binary fractions so float round-trip is bit-stable.
    four.set_top((0.0, 0.5, 1.0))
    four.set_right((0.25, 0.5, 0.75))
    four.set_bottom((0.125, 0.25, 0.5))
    four.set_left((0.0625, 0.125, 0.1875))
    # Geometric setters write to identical slots as the British accessors.
    assert four.get_before_colour() == (0.0, 0.5, 1.0)
    assert four.get_after_colour() == (0.25, 0.5, 0.75)
    assert four.get_start_colour() == (0.125, 0.25, 0.5)
    assert four.get_end_colour() == (0.0625, 0.125, 0.1875)
    # And vice-versa.
    four.set_before_colour((0.0, 0.0, 0.0))
    assert four.get_top() == (0.0, 0.0, 0.0)


# ---------- index-based access ----------


def test_colour_by_index_round_trip() -> None:
    four = PDFourColours()
    # Exactly-representable fractions so float round-trip is bit-stable.
    four.set_colour_by_index(0, (0.125, 0.125, 0.125))
    four.set_colour_by_index(1, (0.25, 0.25, 0.25))
    four.set_colour_by_index(2, (0.5, 0.5, 0.5))
    four.set_colour_by_index(3, (0.75, 0.75, 0.75))
    assert four.get_colour_by_index(0) == (0.125, 0.125, 0.125)
    assert four.get_colour_by_index(1) == (0.25, 0.25, 0.25)
    assert four.get_colour_by_index(2) == (0.5, 0.5, 0.5)
    assert four.get_colour_by_index(3) == (0.75, 0.75, 0.75)
    # Mapping: index 2 == start.
    assert four.get_start_colour() == (0.5, 0.5, 0.5)


def test_colour_by_index_out_of_range_raises() -> None:
    four = PDFourColours()
    with pytest.raises(IndexError):
        four.get_colour_by_index(4)
    with pytest.raises(IndexError):
        four.set_colour_by_index(-1, (0.0, 0.0, 0.0))


# ---------- default state on a fresh empty COSArray ----------


def test_default_state_is_empty_tuple_for_each_side() -> None:
    four = PDFourColours(COSArray())
    # No colour has been written; each slot is an empty inner array, which
    # surfaces as () (no components) rather than None.
    assert four.get_before_colour() == ()
    assert four.get_after_colour() == ()
    assert four.get_start_colour() == ()
    assert four.get_end_colour() == ()
    # COS surface is the four-slot envelope.
    assert four.get_cos_object() is four.get_cos_array()
    assert four.get_cos_object().size() == 4


# ---------- index 2 → set_colour_by_index → get_start_colour parity ----------


def test_set_index_two_visible_via_get_start_colour() -> None:
    four = PDFourColours()
    four.set_colour_by_index(2, (0.5, 0.5, 0.5))
    assert four.get_start_colour() == (0.5, 0.5, 0.5)
    # And via the geometric alias (index 2 == bottom).
    assert four.get_bottom() == (0.5, 0.5, 0.5)
