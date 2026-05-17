from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSFloat, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import _GState


def _make_doc(width: float = 10.0, height: float = 10.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (10, 10)) -> tuple[PDDocument, PDFRenderer]:
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


def test_gray_and_cmyk_color_operators_update_stroke_and_fill() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer.process_operator("G", [COSFloat(0.25)])
        renderer.process_operator("g", [COSFloat(0.75)])
        renderer.process_operator(
            "K",
            [COSFloat(0.0), COSFloat(1.0), COSFloat(0.0), COSFloat(0.5)],
        )
        renderer.process_operator(
            "k",
            [COSFloat(1.0), COSFloat(0.0), COSFloat(1.0), COSFloat(0.25)],
        )

        assert renderer._gs.stroke_rgb == (128, 0, 128)
        assert renderer._gs.fill_rgb == (0, 191, 0)
    finally:
        _finish(renderer)
        doc.close()


def test_curve_shortcuts_append_expected_control_points() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer.process_operator("m", [COSFloat(1.0), COSFloat(2.0)])
        renderer.process_operator(
            "v",
            [COSFloat(3.0), COSFloat(4.0), COSFloat(5.0), COSFloat(6.0)],
        )
        renderer.process_operator(
            "y",
            [COSFloat(7.0), COSFloat(8.0), COSFloat(9.0), COSFloat(10.0)],
        )

        assert renderer._subpaths == [
            [
                ("M", 1.0, 2.0),
                ("C", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
                ("C", 7.0, 8.0, 9.0, 10.0, 9.0, 10.0),
            ]
        ]
        assert renderer._current_point == (9.0, 10.0)
    finally:
        _finish(renderer)
        doc.close()


def test_compound_paint_operators_close_path_before_painting(monkeypatch: Any) -> None:
    doc, renderer = _prepared_renderer()
    calls: list[tuple[bool, bool, bool, tuple[Any, ...]]] = []
    try:
        monkeypatch.setattr(
            renderer,
            "_paint",
            lambda *, stroke, fill, even_odd: calls.append(
                (stroke, fill, even_odd, tuple(renderer._current_subpath or ()))
            ),
        )

        renderer.process_operator("m", [COSFloat(0.0), COSFloat(0.0)])
        renderer.process_operator("s", [])
        renderer.process_operator("m", [COSFloat(1.0), COSFloat(1.0)])
        renderer.process_operator("b", [])
        renderer.process_operator("m", [COSFloat(2.0), COSFloat(2.0)])
        renderer.process_operator("b*", [])

        assert calls == [
            (True, False, False, (("M", 0.0, 0.0), ("Z",))),
            (True, True, False, (("M", 1.0, 1.0), ("Z",))),
            (True, True, True, (("M", 2.0, 2.0), ("Z",))),
        ]
    finally:
        _finish(renderer)
        doc.close()


def test_shading_fill_defensive_paths_do_not_paint(monkeypatch: Any) -> None:
    class _MissingResources:
        def get_shading(self, _name: COSName) -> None:
            return None

    doc, renderer = _prepared_renderer()
    calls: list[object] = []
    try:
        monkeypatch.setattr(
            renderer,
            "_paint_shading",
            lambda shading, *, region_mask: calls.append((shading, region_mask)),
        )

        renderer.process_operator("sh", [])
        renderer.process_operator("sh", [COSFloat(1.0)])
        renderer._resources = None
        renderer.process_operator("sh", [COSName.get_pdf_name("Shade")])
        renderer._resources = _MissingResources()
        renderer.process_operator("sh", [COSName.get_pdf_name("Shade")])

        assert calls == []
    finally:
        _finish(renderer)
        doc.close()
