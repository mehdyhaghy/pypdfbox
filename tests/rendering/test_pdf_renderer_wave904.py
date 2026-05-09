from __future__ import annotations

import builtins
from typing import Any

from tests.rendering import test_pdf_renderer_wave721 as wave721


class _CountingDocument:
    def __init__(self) -> None:
        self.pages = [object()]
        self.removed: list[int] = []

    def get_number_of_pages(self) -> int:
        return len(self.pages)

    def remove_page(self, index: int) -> None:
        self.removed.append(index)
        self.pages.pop(index)

    def add_page(self, page: object) -> None:
        self.pages.append(page)


def test_wave721_make_doc_removes_default_page(monkeypatch: Any) -> None:
    created: list[_CountingDocument] = []

    def document_factory() -> _CountingDocument:
        doc = _CountingDocument()
        created.append(doc)
        return doc

    monkeypatch.setattr(wave721, "PDDocument", document_factory)

    doc, page = wave721._make_doc()  # noqa: SLF001

    assert doc is created[0]
    assert doc.removed == [0]
    assert doc.pages == [page]


def test_wave721_force_round_delegates_for_other_round_shapes(
    monkeypatch: Any,
) -> None:
    wave721._force_round(monkeypatch, 7)  # noqa: SLF001

    assert builtins.round(0.5) == 7
    assert builtins.round(1000.5) == 1000
    assert builtins.round(1.234, 2) == 1.23
