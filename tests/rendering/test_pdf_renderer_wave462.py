from __future__ import annotations

import logging
from typing import Any

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _GState


def _make_doc(width: float = 12.0, height: float = 12.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (12, 12)) -> tuple[PDDocument, PDFRenderer]:
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


def test_show_type3_string_without_encoding_advances_by_spacing_only() -> None:
    class _Font:
        def get_font_matrix(self) -> list[float]:
            return [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]

        def get_encoding_typed(self) -> Any:
            raise RuntimeError("no encoding")

        def get_first_char(self) -> int:
            return -1

        def get_widths(self) -> list[float]:
            return []

        def get_char_proc(self, _glyph_name: str) -> None:
            return None

    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.text_font_size = 10.0  # noqa: SLF001
        renderer._gs.text_charspace = 2.0  # noqa: SLF001
        renderer._gs.text_wordspace = 3.0  # noqa: SLF001

        renderer._show_type3_string(_Font(), b" A")  # noqa: SLF001

        assert renderer._gs.text_matrix[4] == 7.0  # noqa: SLF001
        assert renderer._image.getbbox() == (0, 0, 12, 12)  # noqa: SLF001
        assert renderer._image.getpixel((6, 6)) == (255, 255, 255)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_render_type3_charproc_logs_unreadable_stream_and_restores_scope(
    caplog: Any,
) -> None:
    class _Font:
        def get_resources(self) -> object:
            return font_resources

    class _BadCharProc(COSStream):
        def to_byte_array(self) -> bytes:
            raise RuntimeError("charproc boom")

    doc, renderer = _prepared_renderer()
    font_resources = object()
    original_resources = object()
    original_path = [[("M", 1.0, 1.0)]]
    renderer._resources = original_resources  # noqa: SLF001
    renderer._subpaths = original_path  # noqa: SLF001
    renderer._current_subpath = original_path[0]  # noqa: SLF001
    renderer._current_point = (1.0, 1.0)  # noqa: SLF001
    renderer._pending_clip = "W"  # noqa: SLF001
    renderer._gs.ctm = (2.0, 0.0, 0.0, 2.0, 0.0, 0.0)  # noqa: SLF001
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")

        renderer._render_type3_charproc(  # noqa: SLF001
            _Font(),
            _BadCharProc(),
            [0.001, 0.0, 0.0, 0.001, 0.0, 0.0],
        )

        assert "cannot read Type 3 charproc: charproc boom" in caplog.text
        assert renderer._resources is original_resources  # noqa: SLF001
        assert renderer._subpaths is original_path  # noqa: SLF001
        assert renderer._current_subpath is original_path[0]  # noqa: SLF001
        assert renderer._current_point == (1.0, 1.0)  # noqa: SLF001
        assert renderer._pending_clip == "W"  # noqa: SLF001
        assert len(renderer._gs_stack) == 1  # noqa: SLF001
        assert renderer._gs.ctm == (2.0, 0.0, 0.0, 2.0, 0.0, 0.0)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()
