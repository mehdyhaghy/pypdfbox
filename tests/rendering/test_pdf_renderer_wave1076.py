from __future__ import annotations

import pytest

from tests.rendering import test_pdf_renderer_wave461 as wave461


def test_wave461_make_doc_removes_existing_factory_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_document = wave461.PDDocument

    def document_with_existing_page() -> wave461.PDDocument:
        doc = original_document()
        doc.add_page(wave461.PDPage(wave461.PDRectangle(0.0, 0.0, 1.0, 1.0)))
        return doc

    monkeypatch.setattr(wave461, "PDDocument", document_with_existing_page)

    doc, page = wave461._make_doc(5.0, 7.0)  # noqa: SLF001
    try:
        assert doc.get_number_of_pages() == 1
        media_box = page.get_media_box()
        assert media_box.width == 5.0
        assert media_box.height == 7.0
    finally:
        doc.close()
