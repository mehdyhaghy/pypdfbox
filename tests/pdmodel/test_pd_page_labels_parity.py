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
