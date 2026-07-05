from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSNull
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.common.function import PDFunction
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
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def eval(self, _inputs: list[float]) -> list[float]:
        return self._values


class _RaisesEval:
    def eval(self, _inputs: list[float]) -> list[float]:
        raise RuntimeError("eval failed")


class _EmptyEval:
    def eval(self, _inputs: list[float]) -> list[float]:
        return []


def test_function_shading_array_bad_subfunctions_skip_pixel(
    monkeypatch: Any,
) -> None:
    class _Shading:
        def get_domain(self) -> COSArray:
            return _float_array(0.0, 1.0, 0.0, 1.0)

        def get_matrix(self) -> None:
            return None

        def get_function(self) -> COSArray:
            functions = COSArray()
            functions.add(COSNull.NULL)
            functions.add(COSName.get_pdf_name("BadCreate"))
            functions.add(COSName.get_pdf_name("RaisesEval"))
            functions.add(COSName.get_pdf_name("EmptyEval"))
            functions.add(COSName.get_pdf_name("Blue"))
            return functions

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceCMYK")

    def create(entry: Any) -> Any:
        if isinstance(entry, COSName) and entry.name == "BadCreate":
            raise RuntimeError("factory failed")
        if isinstance(entry, COSName) and entry.name == "RaisesEval":
            return _RaisesEval()
        if isinstance(entry, COSName) and entry.name == "EmptyEval":
            return _EmptyEval()
        return _RGBFunction([0.5])

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        monkeypatch.setattr(PDFunction, "create", staticmethod(create))

        renderer._paint_function_shading(  # noqa: SLF001
            _Shading(),
            region_mask=Image.new("L", (1, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        # Wave 1598: any bad array entry (create failure / eval failure /
        # empty output) aborts the pixel's evaluation — upstream
        # PDShading.evalFunction propagates the IOException and
        # Type1ShadingContext.getRaster skips the pixel. Canvas preserved.
        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_function_shading_scalar_factory_failure_preserves_canvas(
    monkeypatch: Any,
) -> None:
    class _Shading:
        def get_domain(self) -> COSArray:
            return _float_array(0.0, 1.0, 0.0, 1.0)

        def get_matrix(self) -> None:
            return None

        def get_function(self) -> object:
            return object()

    doc, renderer = _prepared_renderer(size=(2, 2))
    try:
        before = renderer._image.copy()  # noqa: SLF001
        monkeypatch.setattr(
            PDFunction,
            "create",
            staticmethod(
                lambda _entry: (_ for _ in ()).throw(RuntimeError("bad function"))
            ),
        )

        renderer._paint_function_shading(  # noqa: SLF001
            _Shading(),
            region_mask=Image.new("L", (2, 2), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.tobytes() == before.tobytes()  # noqa: SLF001
    finally:
        doc.close()


def test_axial_shading_constant_domain_uses_first_ramp_entry() -> None:
    class _Shading:
        def get_coords(self) -> _Coords:
            return _Coords(0.0, 0.0, 1.0, 0.0)

        def get_domain(self) -> COSArray:
            return _float_array(0.25, 0.25)

        def get_extend(self) -> tuple[bool, bool]:
            return (True, True)

        def get_function(self) -> _RGBFunction:
            return _RGBFunction([0.25, 0.0, 0.0])

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

    doc, renderer = _prepared_renderer(size=(2, 1))
    try:
        renderer._paint_axial_shading(  # noqa: SLF001
            _Shading(),
            region_mask=Image.new("L", (2, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (64, 0, 0)  # noqa: SLF001
        assert renderer._image.getpixel((1, 0)) == (64, 0, 0)  # noqa: SLF001
    finally:
        doc.close()


def test_radial_shading_without_valid_root_leaves_region_white() -> None:
    class _Shading:
        def get_coords(self) -> _Coords:
            return _Coords(0.0, 0.0, 1.0, 0.0, 0.0, 1.0)

        def get_domain(self) -> None:
            return None

        def get_extend(self) -> tuple[bool, bool]:
            return (True, True)

        def get_function(self) -> _RGBFunction:
            return _RGBFunction([1.0, 0.0, 0.0])

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

    doc, renderer = _prepared_renderer(size=(2, 1))
    try:
        renderer._paint_radial_shading(  # noqa: SLF001
            _Shading(),
            region_mask=Image.new("L", (2, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)  # noqa: SLF001
        assert renderer._image.getpixel((1, 0)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()
