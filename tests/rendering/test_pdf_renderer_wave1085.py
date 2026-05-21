from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle


def _make_doc(width: float = 36.0, height: float = 18.0) -> PDDocument:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    doc.add_page(PDPage(PDRectangle(0.0, 0.0, width, height)))
    return doc


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


def test_make_doc_removes_existing_page_before_adding_new_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "tests.rendering.test_pdf_renderer_wave1085.PDDocument",
        _DocWithExistingPage,
    )

    doc = _make_doc(17.0, 19.0)

    assert isinstance(doc, _DocWithExistingPage)
    assert doc.removed_indices == [0]
    assert len(doc.added_pages) == 1
    assert doc.get_number_of_pages() == 1
