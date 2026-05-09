from __future__ import annotations

from typing import Any

from tests.rendering import test_pdf_renderer_wave602 as wave602


def test_wave602_make_doc_removes_default_pages(monkeypatch: Any) -> None:
    class _Document:
        def __init__(self) -> None:
            self.pages: list[object] = [object()]
            self.removed_indexes: list[int] = []

        def get_number_of_pages(self) -> int:
            return len(self.pages)

        def remove_page(self, index: int) -> None:
            self.removed_indexes.append(index)
            self.pages.pop(index)

        def add_page(self, page: object) -> None:
            self.pages.append(page)

    monkeypatch.setattr(wave602, "PDDocument", _Document)

    doc, page = wave602._make_doc()  # noqa: SLF001

    assert doc.removed_indexes == [0]
    assert doc.pages == [page]
