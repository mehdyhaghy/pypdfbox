from __future__ import annotations

import io
from typing import Any

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
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


def test_decode_image_xobject_ignores_non_image_helper_result_and_uses_raw_rgb() -> None:
    class _ImageXObject:
        def __init__(self) -> None:
            self._stream = COSStream()

        def to_pil_image(self) -> object:
            return object()

        def get_cos_object(self) -> COSStream:
            return self._stream

        def get_width(self) -> int:
            return 1

        def get_height(self) -> int:
            return 1

        def get_bits_per_component(self) -> int:
            return -1

        def get_color_space(self) -> None:
            return None

        def create_input_stream(self) -> io.BytesIO:
            return io.BytesIO(b"\x11\x22\x33")

    doc, renderer = _prepared_renderer()
    try:
        image = renderer._decode_image_xobject(_ImageXObject())  # noqa: SLF001

        assert image is not None
        assert image.mode == "RGB"
        assert image.getpixel((0, 0)) == (17, 34, 51)
    finally:
        _finish(renderer)
        doc.close()


def test_render_tiling_cell_rejects_non_stream_and_degenerate_bbox() -> None:
    class _Pattern:
        def __init__(self, cos_object: object) -> None:
            self._cos_object = cos_object

        def get_cos_object(self) -> object:
            return self._cos_object

        def get_resources(self) -> None:
            return None

    class _BBox:
        def __init__(self, width: float, height: float) -> None:
            self._width = width
            self._height = height

        def get_width(self) -> float:
            return self._width

        def get_height(self) -> float:
            return self._height

        def get_lower_left_x(self) -> float:
            return 0.0

        def get_lower_left_y(self) -> float:
            return 0.0

    stream = COSStream()
    stream.set_raw_data(b"0 0 m\n")
    doc, renderer = _prepared_renderer()
    try:
        assert renderer._render_tiling_cell(  # noqa: SLF001
            _Pattern(object()),
            bbox=_BBox(1.0, 1.0),
            tile_size=(2, 2),
        ) is None
        assert renderer._render_tiling_cell(  # noqa: SLF001
            _Pattern(stream),
            bbox=_BBox(0.0, 1.0),
            tile_size=(2, 2),
        ) is None
        assert renderer._render_tiling_cell(  # noqa: SLF001
            _Pattern(stream),
            bbox=_BBox(1.0, -1.0),
            tile_size=(2, 2),
        ) is None
    finally:
        _finish(renderer)
        doc.close()


def test_build_transfer_lookup_clamps_function_outputs(
    monkeypatch: Any,
) -> None:
    class _Function:
        def eval(self, values: list[float]) -> list[float]:
            x = values[0]
            if x == 0.0:
                return [-1.0]
            if x == 1.0:
                return [2.0]
            return [0.5]

    from pypdfbox.pdmodel.common.function import PDFunction

    monkeypatch.setattr(PDFunction, "create", staticmethod(lambda _tr: _Function()))

    lookup = PDFRenderer._build_transfer_lookup(object())  # noqa: SLF001

    assert lookup is not None
    assert lookup[0] == 0
    assert lookup[128] == 128
    assert lookup[255] == 255


def test_soft_mask_backdrop_rgb_pads_short_rgb_arrays() -> None:
    class _Backdrop:
        def to_float_array(self) -> list[float]:
            return [0.25, 0.75]

    class _SoftMask:
        def get_backdrop_color(self) -> COSArray:
            array = COSArray()
            for value in _Backdrop().to_float_array():
                array.add(COSFloat(value))
            return array

    doc, renderer = _prepared_renderer()
    try:
        assert renderer._soft_mask_backdrop_rgb(_SoftMask()) == (64, 191, 0)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_build_transfer_lookup_returns_none_when_function_eval_fails(
    monkeypatch: Any,
) -> None:
    class _Function:
        def eval(self, _values: list[float]) -> list[float]:
            raise RuntimeError("transfer boom")

    from pypdfbox.pdmodel.common.function import PDFunction

    monkeypatch.setattr(PDFunction, "create", staticmethod(lambda _tr: _Function()))

    assert PDFRenderer._build_transfer_lookup(COSName.get_pdf_name("TR0")) is None  # noqa: SLF001

