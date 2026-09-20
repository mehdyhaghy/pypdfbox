from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(width: float = 8.0, height: float = 8.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (8, 8)) -> tuple[PDDocument, PDFRenderer]:
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


def test_pattern_fill_with_stroke_without_clip_uses_direct_stroke(
    monkeypatch: Any,
) -> None:
    doc, renderer = _prepared_renderer()
    calls: list[tuple[str, bool | None]] = []
    try:
        renderer._gs.fill_pattern = object()
        renderer._subpaths = [
            [("M", 1.0, 1.0), ("L", 6.0, 1.0), ("L", 6.0, 6.0), ("Z",)]
        ]
        renderer._current_subpath = renderer._subpaths[0]

        def _pattern_fill(*, even_odd: bool) -> None:
            calls.append(("pattern", even_odd))

        def _stroke() -> None:
            calls.append(("stroke", None))

        monkeypatch.setattr(renderer, "_paint_pattern_fill", _pattern_fill)
        monkeypatch.setattr(renderer, "_stroke_via_aggdraw", _stroke)

        renderer._paint(stroke=True, fill=True, even_odd=False)

        assert calls == [("pattern", False), ("stroke", None)]
        assert renderer._subpaths == []
        assert renderer._current_subpath is None
    finally:
        _finish(renderer)
        doc.close()


def test_nonzero_path_mask_unions_multiple_subpaths() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._subpaths = [
            [("M", 1.0, 1.0), ("L", 3.0, 1.0), ("L", 3.0, 3.0), ("Z",)],
            [("M", 5.0, 5.0), ("L", 7.0, 5.0), ("L", 7.0, 7.0), ("Z",)],
        ]

        mask = renderer._build_path_mask(even_odd=False)

        assert mask is not None
        # Wave 1373: edge pixels carry sub-pixel AA (not fully 255). Both
        # triangle interiors still contribute at least half-coverage,
        # and the gap between them remains fully transparent.
        assert mask.getpixel((2, 2)) >= 128
        assert mask.getpixel((6, 6)) >= 128
        assert mask.getpixel((4, 4)) == 0
    finally:
        _finish(renderer)
        doc.close()

