from __future__ import annotations

import io

from pypdfbox import PDDocument, PDPage
from pypdfbox.multipdf import PageExtractor


def _make_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n_pages):
        doc.add_page(PDPage())
    return doc


def test_extract_default_returns_full_document_copy() -> None:
    """No args → clone every page (upstream no-arg constructor sets
    ``endPage = source.getNumberOfPages()``)."""
    src = _make_doc(3)
    extractor = PageExtractor(src)
    result = extractor.extract()
    assert result.get_number_of_pages() == 3
    # Result must be a *separate* PDDocument with its own page tree.
    assert result is not src
    assert result.get_pages() is not src.get_pages()
    src.close()
    result.close()


def test_extract_single_page_in_middle() -> None:
    """Hand-written: build a 3-page PDF, extract pages 2..2, verify result
    is a 1-page PDF."""
    src = _make_doc(3)
    extractor = PageExtractor(src, start_page=2, end_page=2)
    result = extractor.extract()
    assert result.get_number_of_pages() == 1
    src.close()
    result.close()


def test_extract_range_inclusive_at_both_ends() -> None:
    src = _make_doc(5)
    result = PageExtractor(src, 2, 4).extract()
    assert result.get_number_of_pages() == 3
    src.close()
    result.close()


def test_extract_clamps_end_above_total() -> None:
    """``end_page`` past the last page clamps to ``get_number_of_pages``."""
    src = _make_doc(3)
    result = PageExtractor(src, 1, 99).extract()
    assert result.get_number_of_pages() == 3
    src.close()
    result.close()


def test_extract_clamps_start_below_one() -> None:
    src = _make_doc(3)
    result = PageExtractor(src, 0, 2).extract()
    # ``start = max(0, 1) = 1``, ``end = 2`` → 2 pages.
    assert result.get_number_of_pages() == 2
    src.close()
    result.close()


def test_extract_returns_blank_when_start_after_end() -> None:
    """Upstream: ``endPage - startPage + 1 <= 0`` → ``new PDDocument()``."""
    src = _make_doc(3)
    result = PageExtractor(src, 2, 1).extract()
    assert result.get_number_of_pages() == 0
    src.close()
    result.close()


def test_extracted_document_is_saveable_and_round_trips() -> None:
    """The new doc owns its resource graph — saving and reloading must
    preserve the page count."""
    src = _make_doc(4)
    result = PageExtractor(src, 2, 3).extract()
    sink = io.BytesIO()
    result.save(sink)
    src.close()
    result.close()

    with PDDocument.load(sink.getvalue()) as reloaded:
        assert reloaded.get_number_of_pages() == 2


def test_getters_and_setters_round_trip() -> None:
    src = _make_doc(3)
    extractor = PageExtractor(src, 1, 3)
    assert extractor.get_start_page() == 1
    assert extractor.get_end_page() == 3
    extractor.set_start_page(2)
    extractor.set_end_page(2)
    assert extractor.get_start_page() == 2
    assert extractor.get_end_page() == 2
    assert extractor.extract().get_number_of_pages() == 1
    src.close()
