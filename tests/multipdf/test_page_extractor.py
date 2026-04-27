from __future__ import annotations

import io

from pypdfbox import PDDocument, PDPage
from pypdfbox.multipdf import PageExtractor
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_viewer_preferences import PDViewerPreferences


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


def test_extract_copies_document_information() -> None:
    """Upstream sets the new doc's /Info from the source's. Verify the
    extracted document round-trips title and author."""
    src = _make_doc(3)
    info = src.get_document_information()
    info.set_title("Sample Title")
    info.set_author("Jane Doe")
    result = PageExtractor(src, 1, 1).extract()
    out_info = result.get_document_information()
    assert out_info.get_title() == "Sample Title"
    assert out_info.get_author() == "Jane Doe"
    src.close()
    result.close()


def test_extract_copies_viewer_preferences() -> None:
    """Upstream copies /ViewerPreferences from source catalog onto the
    extracted catalog."""
    src = _make_doc(3)
    src_catalog = src.get_document_catalog()
    prefs = PDViewerPreferences()
    prefs.set_hide_toolbar(True)
    src_catalog.set_viewer_preferences(prefs)
    result = PageExtractor(src, 1, 2).extract()
    out_prefs = result.get_document_catalog().get_viewer_preferences()
    assert out_prefs is not None
    assert out_prefs.hide_toolbar() is True
    src.close()
    result.close()


def test_extract_preserves_page_media_box_via_setter() -> None:
    """The defensive ``set_media_box`` re-application means the
    extracted page's dict carries the source rectangle even when the
    source page inherited it."""
    src = PDDocument()
    page = PDPage()
    page.set_media_box(PDRectangle(0.0, 0.0, 200.0, 300.0))
    src.add_page(page)
    result = PageExtractor(src, 1, 1).extract()
    out_box = result.get_page(0).get_media_box()
    assert out_box.get_width() == 200.0
    assert out_box.get_height() == 300.0
    src.close()
    result.close()


def test_extract_preserves_rotation() -> None:
    src = PDDocument()
    page = PDPage()
    page.set_rotation(90)
    src.add_page(page)
    result = PageExtractor(src, 1, 1).extract()
    assert result.get_page(0).get_rotation() == 90
    src.close()
    result.close()


def test_extract_with_none_end_page_treats_as_full_doc() -> None:
    """``end_page=None`` should mirror the no-arg constructor: extract
    every page in the document."""
    src = _make_doc(4)
    result = PageExtractor(src, 1, None).extract()
    assert result.get_number_of_pages() == 4
    src.close()
    result.close()


def test_extract_does_not_mutate_source_page_count() -> None:
    """Extraction must not mutate the source document's page count."""
    src = _make_doc(5)
    PageExtractor(src, 2, 4).extract().close()
    assert src.get_number_of_pages() == 5
    src.close()


def test_extract_pages_are_detached_from_source_tree() -> None:
    """Extracted pages must be deep copies — mutating the new page must
    not leak back into the source page dictionary."""
    src = _make_doc(2)
    src.get_page(0).set_rotation(0)
    result = PageExtractor(src, 1, 1).extract()
    result.get_page(0).set_rotation(180)
    assert src.get_page(0).get_rotation() == 0
    src.close()
    result.close()
