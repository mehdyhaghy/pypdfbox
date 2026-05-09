from __future__ import annotations

import pytest

from tests.rendering import test_pdf_renderer_wave303 as wave303


def test_wave303_make_doc_removes_existing_factory_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_document = wave303.PDDocument

    def document_with_existing_page() -> wave303.PDDocument:
        doc = original_document()
        doc.add_page(wave303.PDPage(wave303.PDRectangle(0.0, 0.0, 1.0, 1.0)))
        return doc

    monkeypatch.setattr(wave303, "PDDocument", document_with_existing_page)

    doc = wave303._make_doc()  # noqa: SLF001
    try:
        assert doc.get_number_of_pages() == 1
        page = doc.get_page(0)
        media_box = page.get_media_box()
        assert media_box.width == 20.0
        assert media_box.height == 20.0
    finally:
        doc.close()
