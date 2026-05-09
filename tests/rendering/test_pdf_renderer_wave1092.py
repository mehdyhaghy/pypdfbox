from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDPage, PDRectangle
from tests.rendering import test_pdf_renderer_pattern_shading as pattern_shading


class _SeededDocument(pattern_shading.PDDocument):
    def __init__(self) -> None:
        super().__init__()
        self.add_page(PDPage(PDRectangle(0.0, 0.0, 1.0, 1.0)))


def test_pattern_shading_make_doc_removes_seed_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pattern_shading, "PDDocument", _SeededDocument)

    doc, page = pattern_shading._make_doc(width=11.0, height=13.0)  # noqa: SLF001
    try:
        stored_page = doc.get_page(0)
        assert doc.get_number_of_pages() == 1
        assert stored_page.get_media_box().get_width() == page.get_media_box().get_width()
        assert stored_page.get_media_box().get_height() == page.get_media_box().get_height()
        assert page.get_media_box().get_width() == 11.0
        assert page.get_media_box().get_height() == 13.0
    finally:
        doc.close()
