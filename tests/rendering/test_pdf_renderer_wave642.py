from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _AggdrawPathPen, _GState


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


def test_close_open_subpath_is_noop_without_current_subpath() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._current_subpath = None  # noqa: SLF001
        renderer._subpaths = []  # noqa: SLF001

        renderer._close_open_subpath()  # noqa: SLF001

        assert renderer._subpaths == []  # noqa: SLF001
        assert renderer._current_subpath is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_build_path_mask_returns_none_without_active_image() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._image = None  # noqa: SLF001

        assert renderer._build_path_mask(even_odd=False) is None  # noqa: SLF001
    finally:
        renderer._draw = None  # noqa: SLF001
        doc.close()


def test_pattern_fill_returns_for_absent_pattern_or_degenerate_mask(
    monkeypatch: Any,
) -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.fill_pattern = None  # noqa: SLF001
        renderer._paint_pattern_fill(even_odd=False)  # noqa: SLF001

        renderer._gs.fill_pattern = object()  # noqa: SLF001
        monkeypatch.setattr(renderer, "_build_path_mask", lambda *, even_odd: None)

        renderer._paint_pattern_fill(even_odd=True)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_aggdraw_pen_curve_to_records_complete_cubic_segment() -> None:
    pen = _AggdrawPathPen(scale=0.5)

    pen.curveTo((2.0, 4.0), (6.0, 8.0), (10.0, 12.0))

    assert pen.has_segments is True
    assert pen._last == (5.0, 6.0)  # noqa: SLF001
