"""Adobe Glyph List + ZapfDingbats glyph list — CharCode-to-Unicode dispatch.

Wave 1369 round-out — exercises the chain a Type 1 font walks when
resolving an arbitrary character code into a Unicode string:

    char code -> glyph name (via the font's Encoding)
              -> Unicode string (via the GlyphList for the font)

This is the canonical fallback when no /ToUnicode CMap is present
(the most common case for the Standard14 Type 1 fonts).
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.encoding.glyph_list import GlyphList
from pypdfbox.pdmodel.font.encoding import (
    Encoding,
    StandardEncoding,
    WinAnsiEncoding,
    ZapfDingbatsEncoding,
)


def _dispatch(encoding: Encoding, glyph_list: GlyphList, code: int) -> str | None:
    """Replicate the Encoding+GlyphList dispatch for a single code."""
    name = encoding.get_name(code)
    return glyph_list.to_unicode(name)


@pytest.mark.parametrize(
    "code,expected",
    [
        (0x41, "A"),
        (0x42, "B"),
        (0x61, "a"),
        (0x20, " "),
        (0x30, "0"),
    ],
)
def test_winansi_dispatch_to_agl(code: int, expected: str) -> None:
    enc = WinAnsiEncoding.INSTANCE
    agl = GlyphList.DEFAULT
    assert _dispatch(enc, agl, code) == expected


@pytest.mark.parametrize(
    "code,expected",
    [
        (0x41, "A"),  # /A
        (0x42, "B"),  # /B
        (0x20, " "),  # /space
    ],
)
def test_standard_encoding_dispatch_to_agl(code: int, expected: str) -> None:
    enc = StandardEncoding.INSTANCE
    agl = GlyphList.DEFAULT
    assert _dispatch(enc, agl, code) == expected


def test_zapf_dingbats_dispatch_uses_zapf_glyph_list() -> None:
    # ZapfDingbats codes map to their own glyph names (a*); those names are
    # only present in the Zapf glyph list, not the AGL.
    enc = ZapfDingbatsEncoding.INSTANCE
    zapf = GlyphList.ZAPF_DINGBATS
    # Pick a known mapping: code 0x21 in ZapfDingbats is /a1 (U+2701).
    # Confirm via dispatch.
    name = enc.get_name(0x21)
    assert name != ".notdef"
    via_zapf = zapf.to_unicode(name)
    assert via_zapf is not None and len(via_zapf) == 1


def test_unknown_code_dispatches_to_notdef_then_none() -> None:
    # A code that has no glyph name should produce ".notdef" from the encoding,
    # which the glyph list resolves to None.
    enc = WinAnsiEncoding.INSTANCE
    agl = GlyphList.DEFAULT
    # Code 0x01 is unmapped in WinAnsi.
    assert enc.get_name(0x01) == ".notdef"
    assert agl.to_unicode(".notdef") is None


def test_uni_pattern_dispatch_through_glyph_list() -> None:
    # Custom encoding entry "uni20AC" (€) — the AGL synthesizes the unicode
    # value from the hex suffix even if "uni20AC" isn't an explicit table key.
    agl = GlyphList.DEFAULT
    assert agl.to_unicode("uni20AC") == "€"


def test_glyph_list_is_unicode_lookup_classifier() -> None:
    # is_unicode_lookup is a static classifier — it does not require the
    # name to be present in the table.
    assert GlyphList.is_unicode_lookup("uni0041") is True
    assert GlyphList.is_unicode_lookup("u00041") is True
    assert GlyphList.is_unicode_lookup("u041") is False  # 3 hex digits
    assert GlyphList.is_unicode_lookup("A") is False
    assert GlyphList.is_unicode_lookup(None) is False
    assert GlyphList.is_unicode_lookup("") is False


def test_glyph_list_get_or_unicode_lookup_falls_back_to_uni_pattern() -> None:
    agl = GlyphList.DEFAULT
    # Known glyph name -> normal lookup.
    assert agl.get_or_unicode_lookup("A") == "A"
    # Synthesized name not in the table -> synthesised lookup.
    assert agl.get_or_unicode_lookup("uni20AC") == "€"
    # Unknown name that doesn't match the pattern -> None.
    assert agl.get_or_unicode_lookup("never_a_real_glyph") is None
    assert agl.get_or_unicode_lookup(None) is None


def test_dot_suffix_stripping_via_glyph_list() -> None:
    # ``glyphname.alt`` falls back to ``glyphname`` per upstream's
    # GlyphList.toUnicode dot-stripping rule. Common in stylistic-alt subset
    # fonts that name variants with ``.alt`` / ``.sc`` / ``.smcp`` suffixes.
    agl = GlyphList.DEFAULT
    assert agl.to_unicode("A.alt") == "A"
    assert agl.to_unicode("A.sc") == "A"
    assert agl.to_unicode("A.smcp") == "A"
    # Two-level suffix collapses to the base name (recursion through the
    # dot-stripping rule).
    assert agl.to_unicode("A.sc.alt") == "A"


def test_zapf_glyph_list_does_not_resolve_latin_glyphs() -> None:
    # The Zapf glyph list is intentionally narrow — Latin letter glyph names
    # are not present and must not be answered to with an AGL fallback.
    zapf = GlyphList.ZAPF_DINGBATS
    # ``A`` is not in the Zapf glyph list.
    assert zapf.to_unicode("A") is None


def test_default_glyph_list_singleton_identity() -> None:
    # The DEFAULT and ZAPF_DINGBATS singletons must be stable across calls.
    assert GlyphList.get_default() is GlyphList.DEFAULT
    assert GlyphList.get_default_glyph_list() is GlyphList.DEFAULT
    assert GlyphList.get_adobe_glyph_list() is GlyphList.DEFAULT
    assert GlyphList.get_zapf_dingbats() is GlyphList.ZAPF_DINGBATS
    # The two are distinct.
    assert GlyphList.DEFAULT is not GlyphList.ZAPF_DINGBATS
