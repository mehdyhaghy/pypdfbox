from __future__ import annotations

from tests.rendering import test_pdf_renderer_wave502 as wave502


def test_wave502_make_doc_removes_existing_pages(monkeypatch) -> None:
    class FakeDocument:
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

    monkeypatch.setattr(wave502, "PDDocument", FakeDocument)

    doc, page = wave502._make_doc(11.0, 13.0)  # noqa: SLF001

    assert isinstance(doc, FakeDocument)
    assert doc.removed_indexes == [0]
    assert doc.added_pages == [page]
    assert doc.pages == [page]
