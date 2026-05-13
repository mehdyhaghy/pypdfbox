from __future__ import annotations

import logging
from typing import Any

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _GState


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


def test_show_string_handles_zero_consumed_code_and_spacing(monkeypatch: Any) -> None:
    class _Font:
        def __init__(self) -> None:
            self.calls = 0

        def read_code(self, data: bytes, offset: int) -> tuple[int, int]:
            self.calls += 1
            assert data == b" A"
            if offset == 0:
                return (0x20, 0)
            raise RuntimeError("read_code boom")

    doc, renderer = _prepared_renderer()
    font = _Font()
    drawn_codes: list[int] = []
    try:
        renderer._gs.text_font = font  # noqa: SLF001
        renderer._gs.text_font_size = 10.0  # noqa: SLF001
        renderer._gs.text_charspace = 2.0  # noqa: SLF001
        renderer._gs.text_wordspace = 3.0  # noqa: SLF001
        renderer._gs.text_horizontal_scaling = 50.0  # noqa: SLF001
        monkeypatch.setattr(renderer, "_get_ttf_glyph_set", lambda _font: (None, None))
        monkeypatch.setattr(renderer, "_get_type1_units_per_em", lambda _font: None)

        def _draw_glyph(
            _font: object,
            code: int,
            _ttf: object,
            _glyph_set: object,
            _type1_units_per_em: object,
        ) -> float:
            drawn_codes.append(code)
            return 500.0

        monkeypatch.setattr(renderer, "_draw_glyph", _draw_glyph)

        renderer._show_string(b" A")  # noqa: SLF001

        assert drawn_codes == [0x20, ord("A")]
        assert font.calls == 2
        assert renderer._gs.text_matrix[4] == 8.5  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_standard14_placeholder_warning_is_once_per_font(caplog: Any) -> None:
    """Symbol / ZapfDingbats have no Liberation substitute — the
    placeholder log fires exactly once per font, never per glyph.

    Wave 1303 swapped the Helvetica / Times / Courier branch over to
    bundled Liberation TTFs, so only the two symbolic Standard 14 names
    still travel through the placeholder-warn path.
    """
    class _Font:
        def get_name(self) -> str:
            return "Symbol"

    doc, renderer = _prepared_renderer()
    font = _Font()
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")

        renderer._maybe_warn_standard14(font)  # noqa: SLF001
        renderer._maybe_warn_standard14(font)  # noqa: SLF001

        assert caplog.text.count("Symbol is a Standard 14 font") == 1
        assert id(font) in renderer._warned_standard14_fonts  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_standard14_warn_suppressed_for_helvetica_with_liberation(
    caplog: Any,
) -> None:
    """Helvetica (and the other Standard 14 names with a Liberation
    substitute) must not trigger the placeholder log — the renderer
    resolves the outline through the bundled Liberation TTF instead.
    """
    class _Font:
        def get_name(self) -> str:
            return "Helvetica"

    doc, renderer = _prepared_renderer()
    font = _Font()
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")

        renderer._maybe_warn_standard14(font)  # noqa: SLF001
        renderer._maybe_warn_standard14(font)  # noqa: SLF001

        assert "Helvetica is a Standard 14 font" not in caplog.text
        # The cache entry is only added when the warning fires, so it
        # should still be absent.
        assert id(font) not in renderer._warned_standard14_fonts  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_fallback_advance_units_uses_default_when_units_per_em_fails() -> None:
    class _Substitute:
        def get_width(self, glyph_name: str) -> float:
            assert glyph_name == "A"
            return 700.0

        def get_units_per_em(self) -> int:
            raise RuntimeError("units boom")

    assert PDFRenderer._fallback_advance_units(_Substitute(), 65, 500.0) == 700.0  # noqa: E501, SLF001


def test_draw_glyph_does_not_warn_for_non_standard_font(caplog: Any) -> None:
    class _Font:
        def get_name(self) -> str:
            return "CustomFont"

        def get_glyph_width(self, _code: int) -> float:
            return 250.0

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        renderer._gs.text_font_size = 10.0  # noqa: SLF001

        advance = renderer._draw_glyph(_Font(), 65, None, None)  # noqa: SLF001
        _finish(renderer)

        assert advance == 250.0
        assert "Standard 14 font" not in caplog.text
    finally:
        doc.close()
