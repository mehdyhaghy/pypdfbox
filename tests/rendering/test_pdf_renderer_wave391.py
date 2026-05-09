from __future__ import annotations

import logging
import math
from typing import Any

import aggdraw  # type: ignore[import-not-found]
import pytest
from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import (
    _cmyk_to_rgb_bytes,
    _GState,
    _require_positive_finite,
    _rgb_bytes,
)


def _make_doc(width: float = 24.0, height: float = 24.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (24, 24)) -> tuple[PDDocument, PDFRenderer]:
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


def test_numeric_colour_helpers_clamp_and_reject_bad_dimensions() -> None:
    assert _require_positive_finite(2, "scale") == 2.0
    for value in (0.0, -1.0, math.inf, math.nan):
        with pytest.raises(ValueError, match="dpi must be a positive finite number"):
            _require_positive_finite(value, "dpi")

    assert _rgb_bytes(-0.5, 0.5, 2.0) == (0, 128, 255)
    assert _cmyk_to_rgb_bytes(1.0, 0.0, 0.0, 0.0) == (0, 255, 255)
    assert _cmyk_to_rgb_bytes(0.0, 1.0, 0.0, 0.5) == (128, 0, 128)


def test_color_space_ops_reset_only_non_pattern_paints() -> None:
    doc, renderer = _prepared_renderer()
    try:
        fill_pattern = object()
        stroke_pattern = object()
        renderer._gs.fill_pattern = fill_pattern  # noqa: SLF001
        renderer._gs.stroke_pattern = stroke_pattern  # noqa: SLF001

        renderer.process_operator("cs", [COSName.get_pdf_name("Pattern")])
        renderer.process_operator("CS", [COSName.get_pdf_name("Pattern")])
        assert renderer._gs.fill_pattern is fill_pattern  # noqa: SLF001
        assert renderer._gs.stroke_pattern is stroke_pattern  # noqa: SLF001

        renderer.process_operator("cs", [COSName.get_pdf_name("DeviceRGB")])
        renderer.process_operator("CS", [])
        assert renderer._gs.fill_pattern is None  # noqa: SLF001
        assert renderer._gs.stroke_pattern is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_degenerate_paths_do_not_build_masks_or_draw() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer.process_operator("m", [])
        renderer._current_subpath = []  # noqa: SLF001
        renderer._close_open_subpath()  # noqa: SLF001
        assert renderer._current_subpath == []  # noqa: SLF001

        renderer.process_operator("m", [COSName.get_pdf_name("Bad"), COSName.get_pdf_name("Bad")])
        renderer.process_operator("l", [COSName.get_pdf_name("Bad"), COSName.get_pdf_name("Bad")])
        assert renderer._build_path_mask(even_odd=False) is None  # noqa: SLF001
        assert renderer._build_path_mask(even_odd=True) is None  # noqa: SLF001

        before = renderer._image.copy()  # noqa: SLF001
        renderer._subpaths = [[("Z",)]]  # noqa: SLF001
        renderer._draw_via_aggdraw(stroke=True, fill=True)  # noqa: SLF001
        _finish(renderer)
        assert renderer._image.tobytes() == before.tobytes()  # noqa: SLF001
    finally:
        doc.close()


def test_unsupported_pattern_fill_falls_back_through_current_clip(caplog: Any) -> None:
    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        clip = Image.new("L", (24, 24), 0)
        clip.paste(255, (0, 0, 12, 24))
        renderer._gs.clip_mask = clip  # noqa: SLF001
        renderer._gs.fill_pattern = object()  # noqa: SLF001
        renderer._gs.fill_rgb = (0, 0, 255)  # noqa: SLF001
        renderer.process_operator("re", [COSName.get_pdf_name("Bad")] * 4)
        renderer._subpaths = [[("M", 0.0, 0.0), ("L", 24.0, 0.0), ("L", 24.0, 24.0), ("L", 0.0, 24.0), ("Z",)]]  # noqa: E501, SLF001

        renderer._paint_pattern_fill(even_odd=False)  # noqa: SLF001
        _finish(renderer)

        assert "unsupported pattern type object" in caplog.text
        assert renderer._image.getpixel((6, 12)) == (0, 0, 255)  # noqa: SLF001
        assert renderer._image.getpixel((18, 12)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_tiling_pattern_invalid_metadata_and_render_failure_are_debug_logged(
    caplog: Any,
) -> None:
    class _Pattern:
        def __init__(self, bbox: Any, x_step: float, y_step: float) -> None:
            self._bbox = bbox
            self._x_step = x_step
            self._y_step = y_step

        def get_b_box(self) -> Any:
            return self._bbox

        def get_x_step(self) -> float:
            return self._x_step

        def get_y_step(self) -> float:
            return self._y_step

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        mask = Image.new("L", (24, 24), 255)

        renderer._paint_tiling_pattern(  # noqa: SLF001
            _Pattern(None, 4.0, 4.0), region_mask=mask
        )
        assert "tiling pattern missing /BBox or /XStep/YStep" in caplog.text

        renderer._paint_tiling_pattern(  # noqa: SLF001
            _Pattern(PDRectangle(0.0, 0.0, 4.0, 4.0), 4.0, 4.0),
            region_mask=mask,
        )
        assert "tiling pattern cell render failed" in caplog.text
    finally:
        _finish(renderer)
        doc.close()


def test_unknown_shading_type_falls_back_to_function_value(caplog: Any) -> None:
    class _Function:
        def eval(self, _inputs: list[float]) -> list[float]:
            return [0.25]

    class _Shading:
        def get_function(self) -> _Function:
            return _Function()

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceGray")

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        mask = Image.new("L", (24, 24), 0)
        mask.paste(255, (4, 4, 20, 20))

        renderer._paint_shading(_Shading(), region_mask=mask)  # noqa: SLF001
        _finish(renderer)

        assert "unsupported shading type _Shading" in caplog.text
        assert renderer._image.getpixel((8, 8)) == (64, 64, 64)  # noqa: SLF001
        assert renderer._image.getpixel((2, 2)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()
