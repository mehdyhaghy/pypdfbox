from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary
from tests.rendering import test_pdf_renderer_wave382 as wave382


class _DocWithExistingPage:
    def __init__(self) -> None:
        self._pages = 1
        self.added_pages: list[Any] = []
        self.removed_indexes: list[int] = []

    def get_number_of_pages(self) -> int:
        return self._pages

    def remove_page(self, index: int) -> None:
        self.removed_indexes.append(index)
        self._pages -= 1

    def add_page(self, page: object) -> None:
        self.added_pages.append(page)


def test_wave382_make_doc_removes_existing_pages(monkeypatch: Any) -> None:
    doc = _DocWithExistingPage()
    monkeypatch.setattr(wave382, "PDDocument", lambda: doc)

    returned_doc, page = wave382._make_doc()  # noqa: SLF001

    assert returned_doc is doc
    assert doc.removed_indexes == [0]
    assert doc.added_pages == [page]


def test_wave382_tiling_pattern_returns_resources() -> None:
    resources = object()
    pattern = wave382._TilingPattern(COSDictionary(), resources)  # noqa: SLF001

    assert pattern.get_resources() is resources
