from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import ImageType, PDFRenderer


def _make_doc(
    width: float = 6.0,
    height: float = 4.0,
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def test_render_image_with_bgr_uses_rgb_pillow_mode_and_caches_result() -> None:
    doc, _page = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        image = renderer.render_image(0, image_type=ImageType.BGR)

        assert image.mode == "RGB"
        assert image.size == (6, 4)
        assert renderer.get_page_image() is image
    finally:
        doc.close()


def test_get_page_for_render_rejects_negative_index_without_wraparound() -> None:
    doc, _page = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        with pytest.raises(IndexError, match="page index out of range: -1"):
            renderer._get_page_for_render(-1)  # noqa: SLF001
    finally:
        doc.close()

