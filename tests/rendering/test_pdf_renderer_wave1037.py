from __future__ import annotations

from typing import Any

from tests.rendering import test_pdf_renderer_wave692 as wave692


class _DocWithExistingPage:
    def __init__(self) -> None:
        self._pages = 1
        self.added_pages = []

    def get_number_of_pages(self) -> int:
        return self._pages

    def remove_page(self, index: int) -> None:
        assert index == 0
        self._pages -= 1

    def add_page(self, page: object) -> None:
        self.added_pages.append(page)


def test_wave692_make_doc_removes_existing_pages(monkeypatch: Any) -> None:
    doc = _DocWithExistingPage()
    monkeypatch.setattr(wave692, "PDDocument", lambda: doc)

    returned_doc, page = wave692._make_doc()

    assert returned_doc is doc
    assert doc._pages == 0
    assert doc.added_pages == [page]
