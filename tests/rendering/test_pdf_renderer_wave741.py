from __future__ import annotations

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
    size: tuple[int, int] = (1, 1),
) -> tuple[PDDocument, PDFRenderer]:
    doc, _page = _make_doc(float(size[0]), float(size[1]))
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", size, (255, 255, 255))
    renderer._draw = aggdraw.Draw(renderer._image)
    renderer._draw.setantialias(True)
    renderer._gs_stack = [_GState()]
    renderer._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    return doc, renderer


def _finish(renderer: PDFRenderer) -> None:
    draw = renderer._draw
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


class _Radial:
    def __init__(self, *coords: float) -> None:
        self._coords = coords

    def get_coords(self) -> _Coords:
        return _Coords(*self._coords)

    def get_domain(self) -> COSArray:
        return _float_array(0.0, 1.0)

    def get_extend(self) -> tuple[bool, bool]:
        return (False, False)

    def get_function(self) -> _RGBFunction:
        return _RGBFunction()

    def get_color_space(self) -> COSName:
        return COSName.get_pdf_name("DeviceRGB")


def test_radial_shading_skips_sample_before_unextended_start() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._paint_radial_shading(
            _Radial(1.0, 0.0, 0.0, 2.0, 0.0, 0.0),
            region_mask=Image.new("L", (1, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None
        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)
    finally:
        doc.close()


def test_radial_shading_skips_sample_after_unextended_end() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._device_ctm = (1.0, 0.0, 0.0, 1.0, -2.0, 0.0)

        renderer._paint_radial_shading(
            _Radial(0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            region_mask=Image.new("L", (1, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None
        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)
    finally:
        doc.close()


def test_resolve_font_program_handles_type1c_probe_failure(
    monkeypatch: Any,
) -> None:
    import pypdfbox.fontbox.font_mappers as mapper_module
    import pypdfbox.pdmodel.font.pd_type1c_font as type1c_module

    class _Type1CFont:
        def _get_cff_font(self) -> object:
            raise RuntimeError("cff probe failed")

        def get_name(self) -> str:
            return "BrokenCFF"

        def get_font_descriptor(self) -> None:
            return None

    class _Mapping:
        def get_font(self) -> str:
            return "fallback"

    class _Mapper:
        def get_font_box_font(self, _name: str, _descriptor: object | None) -> _Mapping:
            return _Mapping()

    doc, renderer = _prepared_renderer()
    try:
        monkeypatch.setattr(renderer, "_get_ttf_glyph_set", lambda _font: (None, None))
        monkeypatch.setattr(type1c_module, "PDType1CFont", _Type1CFont)
        monkeypatch.setattr(
            mapper_module.FontMappers,
            "instance",
            staticmethod(lambda: _Mapper()),
        )

        font = _Type1CFont()

        assert renderer._resolve_font_program(font) == "fallback"
        assert renderer._font_program_cache[id(font)] == "fallback"
    finally:
        doc.close()
