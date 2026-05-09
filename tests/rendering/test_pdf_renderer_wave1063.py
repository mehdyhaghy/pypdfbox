from __future__ import annotations

from typing import Any

from tests.rendering import test_pdf_renderer_wave542 as wave542


def test_wave542_make_doc_removes_existing_pages(monkeypatch: Any) -> None:
    class FakeDocument:
        def __init__(self) -> None:
            self.removed_indexes: list[int] = []
            self.added_pages: list[Any] = []
            self._remaining_pages = 1

        def get_number_of_pages(self) -> int:
            return self._remaining_pages

        def remove_page(self, index: int) -> None:
            self.removed_indexes.append(index)
            self._remaining_pages -= 1

        def add_page(self, page: Any) -> None:
            self.added_pages.append(page)

    monkeypatch.setattr(wave542, "PDDocument", FakeDocument)

    doc, page = wave542._make_doc(21.0, 23.0)  # noqa: SLF001

    assert isinstance(doc, FakeDocument)
    assert doc.removed_indexes == [0]
    assert doc.added_pages == [page]
    assert page.get_media_box().get_width() == 21.0
    assert page.get_media_box().get_height() == 23.0
