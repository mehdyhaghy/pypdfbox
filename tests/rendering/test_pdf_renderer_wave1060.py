from __future__ import annotations

from tests.rendering import test_pdf_renderer_wave552 as wave552


def test_make_doc_removes_default_pages_before_adding_requested_page(
    monkeypatch,
) -> None:
    class _Document:
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
            self.pages.append(page)

    monkeypatch.setattr(wave552, "PDDocument", _Document)

    doc, page = wave552._make_doc(17.0, 19.0)  # noqa: SLF001

    assert doc.removed_indexes == [0]
    assert doc.added_pages == [page]
    assert doc.pages == [page]
