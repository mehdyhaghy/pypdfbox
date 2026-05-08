from __future__ import annotations

import math

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer


def _make_doc() -> PDDocument:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    doc.add_page(PDPage(PDRectangle(0.0, 0.0, 20.0, 20.0)))
    return doc


@pytest.mark.parametrize("scale", [0.0, -1.0, math.inf, math.nan])
def test_render_image_rejects_non_positive_or_non_finite_scale(scale: float) -> None:
    doc = _make_doc()
    renderer = PDFRenderer(doc)

    try:
        with pytest.raises(ValueError, match="scale must be a positive finite number"):
            renderer.render_image(0, scale=scale)

        assert renderer.get_page_image() is None
    finally:
        doc.close()


@pytest.mark.parametrize("dpi", [0.0, -72.0, math.inf, math.nan])
def test_render_image_with_dpi_rejects_non_positive_or_non_finite_dpi(
    dpi: float,
) -> None:
    doc = _make_doc()
    renderer = PDFRenderer(doc)

    try:
        with pytest.raises(ValueError, match="dpi must be a positive finite number"):
            renderer.render_image_with_dpi(0, dpi=dpi)

        assert renderer.get_page_image() is None
    finally:
        doc.close()
