from __future__ import annotations

import pytest

from tests.rendering import test_pdf_renderer_wave452 as wave452


def test_wave452_make_doc_removes_existing_factory_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_document = wave452.PDDocument

    def document_with_existing_page() -> wave452.PDDocument:
        doc = original_document()
        doc.add_page(wave452.PDPage(wave452.PDRectangle(0.0, 0.0, 1.0, 1.0)))
        return doc

    monkeypatch.setattr(wave452, "PDDocument", document_with_existing_page)

    doc, page = wave452._make_doc(13.0, 17.0)  # noqa: SLF001
    try:
        assert doc.get_number_of_pages() == 1
        media_box = page.get_media_box()
        assert media_box.width == 13.0
        assert media_box.height == 17.0
    finally:
        doc.close()
