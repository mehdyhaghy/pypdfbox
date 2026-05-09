from __future__ import annotations

from typing import Any

from tests.rendering import test_pdf_renderer_wave671 as wave671


def test_wave671_make_doc_removes_existing_pages(monkeypatch: Any) -> None:
    class ExistingPagesDocument:
        def __init__(self) -> None:
            self.pages = [object()]
            self.removed_indexes: list[int] = []
            self.added_pages: list[object] = []

        def get_number_of_pages(self) -> int:
            return len(self.pages)

        def remove_page(self, index: int) -> None:
            self.removed_indexes.append(index)
            self.pages.pop(index)

        def add_page(self, page: object) -> None:
            self.added_pages.append(page)

    created_docs: list[ExistingPagesDocument] = []

    def make_document() -> ExistingPagesDocument:
        doc = ExistingPagesDocument()
        created_docs.append(doc)
        return doc

    monkeypatch.setattr(wave671, "PDDocument", make_document)

    doc, page = wave671._make_doc()  # noqa: SLF001

    assert doc is created_docs[0]
    assert doc.removed_indexes == [0]
    assert doc.added_pages == [page]
