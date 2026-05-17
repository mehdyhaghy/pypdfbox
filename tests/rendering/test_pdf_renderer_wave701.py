from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSArray, COSBoolean, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.shading import PDShadingType4
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState, _to_float


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
    def __init__(self, values: list[float] | None) -> None:
        self._values = values

    def eval(self, _inputs: list[float]) -> list[float]:
        if self._values is None:
            raise RuntimeError("eval failed")
        return self._values


def test_to_float_accepts_direct_integer_and_float_values() -> None:
    assert _to_float(COSInteger.get(7)) == 7.0  # noqa: SLF001
    assert _to_float(COSFloat(2.5)) == 2.5  # noqa: SLF001


def test_mesh_shading_fallback_paints_evaluated_color(monkeypatch: Any) -> None:
    doc, renderer = _prepared_renderer(size=(2, 2))
    try:
        monkeypatch.setattr(
            renderer,
            "_evaluate_shading_rgb",
            lambda _shading, _t: (0.25, 0.5, 1.0),
        )

        renderer._paint_shading(  # noqa: SLF001
            PDShadingType4(),
            region_mask=Image.new("L", (2, 2), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (64, 128, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_axial_shading_uses_black_ramp_entry_when_eval_fails() -> None:
    class _Axial:
        def get_coords(self) -> _Coords:
            return _Coords(0.0, 0.0, 1.0, 0.0)

        def get_domain(self) -> COSArray:
            return _float_array(0.0, 1.0)

        def get_extend(self) -> tuple[bool, bool]:
            return (True, True)

        def get_function(self) -> _RGBFunction:
            return _RGBFunction(None)

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        renderer._paint_axial_shading(  # noqa: SLF001
            _Axial(),
            region_mask=Image.new("L", (1, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (0, 0, 0)  # noqa: SLF001
    finally:
        doc.close()


def test_function_shading_handles_color_space_error_and_zero_mask() -> None:
    class _FunctionShading:
        def get_domain(self) -> COSArray:
            return _float_array(0.0, 1.0, 0.0, 1.0)

        def get_matrix(self) -> None:
            return None

        def get_function(self) -> _RGBFunction:
            return _RGBFunction([1.0, 0.0, 0.0])

        def get_color_space(self) -> object:
            raise RuntimeError("color space unavailable")

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        before = renderer._image.copy()  # noqa: SLF001

        renderer._paint_function_shading(  # noqa: SLF001
            _FunctionShading(),
            region_mask=Image.new("L", (1, 1), 0),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.tobytes() == before.tobytes()  # noqa: SLF001
    finally:
        doc.close()


def test_shading_extend_reads_cos_boolean_array_values() -> None:
    ext = COSArray()
    ext.add(COSBoolean.TRUE)
    ext.add(COSBoolean.FALSE)

    class _Shading:
        def get_extend(self) -> COSArray:
            return ext

    assert PDFRenderer._shading_extend(_Shading()) == (True, False)  # noqa: SLF001
