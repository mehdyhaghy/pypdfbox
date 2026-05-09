from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from tests.rendering import test_pdf_renderer_wave621 as wave621


def test_wave621_make_doc_removes_existing_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = PDDocument()
    doc.add_page(PDPage(PDRectangle(0.0, 0.0, 1.0, 1.0)))
    monkeypatch.setattr(wave621, "PDDocument", lambda: doc)
    try:
        made_doc, page = wave621._make_doc()  # noqa: SLF001

        assert made_doc is doc
        assert doc.get_number_of_pages() == 1
        assert page.get_media_box().get_width() == 8.0
        assert page.get_media_box().get_height() == 8.0
        assert doc.get_page(0).get_media_box().get_width() == 8.0
        assert doc.get_page(0).get_media_box().get_height() == 8.0
    finally:
        doc.close()
