from __future__ import annotations

from tests.rendering import test_pdf_renderer_wave701 as wave701


def test_wave701_make_doc_removes_existing_page(monkeypatch) -> None:
    class _Document:
        def __init__(self) -> None:
            self.pages = 1
            self.removed_indexes: list[int] = []
            self.added_page = None

        def get_number_of_pages(self) -> int:
            return self.pages

        def remove_page(self, index: int) -> None:
            self.removed_indexes.append(index)
            self.pages -= 1

        def add_page(self, page) -> None:
            self.added_page = page
            self.pages += 1

    document = _Document()
    monkeypatch.setattr(wave701, "PDDocument", lambda: document)

    doc, page = wave701._make_doc()  # noqa: SLF001

    assert doc is document
    assert document.removed_indexes == [0]
    assert document.added_page is page
