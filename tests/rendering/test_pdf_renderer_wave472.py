from __future__ import annotations

import logging
from typing import Any

import aggdraw  # type: ignore[import-not-found]
import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _GState


def _make_doc(width: float = 6.0, height: float = 6.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (6, 6)) -> tuple[PDDocument, PDFRenderer]:
    doc, _page = _make_doc(float(size[0]), float(size[1]))
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", size, (255, 255, 255))  # noqa: SLF001
    renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
    renderer._draw.setantialias(True)  # noqa: SLF001
    renderer._gs_stack = [_GState()]  # noqa: SLF001
    renderer._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001
    return doc, renderer


def _finish(renderer: PDFRenderer) -> None:
    draw = renderer._draw  # noqa: SLF001
    if draw is not None:
        draw.flush()


def _inline_params() -> COSDictionary:
    params = COSDictionary()
    params.set_item(COSName.get_pdf_name("W"), COSInteger.get(1))
    params.set_item(COSName.get_pdf_name("H"), COSInteger.get(1))
    params.set_item(COSName.get_pdf_name("BPC"), COSInteger.get(8))
    params.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("RGB"))
    return params


def test_process_form_bytes_restores_knockout_depth_when_dispatch_raises(
    monkeypatch: Any,
) -> None:
    def _raise_dispatch(_parser: Any) -> None:
        raise RuntimeError("dispatch boom")

    doc, renderer = _prepared_renderer()
    renderer._knockout_active = True  # noqa: SLF001
    renderer._knockout_form_depth = 4  # noqa: SLF001
    try:
        monkeypatch.setattr(renderer, "_dispatch_tokens", _raise_dispatch)

        with pytest.raises(RuntimeError, match="dispatch boom"):
            renderer._process_form_bytes(b"0 0 m")  # noqa: SLF001

        assert renderer._knockout_form_depth == 4  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_show_inline_image_falls_back_to_legacy_decoder_success(
    caplog: Any,
) -> None:
    class _InlineImage:
        def to_pil_image(self) -> None:
            raise RuntimeError("helper boom")

        def get_cos_object(self) -> COSDictionary:
            return _inline_params()

        def get_stream(self) -> bytes:
            return bytes([12, 34, 56])

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")

        renderer.show_inline_image(_InlineImage())
        _finish(renderer)

        assert "cannot decode inline image (helper): helper boom" in caplog.text
        assert renderer._image.getpixel((0, 0)) == (12, 34, 56)  # noqa: SLF001
        assert renderer._image.getpixel((1, 1)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_decode_image_xobject_helper_converts_to_rgb_without_stream_fallback() -> None:
    class _Image:
        def to_pil_image(self) -> Image.Image:
            return Image.new("RGBA", (1, 1), (10, 20, 30, 40))

        def get_cos_object(self) -> Any:
            raise AssertionError("stream fallback should not be used")

    doc, renderer = _prepared_renderer()
    try:
        decoded = renderer._decode_image_xobject(_Image())  # noqa: SLF001

        assert decoded is not None
        assert decoded.mode == "RGB"
        assert decoded.getpixel((0, 0)) == (10, 20, 30)
    finally:
        _finish(renderer)
        doc.close()


def test_paste_image_alpha_without_clip_preserves_background() -> None:
    doc, renderer = _prepared_renderer((2, 2))
    try:
        source = Image.new("RGBA", (1, 1), (200, 10, 20, 0))

        renderer._paste_image(source)  # noqa: SLF001
        _finish(renderer)

        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)  # noqa: SLF001

        source.putpixel((0, 0), (200, 10, 20, 255))
        renderer._paste_image(source)  # noqa: SLF001
        _finish(renderer)

        assert renderer._image.getpixel((0, 0)) == (200, 10, 20)  # noqa: SLF001
    finally:
        doc.close()
