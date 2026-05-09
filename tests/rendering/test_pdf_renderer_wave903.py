from __future__ import annotations

import builtins
from typing import Any

from pypdfbox.cos import COSFloat
from tests.rendering import test_pdf_renderer_wave712 as wave712


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


def test_wave712_make_doc_removes_default_page(monkeypatch: Any) -> None:
    created: list[_CountingDocument] = []

    def document_factory() -> _CountingDocument:
        doc = _CountingDocument()
        created.append(doc)
        return doc

    monkeypatch.setattr(wave712, "PDDocument", document_factory)

    doc, page = wave712._make_doc()  # noqa: SLF001

    assert doc is created[0]
    assert doc.removed == [0]
    assert doc.pages == [page]


def test_wave712_float_array_adds_each_value() -> None:
    array = wave712._float_array(1.25, -2.5)  # noqa: SLF001

    assert array.size() == 2
    assert isinstance(array.get_object(0), COSFloat)
    assert array.get_object(0).float_value() == 1.25
    assert array.get_object(1).float_value() == -2.5


def test_wave712_import_stub_delegates_for_non_matching_import(
    monkeypatch: Any,
) -> None:
    delegated = False

    def shading_extend(_shading: object) -> tuple[bool, bool]:
        nonlocal delegated
        builtins.__import__("math")
        delegated = True
        return (False, False)

    monkeypatch.setattr(
        wave712.PDFRenderer,
        "_shading_extend",
        staticmethod(shading_extend),
    )
    wave712.test_shading_extend_defaults_when_cosboolean_import_fails(
        monkeypatch,
    )

    assert delegated is True
