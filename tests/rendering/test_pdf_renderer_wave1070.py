from __future__ import annotations

import pytest

from tests.rendering import test_pdf_renderer_wave491 as wave491


def test_wave491_make_doc_removes_existing_factory_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_document = wave491.PDDocument

    def document_with_existing_page() -> wave491.PDDocument:
        doc = original_document()
        doc.add_page(wave491.PDPage(wave491.PDRectangle(0.0, 0.0, 1.0, 1.0)))
        return doc

    monkeypatch.setattr(wave491, "PDDocument", document_with_existing_page)

    doc, page = wave491._make_doc(9.0, 11.0)  # noqa: SLF001
    try:
        assert doc.get_number_of_pages() == 1
        media_box = page.get_media_box()
        assert media_box.width == 9.0
        assert media_box.height == 11.0
    finally:
        doc.close()
