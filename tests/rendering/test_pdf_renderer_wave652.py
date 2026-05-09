from __future__ import annotations

from typing import Any

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.cos import COSFloat, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.common.function import PDFunction
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(
    width: float = 6.0,
    height: float = 6.0,
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(
    size: tuple[int, int] = (6, 6),
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


class _Coords:
    def __init__(self, *values: float) -> None:
        self._values = values

    def size(self) -> int:
        return len(self._values)

    def get_object(self, index: int) -> COSFloat:
        return COSFloat(self._values[index])


class _Domain:
    def __init__(self, *values: float) -> None:
        self._values = values

    def to_float_array(self) -> list[float]:
        return list(self._values)


class _EvalFunction:
    def __init__(self, output: list[float] | None = None) -> None:
        self._output = [0.0, 1.0, 0.0] if output is None else output

    def eval(self, _values: list[float]) -> list[float]:
        return self._output


class _RaisesEval:
    def eval(self, _values: list[float]) -> list[float]:
        raise RuntimeError("cannot evaluate")


class _Shading:
    def __init__(
        self,
        *,
        function: Any = None,
        coords: _Coords | None = None,
        domain: _Domain | None = None,
        extend: tuple[bool, bool] | None = None,
        color_space: COSName | None = None,
        raise_function: bool = False,
        raise_color_space: bool = False,
    ) -> None:
        self._function = _EvalFunction() if function is None else function
        self._coords = coords
        self._domain = domain
        self._extend = extend
        self._color_space = color_space or COSName.get_pdf_name("DeviceRGB")
        self._raise_function = raise_function
        self._raise_color_space = raise_color_space

    def get_function(self) -> Any:
        if self._raise_function:
            raise RuntimeError("no function")
        return self._function

    def get_color_space(self) -> COSName:
        if self._raise_color_space:
            raise RuntimeError("no color space")
        return self._color_space

    def get_coords(self) -> _Coords | None:
        return self._coords

    def get_domain(self) -> _Domain | None:
        return self._domain

    def get_extend(self) -> tuple[bool, bool] | None:
        return self._extend


def test_evaluate_shading_rgb_returns_none_for_malformed_functions(
    monkeypatch: Any,
) -> None:
    doc, renderer = _prepared_renderer()
    try:
        assert renderer._evaluate_shading_rgb(  # noqa: SLF001
            _Shading(raise_function=True),
            0.5,
        ) is None

        def raise_create(_function: Any) -> PDFunction:
            raise RuntimeError("factory failed")

        monkeypatch.setattr(PDFunction, "create", staticmethod(raise_create))
        assert renderer._evaluate_shading_rgb(  # noqa: SLF001
            _Shading(function=object()),
            0.5,
        ) is None

        monkeypatch.setattr(PDFunction, "create", staticmethod(lambda _fn: None))
        assert renderer._evaluate_shading_rgb(  # noqa: SLF001
            _Shading(function=object()),
            0.5,
        ) is None

        assert renderer._evaluate_shading_rgb(  # noqa: SLF001
            _Shading(function=_RaisesEval()),
            0.5,
        ) is None
        assert renderer._evaluate_shading_rgb(  # noqa: SLF001
            _Shading(function=_EvalFunction([])),
            0.5,
        ) is None
        assert renderer._evaluate_shading_rgb(  # noqa: SLF001
            _Shading(
                function=_EvalFunction([0.25, 0.5, 0.75]),
                raise_color_space=True,
            ),
            0.5,
        ) == (0.25, 0.5, 0.75)
    finally:
        _finish(renderer)
        doc.close()


def test_unknown_shading_uses_fallback_function_or_skips_when_missing() -> None:
    doc, renderer = _prepared_renderer()
    try:
        mask = Image.new("L", (6, 6), 255)
        renderer._paint_shading(_Shading(function=_EvalFunction([0.0, 1.0, 0.0])), region_mask=mask)  # noqa: E501, SLF001

        _finish(renderer)
        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((2, 2)) == (0, 255, 0)  # noqa: SLF001

        before = renderer._image.copy()  # noqa: SLF001
        renderer._paint_shading(_Shading(raise_function=True), region_mask=mask)  # noqa: SLF001
        _finish(renderer)
        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.tobytes() == before.tobytes()  # noqa: SLF001

        renderer._image = None  # noqa: SLF001
        renderer._paint_shading(_Shading(), region_mask=mask)  # noqa: SLF001
    finally:
        renderer._draw = None  # noqa: SLF001
        doc.close()


def test_axial_shading_ignores_unpaintable_inputs() -> None:
    doc, renderer = _prepared_renderer()
    try:
        mask = Image.new("L", (6, 6), 255)

        renderer._image = None  # noqa: SLF001
        renderer._paint_axial_shading(_Shading(), region_mask=mask)  # noqa: SLF001

        renderer._image = Image.new("RGB", (6, 6), (255, 255, 255))  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        renderer._paint_axial_shading(_Shading(coords=_Coords(0.0, 0.0)), region_mask=mask)  # noqa: E501, SLF001
        renderer._paint_axial_shading(  # noqa: SLF001
            _Shading(coords=_Coords(1.0, 1.0, 1.0, 1.0)),
            region_mask=mask,
        )

        renderer._device_ctm = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)  # noqa: SLF001
        renderer._paint_axial_shading(  # noqa: SLF001
            _Shading(coords=_Coords(0.0, 0.0, 5.0, 0.0)),
            region_mask=mask,
        )

        _finish(renderer)
        assert renderer._image.getpixel((3, 3)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_radial_shading_respects_masks_and_extend_flags() -> None:
    doc, renderer = _prepared_renderer(size=(5, 1))
    try:
        coords = _Coords(0.0, 0.0, 1.0, 0.0, 0.0, 2.0)
        function = _EvalFunction([1.0, 0.0, 0.0])

        mask = Image.new("L", (5, 1), 255)
        mask.putpixel((0, 0), 0)
        renderer._paint_radial_shading(  # noqa: SLF001
            _Shading(coords=coords, function=function, extend=(False, False)),
            region_mask=mask,
        )
        _finish(renderer)
        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)  # noqa: SLF001
        assert renderer._image.getpixel((4, 0)) == (255, 255, 255)  # noqa: SLF001

        renderer._image = Image.new("RGB", (5, 1), (255, 255, 255))  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        renderer._draw.setantialias(True)  # noqa: SLF001
        renderer._paint_radial_shading(  # noqa: SLF001
            _Shading(coords=coords, function=function, extend=(True, True)),
            region_mask=Image.new("L", (5, 1), 255),
        )
        _finish(renderer)
        assert renderer._image.getpixel((4, 0)) == (255, 0, 0)  # noqa: SLF001
    finally:
        doc.close()


def test_text_state_operators_ignore_incomplete_operands() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.text_charspace = 1.0  # noqa: SLF001
        renderer._gs.text_wordspace = 2.0  # noqa: SLF001
        renderer._gs.text_leading = 3.0  # noqa: SLF001
        renderer._gs.text_horizontal_scaling = 90.0  # noqa: SLF001
        renderer._gs.text_rise = 4.0  # noqa: SLF001

        renderer._op_set_font(None, [])  # noqa: SLF001
        renderer._op_set_font(None, [COSFloat(12.0), COSFloat(9.0)])  # noqa: SLF001
        renderer._op_set_charspace(None, [])  # noqa: SLF001
        renderer._op_set_wordspace(None, [])  # noqa: SLF001
        renderer._op_set_leading(None, [])  # noqa: SLF001
        renderer._op_set_horizontal_scaling(None, [])  # noqa: SLF001
        renderer._op_set_text_rise(None, [])  # noqa: SLF001
        renderer._op_show_text(None, [])  # noqa: SLF001

        assert renderer._gs.text_font is None  # noqa: SLF001
        assert renderer._gs.text_charspace == 1.0  # noqa: SLF001
        assert renderer._gs.text_wordspace == 2.0  # noqa: SLF001
        assert renderer._gs.text_leading == 3.0  # noqa: SLF001
        assert renderer._gs.text_horizontal_scaling == 90.0  # noqa: SLF001
        assert renderer._gs.text_rise == 4.0  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_resolve_font_handles_absent_failing_and_missing_resources() -> None:
    class RaisingResources:
        def get_font(self, _name: COSName) -> Any:
            raise RuntimeError("font lookup failed")

    class EmptyResources:
        def get_font(self, _name: COSName) -> None:
            return None

    doc, renderer = _prepared_renderer()
    try:
        name = COSName.get_pdf_name("F1")

        renderer._resources = None  # noqa: SLF001
        assert renderer._resolve_font(name) is None  # noqa: SLF001

        renderer._resources = RaisingResources()  # noqa: SLF001
        assert renderer._resolve_font(name) is None  # noqa: SLF001

        renderer._resources = EmptyResources()  # noqa: SLF001
        assert renderer._resolve_font(name) is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_inline_image_paths_ignore_missing_canvas_and_decode_none(
    monkeypatch: Any,
) -> None:
    class InlineImage:
        def to_pil_image(self) -> None:
            return None

        def get_cos_object(self) -> Any:
            return object()

        def get_stream(self) -> bytes:
            return b""

    doc, renderer = _prepared_renderer()
    try:
        renderer._image = None  # noqa: SLF001
        renderer._op_inline_image(None, [])  # noqa: SLF001

        renderer._image = Image.new("RGB", (6, 6), (255, 255, 255))  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        monkeypatch.setattr(renderer, "_decode_inline_image", lambda *_: None)

        renderer.show_inline_image(InlineImage())
        _finish(renderer)

        assert renderer._image.getpixel((3, 3)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()
