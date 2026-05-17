from __future__ import annotations

import builtins
from collections.abc import Callable
from typing import Any

from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import _aggdraw_compat as aggdraw
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
    def eval(self, _inputs: list[float]) -> list[float]:
        return [1.0, 0.0, 0.0]


def _force_round(monkeypatch: Any, value: int) -> None:
    original_round: Callable[..., object] = builtins.round

    def forced_round(number: float, ndigits: int | None = None) -> object:
        if ndigits is None and 0.0 <= number <= 255.0:
            return value
        if ndigits is None:
            return original_round(number)
        return original_round(number, ndigits)

    monkeypatch.setattr(builtins, "round", forced_round)


def test_axial_shading_clamps_negative_ramp_index(monkeypatch: Any) -> None:
    class _Axial:
        def get_coords(self) -> _Coords:
            return _Coords(0.0, 0.0, 1.0, 0.0)

        def get_domain(self) -> COSArray:
            return _float_array(0.0, 1.0)

        def get_extend(self) -> tuple[bool, bool]:
            return (True, True)

        def get_function(self) -> _RGBFunction:
            return _RGBFunction()

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        _force_round(monkeypatch, -8)

        renderer._paint_axial_shading(  # noqa: SLF001
            _Axial(),
            region_mask=Image.new("L", (1, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (255, 0, 0)  # noqa: SLF001
    finally:
        doc.close()


def test_axial_shading_clamps_large_ramp_index(monkeypatch: Any) -> None:
    class _Axial:
        def get_coords(self) -> _Coords:
            return _Coords(0.0, 0.0, 1.0, 0.0)

        def get_domain(self) -> COSArray:
            return _float_array(0.0, 1.0)

        def get_extend(self) -> tuple[bool, bool]:
            return (True, True)

        def get_function(self) -> _RGBFunction:
            return _RGBFunction()

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        _force_round(monkeypatch, 999)

        renderer._paint_axial_shading(  # noqa: SLF001
            _Axial(),
            region_mask=Image.new("L", (1, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (255, 0, 0)  # noqa: SLF001
    finally:
        doc.close()


def test_radial_shading_clamps_negative_ramp_index(monkeypatch: Any) -> None:
    class _Radial:
        def get_coords(self) -> _Coords:
            return _Coords(0.0, 0.0, 1.0, 1.0, 0.0, 2.0)

        def get_domain(self) -> COSArray:
            return _float_array(0.0, 1.0)

        def get_extend(self) -> tuple[bool, bool]:
            return (True, True)

        def get_function(self) -> _RGBFunction:
            return _RGBFunction()

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        _force_round(monkeypatch, -8)

        renderer._paint_radial_shading(  # noqa: SLF001
            _Radial(),
            region_mask=Image.new("L", (1, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (255, 0, 0)  # noqa: SLF001
    finally:
        doc.close()


def test_radial_shading_clamps_large_ramp_index(monkeypatch: Any) -> None:
    class _Radial:
        def get_coords(self) -> _Coords:
            return _Coords(0.0, 0.0, 1.0, 1.0, 0.0, 2.0)

        def get_domain(self) -> COSArray:
            return _float_array(0.0, 1.0)

        def get_extend(self) -> tuple[bool, bool]:
            return (True, True)

        def get_function(self) -> _RGBFunction:
            return _RGBFunction()

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        _force_round(monkeypatch, 999)

        renderer._paint_radial_shading(  # noqa: SLF001
            _Radial(),
            region_mask=Image.new("L", (1, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (255, 0, 0)  # noqa: SLF001
    finally:
        doc.close()
