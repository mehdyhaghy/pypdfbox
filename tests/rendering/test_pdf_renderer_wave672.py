from __future__ import annotations

import types
from typing import Any

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(
    width: float = 3.0,
    height: float = 3.0,
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(
    size: tuple[int, int] = (3, 3),
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


def test_do_operator_ignores_valid_name_without_canvas() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._draw = None  # noqa: SLF001
        renderer._image = None  # noqa: SLF001

        renderer._op_do(None, [COSName.get_pdf_name("Im1")])  # noqa: SLF001
    finally:
        doc.close()


def test_transparency_group_get_group_failure_still_uses_blend_mode(
    monkeypatch: Any,
) -> None:
    class _Form:
        def get_group(self) -> None:
            raise RuntimeError("group unavailable")

    class _MultiplyMode:
        name = "Multiply"

        def is_separable(self) -> bool:
            return True

    def paint_group(_form: Any) -> None:
        assert renderer._image is not None  # noqa: SLF001
        renderer._image.paste((128, 0, 0, 255), (0, 0, 1, 1))  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        renderer._draw.setantialias(True)  # noqa: SLF001

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        renderer._gs.blend_mode = _MultiplyMode()  # noqa: SLF001
        monkeypatch.setattr(renderer, "_render_form_xobject", paint_group)

        renderer._render_transparency_group(_Form())  # noqa: SLF001
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (128, 0, 0)  # noqa: SLF001
    finally:
        doc.close()


def test_resolve_font_program_caches_embedded_ttf(
    monkeypatch: Any,
) -> None:
    doc, renderer = _prepared_renderer()
    try:
        program = object()
        font = object()
        calls = 0

        def get_ttf_glyph_set(_font: object) -> tuple[object, object]:
            nonlocal calls
            calls += 1
            return program, object()

        monkeypatch.setattr(renderer, "_get_ttf_glyph_set", get_ttf_glyph_set)

        assert renderer._resolve_font_program(font) is program  # noqa: SLF001
        assert renderer._resolve_font_program(font) is program  # noqa: SLF001
        assert calls == 1
    finally:
        _finish(renderer)
        doc.close()


def test_resolve_font_program_returns_embedded_type1_program(
    monkeypatch: Any,
) -> None:
    import pypdfbox.pdmodel.font.pd_type1_font as type1_module

    class _FakeType1Font:
        def __init__(self, program: object) -> None:
            self._program = program

        def _get_type1_font(self) -> object:
            return self._program

    doc, renderer = _prepared_renderer()
    try:
        program = object()
        font = _FakeType1Font(program)
        monkeypatch.setattr(renderer, "_get_ttf_glyph_set", lambda _font: (None, None))
        monkeypatch.setattr(type1_module, "PDType1Font", _FakeType1Font)

        assert renderer._resolve_font_program(font) is program  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_draw_glyph_uses_ttf_program_advance_when_pdf_width_missing(
    monkeypatch: Any,
) -> None:
    class _Glyph:
        def draw(self, _pen: Any) -> None:
            return None

    class _TTF:
        def __init__(self) -> None:
            self._tt = types.SimpleNamespace(getGlyphName=lambda _gid: "gid4")

        def get_advance_width(self, gid: int) -> float:
            assert gid == 4
            return 500.0

        def get_units_per_em(self) -> int:
            return 2000

    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.text_font_size = 12.0  # noqa: SLF001
        ttf = _TTF()
        glyph_set = {"gid4": _Glyph()}
        monkeypatch.setattr(
            PDFRenderer,
            "_code_to_gid",
            staticmethod(lambda _font, _code, _ttf: 4),
        )
        monkeypatch.setattr(renderer, "_font_width_units", lambda _font, _code: 0.0)

        advance = renderer._draw_glyph(  # noqa: SLF001
            object(),
            65,
            ttf,
            glyph_set,
        )

        assert advance == 250.0
    finally:
        _finish(renderer)
        doc.close()


def test_maybe_warn_standard14_ignores_font_name_failures() -> None:
    class _BrokenFont:
        def get_name(self) -> str:
            raise RuntimeError("name unavailable")

    doc, renderer = _prepared_renderer()
    try:
        font = _BrokenFont()

        renderer._maybe_warn_standard14(font)  # noqa: SLF001

        assert id(font) not in renderer._warned_standard14_fonts  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()
