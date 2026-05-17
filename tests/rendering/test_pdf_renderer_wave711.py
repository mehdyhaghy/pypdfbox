from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering import pdf_renderer
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


def _float_array(*values: float) -> COSArray:
    array = COSArray()
    for value in values:
        array.add(COSFloat(value))
    return array


class _Coords:
    def __init__(self, *values: float) -> None:
        self._values = values

    def size(self) -> int:
        return len(self._values)

    def get_object(self, index: int) -> COSFloat:
        return COSFloat(self._values[index])


class _RGBFunction:
    def __init__(self, rgb: list[float]) -> None:
        self._rgb = rgb

    def eval(self, _inputs: list[float]) -> list[float]:
        return self._rgb


def test_to_float_uses_direct_value_fallback_when_cosnumber_does_not_match(
    monkeypatch: Any,
) -> None:
    class _NotCOSNumber:
        pass

    monkeypatch.setattr(pdf_renderer, "COSNumber", _NotCOSNumber)

    assert pdf_renderer._to_float(COSInteger.get(11)) == 11.0  # noqa: SLF001


def test_radial_shading_skips_negative_radius_candidate_then_uses_next_root() -> None:
    class _Radial:
        def get_coords(self) -> _Coords:
            return _Coords(0.0, 0.0, 1.0, 0.0, 0.0, -1.0)

        def get_domain(self) -> COSArray:
            return _float_array(0.0, 1.0)

        def get_extend(self) -> tuple[bool, bool]:
            return (False, False)

        def get_function(self) -> _RGBFunction:
            return _RGBFunction([1.0, 0.0, 0.0])

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        renderer._device_ctm = (  # noqa: SLF001
            1.0,
            0.0,
            0.0,
            1.0,
            -0.5,
            0.0,
        )

        renderer._paint_radial_shading(  # noqa: SLF001
            _Radial(),
            region_mask=Image.new("L", (1, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (255, 0, 0)  # noqa: SLF001
    finally:
        doc.close()


def test_function_shading_cosarray_functions_fill_missing_and_failed_channels(
    monkeypatch: Any,
) -> None:
    class _ScalarFunction:
        def __init__(self, value: float | None) -> None:
            self._value = value

        def eval(self, _inputs: list[float]) -> list[float]:
            if self._value is None:
                raise RuntimeError("channel failed")
            return [self._value]

    created = iter([_ScalarFunction(1.0), _ScalarFunction(None)])

    def create_function(_entry: object) -> _ScalarFunction:
        return next(created)

    from pypdfbox.pdmodel.common.function import PDFunction

    monkeypatch.setattr(PDFunction, "create", create_function)

    function_array = COSArray()
    function_array.add(COSFloat(1.0))
    function_array.add(COSFloat(2.0))
    function_array.add(None)

    class _FunctionShading:
        def get_domain(self) -> COSArray:
            return _float_array(0.0, 1.0, 0.0, 1.0)

        def get_matrix(self) -> None:
            return None

        def get_function(self) -> COSArray:
            return function_array

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        renderer._paint_function_shading(  # noqa: SLF001
            _FunctionShading(),
            region_mask=Image.new("L", (1, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (255, 0, 0)  # noqa: SLF001
    finally:
        doc.close()
