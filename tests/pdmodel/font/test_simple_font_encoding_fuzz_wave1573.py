"""Fuzz / parity coverage for PDSimpleFont encoding resolution (wave 1573).

Hammers the ``/Encoding`` resolution chain shared by ``PDType1Font`` /
``PDTrueTypeFont`` / ``PDSimpleFont``:

* base-encoding-name resolution (Standard / WinAnsi / MacRoman code -> glyph
  name) against the values produced by upstream PDFBox 3.0.7,
* ``/Differences`` array parsing — the ``[code /n1 /n2 code2 /n3 ...]`` form
  where an integer resets the running code and consecutive names increment
  from it,
* ``/Differences`` overriding the base encoding for specific codes,
* missing / invalid ``/BaseEncoding`` falling back to StandardEncoding
  (non-symbolic) or the built-in (symbolic),
* unmapped codes resolving to ``".notdef"`` (never ``None`` for ``get_name``),
* glyph-name -> unicode via the Adobe Glyph List,
* the malformed "leading name before any integer marker" case (upstream lands
  it at code ``-1``; verified live wave 1548).

These are hand-written parity assertions cross-checked against the upstream
Java behaviour (DictionaryEncoding.applyDifferences / Encoding.overwrite /
Encoding.add), not a direct JUnit port — there is no upstream
``DictionaryEncodingTest`` to translate.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.fontbox.encoding.glyph_list import GlyphList
from pypdfbox.pdmodel.font.encoding.dictionary_encoding import DictionaryEncoding
from pypdfbox.pdmodel.font.encoding.encoding import Encoding
from pypdfbox.pdmodel.font.encoding.mac_roman_encoding import MacRomanEncoding
from pypdfbox.pdmodel.font.encoding.standard_encoding import StandardEncoding
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _diff_array(entries: list[int | str]) -> COSArray:
    """Build a /Differences COSArray from a flat list of ints and glyph-name
    strings (ints become COSInteger markers, strings become COSName glyphs)."""
    arr = COSArray()
    for e in entries:
        if isinstance(e, int):
            arr.add(COSInteger.get(e))
        else:
            arr.add(_name(e))
    return arr


def _dict_encoding(
    base: str | None = None,
    differences: list[int | str] | None = None,
    *,
    is_non_symbolic: bool | None = True,
    built_in: Encoding | None = None,
) -> DictionaryEncoding:
    d = COSDictionary()
    if base is not None:
        d.set_item(_name("BaseEncoding"), _name(base))
    if differences is not None:
        d.set_item(_name("Differences"), _diff_array(differences))
    return DictionaryEncoding(
        font_encoding=d, is_non_symbolic=is_non_symbolic, built_in=built_in
    )


# --------------------------------------------------------------------------
# base encoding name -> glyph name
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (65, "A"),
        (66, "B"),
        (90, "Z"),
        (97, "a"),
        (122, "z"),
        (32, "space"),
        (48, "zero"),
        (39, "quoteright"),  # StandardEncoding 0x27 -> quoteright (not quotesingle)
        (96, "quoteleft"),
        (0o247, "section"),
        (0o251, "quotesingle"),
        (7, ".notdef"),  # unmapped low code
        (0xE9, "Oslash"),  # Standard high code is NOT eacute
    ],
)
def test_standard_encoding_code_to_name(code: int, expected: str) -> None:
    assert StandardEncoding.INSTANCE.get_name(code) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (65, "A"),
        (122, "z"),
        (32, "space"),
        (39, "quotesingle"),  # WinAnsi 0x27 -> quotesingle (diverges from Standard)
        (96, "grave"),
        (0x80, "Euro"),
        (0x91, "quoteleft"),
        (0x92, "quoteright"),
        (0xA0, "nbspace"),
        (0xAD, "sfthyphen"),
        (0xE9, "eacute"),
        (0xFF, "ydieresis"),
        (0x95, "bullet"),  # explicit bullet position 0o225
    ],
)
def test_win_ansi_encoding_code_to_name(code: int, expected: str) -> None:
    assert WinAnsiEncoding.INSTANCE.get_name(code) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (65, "A"),
        (122, "z"),
        (32, "space"),
        (0o200, "Adieresis"),
        (0o312, "nbspace"),  # PDFBOX-1611 override
        (165, "bullet"),
        (0xD0, "endash"),
    ],
)
def test_mac_roman_encoding_code_to_name(code: int, expected: str) -> None:
    assert MacRomanEncoding.INSTANCE.get_name(code) == expected


def test_win_ansi_bullet_fill_in_high_codes() -> None:
    # Every otherwise-unused code in 0o41..255 maps to bullet (spec fill-in).
    enc = WinAnsiEncoding.INSTANCE
    assert enc.get_name(0x81) == "bullet"
    assert enc.get_name(0x8D) == "bullet"
    assert enc.is_bullet_fill_code(0x81)
    assert not enc.is_bullet_fill_code(0x95)  # explicit bullet is not a fill-in


# --------------------------------------------------------------------------
# /Differences array parsing — code increment semantics
# --------------------------------------------------------------------------


def test_differences_basic_increment() -> None:
    # [65 /B /C /D] => 65->B, 66->C, 67->D (consecutive names increment)
    enc = _dict_encoding(base="WinAnsiEncoding", differences=[65, "B", "C", "D"])
    assert enc.get_name(65) == "B"
    assert enc.get_name(66) == "C"
    assert enc.get_name(67) == "D"
    # 68 falls through to the base encoding (WinAnsi 'D').
    assert enc.get_name(68) == "D"
    assert enc.get_differences() == {65: "B", 66: "C", 67: "D"}


def test_differences_multiple_markers() -> None:
    enc = _dict_encoding(
        base="WinAnsiEncoding",
        differences=[1, "a", "b", 100, "x", 200, "eacute"],
    )
    assert enc.get_name(1) == "a"
    assert enc.get_name(2) == "b"
    assert enc.get_name(100) == "x"
    assert enc.get_name(101) == "e"  # WinAnsi base 0x65 -> 'e'
    assert enc.get_name(200) == "eacute"
    assert enc.get_differences() == {1: "a", 2: "b", 100: "x", 200: "eacute"}


def test_differences_override_base() -> None:
    # Override a single code; surrounding codes keep the base mapping.
    enc = _dict_encoding(base="WinAnsiEncoding", differences=[65, "Alpha"])
    assert enc.get_name(65) == "Alpha"
    assert enc.get_name(64) == "at"  # base WinAnsi 0x40
    assert enc.get_name(66) == "B"  # base WinAnsi 0x42
    assert enc.get_base_encoding_name() == "WinAnsiEncoding"


def test_differences_empty_array_is_pure_base() -> None:
    enc = _dict_encoding(base="MacRomanEncoding", differences=[])
    assert enc.get_name(65) == "A"
    assert enc.get_differences() == {}
    assert enc.has_differences()  # the key is present (empty array)


def test_differences_no_array_is_pure_base() -> None:
    enc = _dict_encoding(base="StandardEncoding", differences=None)
    assert enc.get_name(65) == "A"
    assert not enc.has_differences()
    assert enc.get_differences() == {}


# --------------------------------------------------------------------------
# missing / invalid base encoding fallback
# --------------------------------------------------------------------------


def test_missing_base_non_symbolic_falls_back_to_standard() -> None:
    enc = _dict_encoding(base=None, differences=[65, "B"], is_non_symbolic=True)
    assert enc.get_base_encoding_name() == "StandardEncoding"
    assert enc.get_name(65) == "B"
    assert enc.get_name(66) == "B"  # Standard 0x42 -> B


def test_invalid_base_name_non_symbolic_falls_back_to_standard() -> None:
    # /BaseEncoding /PDFDocEncoding is not a valid Encoding.getInstance name.
    enc = _dict_encoding(
        base="PDFDocEncoding", differences=[65, "B"], is_non_symbolic=True
    )
    assert enc.get_base_encoding_name() == "StandardEncoding"
    assert enc.get_name(65) == "B"
    assert enc.get_encoding_name() == "StandardEncoding with differences"


def test_missing_base_symbolic_uses_built_in() -> None:
    built_in = WinAnsiEncoding.INSTANCE
    enc = _dict_encoding(
        base=None, differences=[65, "B"], is_non_symbolic=False, built_in=built_in
    )
    assert enc.get_base_encoding() is built_in
    assert enc.get_name(0xE9) == "eacute"  # from WinAnsi built-in
    assert enc.get_name(65) == "B"  # override


def test_symbolic_without_built_in_raises() -> None:
    d = COSDictionary()
    d.set_item(_name("Differences"), _diff_array([65, "B"]))
    with pytest.raises(ValueError, match="built-in"):
        DictionaryEncoding(font_encoding=d, is_non_symbolic=False, built_in=None)


def test_valid_base_name_used_directly() -> None:
    enc = _dict_encoding(base="WinAnsiEncoding", differences=None, is_non_symbolic=True)
    assert enc.get_base_encoding_name() == "WinAnsiEncoding"
    assert enc.get_name(0x80) == "Euro"


# --------------------------------------------------------------------------
# Type 3 mode (no implicit base) and unmapped codes
# --------------------------------------------------------------------------


def test_type3_mode_no_base() -> None:
    d = COSDictionary()
    d.set_item(_name("Differences"), _diff_array([65, "B", "C"]))
    enc = DictionaryEncoding(font_encoding=d)  # Type 3 constructor form
    assert enc.get_base_encoding() is None
    assert enc.is_type3()
    assert enc.get_name(65) == "B"
    assert enc.get_name(66) == "C"
    # Every non-overridden code is .notdef (the /Differences are the whole map).
    assert enc.get_name(67) == ".notdef"
    assert enc.get_name(90) == ".notdef"
    assert enc.get_encoding_name() == "differences"


def test_unmapped_code_returns_notdef_not_none() -> None:
    enc = _dict_encoding(base="StandardEncoding")
    # get_name uses getOrDefault(code, ".notdef") upstream — never None.
    assert enc.get_name(7) == ".notdef"
    assert enc.get_name(256) == ".notdef"
    assert enc.get_name(-5) == ".notdef"


# --------------------------------------------------------------------------
# malformed: leading name before any integer marker
# --------------------------------------------------------------------------


def test_leading_name_lands_at_minus_one() -> None:
    # Upstream applyDifferences starts currentIndex = -1 with no >= 0 guard;
    # a leading name before any marker lands at code -1 (verified live 1548).
    d = COSDictionary()
    d.set_item(_name("Differences"), _diff_array(["alpha", 65, "B"]))
    enc = DictionaryEncoding(font_encoding=d)
    assert enc.get_name(-1) == "alpha"
    assert enc.get_name(65) == "B"
    assert enc.get_differences() == {-1: "alpha", 65: "B"}


def test_negative_marker_then_name() -> None:
    d = COSDictionary()
    d.set_item(_name("Differences"), _diff_array([-3, "x", "y"]))
    enc = DictionaryEncoding(font_encoding=d)
    assert enc.get_name(-3) == "x"
    assert enc.get_name(-2) == "y"


# --------------------------------------------------------------------------
# glyph name -> unicode via the glyph list
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("A", "A"),
        ("eacute", "é"),
        ("nbspace", " "),
        ("sfthyphen", "­"),
        ("space", " "),
        ("bullet", "•"),
        ("Euro", "€"),
        ("uni00A0", " "),
        ("uni20AC", "€"),
        ("fi", "ﬁ"),
        (".notdef", None),
        ("g123.alt", None),  # unknown base, no AGL entry
    ],
)
def test_glyph_name_to_unicode(name: str, expected: str | None) -> None:
    assert GlyphList.DEFAULT.to_unicode(name) == expected


def test_code_to_unicode_through_win_ansi() -> None:
    # 0xE9 -> 'eacute' (WinAnsi) -> U+00E9 via the AGL.
    enc = WinAnsiEncoding.INSTANCE
    name = enc.get_name(0xE9)
    assert name == "eacute"
    assert GlyphList.DEFAULT.to_unicode(name) == "é"


def test_differences_unicode_resolution() -> None:
    # A /Differences override resolves all the way to unicode.
    enc = _dict_encoding(base="WinAnsiEncoding", differences=[65, "Euro"])
    name = enc.get_name(65)
    assert name == "Euro"
    assert GlyphList.DEFAULT.to_unicode(name) == "€"


# --------------------------------------------------------------------------
# reverse map: overwrite cleanup parity with upstream Encoding.overwrite
# --------------------------------------------------------------------------


def test_overwrite_removes_reverse_when_old_code_matches() -> None:
    # WinAnsi 'bullet' reverse maps to its explicit code 149 (0o225). Overriding
    # code 149 removes the 'bullet' reverse mapping entirely (upstream overwrite
    # semantics), even though many fill-in codes still map to 'bullet'.
    enc = _dict_encoding(base="WinAnsiEncoding", differences=[149, "foo"])
    assert enc.get_name(149) == "foo"
    assert enc.get_code("foo") == 149
    assert enc.get_code("bullet") is None
    # other fill-in bullet codes survive on the forward map.
    assert enc.get_name(0x81) == "bullet"


def test_reverse_map_last_code_wins_for_duplicate_difference_name() -> None:
    # [65 /dup 66 /dup] — both codes forward-map to 'dup'. /Differences are
    # applied via Encoding.overwrite (unconditional inverted.put), so the LAST
    # occurrence wins the reverse map (66), unlike the putIfAbsent semantics
    # of base-encoding construction.
    enc = _dict_encoding(base="WinAnsiEncoding", differences=[65, "dup", 66, "dup"])
    assert enc.get_name(65) == "dup"
    assert enc.get_name(66) == "dup"
    assert enc.get_code("dup") == 66
    assert enc.get_codes_for_name("dup") == [65, 66]


# --------------------------------------------------------------------------
# Encoding.get_instance factory
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("StandardEncoding", StandardEncoding),
        ("WinAnsiEncoding", WinAnsiEncoding),
        ("MacRomanEncoding", MacRomanEncoding),
    ],
)
def test_get_instance_predefined(name: str, expected: type) -> None:
    inst = Encoding.get_instance(_name(name))
    assert isinstance(inst, expected)


def test_get_instance_unknown_returns_none() -> None:
    assert Encoding.get_instance(_name("PDFDocEncoding")) is None
    assert Encoding.get_instance(None) is None
