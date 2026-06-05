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


def test_set_style_stores_arbitrary_value_like_upstream() -> None:
    # Upstream PDPageLabelRange.setStyle stores ANY string verbatim via
    # setName (no validation); the label generator falls back to decimal for
    # unrecognised codes. Confirmed against Apache PDFBox 3.0.7
    # (PageLabelRangeAccessorProbe: setStyle("Q") -> getStyle()=="Q").
    r = PDPageLabelRange()
    r.set_style("X")
    assert r.get_style() == "X"


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


def test_set_prefix_empty_string_round_trips() -> None:
    """An empty prefix is a legal value (matches upstream's ``setString``
    behaviour), distinct from ``None`` which clears the entry."""
    r = PDPageLabelRange()
    r.set_prefix("")
    # Upstream stores the empty string; our get_prefix mirrors that.
    assert r.get_prefix() == ""
    # ``compute_label_for_offset`` with an empty prefix and no style yields
    # an empty label — no spurious whitespace or formatting.
    assert r.compute_label_for_offset(0) == ""


def test_set_prefix_none_after_value_clears_entry() -> None:
    """Setting prefix to ``None`` removes the /P entry entirely (mirrors
    upstream ``setPrefix(null)``)."""
    r = PDPageLabelRange()
    r.set_prefix("draft-")
    assert r.get_prefix() == "draft-"
    r.set_prefix(None)
    assert r.get_prefix() is None
    # /P key really gone from the underlying dictionary.
    assert not r.get_cos_object().contains_key("P")


def test_compute_label_trims_prefix_at_first_nul() -> None:
    """PDFBOX-1047: a prefix containing a NUL is truncated at the first NUL
    byte when rendering labels (the underlying dict still holds the raw
    string, only ``compute_label_for_offset`` trims)."""
    r = PDPageLabelRange()
    r.set_style(PDPageLabelRange.STYLE_DECIMAL)
    r.set_prefix("App\x00endix-")
    # Render-time trim — only "App" survives.
    assert r.compute_label_for_offset(0) == "App1"
    # Underlying dict keeps the raw prefix unchanged (round-trip
    # serialization should not silently rewrite it).
    assert r.get_prefix() == "App\x00endix-"
