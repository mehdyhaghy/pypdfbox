from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from tests.rendering import test_pdf_renderer_wave511 as wave511


def test_wave511_make_doc_removes_existing_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = PDDocument()
    doc.add_page(PDPage(PDRectangle(0.0, 0.0, 1.0, 1.0)))
    monkeypatch.setattr(wave511, "PDDocument", lambda: doc)
    try:
        made_doc, page = wave511._make_doc(10.0, 12.0)  # noqa: SLF001

        assert made_doc is doc
        assert doc.get_number_of_pages() == 1
        assert page.get_media_box().get_width() == 10.0
        assert page.get_media_box().get_height() == 12.0
        assert doc.get_page(0).get_media_box().get_width() == 10.0
        assert doc.get_page(0).get_media_box().get_height() == 12.0
    finally:
        doc.close()
