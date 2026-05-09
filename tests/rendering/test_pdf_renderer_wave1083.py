from __future__ import annotations

import pytest

from tests.rendering import test_pdf_renderer_wave381 as wave381


def test_wave381_make_doc_removes_existing_factory_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_document = wave381.PDDocument

    def document_with_existing_page() -> wave381.PDDocument:
        doc = original_document()
        doc.add_page(wave381.PDPage(wave381.PDRectangle(0.0, 0.0, 1.0, 1.0)))
        return doc

    monkeypatch.setattr(wave381, "PDDocument", document_with_existing_page)

    doc, page = wave381._make_doc(17.0, 19.0)  # noqa: SLF001
    try:
        assert doc.get_number_of_pages() == 1
        media_box = page.get_media_box()
        assert media_box.width == 17.0
        assert media_box.height == 19.0
    finally:
        doc.close()
