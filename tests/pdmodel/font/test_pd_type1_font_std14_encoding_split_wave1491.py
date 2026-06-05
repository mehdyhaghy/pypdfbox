"""Wave 1491 — the non-embedded Standard-14 toUnicode-vs-WinAnsi split.

Closes the wave-1468 deferral: a Standard-14 core font *parsed from a PDF
dict that carries no ``/Encoding``* must read its built-in encoding from the
bundled Adobe AFM (``Type1Encoding``, AdobeStandardEncoding / FontSpecific),
exactly as upstream ``PDType1Font.readEncodingFromFont`` does
(PDType1Font.java lines 495-498). The *direct* ``new PDType1Font(FontName)``
constructor — ported as :meth:`PDType1Font.standard14` — instead assigns
``WinAnsiEncoding`` to the Latin cores (with an explicit ``/Encoding
/WinAnsiEncoding`` written into the dict, line 120) and the FontSpecific
``SymbolEncoding`` / ``ZapfDingbatsEncoding`` singletons to the symbol fonts.

These two construction paths genuinely diverge in PDFBox too — most visibly
for ZapfDingbats codes 128-141, which the AFM maps to ``a89``-``a96`` but the
built-in ``ZapfDingbatsEncoding`` leaves as ``.notdef``. The split is pinned
against the live oracle in ``oracle/test_std14_metrics_oracle.py`` and
``oracle/test_symbol_encoding_oracle.py``; this module is the hand-written
companion that runs without Java.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.fontbox.encoding.glyph_list import GlyphList
from pypdfbox.pdmodel.font.encoding.symbol_encoding import SymbolEncoding
from pypdfbox.pdmodel.font.encoding.type1_encoding import Type1Encoding
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.encoding.zapf_dingbats_encoding import (
    ZapfDingbatsEncoding,
)
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

_BASE_FONT = COSName.get_pdf_name("BaseFont")
_ENCODING = COSName.get_pdf_name("Encoding")


def _dict_font(base_font: str) -> PDType1Font:
    """A core font parsed from a PDF dict with NO /Encoding."""
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("Subtype"), "Type1")
    d.set_name(_BASE_FONT, base_font)
    return PDType1Font(d)


# ---------- dict-loaded, no /Encoding -> AFM Type1Encoding (Standard) ----------


def test_dict_no_encoding_latin_reads_afm_standard_for_tounicode() -> None:
    font = _dict_font("Helvetica")
    enc = font.read_encoding_from_font()
    assert isinstance(enc, Type1Encoding)
    # AdobeStandardEncoding glyph names, NOT WinAnsi spellings.
    assert enc.get_name(0x27) == "quoteright"  # WinAnsi would be quotesingle
    assert enc.get_name(0x60) == "quoteleft"  # WinAnsi would be grave
    assert enc.get_name(0xAD) == "guilsinglright"  # WinAnsi would be sfthyphen


def test_dict_no_encoding_latin_tounicode_codepoints() -> None:
    """The pinned toUnicode pins from the wave-1468 deferral."""
    font = _dict_font("Helvetica")
    enc = font.get_encoding_typed()
    assert isinstance(enc, Type1Encoding)
    gl = GlyphList.DEFAULT
    assert gl.to_unicode(enc.get_name(0x27)) == "’"  # quoteright
    assert gl.to_unicode(enc.get_name(0x60)) == "‘"  # quoteleft
    assert gl.to_unicode(enc.get_name(0xAD)) == "›"  # guilsinglright


def test_dict_no_encoding_symbol_matches_symbol_encoding() -> None:
    font = _dict_font("Symbol")
    enc = font.read_encoding_from_font()
    assert isinstance(enc, Type1Encoding)
    ref = SymbolEncoding.INSTANCE
    assert all(enc.get_name(c) == ref.get_name(c) for c in range(256))


def test_dict_no_encoding_zapf_maps_afm_only_glyphs() -> None:
    """AFM Type1Encoding for ZapfDingbats reaches glyphs the built-in
    encoding leaves as .notdef (codes 128-141 -> a89..a96)."""
    font = _dict_font("ZapfDingbats")
    enc = font.read_encoding_from_font()
    assert isinstance(enc, Type1Encoding)
    assert enc.get_name(128) == "a89"
    assert enc.get_name(141) == "a96"
    # The built-in direct-constructor encoding leaves those as .notdef.
    assert ZapfDingbatsEncoding.INSTANCE.get_name(128) == ".notdef"


# ---------- direct constructor (standard14) -> WinAnsi / built-in ----------


def test_standard14_latin_uses_winansi_and_writes_encoding_entry() -> None:
    font = PDType1Font.standard14("Helvetica")
    # The dict carries an explicit /Encoding /WinAnsiEncoding (line 120).
    assert font.get_cos_object().get_item(_ENCODING) == COSName.WIN_ANSI_ENCODING
    enc = font.get_encoding_typed()
    assert isinstance(enc, WinAnsiEncoding)
    # WinAnsi spellings at the disagreeing codes.
    assert enc.get_name(0x27) == "quotesingle"
    assert enc.get_name(0x60) == "grave"
    assert enc.get_name(0xAD) == "sfthyphen"


def test_standard14_symbol_uses_symbol_encoding_singleton() -> None:
    font = PDType1Font.standard14("Symbol")
    # No /Encoding entry written for FontSpecific cores.
    assert font.get_cos_object().get_item(_ENCODING) is None
    assert font.get_encoding_typed() is SymbolEncoding.INSTANCE


def test_standard14_zapf_uses_dingbats_encoding_singleton() -> None:
    font = PDType1Font.standard14("ZapfDingbats")
    assert font.get_cos_object().get_item(_ENCODING) is None
    enc = font.get_encoding_typed()
    assert enc is ZapfDingbatsEncoding.INSTANCE
    # Built-in encoding leaves the AFM-only codes as .notdef.
    assert enc.get_name(128) == ".notdef"


def test_standard14_alias_resolves_to_canonical() -> None:
    """An alias (Arial -> Helvetica) lands on the canonical core font."""
    font = PDType1Font.standard14("Arial")
    assert font.get_name() == "Helvetica"
    assert font.get_cos_object().get_item(_ENCODING) == COSName.WIN_ANSI_ENCODING


# ---------- non-Standard-14 unaffected ----------


def test_non_standard14_dict_no_encoding_falls_back_to_standard() -> None:
    """A non-Std-14, non-embedded font with no /Encoding still falls through
    to StandardEncoding (no AFM available), unchanged by wave 1491."""
    from pypdfbox.pdmodel.font.encoding.standard_encoding import StandardEncoding

    font = _dict_font("SomeRandomFont")
    assert font.read_encoding_from_font() is StandardEncoding.INSTANCE


# ---------- set_encoding helper ----------


def test_set_encoding_overrides_resolution() -> None:
    font = _dict_font("Helvetica")
    font.set_encoding(WinAnsiEncoding.INSTANCE)
    assert font.get_encoding_typed() is WinAnsiEncoding.INSTANCE
