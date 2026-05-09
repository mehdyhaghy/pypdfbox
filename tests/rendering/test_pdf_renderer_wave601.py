from __future__ import annotations

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.cos import COSFloat, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


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


def _nums(*values: float) -> list[COSFloat]:
    return [COSFloat(value) for value in values]


def test_curve_shorthand_operators_use_current_point_controls() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer.process_operator("v", _nums(2.0, 3.0, 4.0, 5.0))
        assert renderer._subpaths == []  # noqa: SLF001

        renderer.process_operator("m", _nums(1.0, 1.0))
        renderer.process_operator("v", _nums(2.0, 3.0, 4.0, 5.0))
        renderer.process_operator("y", _nums(6.0, 7.0, 8.0, 9.0))

        assert renderer._current_point == (8.0, 9.0)  # noqa: SLF001
        assert renderer._subpaths == [  # noqa: SLF001
            [
                ("M", 1.0, 1.0),
                ("C", 1.0, 1.0, 2.0, 3.0, 4.0, 5.0),
                ("C", 6.0, 7.0, 8.0, 9.0, 8.0, 9.0),
            ]
        ]
    finally:
        _finish(renderer)
        doc.close()


def test_rect_starts_new_subpath_and_close_resets_current_point() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer.process_operator("m", _nums(1.0, 2.0))
        renderer.process_operator("l", _nums(2.0, 3.0))
        renderer.process_operator("h", [])
        assert renderer._current_point == (1.0, 2.0)  # noqa: SLF001

        renderer.process_operator("re", _nums(3.0, 4.0, 2.0, 1.0))

        assert renderer._current_point == (3.0, 4.0)  # noqa: SLF001
        assert renderer._subpaths[-1] == [  # noqa: SLF001
            ("M", 3.0, 4.0),
            ("L", 5.0, 4.0),
            ("L", 5.0, 5.0),
            ("L", 3.0, 5.0),
            ("Z",),
        ]
    finally:
        _finish(renderer)
        doc.close()


def test_color_and_line_width_operators_ignore_short_inputs_and_clamp() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.stroke_rgb = (10, 20, 30)  # noqa: SLF001
        renderer._gs.fill_rgb = (40, 50, 60)  # noqa: SLF001

        renderer.process_operator("RG", _nums(0.1, 0.2))
        renderer.process_operator("rg", _nums(2.0, -1.0, 0.5))
        renderer.process_operator("G", _nums(0.25))
        renderer.process_operator("g", [])
        renderer.process_operator("K", _nums(0.0, 1.0, 1.0, 0.0))
        renderer.process_operator("k", _nums(0.0, 0.0, 0.0, 0.5))
        renderer.process_operator("w", _nums(-7.0))

        assert renderer._gs.stroke_rgb == (255, 0, 0)  # noqa: SLF001
        assert renderer._gs.fill_rgb == (128, 128, 128)  # noqa: SLF001
        assert renderer._gs.line_width == 0.0  # noqa: SLF001

        renderer.process_operator("w", _nums(2.25))
        assert renderer._gs.line_width == 2.25  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_color_space_operators_clear_pattern_paints_for_non_pattern_spaces() -> None:
    doc, renderer = _prepared_renderer()
    try:
        stroke_pattern = object()
        fill_pattern = object()
        renderer._gs.stroke_pattern = stroke_pattern  # noqa: SLF001
        renderer._gs.fill_pattern = fill_pattern  # noqa: SLF001

        renderer.process_operator("CS", [COSName.get_pdf_name("Pattern")])
        renderer.process_operator("cs", [COSName.get_pdf_name("Pattern")])
        assert renderer._gs.stroke_pattern is stroke_pattern  # noqa: SLF001
        assert renderer._gs.fill_pattern is fill_pattern  # noqa: SLF001

        renderer.process_operator("CS", [COSName.get_pdf_name("DeviceRGB")])
        renderer.process_operator("cs", [])
        assert renderer._gs.stroke_pattern is None  # noqa: SLF001
        assert renderer._gs.fill_pattern is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()
