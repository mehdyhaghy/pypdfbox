from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.fontbox.font_mappers import FontMappers
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import (
    PDFRenderer,
    _AggdrawPathPen,
    _GState,
)


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


class _Domain:
    def __init__(self, *values: float) -> None:
        self._values = values

    def to_float_array(self) -> list[float]:
        return list(self._values)


class _Matrix:
    def __init__(self, *values: float) -> None:
        self._values = values

    def to_float_array(self) -> list[float]:
        return list(self._values)


class _FunctionShading:
    def __init__(
        self,
        *,
        domain: _Domain,
        matrix: _Matrix | None = None,
    ) -> None:
        self._domain = domain
        self._matrix = matrix

    def get_domain(self) -> _Domain:
        return self._domain

    def get_matrix(self) -> _Matrix | None:
        return self._matrix

    def get_function(self) -> None:
        return None


def test_function_shading_ignores_missing_canvas_bad_domain_and_singular_ctm() -> None:
    doc, renderer = _prepared_renderer()
    try:
        mask = Image.new("L", (6, 6), 255)

        renderer._image = None  # noqa: SLF001
        renderer._paint_function_shading(  # noqa: SLF001
            _FunctionShading(domain=_Domain(0.0, 1.0, 0.0, 1.0)),
            region_mask=mask,
        )

        renderer._image = Image.new("RGB", (6, 6), (255, 255, 255))  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        renderer._paint_function_shading(  # noqa: SLF001
            _FunctionShading(domain=_Domain(1.0, 0.0, 0.0, 1.0)),
            region_mask=mask,
        )
        renderer._paint_function_shading(  # noqa: SLF001
            _FunctionShading(
                domain=_Domain(0.0, 1.0, 0.0, 1.0),
                matrix=_Matrix(1.0, 2.0, 2.0, 4.0, 0.0, 0.0),
            ),
            region_mask=mask,
        )

        renderer._device_ctm = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)  # noqa: SLF001
        renderer._paint_function_shading(  # noqa: SLF001
            _FunctionShading(domain=_Domain(0.0, 1.0, 0.0, 1.0)),
            region_mask=mask,
        )

        _finish(renderer)
        assert renderer._image.getpixel((3, 3)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_resolve_font_program_handles_mapper_failure_and_caches_none(
    monkeypatch: Any,
) -> None:
    class Font:
        def get_name(self) -> str:
            return "BrokenFont"

        def get_font_descriptor(self) -> None:
            return None

    def raise_instance() -> Any:
        raise RuntimeError("mapper unavailable")

    doc, renderer = _prepared_renderer()
    try:
        monkeypatch.setattr(FontMappers, "instance", raise_instance)
        font = Font()

        assert renderer._resolve_font_program(font) is None  # noqa: SLF001
        assert id(font) in renderer._font_program_cache  # noqa: SLF001
        assert renderer._resolve_font_program(font) is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_draw_glyph_type1_path_failures_and_placeholder_width_fallback(
    monkeypatch: Any,
) -> None:
    class Type1LikeFont:
        def get_glyph_path(self, _code: int) -> list[tuple[str, float, float]]:
            return [("moveto", 0.0, 0.0), ("lineto", 100.0, 0.0)]

        def get_glyph_width(self, _code: int) -> float:
            return 321.0

    class WidthlessFont:
        pass

    doc, renderer = _prepared_renderer()
    try:
        monkeypatch.setattr(
            PDFRenderer,
            "_build_aggdraw_path_from_commands",
            staticmethod(
                lambda _commands, _scale: (_ for _ in ()).throw(
                    RuntimeError("bad outline")
                )
            ),
        )
        assert renderer._draw_glyph(  # noqa: SLF001
            Type1LikeFont(),
            65,
            None,
            None,
            type1_units_per_em=1000,
        ) == 321.0

        monkeypatch.setattr(
            PDFRenderer,
            "_font_width_units",
            staticmethod(
                lambda _font, _code: (_ for _ in ()).throw(
                    RuntimeError("width failed")
                )
            ),
        )
        monkeypatch.setattr(renderer, "_resolve_font_program", lambda _font: None)
        monkeypatch.setattr(renderer, "_maybe_warn_standard14", lambda _font: None)

        assert renderer._draw_glyph(WidthlessFont(), 65, None, None) == 500.0  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_placeholder_and_pen_empty_paths_are_noops() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._draw = None  # noqa: SLF001
        renderer._draw_placeholder_box(  # noqa: SLF001
            (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            500.0,
        )

        assert PDFRenderer._build_aggdraw_path_from_commands(  # noqa: SLF001
            [("moveto", 10.0, 20.0)],
            scale=1.0,
        ) is None

        pen = _AggdrawPathPen(scale=1.0)
        pen.qCurveTo((10.0, 10.0))
        assert not pen.has_segments
    finally:
        doc.close()
