"""Wave 226 — PDPageLabels / PDPageLabelRange Pythonic surface helpers.

Covers:
- ``PDPageLabelRange.is_empty()`` predicate.
- ``PDPageLabelRange.has_style()`` / ``has_prefix()`` / ``has_start()``
  presence predicates that distinguish "absent" from "explicit default".
- ``PDPageLabelRange.__eq__`` / ``__hash__`` structural-equality semantics.
- ``PDPageLabels.__iter__`` yielding sorted start-page indices.
- ``PDPageLabels.has_default_range`` and ``ensure_default_range``
  idempotent default-entry helpers (matters after ``clear_label_ranges``).
- ``PDPageLabels.copy()`` shallow clone of all ranges.
"""

from __future__ import annotations

from pypdfbox.pdmodel import (
    PDDocument,
    PDPage,
    PDPageLabelRange,
    PDPageLabels,
)


def _doc_with_pages(n: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n):
        doc.add_page(PDPage())
    return doc


# ---------- PDPageLabelRange.is_empty ----------


def test_range_is_empty_on_fresh_instance() -> None:
    """Fresh ``PDPageLabelRange()`` has no /S, /P, /St → empty."""
    assert PDPageLabelRange().is_empty()


def test_range_not_empty_after_setting_style() -> None:
    r = PDPageLabelRange()
    r.set_style(PDPageLabelRange.STYLE_ROMAN_LOWER)
    assert not r.is_empty()


def test_range_not_empty_after_setting_prefix() -> None:
    r = PDPageLabelRange()
    r.set_prefix("App-")
    assert not r.is_empty()


def test_range_not_empty_after_setting_start() -> None:
    r = PDPageLabelRange()
    r.set_start(7)
    assert not r.is_empty()


def test_range_is_empty_after_clearing_style() -> None:
    r = PDPageLabelRange()
    r.set_style(PDPageLabelRange.STYLE_DECIMAL)
    r.set_style(None)
    assert r.is_empty()


# ---------- has_style / has_prefix / has_start ----------


def test_has_style_present_and_absent() -> None:
    r = PDPageLabelRange()
    assert not r.has_style()
    r.set_style(PDPageLabelRange.STYLE_DECIMAL)
    assert r.has_style()
    r.set_style(None)
    assert not r.has_style()


def test_has_prefix_distinguishes_absent_from_empty_string() -> None:
    """Absent /P → has_prefix() False; explicit "" → has_prefix() True."""
    r = PDPageLabelRange()
    assert not r.has_prefix()
    r.set_prefix("")
    # Empty-string prefix is recorded explicitly per PDF 32000-1.
    assert r.has_prefix()
    assert r.get_prefix() == ""
    r.set_prefix(None)
    assert not r.has_prefix()


def test_has_start_distinguishes_default_from_explicit_one() -> None:
    """When /St is absent, get_start() returns the spec default 1, but
    has_start() returns False — the entry was never written."""
    r = PDPageLabelRange()
    assert not r.has_start()
    assert r.get_start() == 1  # spec default
    r.set_start(1)
    # Now /St=1 is recorded explicitly even though it matches the default.
    assert r.has_start()
    assert r.get_start() == 1


# ---------- structural equality ----------


def test_range_equal_when_attributes_match() -> None:
    """Two ranges with identical style/prefix/start/start_index are ==."""
    a = PDPageLabelRange(start_index=3)
    a.set_style(PDPageLabelRange.STYLE_ROMAN_UPPER)
    a.set_prefix("Ch")
    a.set_start(2)
    b = PDPageLabelRange(start_index=3)
    b.set_style(PDPageLabelRange.STYLE_ROMAN_UPPER)
    b.set_prefix("Ch")
    b.set_start(2)
    assert a == b
    assert hash(a) == hash(b)


def test_range_not_equal_when_style_differs() -> None:
    a = PDPageLabelRange()
    a.set_style(PDPageLabelRange.STYLE_DECIMAL)
    b = PDPageLabelRange()
    b.set_style(PDPageLabelRange.STYLE_ROMAN_LOWER)
    assert a != b


def test_range_not_equal_when_prefix_differs() -> None:
    a = PDPageLabelRange()
    a.set_prefix("A-")
    b = PDPageLabelRange()
    b.set_prefix("B-")
    assert a != b


def test_range_not_equal_when_start_index_differs() -> None:
    """``start_index`` is a positional attribute, not stored in COS — but
    structural equality treats it as part of identity."""
    a = PDPageLabelRange(start_index=0)
    b = PDPageLabelRange(start_index=5)
    assert a != b


def test_range_eq_returns_not_implemented_for_non_range() -> None:
    """Comparing to a non-range returns NotImplemented (so Python falls
    back to ``other.__eq__(self)`` and ultimately ``False``)."""
    r = PDPageLabelRange()
    # Comparison with arbitrary other type does not raise.
    assert r != 42
    assert r != "decimal"
    assert r != None  # noqa: E711 — testing the contract


def test_range_hash_matches_eq_in_sets() -> None:
    """Hashable ranges work correctly in a Python ``set``."""
    a = PDPageLabelRange()
    a.set_style(PDPageLabelRange.STYLE_DECIMAL)
    a.set_prefix("X")
    b = PDPageLabelRange()
    b.set_style(PDPageLabelRange.STYLE_DECIMAL)
    b.set_prefix("X")
    s = {a, b}
    assert len(s) == 1


# ---------- PDPageLabels.__iter__ ----------


def test_labels_iter_yields_sorted_start_pages() -> None:
    doc = _doc_with_pages(20)
    labels = PDPageLabels(doc)
    labels.set_label_range(10, style=PDPageLabelRange.STYLE_ROMAN_LOWER)
    labels.set_label_range(5, style=PDPageLabelRange.STYLE_LETTERS_UPPER)
    labels.set_label_range(15, style=PDPageLabelRange.STYLE_DECIMAL)
    assert list(labels) == [0, 5, 10, 15]


def test_labels_iter_default_only_yields_zero() -> None:
    doc = _doc_with_pages(3)
    labels = PDPageLabels(doc)
    assert list(labels) == [0]


def test_labels_iter_after_clear_yields_nothing() -> None:
    doc = _doc_with_pages(3)
    labels = PDPageLabels(doc)
    labels.clear_label_ranges()
    assert list(labels) == []


# ---------- has_default_range / ensure_default_range ----------


def test_has_default_range_on_fresh_instance() -> None:
    doc = _doc_with_pages(2)
    labels = PDPageLabels(doc)
    assert labels.has_default_range()


def test_has_default_range_false_after_remove() -> None:
    doc = _doc_with_pages(2)
    labels = PDPageLabels(doc)
    assert labels.remove_label_range(0) is True
    assert not labels.has_default_range()


def test_ensure_default_range_returns_existing() -> None:
    doc = _doc_with_pages(2)
    labels = PDPageLabels(doc)
    existing = labels.get_page_label_range(0)
    again = labels.ensure_default_range()
    assert again is existing


def test_ensure_default_range_creates_when_absent() -> None:
    doc = _doc_with_pages(2)
    labels = PDPageLabels(doc)
    labels.clear_label_ranges()
    assert not labels.has_default_range()
    fresh = labels.ensure_default_range()
    assert labels.has_default_range()
    assert fresh.get_style() == PDPageLabelRange.STYLE_DECIMAL
    assert fresh.get_prefix() is None


def test_ensure_default_range_idempotent() -> None:
    """Calling ensure_default_range twice returns the same instance."""
    doc = _doc_with_pages(2)
    labels = PDPageLabels(doc)
    labels.clear_label_ranges()
    first = labels.ensure_default_range()
    second = labels.ensure_default_range()
    assert first is second


# ---------- PDPageLabels.copy() ----------


def test_copy_preserves_all_ranges() -> None:
    doc = _doc_with_pages(15)
    labels = PDPageLabels(doc)
    labels.set_label_range(
        5, style=PDPageLabelRange.STYLE_ROMAN_LOWER, prefix="pre-"
    )
    labels.set_label_range(
        10, style=PDPageLabelRange.STYLE_LETTERS_UPPER, start_number=3
    )
    clone = labels.copy()
    assert list(clone) == [0, 5, 10]
    assert clone.get_label_for_page(5) == "pre-i"
    assert clone.get_label_for_page(10) == "C"


def test_copy_is_independent_of_source() -> None:
    """Mutating the clone's ranges does not change the source."""
    doc = _doc_with_pages(8)
    labels = PDPageLabels(doc)
    labels.set_label_range(3, style=PDPageLabelRange.STYLE_ROMAN_LOWER)
    clone = labels.copy()

    # Mutate the cloned range.
    clone.get_page_label_range(3).set_style(PDPageLabelRange.STYLE_DECIMAL)
    # Original is untouched.
    assert (
        labels.get_page_label_range(3).get_style()
        == PDPageLabelRange.STYLE_ROMAN_LOWER
    )


def test_copy_independent_after_clear_in_source() -> None:
    doc = _doc_with_pages(5)
    labels = PDPageLabels(doc)
    labels.set_label_range(2, style=PDPageLabelRange.STYLE_ROMAN_LOWER)
    clone = labels.copy()
    labels.clear_label_ranges()
    # Clone retains its content.
    assert list(clone) == [0, 2]
    assert list(labels) == []


def test_copy_preserves_explicit_page_count_override() -> None:
    doc = _doc_with_pages(2)
    labels = PDPageLabels(doc)
    labels.set_number_of_pages(99)
    clone = labels.copy()
    assert clone.get_number_of_pages() == 99


def test_copy_of_empty_labels_yields_empty() -> None:
    doc = _doc_with_pages(2)
    labels = PDPageLabels(doc)
    labels.clear_label_ranges()
    clone = labels.copy()
    assert list(clone) == []
    assert not clone.has_default_range()
