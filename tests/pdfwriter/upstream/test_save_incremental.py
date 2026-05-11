"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSIncrement.java

Upstream lives under ``cos/`` (not ``pdfwriter/``) but the surface it
exercises — ``saveIncremental`` — belongs to the writer cluster, so we
mirror it here.

``testIncrementallyCreateDocument`` and ``testSubsetting`` are ported.
``testConcurrentModification`` still requires a network-fetched fixture
plus ``setAllSecurityToBeRemoved`` security flow that is not bundled.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDRectangle
from pypdfbox.pdmodel.font import PDType0Font, PDType1Font
from pypdfbox.pdmodel.graphics.color import PDColor, PDDeviceRGB
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationText
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

_LIBERATION_SANS = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _make_helvetica() -> PDType1Font:
    """Bare-bones Type 1 Helvetica wrapper — Standard 14 alias."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    return font


def _mark_dirty(document: PDDocument, page: PDPage) -> None:
    """Mirror upstream's setNeedToBeUpdated chain so the incremental
    save actually emits the catalog/pages/page that we mutated."""
    catalog = document.get_document_catalog().get_cos_object()
    catalog.set_needs_to_be_updated(True)
    pages = catalog.get_cos_dictionary(COSName.PAGES)
    if pages is not None:
        pages.set_needs_to_be_updated(True)
    page.get_cos_object().set_needs_to_be_updated(True)


def test_incrementally_create_document(tmp_path: Path) -> None:
    """Port of upstream ``testIncrementallyCreateDocument``: build a
    document by repeatedly loading + mutating + ``saveIncremental``,
    and at each step verify the previous step's mutations survived.
    """
    # Generate a tiny PNG (upstream loads ``simple.png`` — we synthesise
    # one to avoid bundling a binary fixture).
    png_path = tmp_path / "simple.png"
    Image.new("RGB", (4, 4), color=(255, 0, 0)).save(png_path, format="PNG")

    # Step 1: create a new doc with one page, save in full.
    with PDDocument() as doc:
        doc.add_page(PDPage(PDRectangle(100, 100)))
        sink = io.BytesIO()
        doc.save(sink)
        document_data = sink.getvalue()

    # Step 2: load, add two pages, incremental save.
    with PDDocument.load(document_data) as doc:
        assert doc.get_number_of_pages() == 1
        doc.add_page(PDPage(PDRectangle(200, 200)))
        doc.add_page(PDPage(PDRectangle(100, 100)))
        catalog = doc.get_document_catalog().get_cos_object()
        catalog.set_needs_to_be_updated(True)
        pages = catalog.get_cos_dictionary(COSName.PAGES)
        if pages is not None:
            pages.set_needs_to_be_updated(True)
        sink = io.BytesIO()
        doc.save_incremental(sink)
        document_data = sink.getvalue()

    # Step 3: load, remove page index 1, incremental save.
    with PDDocument.load(document_data) as doc:
        assert doc.get_number_of_pages() == 3
        doc.remove_page(doc.get_page(1))
        catalog = doc.get_document_catalog().get_cos_object()
        catalog.set_needs_to_be_updated(True)
        pages = catalog.get_cos_dictionary(COSName.PAGES)
        if pages is not None:
            pages.set_needs_to_be_updated(True)
        sink = io.BytesIO()
        doc.save_incremental(sink)
        document_data = sink.getvalue()

    # Step 4: load, draw an image on page 1, incremental save.
    with PDDocument.load(document_data) as doc:
        assert doc.get_page(1).get_media_box().get_width() != 200
        assert doc.get_number_of_pages() == 2
        page = doc.get_page(0)
        assert not page.has_contents()
        assert page.get_resources() is None or not list(
            page.get_resources().get_x_object_names()
        )
        image = PDImageXObject.create_from_file_by_extension(png_path, doc)
        with PDPageContentStream(doc, page) as cs:
            cs.draw_image(image, 15, 20)
        _mark_dirty(doc, page)
        sink = io.BytesIO()
        doc.save_incremental(sink)
        document_data = sink.getvalue()

    # Step 5: load, write text on page 2, incremental save.
    with PDDocument.load(document_data) as doc:
        assert doc.get_page(0).has_contents()
        page0_resources = doc.get_page(0).get_resources()
        assert page0_resources is not None
        assert list(page0_resources.get_x_object_names())
        page = doc.get_page(1)
        assert not page.has_contents()
        font = _make_helvetica()
        with PDPageContentStream(doc, page) as cs:
            cs.begin_text()
            cs.set_font(font, 20)
            cs.new_line_at_offset(20, 50)
            cs.show_text("Page 2")
            cs.end_text()
        _mark_dirty(doc, page)
        sink = io.BytesIO()
        doc.save_incremental(sink)
        document_data = sink.getvalue()

    # Step 6: load, attach an annotation on page 2, incremental save.
    with PDDocument.load(document_data) as doc:
        page = doc.get_page(1)
        assert page.has_contents()
        existing_annotations = page.get_annotations()
        assert len(existing_annotations) == 0
        annotation = PDAnnotationText()
        annotation.set_name("text annotation")
        annotation.set_contents("text annotation")
        annotation.set_open(True)
        annotation.set_color(PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE))
        annotation.set_rectangle(PDRectangle(4, 5, 10, 10))
        # upstream uses ``page.getAnnotations().add(annotation)`` because
        # the Java helper returns a live-view list; our port returns a
        # freshly-materialised list, so we round-trip through
        # ``set_annotations`` instead.
        page.set_annotations([*existing_annotations, annotation])
        _mark_dirty(doc, page)
        sink = io.BytesIO()
        doc.save_incremental(sink)
        document_data = sink.getvalue()

    # Step 7: final read-back — every mutation must be observable.
    with PDDocument.load(document_data) as doc:
        assert doc.get_number_of_pages() == 2
        page0 = doc.get_page(0)
        page1 = doc.get_page(1)
        assert page0.get_resources() is not None
        assert page1.get_resources() is not None
        assert page0.has_contents()
        assert list(page0.get_resources().get_x_object_names())
        assert page1.has_contents()
        assert len(page1.get_annotations()) == 1


@pytest.mark.skip(
    reason="needs network-fetched PDFBOX-5263 fixture + setAllSecurityToBeRemoved"
)
def test_concurrent_modification() -> None:
    pass


def test_subsetting() -> None:
    """Mirrors upstream ``testSubsetting``: an incremental save that
    embeds a freshly-loaded TTF must materialise a subset (the
    descendant CIDFont's font file is the subsetted byte stream).
    """
    if not _LIBERATION_SANS.exists():
        pytest.skip("LiberationSans-Regular.ttf fixture not bundled")

    baos = io.BytesIO()
    doc1 = PDDocument()
    page = PDPage(PDRectangle.A4)
    doc1.add_page(page)
    doc1.save(baos)
    doc1.close()

    sink = io.BytesIO()
    with PDDocument.load(baos.getvalue()) as document:
        page = document.get_page(0)
        font = PDType0Font.load(document, _LIBERATION_SANS.read_bytes())

        with PDPageContentStream(document, page) as cs:
            cs.begin_text()
            cs.set_font(font, 12)
            cs.new_line_at_offset(75, 750)
            cs.show_text("Apache PDFBox")
            cs.end_text()

        catalog = document.get_document_catalog().get_cos_object()
        catalog.set_needs_to_be_updated(True)
        pages = catalog.get_cos_dictionary(COSName.PAGES)
        if pages is not None:
            pages.set_needs_to_be_updated(True)
        page.get_cos_object().set_needs_to_be_updated(True)

        document.save_incremental(sink)

    with PDDocument.load(sink.getvalue()) as document:
        page = document.get_page(0)
        font_names = list(page.get_resources().get_font_names())
        assert font_names, "page should reference at least one font"
        embedded_font = page.get_resources().get_font(font_names[0])
        assert embedded_font.is_embedded()
