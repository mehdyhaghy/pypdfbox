"""Hand-written tests for the TrueType hinting render wiring (PDFBOX-3293):
``PDFRenderer.set_hinting_enabled``, ``PageDrawerParameters``,
``PageDrawer``, ``GlyphCache`` and the printing classes.

The GlyphHinter interpreter lands in a later wave, so the tests that need
a hinted outline stub ``TrueTypeFont.get_hinted_path``; with hinting
disabled (the default) rendering must be byte-identical to the unhinted
path."""

import io
import logging
import sys
from pathlib import Path
from typing import Any

import pytest
from fontTools.pens.recordingPen import RecordingPen
from PIL import ImageChops

from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDTrueTypeFont, PDType0Font
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.printing.pdf_pageable import PDFPageable
from pypdfbox.printing.pdf_printable import PDFPrintable
from pypdfbox.rendering import GlyphCache, PDFRenderer, RenderDestination
from pypdfbox.rendering.page_drawer import PageDrawer
from pypdfbox.rendering.page_drawer_parameters import PageDrawerParameters

_TTF = Path(__file__).resolve().parents[1] / "fixtures" / "fontbox" / "ttf"
_LIBERATION = _TTF / "LiberationSans-Regular.ttf"


# ---------------------------------------------------------------------------
# flags
# ---------------------------------------------------------------------------


def test_renderer_hinting_default_off_and_round_trip() -> None:
    with PDDocument() as doc:
        renderer = PDFRenderer(doc)
        assert renderer.is_hinting_enabled() is False
        renderer.set_hinting_enabled(True)
        assert renderer.is_hinting_enabled() is True
        renderer.set_hinting_enabled(0)  # type: ignore[arg-type]
        assert renderer.is_hinting_enabled() is False


def test_page_drawer_parameters_carry_hinting_flag() -> None:
    with PDDocument() as doc:
        page = PDPage(PDRectangle(0.0, 0.0, 10.0, 10.0))
        doc.add_page(page)
        renderer = PDFRenderer(doc)
        params = PageDrawerParameters(
            renderer, page, False, True, RenderDestination.VIEW, None, 0.5
        )
        assert params.is_hinting_enabled() is True
        assert params.is_subsampling_allowed() is False
        assert params.get_destination() is RenderDestination.VIEW
        drawer = PageDrawer(params)
        assert drawer._hinting_enabled is True


def test_printable_and_pageable_hinting_flags() -> None:
    with PDDocument() as doc:
        doc.add_page(PDPage(PDRectangle(0.0, 0.0, 10.0, 10.0)))
        printable = PDFPrintable(doc)
        assert printable.is_hinting_enabled() is False
        printable.set_hinting_enabled(True)
        assert printable.is_hinting_enabled() is True

        pageable = PDFPageable(doc)
        assert pageable.is_hinting_enabled() is False
        pageable.set_hinting_enabled(True)
        assert pageable.is_hinting_enabled() is True
        assert pageable.get_printable(0).is_hinting_enabled() is True


def test_printable_forwards_hinting_to_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    class _SpyRenderer(PDFRenderer):
        def set_hinting_enabled(self, hinting_enabled: bool) -> None:
            seen["hinting"] = hinting_enabled
            super().set_hinting_enabled(hinting_enabled)

    import pypdfbox.rendering.pdf_renderer as renderer_mod

    monkeypatch.setattr(renderer_mod, "PDFRenderer", _SpyRenderer)
    with PDDocument() as doc:
        doc.add_page(PDPage(PDRectangle(0.0, 0.0, 10.0, 10.0)))
        printable = PDFPrintable(doc)
        printable.set_hinting_enabled(True)
        printable.render(0)
    assert seen["hinting"] is True


# ---------------------------------------------------------------------------
# GlyphCache (code, ppem) overload
# ---------------------------------------------------------------------------


class _StubFont:
    def __init__(self, hinted: Any = None, error: bool = False) -> None:
        self.hinted = hinted
        self.error = error
        self.hinted_calls: list[tuple[int, int]] = []
        self.unhinted_calls: list[int] = []

    def get_name(self) -> str:
        return "Stub"

    def has_glyph(self, code: int) -> bool:
        return True

    def get_normalized_path(self, code: int) -> list[tuple[Any, ...]]:
        self.unhinted_calls.append(code)
        return [("moveto", 0.0, 0.0)]

    def get_hinted_normalized_path(self, code: int, ppem: int) -> Any:
        self.hinted_calls.append((code, ppem))
        if self.error:
            raise OSError("broken bytecode")
        return self.hinted


def test_glyph_cache_returns_and_caches_hinted_path() -> None:
    hinted = [("moveto", 1.0, 1.0)]
    font = _StubFont(hinted)
    cache = GlyphCache(font)  # type: ignore[arg-type]
    assert cache.get_path_for_character_code(65, 16) is hinted
    assert cache.get_path_for_character_code(65, 16) is hinted
    assert font.hinted_calls == [(65, 16)]
    assert font.unhinted_calls == []
    # a different ppem is a different cache key
    cache.get_path_for_character_code(65, 17)
    assert font.hinted_calls == [(65, 16), (65, 17)]


def test_glyph_cache_falls_back_to_unhinted_path() -> None:
    font = _StubFont(None)
    cache = GlyphCache(font)  # type: ignore[arg-type]
    assert cache.get_path_for_character_code(65, 16) == [("moveto", 0.0, 0.0)]
    assert cache.get_path_for_character_code(65, 16) == [("moveto", 0.0, 0.0)]
    assert font.hinted_calls == [(65, 16)]
    assert font.unhinted_calls == [65]  # the unhinted path is itself cached
    # the single-argument overload is unchanged
    assert cache.get_path_for_character_code(65) == [("moveto", 0.0, 0.0)]


def test_glyph_cache_hinting_failure_logs_and_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    font = _StubFont(error=True)
    cache = GlyphCache(font)  # type: ignore[arg-type]
    with caplog.at_level(logging.WARNING, logger="pypdfbox.rendering.glyph_cache"):
        assert cache.get_path_for_character_code(66, 12) == [("moveto", 0.0, 0.0)]
    assert "Hinting failed for code 66 in font Stub" in caplog.text


def test_glyph_cache_font_without_hinting_method() -> None:
    class _Plain:
        def has_glyph(self, code: int) -> bool:
            return True

        def get_normalized_path(self, code: int) -> list[Any]:
            return ["unhinted"]

    cache = GlyphCache(_Plain())  # type: ignore[arg-type]
    assert cache.get_path_for_character_code(1, 20) == ["unhinted"]


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


def _build_pdf(type0: bool = False) -> bytes:
    with PDDocument() as doc:
        page = PDPage(PDRectangle(0.0, 0.0, 160.0, 60.0))
        doc.add_page(page)
        if type0:
            font: Any = PDType0Font.load(doc, _LIBERATION, embed_subset=False)
        else:
            font = PDTrueTypeFont.load(doc, _LIBERATION.read_bytes(), WinAnsiEncoding.INSTANCE)
        with PDPageContentStream(doc, page) as cs:
            cs.begin_text()
            cs.set_font(font, 11)
            cs.new_line_at_offset(8, 24)
            # pre-encode: the lite show_text(str) does not run font.encode
            cs.show_text(font.encode("Hamburgefons 123"))
            cs.end_text()
        out = io.BytesIO()
        doc.save(out)
        return out.getvalue()


def _render(pdf: bytes, hinting: bool | None) -> Any:
    with PDDocument.load(pdf) as doc:
        renderer = PDFRenderer(doc)
        if hinting is not None:
            renderer.set_hinting_enabled(hinting)
        return renderer.render_image_with_dpi(0, 96).convert("RGB")


def _differences(a: Any, b: Any) -> int:
    histogram = ImageChops.difference(a, b).convert("L").histogram()
    return sum(histogram[1:])


@pytest.mark.parametrize("type0", [False, True], ids=["truetype", "type0"])
def test_disabled_hinting_is_pixel_identical_and_never_hints(
    type0: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = _build_pdf(type0)
    baseline = _render(pdf, None)
    assert _differences(baseline, baseline.copy()) == 0
    assert baseline.getextrema() != ((255, 255),) * 3, "text should be painted"

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("hinting must not run while disabled")

    monkeypatch.setattr(PageDrawer, "hinting_ppem", staticmethod(_boom))
    monkeypatch.setattr(PDTrueTypeFont, "get_hinted_normalized_path", _boom)
    monkeypatch.setattr(PDCIDFontType2, "get_hinted_normalized_path", _boom)
    monkeypatch.setattr(TrueTypeFont, "get_hinted_path", _boom)
    assert _differences(baseline, _render(pdf, False)) == 0


@pytest.mark.parametrize("type0", [False, True], ids=["truetype", "type0"])
def test_enabled_hinting_without_glyph_hinter_matches_unhinted(
    type0: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "pypdfbox.fontbox.ttf.glyph_hinter", None)
    pdf = _build_pdf(type0)
    assert _differences(_render(pdf, False), _render(pdf, True)) == 0


@pytest.mark.parametrize("type0", [False, True], ids=["truetype", "type0"])
def test_enabled_hinting_draws_hinted_outline_at_device_ppem(
    type0: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a stub hinter, the hinted outline is what gets painted and the
    ppem is the device pixels per em (11pt at 96dpi = 14.67px -> 15)."""
    seen: list[tuple[int, int]] = []

    def _fake_hinted_path(self: TrueTypeFont, gid: int, ppem: int) -> RecordingPen:
        seen.append((gid, ppem))
        upem = self.get_units_per_em()
        pen = RecordingPen()
        # a full-em box: obviously different from any real glyph outline
        pen.moveTo((0, 0))
        pen.lineTo((upem, 0))
        pen.lineTo((upem, upem))
        pen.lineTo((0, upem))
        pen.closePath()
        return pen

    pdf = _build_pdf(type0)
    off = _render(pdf, False)
    monkeypatch.setattr(TrueTypeFont, "get_hinted_path", _fake_hinted_path)
    on = _render(pdf, True)
    assert on.size == off.size
    assert _differences(off, on) > 0
    assert seen, "the hinted path was never requested"
    assert {ppem for _gid, ppem in seen} == {15}
