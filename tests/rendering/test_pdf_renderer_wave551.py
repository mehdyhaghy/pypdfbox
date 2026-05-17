from __future__ import annotations

from typing import Any

import pytest
from PIL import Image

from pypdfbox.cos import COSFloat, COSInteger
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


def test_color_and_line_state_operators_ignore_short_operands_and_clamp() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.stroke_rgb = (9, 8, 7)  # noqa: SLF001
        renderer._gs.fill_rgb = (6, 5, 4)  # noqa: SLF001

        renderer.process_operator("RG", [COSFloat(0.1), COSFloat(0.2)])
        renderer.process_operator("rg", [COSFloat(0.1), COSFloat(0.2)])
        renderer.process_operator("G", [])
        renderer.process_operator("g", [])
        renderer.process_operator("K", [COSFloat(0.0), COSFloat(0.0)])
        renderer.process_operator("k", [COSFloat(0.0), COSFloat(0.0)])
        assert renderer._gs.stroke_rgb == (9, 8, 7)  # noqa: SLF001
        assert renderer._gs.fill_rgb == (6, 5, 4)  # noqa: SLF001

        renderer.process_operator("RG", [COSFloat(1.2), COSFloat(0.5), COSFloat(-0.1)])
        renderer.process_operator("g", [COSFloat(0.25)])
        renderer.process_operator(
            "K",
            [COSFloat(0.0), COSFloat(1.0), COSFloat(0.0), COSFloat(0.5)],
        )
        renderer.process_operator("w", [COSFloat(-12.0)])

        assert renderer._gs.stroke_rgb == (128, 0, 128)  # noqa: SLF001
        assert renderer._gs.fill_rgb == (64, 64, 64)  # noqa: SLF001
        assert renderer._gs.line_width == 0.0  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_text_state_positioning_operators_update_matrices_and_spacing() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.text_font = object()  # noqa: SLF001
        renderer._gs.text_font_size = 11.0  # noqa: SLF001
        renderer._gs.text_matrix = (2.0, 0.0, 0.0, 2.0, 9.0, 9.0)  # noqa: SLF001
        renderer._gs.text_line_matrix = (3.0, 0.0, 0.0, 3.0, 8.0, 8.0)  # noqa: SLF001

        renderer.process_operator("BT", [])
        assert renderer._gs.text_font_size == 11.0  # noqa: SLF001
        assert renderer._gs.text_matrix == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001
        assert renderer._gs.text_line_matrix == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: E501, SLF001

        renderer.process_operator("Tc", [COSFloat(1.5)])
        renderer.process_operator("Tw", [COSFloat(2.5)])
        renderer.process_operator("TL", [COSFloat(4.0)])
        renderer.process_operator("Tz", [COSFloat(80.0)])
        renderer.process_operator("Ts", [COSFloat(3.0)])
        renderer.process_operator("Td", [COSFloat(6.0), COSFloat(7.0)])
        renderer.process_operator("TD", [COSFloat(1.0), COSFloat(-9.0)])
        renderer.process_operator("T*", [])

        assert renderer._gs.text_charspace == 1.5  # noqa: SLF001
        assert renderer._gs.text_wordspace == 2.5  # noqa: SLF001
        assert renderer._gs.text_leading == 9.0  # noqa: SLF001
        assert renderer._gs.text_horizontal_scaling == 80.0  # noqa: SLF001
        assert renderer._gs.text_rise == 3.0  # noqa: SLF001
        assert renderer._gs.text_matrix[4:] == (7.0, -11.0)  # noqa: SLF001
        assert renderer._gs.text_line_matrix[4:] == (7.0, -11.0)  # noqa: SLF001

        renderer.process_operator(
            "Tm",
            [
                COSFloat(1.0),
                COSFloat(2.0),
                COSFloat(3.0),
                COSFloat(4.0),
                COSFloat(5.0),
                COSFloat(6.0),
            ],
        )
        assert renderer._gs.text_matrix == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)  # noqa: SLF001
        assert renderer._gs.text_line_matrix == renderer._gs.text_matrix  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


@pytest.mark.parametrize(
    ("operator", "expected"),
    [
        ("s", {"stroke": True, "fill": False, "even_odd": False}),
        ("b", {"stroke": True, "fill": True, "even_odd": False}),
        ("b*", {"stroke": True, "fill": True, "even_odd": True}),
    ],
)
def test_close_path_paint_operators_close_open_subpath_before_paint(
    monkeypatch: Any,
    operator: str,
    expected: dict[str, bool],
) -> None:
    doc, renderer = _prepared_renderer()
    calls: list[dict[str, bool]] = []
    try:
        renderer._start_subpath(0.0, 0.0)  # noqa: SLF001
        renderer._current_subpath.append(("L", 1.0, 0.0))  # noqa: SLF001

        def _paint(**kwargs: bool) -> None:
            calls.append(kwargs)
            assert renderer._current_subpath[-1] == ("Z",)  # noqa: SLF001

        monkeypatch.setattr(renderer, "_paint", _paint)

        renderer.process_operator(operator, [])

        assert calls == [expected]
    finally:
        _finish(renderer)
        doc.close()


def test_show_text_ignores_non_string_operand_without_moving_text() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.text_matrix = (1.0, 0.0, 0.0, 1.0, 4.0, 5.0)  # noqa: SLF001

        renderer.process_operator("Tj", [COSInteger.get(65)])
        renderer.process_operator("TJ", [COSInteger.get(1)])

        assert renderer._gs.text_matrix == (1.0, 0.0, 0.0, 1.0, 4.0, 5.0)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()
