from __future__ import annotations

from typing import Any

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.cos import COSFloat, COSStream, COSString
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _GState


def _make_doc(width: float = 20.0, height: float = 20.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (20, 20)) -> tuple[PDDocument, PDFRenderer]:
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


def test_save_restore_graphics_state_operator_keeps_base_state() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.fill_rgb = (1, 2, 3)  # noqa: SLF001
        renderer._gs.line_width = 4.0  # noqa: SLF001

        renderer.process_operator("q", [])
        renderer._gs.fill_rgb = (9, 9, 9)  # noqa: SLF001
        renderer._gs.line_width = 10.0  # noqa: SLF001

        assert len(renderer._gs_stack) == 2  # noqa: SLF001
        renderer.process_operator("Q", [])
        renderer.process_operator("Q", [])

        assert len(renderer._gs_stack) == 1  # noqa: SLF001
        assert renderer._gs.fill_rgb == (1, 2, 3)  # noqa: SLF001
        assert renderer._gs.line_width == 4.0  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_quoted_text_operator_sets_spacing_moves_line_and_advances() -> None:
    class _Font:
        def get_glyph_width(self, _code: int) -> float:
            return 1000.0

    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.text_font = _Font()  # noqa: SLF001
        renderer._gs.text_font_size = 10.0  # noqa: SLF001
        renderer._gs.text_leading = 12.0  # noqa: SLF001

        renderer.process_operator(
            '"',
            [COSFloat(5.0), COSFloat(2.0), COSString(b"A A")],
        )

        assert renderer._gs.text_wordspace == 5.0  # noqa: SLF001
        assert renderer._gs.text_charspace == 2.0  # noqa: SLF001
        assert renderer._gs.text_matrix[4:] == (41.0, -12.0)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_render_tiling_cell_processes_stream_and_restores_state() -> None:
    class _Pattern:
        def __init__(self, stream: COSStream, resources: object) -> None:
            self._stream = stream
            self._resources = resources

        def get_cos_object(self) -> COSStream:
            return self._stream

        def get_resources(self) -> object:
            return self._resources

    doc, renderer = _prepared_renderer()
    stream = COSStream()
    stream.set_raw_data(b"0 1 0 rg\n0 0 2 2 re\nf\n")
    original_resources = object()
    pattern_resources = object()
    renderer._resources = original_resources  # noqa: SLF001
    renderer._gs.fill_rgb = (10, 20, 30)  # noqa: SLF001
    try:
        tile = renderer._render_tiling_cell(  # noqa: SLF001
            _Pattern(stream, pattern_resources),
            bbox=PDRectangle(0.0, 0.0, 2.0, 2.0),
            tile_size=(4, 4),
        )

        assert tile is not None
        assert tile.getpixel((2, 2)) == (0, 255, 0)
        assert renderer._resources is original_resources  # noqa: SLF001
        assert renderer._gs.fill_rgb == (10, 20, 30)  # noqa: SLF001
        assert renderer._subpaths == []  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_show_inline_image_uses_helper_image_before_legacy_decoder() -> None:
    class _InlineImage:
        def to_pil_image(self) -> Image.Image:
            return Image.new("RGB", (1, 1), (200, 10, 20))

        def get_cos_object(self) -> Any:
            raise AssertionError("legacy decoder should not be used")

        def get_stream(self) -> bytes:
            raise AssertionError("legacy decoder should not be used")

    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.ctm = (2.0, 0.0, 0.0, 2.0, 1.0, 1.0)  # noqa: SLF001

        renderer.show_inline_image(_InlineImage())
        _finish(renderer)

        assert renderer._image.getpixel((1, 1)) == (200, 10, 20)  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()
