from __future__ import annotations

import io
from typing import Any

from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _GState

_DEFAULT_COLOR_SPACE = object()


def _make_doc(width: float = 20.0, height: float = 20.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _inline_params(
    *,
    width: int = 1,
    height: int = 1,
    color_space: COSName | None | object = _DEFAULT_COLOR_SPACE,
    bpc: int = 8,
    filter_obj: Any | None = None,
) -> COSDictionary:
    params = COSDictionary()
    params.set_item(COSName.get_pdf_name("W"), COSInteger.get(width))
    params.set_item(COSName.get_pdf_name("H"), COSInteger.get(height))
    params.set_item(COSName.get_pdf_name("BPC"), COSInteger.get(bpc))
    if color_space is _DEFAULT_COLOR_SPACE:
        params.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("RGB"))
    elif color_space is not None:
        params.set_item(COSName.get_pdf_name("CS"), color_space)
    if filter_obj is not None:
        params.set_item(COSName.get_pdf_name("F"), filter_obj)
    return params


def _float_array(values: list[float]) -> COSArray:
    array = COSArray()
    for value in values:
        array.add(COSFloat(value))
    return array


class _TilingPattern:
    def __init__(self, cos_object: Any, resources: Any | None = None) -> None:
        self._cos_object = cos_object
        self._resources = resources

    def get_cos_object(self) -> Any:
        return self._cos_object

    def get_resources(self) -> Any | None:
        return self._resources


def test_decode_inline_image_handles_abbreviations_and_rejects_malformed() -> None:
    gray = PDFRenderer._decode_inline_image(
        _inline_params(width=2, height=1, color_space=COSName.get_pdf_name("G")),
        bytes([0, 255]),
    )
    assert gray is not None
    assert gray.mode == "RGB"
    assert gray.getpixel((0, 0)) == (0, 0, 0)
    assert gray.getpixel((1, 0)) == (255, 255, 255)

    inferred_rgb = PDFRenderer._decode_inline_image(
        _inline_params(width=1, height=1, color_space=None),
        bytes([10, 20, 30]),
    )
    assert inferred_rgb is not None
    assert inferred_rgb.getpixel((0, 0)) == (10, 20, 30)

    unsupported_filter = PDFRenderer._decode_inline_image(
        _inline_params(filter_obj=COSName.get_pdf_name("Fl")),
        b"\x00",
    )
    assert unsupported_filter is None
    assert PDFRenderer._decode_inline_image(_inline_params(bpc=1), b"\x00") is None

    missing_height = COSDictionary()
    missing_height.set_item(COSName.get_pdf_name("W"), COSInteger.get(1))
    assert PDFRenderer._decode_inline_image(missing_height, b"\x00") is None


def test_decode_inline_image_dct_filter_array_uses_encoded_payload() -> None:
    source = Image.new("RGB", (1, 1), (200, 20, 30))
    buf = io.BytesIO()
    source.save(buf, format="JPEG", quality=95)

    filters = COSArray()
    filters.add(COSName.get_pdf_name("DCT"))
    decoded = PDFRenderer._decode_inline_image(
        _inline_params(filter_obj=filters),
        buf.getvalue(),
    )

    assert decoded is not None
    r, g, b = decoded.getpixel((0, 0))
    assert r > 150 and g < 80 and b < 90


def test_decode_image_xobject_helper_fallbacks() -> None:
    class _Input:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def __enter__(self) -> io.BytesIO:
            return io.BytesIO(self._data)

        def __exit__(self, *_exc: Any) -> None:
            return None

    class _FakeImage:
        def __init__(
            self,
            *,
            data: bytes = b"",
            width: int = 1,
            height: int = 1,
            bpc: int = 8,
            color_space: COSName | None | object = _DEFAULT_COLOR_SPACE,
            cos: Any | None = None,
        ) -> None:
            self._data = data
            self._width = width
            self._height = height
            self._bpc = bpc
            self._color_space = (
                COSName.get_pdf_name("DeviceGray")
                if color_space is _DEFAULT_COLOR_SPACE
                else color_space
            )
            self._cos = COSStream() if cos is None else cos

        def get_cos_object(self) -> Any:
            return self._cos

        def get_width(self) -> int:
            return self._width

        def get_height(self) -> int:
            return self._height

        def get_bits_per_component(self) -> int:
            return self._bpc

        def get_color_space(self) -> COSName | None:
            return self._color_space

        def create_input_stream(self, stop_filters: list[str] | None = None) -> _Input:
            del stop_filters
            return _Input(self._data)

    doc, renderer = _make_doc()[0], PDFRenderer(_make_doc()[0])
    try:
        gray = renderer._decode_image_xobject(  # noqa: SLF001
            _FakeImage(data=bytes([64, 192]), width=2, height=1)
        )
        assert gray is not None
        assert gray.mode == "RGB"
        assert gray.getpixel((0, 0)) == (64, 64, 64)
        assert gray.getpixel((1, 0)) == (192, 192, 192)

        rgb = renderer._decode_image_xobject(  # noqa: SLF001
            _FakeImage(
                data=bytes([1, 2, 3]),
                color_space=None,
            )
        )
        assert rgb is not None
        assert rgb.getpixel((0, 0)) == (1, 2, 3)

        assert renderer._decode_image_xobject(_FakeImage(width=0)) is None  # noqa: SLF001
        assert renderer._decode_image_xobject(_FakeImage(bpc=4)) is None  # noqa: SLF001
        assert renderer._decode_image_xobject(_FakeImage(cos=COSDictionary())) is None  # noqa: SLF001
    finally:
        doc.close()
        renderer.get_document().close()


def test_shading_static_helpers_default_and_convert_defensively() -> None:
    class _RaisesDomain:
        def get_domain(self) -> Any:
            raise RuntimeError("domain")

    class _RaisesMatrix:
        def get_matrix(self) -> Any:
            raise RuntimeError("matrix")

    class _Domain:
        def __init__(self, domain: COSArray | None) -> None:
            self._domain = domain

        def get_domain(self) -> COSArray | None:
            return self._domain

    class _Matrix:
        def __init__(self, matrix: COSArray | None) -> None:
            self._matrix = matrix

        def get_matrix(self) -> COSArray | None:
            return self._matrix

    class _Extend:
        def __init__(self, extend: Any) -> None:
            self._extend = extend

        def get_extend(self) -> Any:
            return self._extend

    assert PDFRenderer._shading_domain(_RaisesDomain()) == (0.0, 1.0)  # noqa: SLF001
    assert PDFRenderer._shading_domain(_Domain(None)) == (0.0, 1.0)  # noqa: SLF001
    assert PDFRenderer._shading_domain(_Domain(_float_array([0.25, 0.75]))) == (  # noqa: SLF001
        0.25,
        0.75,
    )
    assert PDFRenderer._shading_domain_2d(_Domain(_float_array([0.0, 2.0]))) == (  # noqa: SLF001
        0.0,
        1.0,
        0.0,
        1.0,
    )
    assert PDFRenderer._shading_matrix(_RaisesMatrix()) == (  # noqa: SLF001
        1.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
    )
    assert PDFRenderer._shading_matrix(_Matrix(_float_array([1, 2, 3, 4, 5, 6]))) == (  # noqa: SLF001
        1.0,
        2.0,
        3.0,
        4.0,
        5.0,
        6.0,
    )

    extend = COSArray()
    extend.add(COSBoolean.get(True))
    extend.add(COSBoolean.get(False))
    assert PDFRenderer._shading_extend(_Extend((True, False))) == (True, False)  # noqa: SLF001
    assert PDFRenderer._shading_extend(_Extend(extend)) == (True, False)  # noqa: SLF001
    assert PDFRenderer._shading_extend(_Extend(COSArray())) == (False, False)  # noqa: SLF001

    assert PDFRenderer._invert_matrix((1.0, 2.0, 2.0, 4.0, 0.0, 0.0)) is None  # noqa: SLF001
    inv = PDFRenderer._invert_matrix((2.0, 0.0, 0.0, 4.0, 6.0, 8.0))  # noqa: SLF001
    assert inv == (0.5, -0.0, -0.0, 0.25, -3.0, -2.0)

    assert PDFRenderer._function_output_to_rgb([], None) == (0, 0, 0)  # noqa: SLF001
    assert PDFRenderer._function_output_to_rgb([0.5], "DeviceGray") == (128, 128, 128)  # noqa: SLF001
    assert PDFRenderer._function_output_to_rgb([1.0, 0.0, 0.0, 0.0], "DeviceCMYK") == (  # noqa: SLF001
        0,
        255,
        255,
    )


def test_render_tiling_cell_empty_and_invalid_inputs() -> None:
    doc, renderer = _make_doc()[0], PDFRenderer(_make_doc()[0])
    renderer._gs_stack = [_GState()]  # noqa: SLF001
    try:
        empty_stream = COSStream()
        empty_stream.set_raw_data(b"")
        tile = renderer._render_tiling_cell(  # noqa: SLF001
            _TilingPattern(empty_stream),
            bbox=PDRectangle(0.0, 0.0, 4.0, 4.0),
            tile_size=(3, 3),
        )
        assert tile is not None
        assert tile.size == (3, 3)
        assert tile.getpixel((1, 1)) == (255, 255, 255)

        assert renderer._render_tiling_cell(  # noqa: SLF001
            _TilingPattern(COSDictionary()),
            bbox=PDRectangle(0.0, 0.0, 4.0, 4.0),
            tile_size=(3, 3),
        ) is None

        nonempty_stream = COSStream()
        nonempty_stream.set_raw_data(b"0 0 1 rg 0 0 1 1 re f\n")
        assert renderer._render_tiling_cell(  # noqa: SLF001
            _TilingPattern(nonempty_stream),
            bbox=PDRectangle(0.0, 0.0, 0.0, 4.0),
            tile_size=(3, 3),
        ) is None
    finally:
        doc.close()
        renderer.get_document().close()
