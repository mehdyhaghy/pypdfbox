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


# ---------- PDPageLabels.find_label_range_containing ----------


def test_find_label_range_containing_picks_correct_range() -> None:
    """``find_label_range_containing`` selects the range whose start is the
    greatest <= ``page_index``, mirroring ``get_label_for_page``'s walk."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.set_label_range(0, style=PDPageLabels.STYLE_ROMAN_LOWER)
    labels.set_label_range(3, style=PDPageLabels.STYLE_DECIMAL, prefix="A-")
    labels.set_label_range(7, style=PDPageLabels.STYLE_LETTERS_UPPER)

    # Page 0..2 → roman range.
    r0 = labels.find_label_range_containing(0)
    r2 = labels.find_label_range_containing(2)
    assert r0 is not None and r0.get_style() == PDPageLabels.STYLE_ROMAN_LOWER
    assert r2 is r0

    # Page 3..6 → decimal/A- range.
    r3 = labels.find_label_range_containing(3)
    r6 = labels.find_label_range_containing(6)
    assert r3 is not None and r3.get_prefix() == "A-"
    assert r6 is r3

    # Page 7+ → letters range.
    r7 = labels.find_label_range_containing(7)
    assert r7 is not None and r7.get_style() == PDPageLabels.STYLE_LETTERS_UPPER

    # Negative index → None.
    assert labels.find_label_range_containing(-1) is None


# ---------- PDPageLabels.get_labels_by_page_indices ----------


def test_get_labels_by_page_indices_spans_all_ranges() -> None:
    """The materialised label list covers every page across every range."""
    doc = _doc_with_pages(6)
    labels = PDPageLabels(doc)
    # Ranges: 0..1 lower roman, 2..4 decimal restart at 1, 5 letters upper.
    labels.set_label_range(0, style=PDPageLabels.STYLE_ROMAN_LOWER)
    labels.set_label_range(2, style=PDPageLabels.STYLE_DECIMAL)
    labels.set_label_range(5, style=PDPageLabels.STYLE_LETTERS_UPPER)

    out = labels.get_labels_by_page_indices()
    assert out == ["i", "ii", "1", "2", "3", "A"]
    # Every page index is represented.
    assert len(out) == doc.get_number_of_pages()


# ---------- PDPageLabelRange.get_prefix / set_prefix round-trip ----------


def test_range_prefix_round_trip() -> None:
    r = PDPageLabelRange()
    assert r.get_prefix() is None
    r.set_prefix("Cover-")
    assert r.get_prefix() == "Cover-"
    # Round-trip also through clear + reset.
    r.set_prefix(None)
    assert r.get_prefix() is None
    r.set_prefix("Appendix ")
    assert r.get_prefix() == "Appendix "


# ---------- PDPageLabelRange.get_start default ----------


def test_range_get_start_defaults_to_one() -> None:
    """Per PDF 32000-1 §12.4.2 Table 159, /St defaults to 1 when absent."""
    r = PDPageLabelRange()
    assert r.get_start() == 1


# ---------- PDPageLabelRange.format_label_index alias ----------


def test_format_label_index_matches_compute_label_for_offset() -> None:
    r = PDPageLabelRange()
    r.set_style(PDPageLabelRange.STYLE_ROMAN_LOWER)
    r.set_start(5)
    r.set_prefix("Pre-")
    for offset in (0, 1, 2, 3, 9, 13):
        assert r.format_label_index(offset) == r.compute_label_for_offset(
            offset
        )


# ---------- PDPageLabels.has_label_range / remove_label_range ----------


def test_has_label_range_default_only() -> None:
    """A fresh ``PDPageLabels`` always has the required default range at 0."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    assert labels.has_label_range(0) is True
    assert labels.has_label_range(1) is False
    assert labels.has_label_range(-1) is False


def test_has_label_range_after_set() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.set_label_range(3, style=PDPageLabels.STYLE_DECIMAL)
    assert labels.has_label_range(0) is True
    assert labels.has_label_range(3) is True
    assert labels.has_label_range(4) is False


def test_remove_label_range_returns_true_when_removed() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.set_label_range(2, style=PDPageLabels.STYLE_ROMAN_UPPER)
    assert labels.has_label_range(2) is True
    assert labels.remove_label_range(2) is True
    assert labels.has_label_range(2) is False
    # Idempotent — second remove returns False.
    assert labels.remove_label_range(2) is False


def test_remove_label_range_returns_false_when_absent() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    assert labels.remove_label_range(99) is False
    # Default range still present.
    assert labels.has_label_range(0) is True


def test_remove_default_range_allowed() -> None:
    """Removing the default range at 0 is permitted (matches the
    underlying TreeMap behaviour upstream uses)."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    assert labels.remove_label_range(0) is True
    assert labels.get_page_range_count() == 0
    assert labels.has_label_range(0) is False


# ---------- PDPageLabels.get_first_page_index / get_last_page_index ----------


def test_first_and_last_page_index_default() -> None:
    """Fresh PDPageLabels: only the default range at 0 — first == last == 0."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    assert labels.get_first_page_index() == 0
    assert labels.get_last_page_index() == 0


def test_first_and_last_page_index_multi_range() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.set_label_range(0, style=PDPageLabels.STYLE_ROMAN_LOWER)
    labels.set_label_range(7, style=PDPageLabels.STYLE_DECIMAL)
    labels.set_label_range(3, style=PDPageLabels.STYLE_LETTERS_UPPER)
    assert labels.get_first_page_index() == 0
    assert labels.get_last_page_index() == 7


def test_first_and_last_page_index_when_empty() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.remove_label_range(0)
    assert labels.get_first_page_index() is None
    assert labels.get_last_page_index() is None
