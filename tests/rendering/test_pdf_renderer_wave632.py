from __future__ import annotations

import io
from typing import Any

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import pdf_renderer as renderer_module
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(
    width: float = 4.0,
    height: float = 4.0,
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(
    size: tuple[int, int] = (4, 4),
) -> tuple[PDDocument, PDFRenderer]:
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


def _png_payload(color: tuple[int, int, int]) -> bytes:
    payload = io.BytesIO()
    Image.new("RGB", (1, 1), color).save(payload, format="PNG")
    return payload.getvalue()


def test_process_operator_logs_and_swallows_handler_type_error(
    monkeypatch: Any,
    caplog: Any,
) -> None:
    def _broken_handler(
        _renderer: PDFRenderer,
        _op: Any,
        _operands: list[Any],
    ) -> None:
        raise TypeError("synthetic type failure")

    doc, renderer = _prepared_renderer()
    original = renderer_module._DISPATCH["RG"]  # noqa: SLF001
    try:
        caplog.set_level("DEBUG", logger="pypdfbox.rendering.pdf_renderer")
        monkeypatch.setitem(renderer_module._DISPATCH, "RG", _broken_handler)  # noqa: SLF001

        renderer.process_operator(
            "RG",
            [COSName.get_pdf_name("Bad"), COSName.get_pdf_name("StillBad")],
        )

        assert "dropping operator RG: synthetic type failure" in caplog.text
        assert renderer._gs.stroke_rgb == (0, 0, 0)  # noqa: SLF001
    finally:
        monkeypatch.setitem(renderer_module._DISPATCH, "RG", original)  # noqa: SLF001
        _finish(renderer)
        doc.close()


def test_decode_image_xobject_dct_path_uses_encoded_stream_payload() -> None:
    class _ImageXObject:
        def __init__(self, payload: bytes) -> None:
            self._stream = COSStream()
            self._stream.set_item(COSName.FILTER, COSName.get_pdf_name("DCTDecode"))
            self._payload = payload
            self.stop_filters: list[list[str]] = []

        def get_cos_object(self) -> COSStream:
            return self._stream

        def get_width(self) -> int:
            return 1

        def get_height(self) -> int:
            return 1

        def get_bits_per_component(self) -> int:
            return 8

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

        def create_input_stream(
            self,
            stop_filters: list[str] | None = None,
        ) -> io.BytesIO:
            self.stop_filters.append(list(stop_filters or []))
            return io.BytesIO(self._payload)

    doc, renderer = _prepared_renderer()
    image = _ImageXObject(_png_payload((21, 43, 65)))
    try:
        decoded = renderer._decode_image_xobject(image)  # noqa: SLF001

        assert decoded is not None
        assert decoded.mode == "RGB"
        assert decoded.getpixel((0, 0)) == (21, 43, 65)
        assert image.stop_filters == [["DCTDecode"]]
    finally:
        _finish(renderer)
        doc.close()
