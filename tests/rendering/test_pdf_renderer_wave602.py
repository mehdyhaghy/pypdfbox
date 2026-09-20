import logging
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


def test_show_string_falls_back_when_font_read_code_raises(
    caplog: Any,
    monkeypatch: Any,
) -> None:
    class _Font:
        def read_code(self, _data: bytes, offset: int) -> tuple[int, int]:
            if offset == 0:
                raise RuntimeError("bad cmap")
            return (0x20, 1)

    doc, renderer = _prepared_renderer()
    drawn_codes: list[int] = []
    try:
        renderer._gs.text_font = _Font()
        renderer._gs.text_font_size = 10.0
        renderer._gs.text_charspace = 1.0
        renderer._gs.text_wordspace = 3.0
        renderer._gs.text_horizontal_scaling = 50.0

        def _draw_glyph(
            _font: object,
            code: int,
            _ttf: object,
            _glyph_set: object,
            _type1_units_per_em: object,
            *,
            vertical: bool = False,
        ) -> float:
            drawn_codes.append(code)
            return 200.0

        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        monkeypatch.setattr(renderer, "_draw_glyph", _draw_glyph)

        renderer._show_string(b"A ")

        assert drawn_codes == [65, 32]
        assert renderer._gs.text_matrix == (
            1.0,
            0.0,
            0.0,
            1.0,
            4.5,
            0.0,
        )
        assert "Type0 read_code failed at offset 0: bad cmap" in caplog.text
    finally:
        _finish(renderer)
        doc.close()


def test_draw_glyph_type1_path_failure_still_returns_font_width(
    caplog: Any,
) -> None:
    class _Font:
        def get_glyph_path(self, _code: int) -> list[object]:
            raise RuntimeError("path boom")

        def get_glyph_width(self, code: int) -> float:
            assert code == 65
            return 321.0

    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.text_font_size = 12.0
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")

        advance = renderer._draw_glyph(
            _Font(),
            65,
            ttf=None,
            glyph_set=None,
            type1_units_per_em=1000,
        )

        assert advance == 321.0
        assert "type1 glyph 65 path build failed: path boom" in caplog.text
    finally:
        _finish(renderer)
        doc.close()


def test_draw_glyph_uses_placeholder_when_font_width_raises(
    monkeypatch: Any,
) -> None:
    class _Font:
        def get_glyph_width(self, _code: int) -> float:
            raise RuntimeError("width boom")

    doc, renderer = _prepared_renderer()
    placeholder_calls: list[float] = []
    try:
        renderer._gs.text_font_size = 12.0
        monkeypatch.setattr(renderer, "_resolve_font_program", lambda _font: None)
        monkeypatch.setattr(
            renderer,
            "_draw_placeholder_box",
            lambda _ctm, advance_units: placeholder_calls.append(advance_units),
        )

        advance = renderer._draw_glyph(
            _Font(),
            66,
            ttf=None,
            glyph_set=None,
        )

        assert advance == 500.0
        assert placeholder_calls == [500.0]
    finally:
        _finish(renderer)
        doc.close()


def test_fill_aggdraw_path_routes_glyph_paint_through_clip_mask() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._image.paste((255, 255, 255), (0, 0, 8, 8))
        clip = Image.new("L", (8, 8), 0)
        clip.paste(255, (0, 0, 4, 8))
        renderer._gs.clip_mask = clip

        path = aggdraw.Path()
        path.moveto(0.0, 0.0)
        path.lineto(8.0, 0.0)
        path.lineto(8.0, 8.0)
        path.lineto(0.0, 8.0)
        path.close()

        renderer._fill_aggdraw_path(
            path,
            (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            (10, 20, 30),
        )

        assert renderer._image.getpixel((1, 1)) == (10, 20, 30)
        assert renderer._image.getpixel((6, 1)) == (255, 255, 255)
    finally:
        _finish(renderer)
        doc.close()
