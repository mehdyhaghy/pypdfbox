from __future__ import annotations

from typing import Any

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.common.function import PDFunction
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


class _Box:
    def __init__(self, width: float = 1.0, height: float = 1.0) -> None:
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


class _Pattern:
    def __init__(
        self,
        *,
        bbox: _Box | None = None,
        x_step: float = 1.0,
        y_step: float = 1.0,
    ) -> None:
        self._bbox = bbox if bbox is not None else _Box()
        self._x_step = x_step
        self._y_step = y_step

    def get_b_box(self) -> _Box | None:
        return self._bbox

    def get_x_step(self) -> float:
        return self._x_step

    def get_y_step(self) -> float:
        return self._y_step


class _EvalFunction:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def eval(self, _inputs: list[float]) -> list[float]:
        return self._values


class _Shading:
    def __init__(self, function: Any, color_space: COSName | None = None) -> None:
        self._function = function
        self._color_space = color_space

    def get_function(self) -> Any:
        return self._function

    def get_color_space(self) -> COSName | None:
        return self._color_space


def test_ext_gstate_defensive_paths_and_alpha_clamping() -> None:
    class _ExtGState:
        def get_blend_mode(self) -> Any:
            raise RuntimeError("blend mode unavailable")

        def get_soft_mask_typed(self) -> Any:
            raise RuntimeError("soft mask unavailable")

        def get_stroking_alpha_constant(self) -> float:
            return -4.0

        def get_non_stroking_alpha_constant(self) -> float:
            return 4.0

    class _Resources:
        def __init__(self) -> None:
            self.raise_lookup = True
            self.return_none = False

        def get_ext_gstate(self, _name: COSName) -> _ExtGState | None:
            if self.raise_lookup:
                raise RuntimeError("lookup failed")
            if self.return_none:
                return None
            return _ExtGState()

    doc, renderer = _prepared_renderer()
    try:
        renderer._op_set_graphics_state_parameters(None, [])  # noqa: SLF001

        resources = _Resources()
        renderer._resources = resources  # noqa: SLF001
        name = COSName.get_pdf_name("GS0")
        renderer._op_set_graphics_state_parameters(None, [name])  # noqa: SLF001

        resources.raise_lookup = False
        resources.return_none = True
        renderer._op_set_graphics_state_parameters(None, [name])  # noqa: SLF001

        resources.return_none = False
        renderer._gs.stroke_alpha = 0.5  # noqa: SLF001
        renderer._gs.fill_alpha = 0.5  # noqa: SLF001
        renderer._op_set_graphics_state_parameters(None, [name])  # noqa: SLF001

        assert renderer._gs.blend_mode is None  # noqa: SLF001
        assert renderer._gs.soft_mask is None  # noqa: SLF001
        assert renderer._gs.stroke_alpha == 0.0  # noqa: SLF001
        assert renderer._gs.fill_alpha == 1.0  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_even_odd_fill_skips_degenerate_subpaths_and_paints_rgba() -> None:
    doc, renderer = _prepared_renderer(size=(3, 3))
    try:
        renderer._image = Image.new("RGBA", (3, 3), (0, 0, 0, 0))  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        renderer._gs.fill_rgb = (10, 20, 30)  # noqa: SLF001
        renderer._subpaths = [  # noqa: SLF001
            [("M", 0.0, 0.0), ("L", 1.0, 0.0)],
            [
                ("M", 0.0, 0.0),
                ("L", 2.0, 0.0),
                ("L", 2.0, 2.0),
                ("Z",),
            ],
        ]

        renderer._fill_even_odd_via_pil()  # noqa: SLF001
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((1, 1)) == (10, 20, 30, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_tiling_pattern_early_returns_and_cell_failures(
    monkeypatch: Any,
) -> None:
    doc, renderer = _prepared_renderer()
    try:
        mask = Image.new("L", (4, 4), 255)
        renderer._image = None  # noqa: SLF001
        renderer._paint_tiling_pattern(_Pattern(), region_mask=mask)  # noqa: SLF001

        renderer._image = Image.new("RGB", (4, 4), (255, 255, 255))  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        renderer._paint_tiling_pattern(  # noqa: SLF001
            _Pattern(bbox=None),
            region_mask=mask,
        )
        renderer._paint_tiling_pattern(  # noqa: SLF001
            _Pattern(bbox=_Box(width=0.0)),
            region_mask=mask,
        )

        monkeypatch.setattr(
            renderer,
            "_render_tiling_cell",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("cell failed")
            ),
        )
        renderer._paint_tiling_pattern(_Pattern(), region_mask=mask)  # noqa: SLF001

        monkeypatch.setattr(
            renderer,
            "_render_tiling_cell",
            lambda *_args, **_kwargs: None,
        )
        renderer._paint_tiling_pattern(_Pattern(), region_mask=mask)  # noqa: SLF001

        _finish(renderer)
        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((2, 2)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_evaluate_shading_rgb_factory_success_and_color_space_fallback(
    monkeypatch: Any,
) -> None:
    doc, renderer = _prepared_renderer()
    try:
        monkeypatch.setattr(
            PDFunction,
            "create",
            staticmethod(lambda _fn: _EvalFunction([0.25])),
        )
        assert renderer._evaluate_shading_rgb(  # noqa: SLF001
            _Shading(object(), COSName.get_pdf_name("DeviceGray")),
            0.5,
        ) == (0.25, 0.25, 0.25)

        assert renderer._evaluate_shading_rgb(  # noqa: SLF001
            _Shading(
                _EvalFunction([0.25, 0.5, 0.0, 0.25]),
                COSName.get_pdf_name("DeviceCMYK"),
            ),
            0.5,
        ) == (0.5625, 0.375, 0.75)

        assert renderer._evaluate_shading_rgb(  # noqa: SLF001
            _Shading(_EvalFunction([0.5]), None),
            0.5,
        ) == (0.5, 0.5, 0.5)
    finally:
        _finish(renderer)
        doc.close()
