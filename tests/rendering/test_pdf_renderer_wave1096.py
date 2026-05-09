from __future__ import annotations

import pytest

import tests.rendering.test_pdf_renderer_image_type as image_type_tests


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


def test_image_type_make_doc_removes_preexisting_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(image_type_tests, "PDDocument", _DocWithExistingPage)

    doc, page = image_type_tests._make_doc()

    assert isinstance(doc, _DocWithExistingPage)
    assert doc.removed_indices == [0]
    assert doc.added_pages == [page]
    assert doc.get_number_of_pages() == 1
