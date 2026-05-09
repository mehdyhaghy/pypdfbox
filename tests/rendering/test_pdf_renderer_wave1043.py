from __future__ import annotations

from typing import Any

from tests.rendering import test_pdf_renderer_wave651 as wave651


class _DocumentWithExistingPage:
    def __init__(self) -> None:
        self._page_count = 1
        self.removed_indexes: list[int] = []
        self.added_pages: list[Any] = []

    def get_number_of_pages(self) -> int:
        return self._page_count

    def remove_page(self, index: int) -> None:
        self.removed_indexes.append(index)
        self._page_count -= 1

    def add_page(self, page: Any) -> None:
        self.added_pages.append(page)
        self._page_count += 1


def test_wave651_make_doc_removes_existing_default_page(monkeypatch: Any) -> None:
    created: list[_DocumentWithExistingPage] = []

    def make_document() -> _DocumentWithExistingPage:
        doc = _DocumentWithExistingPage()
        created.append(doc)
        return doc

    monkeypatch.setattr(wave651, "PDDocument", make_document)

    doc, page = wave651._make_doc(width=8.0, height=9.0)  # noqa: SLF001

    assert doc is created[0]
    assert doc.removed_indexes == [0]
    assert doc.added_pages == [page]
    assert doc.get_number_of_pages() == 1
