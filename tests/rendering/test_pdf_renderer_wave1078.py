from __future__ import annotations

import pytest

from tests.rendering import test_pdf_renderer_wave440 as wave440


def test_wave440_make_doc_removes_existing_factory_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_document = wave440.PDDocument

    def document_with_existing_page() -> wave440.PDDocument:
        doc = original_document()
        doc.add_page(wave440.PDPage(wave440.PDRectangle(0.0, 0.0, 1.0, 1.0)))
        return doc

    monkeypatch.setattr(wave440, "PDDocument", document_with_existing_page)

    doc, page = wave440._make_doc(7.0, 9.0)  # noqa: SLF001
    try:
        assert doc.get_number_of_pages() == 1
        media_box = page.get_media_box()
        assert media_box.width == 7.0
        assert media_box.height == 9.0
    finally:
        doc.close()
