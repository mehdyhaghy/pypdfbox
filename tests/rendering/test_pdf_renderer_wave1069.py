from __future__ import annotations

import pytest

from tests.rendering import test_pdf_renderer_wave492 as wave492


def test_wave492_make_doc_removes_existing_factory_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_document = wave492.PDDocument

    def document_with_existing_page() -> wave492.PDDocument:
        doc = original_document()
        doc.add_page(wave492.PDPage(wave492.PDRectangle(0.0, 0.0, 1.0, 1.0)))
        return doc

    monkeypatch.setattr(wave492, "PDDocument", document_with_existing_page)

    doc, page = wave492._make_doc(12.0, 14.0)  # noqa: SLF001
    try:
        assert doc.get_number_of_pages() == 1
        media_box = page.get_media_box()
        assert media_box.width == 12.0
        assert media_box.height == 14.0
    finally:
        doc.close()
