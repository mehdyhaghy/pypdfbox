from __future__ import annotations

from typing import Any

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(width: float = 4.0, height: float = 4.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (4, 4)) -> tuple[PDDocument, PDFRenderer]:
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


def test_decode_image_xobject_rejects_invalid_raw_image_shapes() -> None:
    class _ImageXObject:
        def __init__(
            self,
            *,
            width: int = 1,
            height: int = 1,
            bpc: int = 8,
            color_space: COSName | None = None,
        ) -> None:
            self._width = width
            self._height = height
            self._bpc = bpc
            self._color_space = color_space or COSName.get_pdf_name("DeviceRGB")
            self._stream = COSDictionary()

        def get_cos_object(self) -> COSDictionary:
            return self._stream

        def get_width(self) -> int:
            return self._width

        def get_height(self) -> int:
            return self._height

        def get_bits_per_component(self) -> int:
            return self._bpc

        def get_color_space(self) -> COSName | None:
            return self._color_space

    doc, renderer = _prepared_renderer()
    try:
        assert renderer._decode_image_xobject(_ImageXObject(width=0)) is None  # noqa: SLF001
        assert renderer._decode_image_xobject(_ImageXObject(height=0)) is None  # noqa: SLF001
        assert renderer._decode_image_xobject(_ImageXObject(bpc=4)) is None  # noqa: SLF001
        assert renderer._decode_image_xobject(  # noqa: SLF001
            _ImageXObject(color_space=COSName.get_pdf_name("DeviceCMYK"))
        ) is None
    finally:
        _finish(renderer)
        doc.close()


def test_inline_image_operator_logs_constructor_failure_and_skips_paste(
    caplog: Any,
    monkeypatch: Any,
) -> None:
    from pypdfbox.pdmodel.graphics.image import pd_inline_image

    class _Operator:
        def get_image_parameters(self) -> COSDictionary:
            params = COSDictionary()
            params.set_item(COSName.get_pdf_name("W"), COSInteger.get(1))
            params.set_item(COSName.get_pdf_name("H"), COSInteger.get(1))
            return params

        def get_image_data(self) -> bytes:
            return b"\x00\x00\x00"

    class _BrokenInlineImage:
        def __init__(self, *_args: object) -> None:
            raise RuntimeError("inline boom")

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level("DEBUG", logger="pypdfbox.rendering.pdf_renderer")
        monkeypatch.setattr(pd_inline_image, "PDInlineImage", _BrokenInlineImage)
        monkeypatch.setattr(
            renderer,
            "_paste_image",
            lambda _image: (_ for _ in ()).throw(AssertionError("pasted")),
        )

        renderer._op_inline_image(_Operator(), [])  # noqa: SLF001

        assert "cannot construct inline image: inline boom" in caplog.text
        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_show_inline_image_falls_back_when_helper_decode_fails(
    monkeypatch: Any,
) -> None:
    params = COSDictionary()
    params.set_item(COSName.get_pdf_name("W"), COSInteger.get(1))
    params.set_item(COSName.get_pdf_name("H"), COSInteger.get(1))
    params.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("RGB"))
    params.set_item(COSName.get_pdf_name("BPC"), COSInteger.get(8))

    class _InlineImage:
        def to_pil_image(self) -> Image.Image:
            raise RuntimeError("helper boom")

        def get_cos_object(self) -> COSDictionary:
            return params

        def get_stream(self) -> bytes:
            return b"\x10\x20\x30"

    doc, renderer = _prepared_renderer()
    pasted: list[Image.Image] = []
    try:
        monkeypatch.setattr(renderer, "_paste_image", lambda image: pasted.append(image))

        renderer.show_inline_image(_InlineImage())

        assert len(pasted) == 1
        assert pasted[0].mode == "RGB"
        assert pasted[0].getpixel((0, 0)) == (16, 32, 48)
    finally:
        _finish(renderer)
        doc.close()
