from __future__ import annotations

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import ImageType, PDFRenderer, RenderDestination


def _make_doc(width: float = 36.0, height: float = 18.0) -> PDDocument:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    doc.add_page(PDPage(PDRectangle(0.0, 0.0, width, height)))
    return doc


def test_wave298_image_type_exposes_pdfbox_camelcase_alias() -> None:
    assert ImageType.GRAY.toBufferedImageType() == ImageType.GRAY.to_buffered_image_type()


def test_wave298_renderer_camelcase_render_aliases_match_existing_behavior() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        scaled = renderer.renderImage(0, 2.0, ImageType.GRAY)
        dpi = renderer.renderImageWithDPI(0, 144.0, ImageType.ARGB)

        assert scaled.mode == "L"
        assert scaled.size == (72, 36)
        assert dpi.mode == "RGBA"
        assert dpi.size == (72, 36)
        assert renderer.get_page_image() is dpi
    finally:
        doc.close()


def test_wave298_renderer_camelcase_destination_alias_round_trips_enum() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        renderer.setDefaultDestination(RenderDestination.EXPORT)

        assert renderer.getDefaultDestination() == "Export"
        assert renderer.get_default_destination() == "Export"
    finally:
        doc.close()
