"""Hand-written coverage for :class:`EmbeddedMultipleFonts`."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.examples.pdmodel.embedded_multiple_fonts import (
    EmbeddedMultipleFonts,
    _load_font,
)
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_document import PDDocument


@pytest.fixture
def patched_glyph_list() -> Any:
    """Provide the missing ``pypdfbox.pdmodel.font.encoding.glyph_list``
    module so :meth:`is_win_ansi_encoding` can import it.

    The real ``GlyphList`` lives under ``pypdfbox.fontbox.encoding``; the
    helper re-exports it under the path the source references and tears
    the shim down on exit.
    """
    mod_name = "pypdfbox.pdmodel.font.encoding.glyph_list"
    from pypdfbox.fontbox.encoding.glyph_list import GlyphList

    shim = types.ModuleType(mod_name)
    shim.GlyphList = GlyphList
    sys.modules[mod_name] = shim
    try:
        yield shim
    finally:
        sys.modules.pop(mod_name, None)


class _StrictAsciiFont:
    """Test double: encodes only ASCII; mirrors :class:`PDFont.encode`."""

    name = "strict_ascii"

    def encode(self, text: str) -> bytes:
        if all(ord(ch) < 128 for ch in text):
            return text.encode("ascii")
        raise ValueError("non-ascii char in strict-ascii font")


class _HangulOnlyFont:
    """Test double: encodes Hangul syllables (plus ``a`` so the
    WinAnsi snap-back branch in ``show_text_multiple`` is exercised)."""

    name = "hangul_only"

    def encode(self, text: str) -> bytes:
        for ch in text:
            if 0xAC00 <= ord(ch) <= 0xD7AF or ch == "a":
                continue
            raise ValueError(f"cannot encode {ch!r}")
        return text.encode("utf-8")


class _RecordingCS:
    """Minimal :class:`PDPageContentStream` stand-in."""

    def __init__(self) -> None:
        self.events: list[tuple[str, Any, Any]] = []

    def set_font(self, font: Any, size: float) -> None:
        self.events.append(("set", font.name, size))

    def show_text(self, text: str) -> None:
        self.events.append(("show", text, None))


def test_constructor_is_a_no_op() -> None:
    assert isinstance(EmbeddedMultipleFonts(), EmbeddedMultipleFonts)


# ---- main() ----------------------------------------------------------


def test_main_with_no_args_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="EmbeddedMultipleFonts"):
        EmbeddedMultipleFonts.main([])


def test_main_with_none_argv_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        EmbeddedMultipleFonts.main(None)


def test_main_with_only_output_path_raises_not_implemented(tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError):
        EmbeddedMultipleFonts.main([str(tmp_path / "out.pdf")])


def test_main_with_missing_font_path_raises_oserror(tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    with pytest.raises(OSError):
        EmbeddedMultipleFonts.main([str(out), str(tmp_path / "missing.ttf")])


# ---- demo_with_fonts() ----------------------------------------------


def test_demo_with_fonts_only_helvetica_anchor_writes_pdf(tmp_path: Path) -> None:
    out = tmp_path / "demo.pdf"
    # Empty fallback list — slot 0 (Helvetica) is the only font; the
    # fast-path encode succeeds for the multi-script sample because
    # Helvetica WinAnsi maps un-encodable chars to ``?``.
    EmbeddedMultipleFonts.demo_with_fonts(out, [])
    assert out.exists() and out.stat().st_size > 0


def test_demo_with_fonts_accepts_path_input(tmp_path: Path) -> None:
    out = tmp_path / "demo-pathlike.pdf"
    EmbeddedMultipleFonts.demo_with_fonts(str(out), [])
    assert out.exists()


# ---- _load_font() ---------------------------------------------------


def test_load_font_helvetica_literal_returns_type1() -> None:
    doc = PDDocument()
    try:
        font = _load_font(doc, "helvetica")
        assert isinstance(font, PDType1Font)
    finally:
        doc.close()


def test_load_font_helvetica_case_insensitive() -> None:
    doc = PDDocument()
    try:
        font = _load_font(doc, "HELVETICA")
        assert isinstance(font, PDType1Font)
    finally:
        doc.close()


def test_load_font_missing_ttc_raises(tmp_path: Path) -> None:
    doc = PDDocument()
    try:
        with pytest.raises(OSError):
            _load_font(doc, (str(tmp_path / "missing.ttc"), "AnyName"))
    finally:
        doc.close()


def test_load_font_missing_ttf_raises(tmp_path: Path) -> None:
    doc = PDDocument()
    try:
        with pytest.raises(OSError):
            _load_font(doc, str(tmp_path / "missing.ttf"))
    finally:
        doc.close()


# ---- show_text_multiple() ------------------------------------------


def test_show_text_multiple_fast_path() -> None:
    cs = _RecordingCS()
    EmbeddedMultipleFonts.show_text_multiple(
        cs, "hello", [_StrictAsciiFont()], 12,
    )
    # Single set_font + single show_text — no per-char walk needed.
    assert cs.events == [("set", "strict_ascii", 12), ("show", "hello", None)]


def test_show_text_multiple_fallback_walk(patched_glyph_list: Any) -> None:
    cs = _RecordingCS()
    EmbeddedMultipleFonts.show_text_multiple(
        cs,
        "abc한국abc",
        [_StrictAsciiFont(), _HangulOnlyFont()],
        18,
    )
    shown = [(kind, text) for kind, text, _ in cs.events if kind == "show"]
    # ASCII → strict, Hangul → hangul, ASCII again → strict.
    assert shown == [("show", "abc"), ("show", "한국"), ("show", "abc")]


def test_show_text_multiple_snap_back_to_anchor_on_win_ansi(
    patched_glyph_list: Any,
) -> None:
    cs = _RecordingCS()
    # The hangul font can also encode ``a``, but the WinAnsi snap-back
    # branch must redirect ``a`` back to fonts[0] mid-word.
    EmbeddedMultipleFonts.show_text_multiple(
        cs,
        "한a국",
        [_StrictAsciiFont(), _HangulOnlyFont()],
        14,
    )
    shown = [(kind, text) for kind, text, _ in cs.events if kind == "show"]
    assert shown == [("show", "한"), ("show", "a"), ("show", "국")]


def test_show_text_multiple_raises_when_no_font_can_encode(
    patched_glyph_list: Any,
) -> None:
    cs = _RecordingCS()
    with pytest.raises(ValueError, match="Could not show"):
        EmbeddedMultipleFonts.show_text_multiple(
            cs,
            "abcéabc",  # é is neither ASCII nor Hangul
            [_StrictAsciiFont(), _HangulOnlyFont()],
            12,
        )


# ---- is_win_ansi_encoding() ----------------------------------------


def test_is_win_ansi_encoding_ascii_letter(patched_glyph_list: Any) -> None:
    assert EmbeddedMultipleFonts.is_win_ansi_encoding(ord("a")) is True


def test_is_win_ansi_encoding_unmapped_code(patched_glyph_list: Any) -> None:
    # Code 0 maps to ``.notdef`` — the branch that short-circuits to False.
    assert EmbeddedMultipleFonts.is_win_ansi_encoding(0) is False


def test_is_win_ansi_encoding_hangul(patched_glyph_list: Any) -> None:
    # Hangul syllable is not in WinAnsi.
    assert EmbeddedMultipleFonts.is_win_ansi_encoding(ord("한")) is False
