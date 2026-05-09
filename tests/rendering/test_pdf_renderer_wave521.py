from __future__ import annotations

import logging
from typing import Any

import aggdraw  # type: ignore[import-not-found]
import pytest
from PIL import Image

from pypdfbox.cos import COSFloat
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _GState


def _make_doc(width: float = 6.0, height: float = 6.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (6, 6)) -> tuple[PDDocument, PDFRenderer]:
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


def test_render_setup_uses_media_box_origin_in_device_ctm(monkeypatch: Any) -> None:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle.from_xywh(10.0, 20.0, 4.0, 5.0))
    doc.add_page(page)
    renderer = PDFRenderer(doc)
    captured: dict[str, object] = {}

    def _capture_page(processed_page: PDPage) -> None:
        captured["page"] = processed_page
        captured["ctm"] = renderer._device_ctm  # noqa: SLF001
        captured["size"] = renderer._image.size  # noqa: SLF001

    try:
        monkeypatch.setattr(renderer, "process_page", _capture_page)

        image = renderer.render_image_with_dpi(0, dpi=72.0)

        processed_page = captured["page"]
        assert isinstance(processed_page, PDPage)
        assert processed_page.get_media_box().get_lower_left_x() == 10.0
        assert processed_page.get_media_box().get_lower_left_y() == 20.0
        assert captured["size"] == (4, 5)
        assert captured["ctm"] == (1.0, 0.0, 0.0, -1.0, -10.0, 25.0)
        assert image.size == (4, 5)
    finally:
        doc.close()


def test_render_failure_clears_live_canvas_without_caching_page(
    monkeypatch: Any,
) -> None:
    doc, _page = _make_doc()
    renderer = PDFRenderer(doc)

    def _raise_page(_page: PDPage) -> None:
        assert renderer._image is not None  # noqa: SLF001
        assert renderer._draw is not None  # noqa: SLF001
        raise RuntimeError("render boom")

    try:
        monkeypatch.setattr(renderer, "process_page", _raise_page)

        with pytest.raises(RuntimeError, match="render boom"):
            renderer.render_image(0)

        assert renderer._image is None  # noqa: SLF001
        assert renderer._draw is None  # noqa: SLF001
        assert renderer.get_page_image() is None
    finally:
        doc.close()


def test_unknown_pattern_fill_combines_path_mask_with_existing_clip() -> None:
    doc, renderer = _prepared_renderer((5, 5))
    try:
        clip = Image.new("L", (5, 5), 0)
        clip.paste(255, (2, 2, 5, 5))
        renderer._gs.clip_mask = clip  # noqa: SLF001
        renderer._gs.fill_pattern = object()  # noqa: SLF001
        renderer._gs.fill_rgb = (20, 40, 60)  # noqa: SLF001
        renderer._subpaths = [  # noqa: SLF001
            [
                ("M", 1.0, 1.0),
                ("L", 4.0, 1.0),
                ("L", 4.0, 4.0),
                ("L", 1.0, 4.0),
                ("Z",),
            ]
        ]

        renderer._paint_pattern_fill(even_odd=False)  # noqa: SLF001
        _finish(renderer)

        assert renderer._image.getpixel((1, 1)) == (255, 255, 255)  # noqa: SLF001
        assert renderer._image.getpixel((3, 3)) == (20, 40, 60)  # noqa: SLF001
        assert renderer._image.getpixel((0, 4)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_tiling_pattern_logs_cell_render_failure_and_leaves_canvas(
    caplog: Any,
    monkeypatch: Any,
) -> None:
    class _Pattern:
        def get_b_box(self) -> PDRectangle:
            return PDRectangle.from_width_height(2.0, 2.0)

        def get_x_step(self) -> float:
            return 2.0

        def get_y_step(self) -> float:
            return 2.0

    def _raise_cell(*_args: object, **_kwargs: object) -> Image.Image:
        raise RuntimeError("tile boom")

    doc, renderer = _prepared_renderer((3, 3))
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        monkeypatch.setattr(renderer, "_render_tiling_cell", _raise_cell)

        renderer._paint_tiling_pattern(  # noqa: SLF001
            _Pattern(),
            region_mask=Image.new("L", (3, 3), 255),
        )
        _finish(renderer)

        assert "tiling pattern cell render failed: tile boom" in caplog.text
        assert renderer._image.getpixel((1, 1)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_line_and_color_operators_ignore_incomplete_operands() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.stroke_rgb = (1, 2, 3)  # noqa: SLF001
        renderer._gs.fill_rgb = (4, 5, 6)  # noqa: SLF001
        renderer._gs.line_width = 7.0  # noqa: SLF001

        renderer.process_operator("RG", [COSFloat(0.0), COSFloat(1.0)])
        renderer.process_operator("rg", [COSFloat(0.0), COSFloat(1.0)])
        renderer.process_operator("K", [COSFloat(0.0), COSFloat(0.0), COSFloat(0.0)])
        renderer.process_operator("k", [COSFloat(0.0), COSFloat(0.0), COSFloat(0.0)])
        renderer.process_operator("w", [])

        assert renderer._gs.stroke_rgb == (1, 2, 3)  # noqa: SLF001
        assert renderer._gs.fill_rgb == (4, 5, 6)  # noqa: SLF001
        assert renderer._gs.line_width == 7.0  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()
