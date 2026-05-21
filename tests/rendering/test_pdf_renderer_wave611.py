from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import ImageType, PDFRenderer


def _make_doc(width: float = 8.0, height: float = 8.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def test_argb_render_makes_background_transparent_but_keeps_paint_opaque() -> None:
    doc, page = _make_doc()
    try:
        contents = COSStream()
        contents.set_raw_data(
            b"1 0 0 rg\n"
            b"2 2 4 4 re\n"
            b"f\n"
        )
        page.get_cos_object().set_item(COSName.CONTENTS, contents)

        image = PDFRenderer(doc).render_image(0, image_type=ImageType.ARGB)

        assert image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (255, 255, 255, 0)
        assert image.getpixel((4, 4)) == (255, 0, 0, 255)
    finally:
        doc.close()


@pytest.mark.parametrize("bad_dpi", [0.0, -1.0, math.inf, math.nan])
def test_render_image_with_dpi_validates_dpi_before_page_lookup(bad_dpi: float) -> None:
    doc, _page = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        with pytest.raises(ValueError, match="dpi must be a positive finite number"):
            renderer.render_image_with_dpi(99, bad_dpi)
    finally:
        doc.close()

