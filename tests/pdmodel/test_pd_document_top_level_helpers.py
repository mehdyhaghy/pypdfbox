"""Tests for the pypdfbox-only top-level helpers on ``PDDocument``:

- :meth:`PDDocument.split`
- :meth:`PDDocument.extract_pages`
- :meth:`PDDocument.merge`

Each delegates to the corresponding multipdf class. Splitter and
PDFMergerUtility may land in a later wave; the tests use
``pytest.importorskip`` to remain dispatch-order-agnostic.
"""

from __future__ import annotations

import pytest

from pypdfbox import PDDocument, PDPage


def _build_doc(num_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(num_pages):
        doc.add_page(PDPage())
    return doc


# ---------------------------------------------------------------------------
# extract_pages — backed by PageExtractor (already lives in the tree)
# ---------------------------------------------------------------------------


def test_extract_pages_returns_subrange() -> None:
    src = _build_doc(4)
    sub = src.extract_pages(2, 3)
    try:
        assert isinstance(sub, PDDocument)
        assert sub.get_number_of_pages() == 2
    finally:
        sub.close()
        src.close()


def test_extract_pages_full_range_matches_input() -> None:
    src = _build_doc(4)
    sub = src.extract_pages(1, 4)
    try:
        assert sub.get_number_of_pages() == 4
    finally:
        sub.close()
        src.close()


def test_extract_pages_clamps_end_to_doc_length() -> None:
    src = _build_doc(4)
    sub = src.extract_pages(3, 99)
    try:
        # PageExtractor clamps end down to N.
        assert sub.get_number_of_pages() == 2
    finally:
        sub.close()
        src.close()


def test_extract_pages_empty_range_returns_empty_doc() -> None:
    src = _build_doc(4)
    sub = src.extract_pages(5, 2)
    try:
        # Degenerate range → empty doc.
        assert sub.get_number_of_pages() == 0
    finally:
        sub.close()
        src.close()


def test_extract_pages_on_closed_doc_raises() -> None:
    doc = _build_doc(2)
    doc.close()
    with pytest.raises(OSError, match="PDDocument has been closed"):
        doc.extract_pages(1, 1)


# ---------------------------------------------------------------------------
# split — backed by Splitter (sibling agent in this wave)
# ---------------------------------------------------------------------------


def test_split_one_per_page() -> None:
    pytest.importorskip("pypdfbox.multipdf.splitter")
    src = _build_doc(4)
    parts = src.split(every=1)
    try:
        assert isinstance(parts, list)
        assert len(parts) == 4
        for part in parts:
            assert isinstance(part, PDDocument)
            assert part.get_number_of_pages() == 1
    finally:
        for part in parts:
            part.close()
        src.close()


def test_split_two_per_chunk() -> None:
    pytest.importorskip("pypdfbox.multipdf.splitter")
    src = _build_doc(4)
    parts = src.split(every=2)
    try:
        assert len(parts) == 2
        assert all(part.get_number_of_pages() == 2 for part in parts)
    finally:
        for part in parts:
            part.close()
        src.close()


def test_split_on_closed_doc_raises() -> None:
    pytest.importorskip("pypdfbox.multipdf.splitter")
    doc = _build_doc(2)
    doc.close()
    with pytest.raises(OSError, match="PDDocument has been closed"):
        doc.split(every=1)


# ---------------------------------------------------------------------------
# merge — backed by PDFMergerUtility (sibling agent in this wave)
# ---------------------------------------------------------------------------


def test_merge_no_args_returns_empty() -> None:
    # No-arg path doesn't touch PDFMergerUtility at all (early return), so
    # it works even before that sibling lands.
    merged = PDDocument.merge()
    try:
        assert isinstance(merged, PDDocument)
        assert merged.get_number_of_pages() == 0
    finally:
        merged.close()


def test_merge_two_docs_combines_pages() -> None:
    pytest.importorskip("pypdfbox.multipdf.pdf_merger_utility")
    a = _build_doc(2)
    b = _build_doc(3)
    merged = PDDocument.merge(a, b)
    try:
        assert isinstance(merged, PDDocument)
        assert merged.get_number_of_pages() == 5
    finally:
        merged.close()
        a.close()
        b.close()


def test_merge_three_docs_combines_pages() -> None:
    pytest.importorskip("pypdfbox.multipdf.pdf_merger_utility")
    a = _build_doc(1)
    b = _build_doc(2)
    c = _build_doc(3)
    merged = PDDocument.merge(a, b, c)
    try:
        assert merged.get_number_of_pages() == 6
    finally:
        merged.close()
        a.close()
        b.close()
        c.close()


# ---------------------------------------------------------------------------
# round-trip: split then merge — pages preserved
# ---------------------------------------------------------------------------


def test_split_then_merge_round_trips_page_count() -> None:
    pytest.importorskip("pypdfbox.multipdf.splitter")
    pytest.importorskip("pypdfbox.multipdf.pdf_merger_utility")
    src = _build_doc(4)
    parts = src.split(every=1)
    try:
        merged = PDDocument.merge(*parts)
        try:
            assert merged.get_number_of_pages() == 4
        finally:
            merged.close()
    finally:
        for part in parts:
            part.close()
        src.close()
