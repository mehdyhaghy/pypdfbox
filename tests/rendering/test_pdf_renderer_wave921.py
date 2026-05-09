from __future__ import annotations

import io
from typing import Any

from PIL import Image

from tests.rendering import test_pdf_renderer_wave632 as wave632


def test_wave632_make_doc_removes_existing_pages(monkeypatch: Any) -> None:
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

    monkeypatch.setattr(wave632, "PDDocument", FakeDocument)

    doc, page = wave632._make_doc()  # noqa: SLF001

    assert isinstance(doc, FakeDocument)
    assert doc.removed_indexes == [0, 0]
    assert doc.added_pages == [page]


def test_wave632_dct_image_stub_accessors_are_exercised(monkeypatch: Any) -> None:
    def decode_stub(_renderer: Any, image_xobject: Any) -> Image.Image:
        assert image_xobject.get_bits_per_component() == 8
        assert image_xobject.get_color_space().name == "DeviceRGB"
        with image_xobject.create_input_stream(stop_filters=["DCTDecode"]) as stream:
            assert isinstance(stream, io.BytesIO)
        return Image.new("RGB", (1, 1), (21, 43, 65))

    monkeypatch.setattr(wave632.PDFRenderer, "_decode_image_xobject", decode_stub)

    wave632.test_decode_image_xobject_dct_path_uses_encoded_stream_payload()
