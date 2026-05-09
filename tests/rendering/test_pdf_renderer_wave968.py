from __future__ import annotations

from typing import Any

import pytest
from PIL import Image

from tests.rendering import test_pdf_renderer_wave472 as wave472


def test_wave472_make_doc_removes_existing_pages(monkeypatch: Any) -> None:
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

    monkeypatch.setattr(wave472, "PDDocument", FakeDocument)

    doc, page = wave472._make_doc()  # noqa: SLF001

    assert isinstance(doc, FakeDocument)
    assert doc.removed_indexes == [0]
    assert doc.added_pages == [page]


def test_wave472_image_xobject_stream_fallback_guard_is_exercised(
    monkeypatch: Any,
) -> None:
    def decode_stub(_renderer: Any, image_xobject: Any) -> Image.Image:
        assert image_xobject.to_pil_image().mode == "RGBA"
        with pytest.raises(AssertionError, match="stream fallback"):
            image_xobject.get_cos_object()
        return Image.new("RGB", (1, 1), (10, 20, 30))

    monkeypatch.setattr(wave472.PDFRenderer, "_decode_image_xobject", decode_stub)

    wave472.test_decode_image_xobject_helper_converts_to_rgb_without_stream_fallback()
