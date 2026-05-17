from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSString
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


def test_axial_shading_guards_bad_coords_zero_axis_and_singular_ctm() -> None:
    class _BadCoords:
        def get_coords(self) -> _Coords:
            return _Coords(0.0, 0.0, 1.0)

    class _ZeroAxis:
        def get_coords(self) -> _Coords:
            return _Coords(1.0, 1.0, 1.0, 1.0)

    class _ValidAxis:
        def get_coords(self) -> _Coords:
            return _Coords(0.0, 0.0, 1.0, 0.0)

        def get_domain(self) -> None:
            return None

        def get_extend(self) -> tuple[bool, bool]:
            return (True, True)

    doc, renderer = _prepared_renderer(size=(2, 2))
    try:
        mask = Image.new("L", (2, 2), 255)
        before = renderer._image.copy()  # noqa: SLF001

        renderer._image = None  # noqa: SLF001
        renderer._paint_axial_shading(_ValidAxis(), region_mask=mask)  # noqa: SLF001

        renderer._image = before.copy()  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        renderer._paint_axial_shading(_BadCoords(), region_mask=mask)  # noqa: SLF001
        renderer._paint_axial_shading(_ZeroAxis(), region_mask=mask)  # noqa: SLF001

        renderer._device_ctm = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)  # noqa: SLF001
        renderer._paint_axial_shading(_ValidAxis(), region_mask=mask)  # noqa: SLF001
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.tobytes() == before.tobytes()  # noqa: SLF001
    finally:
        doc.close()


def test_radial_shading_guards_and_zero_mask_pixels_preserve_canvas() -> None:
    class _BadCoords:
        def get_coords(self) -> _Coords:
            return _Coords(0.0, 0.0, 1.0)

    class _Valid:
        def get_coords(self) -> _Coords:
            return _Coords(0.0, 0.0, 0.0, 1.0, 0.0, 1.0)

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
        before = renderer._image.copy()  # noqa: SLF001

        renderer._image = None  # noqa: SLF001
        renderer._paint_radial_shading(  # noqa: SLF001
            _Valid(),
            region_mask=Image.new("L", (2, 1), 255),
        )

        renderer._image = before.copy()  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        renderer._paint_radial_shading(  # noqa: SLF001
            _BadCoords(),
            region_mask=Image.new("L", (2, 1), 255),
        )

        renderer._device_ctm = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)  # noqa: SLF001
        renderer._paint_radial_shading(  # noqa: SLF001
            _Valid(),
            region_mask=Image.new("L", (2, 1), 255),
        )

        renderer._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001
        renderer._paint_radial_shading(  # noqa: SLF001
            _Valid(),
            region_mask=Image.new("L", (2, 1), 0),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.tobytes() == before.tobytes()  # noqa: SLF001
    finally:
        doc.close()


def test_function_shading_exception_and_scalar_eval_failure_paths(
    monkeypatch: Any,
) -> None:
    class _RaisesFunction:
        def get_domain(self) -> COSArray:
            return _float_array(0.0, 1.0, 0.0, 1.0)

        def get_matrix(self) -> None:
            return None

        def get_function(self) -> object:
            raise RuntimeError("function unavailable")

    class _ScalarShading:
        def get_domain(self) -> COSArray:
            return _float_array(0.0, 1.0, 0.0, 1.0)

        def get_matrix(self) -> None:
            return None

        def get_function(self) -> object:
            return object()

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

    class _BadEval:
        def eval(self, _inputs: list[float]) -> list[float]:
            raise RuntimeError("eval failed")

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        before = renderer._image.copy()  # noqa: SLF001

        renderer._paint_function_shading(  # noqa: SLF001
            _RaisesFunction(),
            region_mask=Image.new("L", (1, 1), 255),
        )
        monkeypatch.setattr(PDFunction, "create", staticmethod(lambda _fn: _BadEval()))
        renderer._paint_function_shading(  # noqa: SLF001
            _ScalarShading(),
            region_mask=Image.new("L", (1, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.tobytes() == before.tobytes()  # noqa: SLF001
    finally:
        doc.close()


def test_text_state_empty_operands_and_non_string_show_text_are_noops() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.text_charspace = 3.0  # noqa: SLF001
        renderer._gs.text_wordspace = 4.0  # noqa: SLF001
        renderer._gs.text_leading = 5.0  # noqa: SLF001
        renderer._gs.text_horizontal_scaling = 80.0  # noqa: SLF001
        renderer._gs.text_rise = 6.0  # noqa: SLF001

        renderer._op_set_charspace(None, [])  # noqa: SLF001
        renderer._op_set_wordspace(None, [])  # noqa: SLF001
        renderer._op_set_leading(None, [])  # noqa: SLF001
        renderer._op_set_horizontal_scaling(None, [])  # noqa: SLF001
        renderer._op_set_text_rise(None, [])  # noqa: SLF001
        renderer._op_show_text(None, [])  # noqa: SLF001
        renderer._op_show_text(None, [COSName.get_pdf_name("NotString")])  # noqa: SLF001

        assert renderer._gs.text_charspace == 3.0  # noqa: SLF001
        assert renderer._gs.text_wordspace == 4.0  # noqa: SLF001
        assert renderer._gs.text_leading == 5.0  # noqa: SLF001
        assert renderer._gs.text_horizontal_scaling == 80.0  # noqa: SLF001
        assert renderer._gs.text_rise == 6.0  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_resolve_font_dictionary_factory_none_and_set_font_non_name(
    monkeypatch: Any,
) -> None:
    import pypdfbox.pdmodel.font.pd_font_factory as factory_module

    class _Resources:
        def __init__(self) -> None:
            self.font_dict = COSDictionary()

        def get_font(self, _name: COSName) -> COSDictionary:
            return self.font_dict

    doc, renderer = _prepared_renderer()
    try:
        resources = _Resources()
        renderer._resources = resources  # noqa: SLF001
        monkeypatch.setattr(
            factory_module.PDFontFactory,
            "create_font",
            staticmethod(lambda _font_dict: None),
        )

        assert renderer._resolve_font(COSName.get_pdf_name("F1")) is None  # noqa: SLF001
        renderer._gs.text_font = "unchanged"  # noqa: SLF001
        renderer._op_set_font(None, [COSString("F1"), COSFloat(12.0)])  # noqa: SLF001

        assert renderer._gs.text_font == "unchanged"  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_get_ttf_glyph_set_accepts_direct_true_type_font(
    monkeypatch: Any,
) -> None:
    import pypdfbox.pdmodel.font.pd_true_type_font as true_type_module

    class _TT:
        def __init__(self, glyph_set: object) -> None:
            self.glyph_set = glyph_set

        def getGlyphSet(self) -> object:  # noqa: N802
            return self.glyph_set

    class _TTF:
        def __init__(self, glyph_set: object) -> None:
            self._tt = _TT(glyph_set)

    class _TrueTypeFont:
        def __init__(self, ttf: _TTF) -> None:
            self.ttf = ttf

        def _get_true_type_font(self) -> _TTF:
            return self.ttf

    doc, renderer = _prepared_renderer()
    try:
        glyph_set = object()
        ttf = _TTF(glyph_set)
        monkeypatch.setattr(true_type_module, "PDTrueTypeFont", _TrueTypeFont)

        assert renderer._get_ttf_glyph_set(_TrueTypeFont(ttf)) == (ttf, glyph_set)  # noqa: SLF001,E501
    finally:
        _finish(renderer)
        doc.close()
