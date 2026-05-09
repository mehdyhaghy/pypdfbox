from __future__ import annotations

import pytest

import tests.rendering.test_pdf_renderer_type3_font as type3_font


class _DocWithExistingPage:
    def __init__(self) -> None:
        self._page_count = 1
        self.removed_indices: list[int] = []
        self.added_pages: list[object] = []

    def get_number_of_pages(self) -> int:
        return self._page_count

    def remove_page(self, index: int) -> None:
        self.removed_indices.append(index)
        self._page_count -= 1

    def add_page(self, page: object) -> None:
        self.added_pages.append(page)
        self._page_count += 1


def test_type3_make_doc_removes_existing_page_before_adding_new_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(type3_font, "PDDocument", _DocWithExistingPage)

    doc, page = type3_font._make_doc(21.0, 23.0)  # noqa: SLF001

    assert isinstance(doc, _DocWithExistingPage)
    assert doc.removed_indices == [0]
    assert doc.added_pages == [page]
    assert doc.get_number_of_pages() == 1
