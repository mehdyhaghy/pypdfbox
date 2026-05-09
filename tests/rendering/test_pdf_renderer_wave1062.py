from __future__ import annotations

import pytest

from tests.rendering import test_pdf_renderer_wave551 as wave551


class _DocumentWithExistingPage:
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


def test_wave551_make_doc_removes_existing_page_before_adding_new_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = _DocumentWithExistingPage()
    monkeypatch.setattr(wave551, "PDDocument", lambda: doc)

    made_doc, page = wave551._make_doc(width=3.0, height=4.0)  # noqa: SLF001

    assert made_doc is doc
    assert doc.removed_indexes == [0]
    assert doc.pages == [page]
