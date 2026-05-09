from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave451 as wave451


def test_wave451_make_doc_removes_existing_pages(monkeypatch: Any) -> None:
    class FakeDocument:
        def __init__(self) -> None:
            self.removed_indexes: list[int] = []
            self.added_pages: list[Any] = []
            self._remaining_pages = 2

        def get_number_of_pages(self) -> int:
            return self._remaining_pages

        def remove_page(self, index: int) -> None:
            self.removed_indexes.append(index)
            self._remaining_pages -= 1

        def add_page(self, page: Any) -> None:
            self.added_pages.append(page)

    monkeypatch.setattr(wave451, "PDDocument", FakeDocument)

    doc, page = wave451._make_doc()  # noqa: SLF001

    assert isinstance(doc, FakeDocument)
    assert doc.removed_indexes == [0, 0]
    assert doc.added_pages == [page]


def test_wave451_inline_image_legacy_stub_guards_are_exercised(
    monkeypatch: Any,
) -> None:
    def show_inline_stub(renderer: Any, inline_image: Any) -> None:
        image = inline_image.to_pil_image()
        with pytest.raises(AssertionError, match="legacy decoder"):
            inline_image.get_cos_object()
        with pytest.raises(AssertionError, match="legacy decoder"):
            inline_image.get_stream()
        renderer._image.putpixel((1, 1), image.getpixel((0, 0)))  # noqa: SLF001
        renderer._draw = None  # noqa: SLF001

    monkeypatch.setattr(wave451.PDFRenderer, "show_inline_image", show_inline_stub)

    wave451.test_show_inline_image_uses_helper_image_before_legacy_decoder()
