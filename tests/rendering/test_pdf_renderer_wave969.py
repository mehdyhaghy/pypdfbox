from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave402 as wave402


class _DocWithExistingPage:
    def __init__(self) -> None:
        self._pages = 1
        self.added_pages: list[Any] = []
        self.removed_indexes: list[int] = []

    def get_number_of_pages(self) -> int:
        return self._pages

    def remove_page(self, index: int) -> None:
        self.removed_indexes.append(index)
        self._pages -= 1

    def add_page(self, page: object) -> None:
        self.added_pages.append(page)


def test_wave402_make_doc_removes_existing_pages(monkeypatch: Any) -> None:
    doc = _DocWithExistingPage()
    monkeypatch.setattr(wave402, "PDDocument", lambda: doc)

    returned_doc, page = wave402._make_doc()  # noqa: SLF001

    assert returned_doc is doc
    assert doc.removed_indexes == [0]
    assert doc.added_pages == [page]


def test_wave402_substitute_units_exception_branch_is_reachable() -> None:
    substitute = wave402._Substitute(600.0, RuntimeError("units"))  # noqa: SLF001

    with pytest.raises(RuntimeError, match="units"):
        substitute.get_units_per_em()
