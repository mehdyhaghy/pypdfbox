from __future__ import annotations

import pytest

import tests.rendering.test_pdf_renderer_render_destination as render_destination_tests


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


def test_render_destination_make_doc_removes_preexisting_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(render_destination_tests, "PDDocument", _DocWithExistingPage)

    doc = render_destination_tests._make_doc()  # noqa: SLF001

    assert isinstance(doc, _DocWithExistingPage)
    assert doc.removed_indices == [0]
    assert len(doc.added_pages) == 1
    assert doc.get_number_of_pages() == 1
