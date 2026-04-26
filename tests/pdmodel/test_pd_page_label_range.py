from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel import PDPageLabelRange


def test_fresh_defaults() -> None:
    """A freshly constructed range has no style, no prefix, start == 1,
    and a default ``start_index`` of 0."""
    r = PDPageLabelRange()
    assert r.get_style() is None
    assert r.get_prefix() is None
    assert r.get_start() == 1
    assert r.get_start_index() == 0
    assert isinstance(r.get_cos_object(), COSDictionary)


def test_round_trip_style_prefix_start() -> None:
    r = PDPageLabelRange()
    r.set_style(PDPageLabelRange.STYLE_DECIMAL)
    r.set_prefix("page-")
    r.set_start(5)
    assert r.get_style() == PDPageLabelRange.STYLE_DECIMAL
    assert r.get_prefix() == "page-"
    assert r.get_start() == 5


def test_set_start_index_round_trip() -> None:
    r = PDPageLabelRange(start_index=4)
    assert r.get_start_index() == 4
    r.set_start_index(11)
    assert r.get_start_index() == 11


def test_compute_label_decimal_with_prefix() -> None:
    """Decimal style + start=5 + prefix='page-' → offset 0 yields 'page-5'."""
    r = PDPageLabelRange()
    r.set_style(PDPageLabelRange.STYLE_DECIMAL)
    r.set_start(5)
    r.set_prefix("page-")
    assert r.compute_label_for_offset(0) == "page-5"
    assert r.compute_label_for_offset(2) == "page-7"


def test_compute_label_roman_lower() -> None:
    """Lower roman + start=1 → offset 2 yields 'iii'."""
    r = PDPageLabelRange()
    r.set_style(PDPageLabelRange.STYLE_ROMAN_LOWER)
    assert r.compute_label_for_offset(2) == "iii"


def test_compute_label_no_style_emits_prefix_only() -> None:
    r = PDPageLabelRange()
    r.set_prefix("Cover")
    assert r.compute_label_for_offset(0) == "Cover"


def test_set_style_rejects_invalid() -> None:
    r = PDPageLabelRange()
    with pytest.raises(ValueError):
        r.set_style("X")


def test_set_style_none_clears() -> None:
    r = PDPageLabelRange()
    r.set_style(PDPageLabelRange.STYLE_DECIMAL)
    r.set_style(None)
    assert r.get_style() is None


def test_set_start_validates_positive() -> None:
    r = PDPageLabelRange()
    with pytest.raises(ValueError):
        r.set_start(0)
    with pytest.raises(ValueError):
        r.set_start(-1)


def test_constructor_wraps_existing_dictionary() -> None:
    """A pre-existing COSDictionary is reflected through the wrapper."""
    d = COSDictionary()
    r = PDPageLabelRange(d)
    r.set_style(PDPageLabelRange.STYLE_ROMAN_UPPER)
    assert r.get_cos_object() is d
    # Round-trip via a fresh wrapper around the same dictionary.
    r2 = PDPageLabelRange(d)
    assert r2.get_style() == PDPageLabelRange.STYLE_ROMAN_UPPER
