from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer


def _make_doc() -> PDDocument:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    doc.add_page(PDPage(PDRectangle(0.0, 0.0, 20.0, 20.0)))
    return doc


@pytest.mark.parametrize("page_index", [-1, 1])
def test_render_image_rejects_page_indexes_outside_document(
    page_index: int,
) -> None:
    doc = _make_doc()
    renderer = PDFRenderer(doc)

    try:
        with pytest.raises(IndexError, match=f"page index out of range: {page_index}"):
            renderer.render_image(page_index)

        assert renderer.get_page_image() is None
    finally:
        doc.close()

