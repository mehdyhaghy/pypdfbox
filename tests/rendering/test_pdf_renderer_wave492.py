from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSStream, COSString
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


def test_apostrophe_text_operator_moves_line_before_showing(monkeypatch: Any) -> None:
    shown: list[bytes] = []
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.text_leading = 3.5  # noqa: SLF001
        renderer._gs.text_matrix = (1.0, 0.0, 0.0, 1.0, 2.0, 9.0)  # noqa: SLF001
        renderer._gs.text_line_matrix = renderer._gs.text_matrix  # noqa: SLF001
        monkeypatch.setattr(renderer, "_show_string", lambda data: shown.append(data))

        renderer.process_operator("'", [COSString(b"next")])

        assert shown == [b"next"]
        assert renderer._gs.text_matrix[4:] == (2.0, 5.5)  # noqa: SLF001
        assert renderer._gs.text_line_matrix[4:] == (2.0, 5.5)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_show_text_array_applies_adjustments_between_strings(monkeypatch: Any) -> None:
    positions: list[tuple[float, float]] = []
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.text_font_size = 20.0  # noqa: SLF001
        renderer._gs.text_horizontal_scaling = 50.0  # noqa: SLF001

        def _show_string(_data: bytes) -> None:
            positions.append(renderer._gs.text_matrix[4:])  # noqa: SLF001

        monkeypatch.setattr(renderer, "_show_string", _show_string)
        array = COSArray()
        array.add(COSString(b"A"))
        array.add(COSFloat(-200.0))
        array.add(COSString(b"B"))
        array.add(COSFloat(100.0))
        array.add(COSString(b"C"))

        renderer.process_operator("TJ", [array])

        assert positions == [(0.0, 0.0), (2.0, 0.0), (1.0, 0.0)]
    finally:
        _finish(renderer)
        doc.close()


def test_render_tiling_cell_restores_transform_path_and_current_point() -> None:
    class _Pattern:
        def get_cos_object(self) -> COSStream:
            return stream

        def get_resources(self) -> None:
            return None

    doc, renderer = _prepared_renderer()
    stream = COSStream()
    stream.set_raw_data(b"0 0 m\n1 1 l\n")
    renderer._device_ctm = (2.0, 0.0, 0.0, 2.0, 3.0, 4.0)  # noqa: SLF001
    renderer._page_height_px = 99.0  # noqa: SLF001
    renderer._subpaths = [[("M", 7.0, 8.0)]]  # noqa: SLF001
    renderer._current_subpath = renderer._subpaths[0]  # noqa: SLF001
    renderer._current_point = (7.0, 8.0)  # noqa: SLF001
    renderer._pending_clip = "W"  # noqa: SLF001
    try:
        tile = renderer._render_tiling_cell(  # noqa: SLF001
            _Pattern(),
            bbox=PDRectangle(0.0, 0.0, 2.0, 2.0),
            tile_size=(4, 4),
        )

        assert tile is not None
        assert renderer._device_ctm == (2.0, 0.0, 0.0, 2.0, 3.0, 4.0)  # noqa: SLF001
        assert renderer._page_height_px == 99.0  # noqa: SLF001
        assert renderer._subpaths == [[("M", 7.0, 8.0)]]  # noqa: SLF001
        assert renderer._current_subpath is renderer._subpaths[0]  # noqa: SLF001
        assert renderer._current_point == (7.0, 8.0)  # noqa: SLF001
        assert renderer._pending_clip == "W"  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_paint_tiling_pattern_skips_missing_or_invalid_geometry() -> None:
    class _Pattern:
        def __init__(self, bbox: PDRectangle | None, x_step: float, y_step: float) -> None:
            self._bbox = bbox
            self._x_step = x_step
            self._y_step = y_step

        def get_b_box(self) -> PDRectangle | None:
            return self._bbox

        def get_x_step(self) -> float:
            return self._x_step

        def get_y_step(self) -> float:
            return self._y_step

    doc, renderer = _prepared_renderer((3, 3))
    mask = Image.new("L", (3, 3), 255)
    try:
        renderer._paint_tiling_pattern(  # noqa: SLF001
            _Pattern(None, 1.0, 1.0),
            region_mask=mask,
        )
        renderer._paint_tiling_pattern(  # noqa: SLF001
            _Pattern(PDRectangle(0.0, 0.0, 0.0, 2.0), 1.0, 1.0),
            region_mask=mask,
        )
        renderer._paint_tiling_pattern(  # noqa: SLF001
            _Pattern(PDRectangle(0.0, 0.0, 2.0, 2.0), 0.0, 1.0),
            region_mask=mask,
        )
        _finish(renderer)

        assert renderer._image.getbbox() == (0, 0, 3, 3)  # noqa: SLF001
        assert renderer._image.getpixel((1, 1)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()
