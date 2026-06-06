"""Hand-written parity tests for wave 1505 (agent E): ``Splitter`` materialises
inherited page geometry, and ``PageExtractor`` delegates to ``Splitter``.

Two genuine divergences were closed this wave:

1. **Splitter inherited-geometry materialisation.** Upstream
   ``PDDocument.importPage`` re-applies ``setCropBox`` / ``setMediaBox`` /
   ``setRotation`` from the resolved source values (PDDocument.java lines
   700-702). pypdfbox's ``import_page`` does not, so a page that inherited
   its box from a page-tree node lost it once detached. ``Splitter.process_page``
   now re-applies the three setters, matching upstream's importPage effect.

2. **PageExtractor delegates to Splitter.** Upstream ``PageExtractor.extract``
   builds a ``Splitter`` and returns ``split().get(0)``. The earlier bespoke
   page-walk diverged on out-of-document ranges (returned an empty doc where
   upstream raises). The port now delegates, restoring the
   ``IllegalArgumentException`` -> ``ValueError`` contract.

The live-oracle byte-parity pin lives in
``tests/multipdf/oracle/test_splitter_inherit_oracle.py``; these structural
tests run without Java so they gate every push.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.multipdf.page_extractor import PageExtractor
from pypdfbox.multipdf.splitter import Splitter
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage

_MEDIA_BOX = COSName.get_pdf_name("MediaBox")
_ROTATE = COSName.get_pdf_name("Rotate")
_PAGES = COSName.get_pdf_name("Pages")


def _doc_with_inherited_mediabox(
    n_pages: int, box: tuple[float, float, float, float]
) -> PDDocument:
    """Build a document where ``/MediaBox`` lives on the page-tree node (so each
    page *inherits* it) and is absent from every page dict."""
    doc = PDDocument()
    for _ in range(n_pages):
        page = PDPage()
        doc.add_page(page)
        page.get_cos_object().remove_item(_MEDIA_BOX)
    root = doc.get_document_catalog().get_cos_object().get_dictionary_object(
        _PAGES
    )
    arr = COSArray()
    for v in box:
        arr.add(COSFloat(v))
    root.set_item(_MEDIA_BOX, arr)
    return doc


def test_split_materialises_inherited_mediabox() -> None:
    """A page that inherits its /MediaBox carries a *materialised* box on its
    own dict after the split (not the Letter fallback)."""
    src = _doc_with_inherited_mediabox(1, (0.0, 0.0, 200.0, 300.0))
    # Sanity: the source page has no /MediaBox key but resolves the inherited box.
    assert not src.get_page(0).get_cos_object().contains_key(_MEDIA_BOX)
    assert src.get_page(0).get_media_box().get_width() == 200.0

    parts = Splitter().split(src)
    try:
        out_page = parts[0].get_page(0)
        # The key is now present directly on the split page dict.
        assert out_page.get_cos_object().contains_key(_MEDIA_BOX)
        box = out_page.get_media_box()
        assert box.get_width() == 200.0
        assert box.get_height() == 300.0
    finally:
        for part in parts:
            part.close()
        src.close()


def test_split_materialises_inherited_box_across_multiple_chunks() -> None:
    """Inherited geometry survives onto every chunk, including the second one."""
    # /MediaBox [llx lly urx ury] = [10 20 400 500] -> width 390, height 480.
    src = _doc_with_inherited_mediabox(4, (10.0, 20.0, 400.0, 500.0))
    parts = Splitter().set_split_at_page(2).split(src)
    try:
        assert len(parts) == 2
        for part in parts:
            for i in range(part.get_number_of_pages()):
                page = part.get_page(i)
                assert page.get_cos_object().contains_key(_MEDIA_BOX)
                box = page.get_media_box()
                assert (box.get_width(), box.get_height()) == (390.0, 480.0)
    finally:
        for part in parts:
            part.close()
        src.close()


def test_split_preserves_explicit_rotation() -> None:
    """An explicit per-page /Rotate rides into the split output."""
    src = PDDocument()
    page = PDPage()
    page.set_rotation(90)
    src.add_page(page)
    parts = Splitter().split(src)
    try:
        assert parts[0].get_page(0).get_rotation() == 90
    finally:
        for part in parts:
            part.close()
        src.close()


def test_split_materialises_inherited_rotation() -> None:
    """A /Rotate that lives on the page-tree node is materialised onto the
    split page so it stays in effect once detached from the source tree."""
    src = PDDocument()
    page = PDPage()
    src.add_page(page)
    page.get_cos_object().remove_item(_ROTATE)
    root = src.get_document_catalog().get_cos_object().get_dictionary_object(
        _PAGES
    )
    root.set_item(_ROTATE, COSInteger.get(180))
    assert src.get_page(0).get_rotation() == 180

    parts = Splitter().split(src)
    try:
        assert parts[0].get_page(0).get_rotation() == 180
    finally:
        for part in parts:
            part.close()
        src.close()


# ---------- PageExtractor delegation ----------


def _make_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n_pages):
        doc.add_page(PDPage())
    return doc


def test_page_extractor_inherits_splitter_materialisation() -> None:
    """PageExtractor (now Splitter-delegating) materialises inherited
    geometry onto the extracted page."""
    src = _doc_with_inherited_mediabox(3, (0.0, 0.0, 123.0, 456.0))
    result = PageExtractor(src, 2, 3).extract()
    try:
        assert result.get_number_of_pages() == 2
        for i in range(2):
            page = result.get_page(i)
            assert page.get_cos_object().contains_key(_MEDIA_BOX)
            assert page.get_media_box().get_width() == 123.0
    finally:
        result.close()
        src.close()


@pytest.mark.parametrize(
    ("start", "end", "match"),
    [
        (9, 9, "End page is smaller than startPage"),
        (29, 31, "End page is smaller than startPage"),
    ],
    ids=["start_past_end_clamped_below_start", "both_past_document"],
)
def test_page_extractor_out_of_document_range_raises(
    start: int, end: int, match: str
) -> None:
    """A range whose clamped window collapses (``max(start, 1)`` exceeds
    ``min(end, N)``) raises ``ValueError`` via Splitter's set_end_page guard,
    mirroring upstream's ``IllegalArgumentException``. (Verified against PDFBox
    3.0.7.)"""
    src = _make_doc(2)
    with pytest.raises(ValueError, match=match):
        PageExtractor(src, start, end).extract()
    src.close()


def test_page_extractor_zero_page_source_raises() -> None:
    """Extracting from a zero-page document raises (set_end_page rejects
    ``min(1, 0) = 0`` -> "End page is smaller than one")."""
    src = _make_doc(0)
    with pytest.raises(ValueError, match="End page is smaller than one"):
        PageExtractor(src, 1, 1).extract()
    src.close()


def test_page_extractor_degenerate_raw_range_returns_empty_doc() -> None:
    """The raw-span guard (``end - start + 1 <= 0``) still returns an empty
    document before any Splitter is built — unchanged from upstream."""
    src = _make_doc(5)
    result = PageExtractor(src, 2, 1).extract()
    try:
        assert result.get_number_of_pages() == 0
    finally:
        result.close()
        src.close()


def test_page_extractor_does_not_mutate_source() -> None:
    """Extraction leaves the source page count untouched."""
    src = _make_doc(5)
    PageExtractor(src, 2, 4).extract().close()
    assert src.get_number_of_pages() == 5
    src.close()
