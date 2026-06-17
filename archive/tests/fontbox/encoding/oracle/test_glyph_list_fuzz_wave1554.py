"""Differential-fuzz parity for GlyphList.to_unicode + the built-in encodings.

Wave 1554. Complements ``test_glyph_list_oracle.py`` (which runs a single-list
name battery through ``GlyphListProbe``) and ``SymbolEncodingProbe`` (the
Standard-14 font path) by combining, in one ``GlyphListFuzzProbe`` run:

* a harder glyph-name battery for the algorithmic ``uniXXXX`` / ``uXXXX``
  synthesis — odd-length names, non-hex digits, mixed-case hex, the exact
  surrogate / disallowed-area boundaries (U+D7FF synthesizes, U+D800..U+DFFF
  reject, U+E000 synthesizes), a leading-dot name (``.notdef.alt``), a
  multi-dot suffix (``a.sc.alt``), a whitespace name, a very long name, and
  dingbat ``aNN`` / ``gNN`` / ``cidNN`` names against the AGL; and
* a sweep of the five predefined encodings' ``get_name(code)`` over the
  boundary codes 0, 32, 127, 128, 160, 255.

Expected values below are pinned from Apache PDFBox 3.0.7
(``GlyphList.getAdobeGlyphList().toUnicode`` and the
``StandardEncoding`` / ``WinAnsiEncoding`` / ``MacRomanEncoding`` /
``SymbolEncoding`` / ``ZapfDingbatsEncoding`` ``INSTANCE.getName(int)``
singletons), captured via ``oracle/probes/GlyphListFuzzProbe.java``. The
value-based tests run everywhere; the ``@requires_oracle`` test re-derives the
same table from the live jar so a future upstream drift is caught.

Honest divergence notes:
* ``.notdef.alt`` -> ``None``: upstream strips a suffix only when
  ``indexOf('.') > 0``; a leading dot (index 0) is NOT stripped, so the name
  falls through to the (failing) uni/u synthesis and returns null. pypdfbox's
  ``_derive`` gates identically on ``dot > 0``.
* ``a.sc.alt`` -> ``U+0061``: upstream recurses on the substring before the
  FIRST dot (``"a"``), not the last. pypdfbox uses ``name.find(".")`` (first
  dot) to match.
* ``uniDeAd`` -> ``None``: 0xDEAD lands in the disallowed surrogate area, so
  even though every digit is valid hex the synthesis is rejected.
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.fontbox.encoding.glyph_list import GlyphList
from pypdfbox.fontbox.encoding.mac_roman_encoding import MacRomanEncoding
from pypdfbox.fontbox.encoding.standard_encoding import StandardEncoding
from pypdfbox.fontbox.encoding.symbol_encoding import SymbolEncoding
from pypdfbox.fontbox.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.fontbox.encoding.zapf_dingbats_encoding import ZapfDingbatsEncoding
from tests.oracle.harness import requires_oracle, run_probe_text

_GLYPH_LOGGER = "pypdfbox.fontbox.encoding.glyph_list"

# name -> expected toUnicode rendering ("NULL" or space-separated U+XXXX),
# pinned from PDFBox 3.0.7 via GlyphListFuzzProbe. Empty string keyed "(empty)".
_GLYPH_EXPECTED: dict[str, str] = {
    # known AGL names
    "A": "U+0041",
    "space": "U+0020",
    "Euro": "U+20AC",
    "bullet": "U+2022",
    # uniXXXX valid
    "uni0041": "U+0041",
    "uni20AC": "U+20AC",
    "uniFFFF": "U+FFFF",
    "uni0000": "U+0000",
    # uniXXXX case sensitivity (hex is case-insensitive; both resolve)
    "uniabcd": "U+ABCD",
    "uniABCD": "U+ABCD",
    "uniDeAd": "NULL",  # 0xDEAD is in the disallowed surrogate area
    # uniXXXX wrong length -> NULL
    "uni041": "NULL",
    "uni00041": "NULL",
    "uni0041AB": "NULL",
    # uniXXXX non-hex -> NULL
    "uniGGGG": "NULL",
    "uniXY12": "NULL",
    "uni00G1": "NULL",
    # uXXXX valid
    "u0041": "U+0041",
    "u20AC": "U+20AC",
    "uFFFF": "U+FFFF",
    # uXXXX wrong length -> NULL
    "u041": "NULL",
    "u00041": "NULL",
    "u041234": "NULL",
    "u0412345": "NULL",
    # u case + non-hex
    "uabcd": "U+ABCD",
    "uGGGG": "NULL",
    # surrogate / disallowed-area boundaries
    "uniD7FF": "U+D7FF",
    "uniD800": "NULL",
    "uniDFFF": "NULL",
    "uniE000": "U+E000",
    "uD800": "NULL",
    "uDFFF": "NULL",
    # multi-code-point uni run -> NULL (upstream does not synthesize)
    "uni00410042": "NULL",
    # dotted suffix stripping
    "a.sc": "U+0061",
    "one.oldstyle": "U+0031",
    "A.sc": "U+0041",
    "uni0041.sc": "U+0041",
    "g123.alt": "NULL",
    # multi-dot + leading-dot suffix edge cases
    "a.sc.alt": "U+0061",
    ".notdef": "NULL",
    ".notdef.alt": "NULL",
    # ligatures (multi-code-point AGL values)
    "ff": "U+FB00",
    "ffi": "U+FB03",
    "fi": "U+FB01",
    "fl": "U+FB02",
    "ffl": "U+FB04",
    # gNN / cidNN / dingbat aNN against the AGL (no entry, no synthesis)
    "g65": "NULL",
    "cid65": "NULL",
    "a10": "NULL",
    # whitespace / very long / unknown
    "  ": "NULL",
    "averylongglyphnamethatisdefinitelynotinanyadobeglyphlistatall": "NULL",
    "notaglyph": "NULL",
    "fi_lig": "NULL",
    "(empty)": "NULL",
}

# (encoding-id, code) -> expected getName(code), pinned from PDFBox 3.0.7.
_CODES: tuple[int, ...] = (0, 32, 127, 128, 160, 255)
_ENCODING_EXPECTED: dict[tuple[str, int], str] = {
    ("Standard", 0): ".notdef",
    ("Standard", 32): "space",
    ("Standard", 127): ".notdef",
    ("Standard", 128): ".notdef",
    ("Standard", 160): ".notdef",
    ("Standard", 255): ".notdef",
    ("WinAnsi", 0): ".notdef",
    ("WinAnsi", 32): "space",
    ("WinAnsi", 127): "bullet",
    ("WinAnsi", 128): "Euro",
    ("WinAnsi", 160): "nbspace",
    ("WinAnsi", 255): "ydieresis",
    ("MacRoman", 0): ".notdef",
    ("MacRoman", 32): "space",
    ("MacRoman", 127): ".notdef",
    ("MacRoman", 128): "Adieresis",
    ("MacRoman", 160): "dagger",
    ("MacRoman", 255): "caron",
    ("Symbol", 0): ".notdef",
    ("Symbol", 32): "space",
    ("Symbol", 127): ".notdef",
    ("Symbol", 128): ".notdef",
    ("Symbol", 160): "Euro",
    ("Symbol", 255): ".notdef",
    ("ZapfDingbats", 0): ".notdef",
    ("ZapfDingbats", 32): "space",
    ("ZapfDingbats", 127): ".notdef",
    ("ZapfDingbats", 128): ".notdef",
    ("ZapfDingbats", 160): ".notdef",
    ("ZapfDingbats", 255): ".notdef",
}

_ENCODINGS = {
    "Standard": StandardEncoding.INSTANCE,
    "WinAnsi": WinAnsiEncoding.INSTANCE,
    "MacRoman": MacRomanEncoding.INSTANCE,
    "Symbol": SymbolEncoding.INSTANCE,
    "ZapfDingbats": ZapfDingbatsEncoding.INSTANCE,
}


def _format(unicode: str | None) -> str:
    """Render to_unicode the same way GlyphListFuzzProbe.java does."""
    if unicode is None:
        return "NULL"
    return " ".join(f"U+{ord(c):04X}" for c in unicode)


def _name_for_key(key: str) -> str:
    """Map the probe's "(empty)" sentinel back to the real glyph name."""
    return "" if key == "(empty)" else key


# -- value-based parity (runs everywhere) ----------------------------------


@pytest.mark.parametrize("key", sorted(_GLYPH_EXPECTED))
def test_glyph_to_unicode_matches_pdfbox(key, caplog):
    """pypdfbox AGL to_unicode == pinned PDFBox 3.0.7 value per edge name."""
    caplog.set_level(logging.ERROR, logger=_GLYPH_LOGGER)
    agl = GlyphList.get_adobe_glyph_list()
    name = _name_for_key(key)
    assert _format(agl.to_unicode(name)) == _GLYPH_EXPECTED[key]


@pytest.mark.parametrize(("enc_id", "code"), sorted(_ENCODING_EXPECTED))
def test_builtin_encoding_get_name_matches_pdfbox(enc_id, code):
    """pypdfbox encoding get_name == pinned PDFBox 3.0.7 value per boundary code."""
    assert _ENCODINGS[enc_id].get_name(code) == _ENCODING_EXPECTED[(enc_id, code)]


# -- live differential oracle (skips without java + jar) -------------------


def _run_probe() -> tuple[dict[str, str], dict[tuple[str, int], str]]:
    out = run_probe_text("GlyphListFuzzProbe")
    glyphs: dict[str, str] = {}
    encs: dict[tuple[str, int], str] = {}
    for line in out.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if parts[0] == "G":
            glyphs[parts[1]] = parts[2]
        elif parts[0] == "E":
            encs[(parts[1], int(parts[2]))] = parts[3]
    return glyphs, encs


@requires_oracle
def test_fuzz_probe_matches_pinned_expectations(caplog):
    """The live PDFBox jar reproduces the pinned expected tables exactly.

    Guards against silent upstream drift in the pinned values and confirms the
    pypdfbox side agrees with the live oracle name-by-name and code-by-code.
    """
    caplog.set_level(logging.ERROR, logger=_GLYPH_LOGGER)
    oracle_glyphs, oracle_encs = _run_probe()

    assert oracle_glyphs == _GLYPH_EXPECTED
    assert oracle_encs == _ENCODING_EXPECTED

    agl = GlyphList.get_adobe_glyph_list()
    glyph_mismatches = {
        key: (_format(agl.to_unicode(_name_for_key(key))), oracle_glyphs[key])
        for key in oracle_glyphs
        if _format(agl.to_unicode(_name_for_key(key))) != oracle_glyphs[key]
    }
    assert not glyph_mismatches, glyph_mismatches

    enc_mismatches = {
        (eid, code): (_ENCODINGS[eid].get_name(code), oracle_encs[(eid, code)])
        for (eid, code) in oracle_encs
        if _ENCODINGS[eid].get_name(code) != oracle_encs[(eid, code)]
    }
    assert not enc_mismatches, enc_mismatches
