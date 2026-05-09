from __future__ import annotations

from typing import Any

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(
    width: float = 5.0,
    height: float = 5.0,
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(
    size: tuple[int, int] = (5, 5),
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


def test_resource_dependent_operators_skip_without_render_context() -> None:
    doc, _page = _make_doc()
    renderer = PDFRenderer(doc)
    renderer._gs_stack = [_GState()]  # noqa: SLF001
    try:
        pattern_name = COSName.get_pdf_name("P0")

        renderer.process_operator("SCN", [pattern_name])
        renderer.process_operator("gs", [COSName.get_pdf_name("GS0")])
        renderer.process_operator("sh", [COSName.get_pdf_name("Sh0")])

        assert renderer._gs.stroke_pattern is None  # noqa: SLF001
        assert renderer._gs.blend_mode is None  # noqa: SLF001
    finally:
        doc.close()


def test_fill_then_stroke_dispatch_uses_non_even_odd_paint(
    monkeypatch: Any,
) -> None:
    doc, renderer = _prepared_renderer()
    calls: list[dict[str, bool]] = []
    try:
        monkeypatch.setattr(renderer, "_paint", lambda **kwargs: calls.append(kwargs))

        renderer.process_operator("B", [])

        assert calls == [{"stroke": True, "fill": True, "even_odd": False}]
    finally:
        _finish(renderer)
        doc.close()


def test_even_odd_fill_with_stroke_runs_stroke_after_pil_fill(
    monkeypatch: Any,
) -> None:
    doc, renderer = _prepared_renderer()
    calls: list[str] = []
    try:
        renderer._subpaths = [  # noqa: SLF001
            [("M", 1.0, 1.0), ("L", 4.0, 1.0), ("L", 4.0, 4.0), ("Z",)]
        ]
        renderer._current_subpath = renderer._subpaths[0]  # noqa: SLF001
        monkeypatch.setattr(
            renderer, "_fill_even_odd_via_pil", lambda: calls.append("fill")
        )
        monkeypatch.setattr(
            renderer, "_stroke_via_aggdraw", lambda: calls.append("stroke")
        )

        renderer._paint(stroke=True, fill=True, even_odd=True)  # noqa: SLF001

        assert calls == ["fill", "stroke"]
        assert renderer._subpaths == []  # noqa: SLF001
        assert renderer._current_subpath is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()
