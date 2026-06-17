"""Spot-check the predefined fontbox encoding tables against the PDF
32000-1 Annex D tables and upstream PDFBox 3.0.7.

Each predefined encoding maps a byte code (0..255) to a PostScript glyph
name; those tables are spec data and must match upstream byte-for-byte.
These tests pin many well-known code -> name mappings (and their reverse
lookups) so a transposed pair or a missing high-byte entry is caught.

Ported parity intent from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/encoding/*Test.java``
plus PDF 32000-1 Annex D Tables D.1-D.5.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.encoding import (
    MacExpertEncoding,
    MacRomanEncoding,
    StandardEncoding,
    SymbolEncoding,
    WinAnsiEncoding,
    ZapfDingbatsEncoding,
)

WIN = WinAnsiEncoding.INSTANCE
STD = StandardEncoding.INSTANCE
MAC = MacRomanEncoding.INSTANCE
MEXP = MacExpertEncoding.INSTANCE
SYM = SymbolEncoding.INSTANCE
ZAPF = ZapfDingbatsEncoding.INSTANCE


# --------------------------------------------------------------------------
# WinAnsiEncoding (Annex D Table D.2 / D.3 windows column)
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("code", "name"),
    [
        (0x41, "A"),
        (0x20, "space"),
        (0x80, "Euro"),
        (0x82, "quotesinglbase"),
        (0x83, "florin"),
        (0x84, "quotedblbase"),
        (0x85, "ellipsis"),
        (0x86, "dagger"),
        (0x87, "daggerdbl"),
        (0x88, "circumflex"),
        (0x89, "perthousand"),
        (0x91, "quoteleft"),
        (0x92, "quoteright"),
        (0x93, "quotedblleft"),
        (0x94, "quotedblright"),
        (0x95, "bullet"),
        (0x96, "endash"),
        (0x97, "emdash"),
        (0x99, "trademark"),
        (0xA0, "nbspace"),
        (0xA9, "copyright"),
        (0xAD, "sfthyphen"),
        (0xAE, "registered"),
        (0xE9, "eacute"),
        (0xFF, "ydieresis"),
    ],
)
def test_win_ansi_code_to_name(code: int, name: str) -> None:
    assert WIN.get_name(code) == name


def test_win_ansi_reverse_lookup() -> None:
    assert WIN.get_code("Euro") == 0x80
    assert WIN.get_code("eacute") == 0xE9
    assert WIN.get_code("trademark") == 0x99
    assert WIN.get_code("space") == 0x20


def test_win_ansi_unused_codes_fill_with_bullet() -> None:
    # PDF spec: WinAnsi maps every unused code > 040 (octal) to bullet.
    assert WIN.get_name(0x81) == "bullet"
    assert WIN.get_name(0x8D) == "bullet"


# --------------------------------------------------------------------------
# StandardEncoding (Annex D Table D.2 std column) -- note the
# quoteright/quoteleft distinction that catches a quotesingle/grave mixup.
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("code", "name"),
    [
        (0x41, "A"),
        (0x20, "space"),
        (0x27, "quoteright"),   # NOT quotesingle in StandardEncoding
        (0x60, "quoteleft"),    # NOT grave in StandardEncoding
        (0xA1, "exclamdown"),
        (0xA2, "cent"),
        (0xA4, "fraction"),
        (0xA8, "currency"),
        (0xAA, "quotedblleft"),
        (0xAB, "guillemotleft"),
        (0xBF, "questiondown"),
        (0xC1, "grave"),
        (0xD0, "emdash"),
        (0xE1, "AE"),
        (0xF1, "ae"),
        (0xF9, "oslash"),
        (0xFA, "oe"),
    ],
)
def test_standard_code_to_name(code: int, name: str) -> None:
    assert STD.get_name(code) == name


def test_standard_has_no_quotesingle_at_0x27() -> None:
    # quotesingle / grave only exist in StandardEncoding via the bare ASCII
    # forms that map to quoteright / quoteleft respectively.
    assert STD.get_name(0x27) != "quotesingle"
    assert STD.get_name(0x60) != "grave"


def test_standard_reverse_lookup() -> None:
    assert STD.get_code("quoteright") == 0x27
    assert STD.get_code("quoteleft") == 0x60
    assert STD.get_code("exclamdown") == 0xA1


# --------------------------------------------------------------------------
# MacRomanEncoding (Annex D Table D.2 mac column)
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("code", "name"),
    [
        (0x41, "A"),
        (0x20, "space"),
        (0x80, "Adieresis"),
        (0x8E, "eacute"),
        (0xAA, "trademark"),
        (0xA5, "bullet"),
        (0xC9, "ellipsis"),
        (0xCA, "nbspace"),   # the PDFBox MacRoman-specific 0xCA entry
        (0xD0, "endash"),
        (0xD1, "emdash"),
        (0xD2, "quotedblleft"),
        (0xD3, "quotedblright"),
        (0xD4, "quoteleft"),
        (0xD5, "quoteright"),
        (0xDB, "currency"),
    ],
)
def test_mac_roman_code_to_name(code: int, name: str) -> None:
    assert MAC.get_name(code) == name


def test_mac_roman_has_nbspace_at_0xca() -> None:
    # Regression: 0xCA (0o312) -> "nbspace" was missing from the table.
    assert MAC.get_name(0xCA) == "nbspace"
    assert MAC.get_code("nbspace") == 0xCA


def test_mac_roman_reverse_lookup() -> None:
    assert MAC.get_code("trademark") == 0xAA
    assert MAC.get_code("endash") == 0xD0


# --------------------------------------------------------------------------
# MacExpertEncoding (Annex D Table D.4)
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("code", "name"),
    [
        (0x20, "space"),
        (0xBE, "AEsmall"),
        (0x21, "exclamsmall"),
    ],
)
def test_mac_expert_code_to_name(code: int, name: str) -> None:
    assert MEXP.get_name(code) == name


def test_mac_expert_reverse_lookup() -> None:
    assert MEXP.get_code("AEsmall") == 0xBE
    assert MEXP.get_code("space") == 0x20


# --------------------------------------------------------------------------
# SymbolEncoding (Annex D Table D.5)
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("code", "name"),
    [
        (0x61, "alpha"),
        (0x62, "beta"),
        (0x42, "Beta"),
        (0x70, "pi"),
        (0xA7, "club"),
        (0xB0, "degree"),
        (0xB7, "bullet"),
    ],
)
def test_symbol_code_to_name(code: int, name: str) -> None:
    assert SYM.get_name(code) == name


def test_symbol_reverse_lookup() -> None:
    assert SYM.get_code("alpha") == 0x61
    assert SYM.get_code("pi") == 0x70


# --------------------------------------------------------------------------
# ZapfDingbatsEncoding (Annex D Table D.6) -- names are a1..a202
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("code", "name"),
    [
        (0x40, "a9"),
        (0x41, "a10"),
        (0xA7, "a108"),
        (0xE4, "a174"),
    ],
)
def test_zapf_code_to_name(code: int, name: str) -> None:
    assert ZAPF.get_name(code) == name


def test_zapf_reverse_lookup() -> None:
    assert ZAPF.get_code("a9") == 0x40
    assert ZAPF.get_code("a10") == 0x41


# --------------------------------------------------------------------------
# Cross-encoding invariants
# --------------------------------------------------------------------------
def test_unmapped_code_returns_notdef() -> None:
    for enc in (STD, MAC, MEXP, SYM, ZAPF):
        # code 0 is never mapped in any of these tables
        assert enc.get_name(0) == ".notdef"


def test_get_code_unknown_name_is_none() -> None:
    for enc in (WIN, STD, MAC, MEXP, SYM, ZAPF):
        assert enc.get_code("this_glyph_does_not_exist") is None


def test_name_to_code_map_is_a_snapshot_copy() -> None:
    m = STD.get_name_to_code_map()
    m["A"] = 999
    assert STD.get_code("A") == 0x41


def test_code_to_name_map_is_a_snapshot_copy() -> None:
    m = MAC.get_code_to_name_map()
    m[0x41] = "BOGUS"
    assert MAC.get_name(0x41) == "A"


def test_encoding_names() -> None:
    assert WIN.get_encoding_name() == "WinAnsiEncoding"
    assert STD.get_encoding_name() == "StandardEncoding"
    assert MAC.get_encoding_name() == "MacRomanEncoding"
