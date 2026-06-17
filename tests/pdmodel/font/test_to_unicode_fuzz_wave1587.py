"""Fuzz pins for the ``PDFont.to_unicode`` / ``/ToUnicode`` extraction chain.

Hammers the code -> Unicode resolution surface end to end:

* a ``/ToUnicode`` CMap mapping a code to a single char (bfchar), to a
  multi-char ligature string (``"ffi"``), to a surrogate-pair codepoint
  (``U+1F600`` via a ``<D83DDE00>`` UTF-16BE surrogate pair), and to a
  contiguous / array-form ``bfrange``;
* the edge destinations ``U+0000`` (explicit NUL) and ``U+FFFD``
  (replacement char) and the empty ``<>`` destination — which PDFBox
  decodes to a single ``U+0000``, *not* ``""`` and *not* ``(none)``;
* the simple-font fallback chain: ``/ToUnicode`` wins when present, then
  ``encoding -> glyph name -> Adobe Glyph List`` when ``/ToUnicode`` is
  absent or lacks the code, then ``None`` when nothing maps;
* the ``Identity-*`` ``/ToUnicode`` fixup (PDFBOX-3123 / PDFBOX-4322 /
  PDFBOX-3550): a ``COSName`` ``/Identity-H`` ``/ToUnicode`` or a stream
  CMap with no Unicode mappings maps each code to ``chr(code)``, but a
  stream CMap that *does* carry real bf-mappings (even one literally
  named ``/Identity-H``) must use those mappings, not ``chr(code)``;
* Type0 / Identity-H resolution via the embedded ``/ToUnicode`` (with the
  Type0 ``has_unicode_mappings`` short-circuit) and the ``None`` return
  for a code absent from every Type0 source.

Cross-checked against Apache PDFBox 3.0.7 via the existing live oracle
probe ``ToUnicodeResolveFuzzProbe`` (see
``tests/pdmodel/font/oracle/test_to_unicode_resolve_fuzz_wave1554.py``);
this module is hand-written and pins the values so the chain is locked
even where the oracle jar is unavailable.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.fontbox.cmap import CMapParser
from pypdfbox.pdmodel.font import PDFontFactory

_TYPE: COSName = COSName.get_pdf_name("Type")
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_BASE_FONT: COSName = COSName.get_pdf_name("BaseFont")
_ENCODING: COSName = COSName.get_pdf_name("Encoding")
_TO_UNICODE: COSName = COSName.get_pdf_name("ToUnicode")
_DESCENDANT_FONTS: COSName = COSName.get_pdf_name("DescendantFonts")


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _make_stream(text: str) -> COSStream:
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(text.encode("ascii"))
    return stream


def _cmap_header(name: str = "Adobe-Identity-UCS", csr: str = "<0000> <FFFF>") -> str:
    return (
        "/CIDInit /ProcSet findresource begin\n"
        "12 dict begin\nbegincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        f"/CMapName /{name} def\n/CMapType 2 def\n"
        f"1 begincodespacerange\n{csr}\nendcodespacerange\n"
    )


def _cmap_footer() -> str:
    return "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"


# Rich /ToUnicode program exercising bfchar single / multi-char / surrogate
# pair + contiguous bfrange + array bfrange + the edge destinations.
_RICH_CMAP = (
    _cmap_header()
    + "5 beginbfchar\n"
    + "<0041> <0041>\n"  # single char 'A'
    + "<0042> <006600660069>\n"  # ligature -> "ffi"
    + "<0043> <D83DDE00>\n"  # surrogate pair -> U+1F600
    + "<0044> <0000>\n"  # explicit NUL
    + "<0045> <FFFD>\n"  # replacement char
    + "endbfchar\n"
    + "2 beginbfrange\n"
    + "<0050> <0052> <0061>\n"  # contiguous -> a b c
    + "<0060> <0062> [<0078> <0079007A> <0058>]\n"  # array -> x, yz, X
    + "endbfrange\n"
    + _cmap_footer()
)


# --------------------------------------------------------------------------- #
# (A) Raw /ToUnicode CMap decode — bfchar / bfrange destinations.
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def rich_cmap() -> object:
    return CMapParser().parse(_RICH_CMAP.encode("ascii"))


def test_bfchar_single_char(rich_cmap: object) -> None:
    assert rich_cmap.to_unicode(0x0041) == "A"


def test_bfchar_ligature_multichar_not_truncated(rich_cmap: object) -> None:
    # The multi-char destination must survive in full, not be truncated to
    # its first code unit.
    assert rich_cmap.to_unicode(0x0042) == "ffi"


def test_bfchar_surrogate_pair_decoded(rich_cmap: object) -> None:
    # <D83DDE00> is a UTF-16BE surrogate pair -> single codepoint U+1F600.
    mapped = rich_cmap.to_unicode(0x0043)
    assert mapped == "\U0001f600"
    assert len(mapped) == 1
    assert ord(mapped) == 0x1F600


def test_bfchar_explicit_nul_destination(rich_cmap: object) -> None:
    # An explicit <0000> destination decodes to U+0000 (one NUL char), not
    # "" and not None.
    assert rich_cmap.to_unicode(0x0044) == "\x00"


def test_bfchar_replacement_char_destination(rich_cmap: object) -> None:
    assert rich_cmap.to_unicode(0x0045) == "�"


def test_bfrange_contiguous(rich_cmap: object) -> None:
    assert rich_cmap.to_unicode(0x0050) == "a"
    assert rich_cmap.to_unicode(0x0051) == "b"
    assert rich_cmap.to_unicode(0x0052) == "c"


def test_bfrange_array_form_multichar(rich_cmap: object) -> None:
    assert rich_cmap.to_unicode(0x0060) == "x"
    assert rich_cmap.to_unicode(0x0061) == "yz"  # multi-char array entry
    assert rich_cmap.to_unicode(0x0062) == "X"


def test_unmapped_code_is_none(rich_cmap: object) -> None:
    assert rich_cmap.to_unicode(0x7FFF) is None


def test_empty_bfchar_destination_is_single_nul() -> None:
    # PDFBox decodes <> via getMapping([]) -> twoByteMappings.get(0) == "\x00".
    text = (
        _cmap_header()
        + "1 beginbfchar\n<0001> <>\nendbfchar\n"
        + _cmap_footer()
    )
    cmap = CMapParser().parse(text.encode("ascii"))
    mapped = cmap.to_unicode(0x0001)
    assert mapped == "\x00"
    assert mapped is not None
    assert mapped != ""


def test_surrogate_boundary_bfrange_no_lone_surrogates() -> None:
    # <0005> <0007> <D7FF> would increment into the lone-high-surrogate block
    # (D800, D801); PDFBox replaces those with U+FFFD rather than emitting a
    # lone surrogate.
    text = (
        _cmap_header()
        + "1 beginbfrange\n<0005> <0007> <D7FF>\nendbfrange\n"
        + _cmap_footer()
    )
    cmap = CMapParser().parse(text.encode("ascii"))
    assert cmap.to_unicode(0x0005) == "퟿"
    assert cmap.to_unicode(0x0006) == "�"
    assert cmap.to_unicode(0x0007) == "�"


def test_one_byte_mapping_wins_over_two_byte_for_low_code() -> None:
    # CMap.toUnicode(int) tries the 1-byte table first for code < 256.
    text = (
        _cmap_header(csr="<00> <FFFF>")
        + "2 beginbfchar\n<41> <0058>\n<0041> <0059>\nendbfchar\n"
        + _cmap_footer()
    )
    cmap = CMapParser().parse(text.encode("ascii"))
    assert cmap.to_unicode(0x41) == "X"
    assert cmap.to_unicode_with_length(0x41, 1) == "X"
    assert cmap.to_unicode_with_length(0x41, 2) == "Y"


# --------------------------------------------------------------------------- #
# (B) Simple-font resolution chain (/ToUnicode -> encoding -> AGL -> None).
# --------------------------------------------------------------------------- #


def _build_simple(*, with_to_unicode: bool, cmap_text: str = "") -> object:
    font = COSDictionary()
    font.set_name(_TYPE, "Font")
    font.set_name(_SUBTYPE, "Type1")
    font.set_name(_BASE_FONT, "Helvetica")
    font.set_name(_ENCODING, "WinAnsiEncoding")
    if with_to_unicode:
        font.set_item(_TO_UNICODE, _make_stream(cmap_text))
    return PDFontFactory.create_font(font)


# Simple-font /ToUnicode mapping 0x41 -> PUA U+E001 (overrides encoding 'A').
_SIMPLE_OVERRIDE_CMAP = (
    _cmap_header(csr="<00> <FF>")
    + "1 beginbfchar\n<41> <E001>\nendbfchar\n"
    + _cmap_footer()
)


def test_simple_no_to_unicode_encoding_to_agl() -> None:
    # No /ToUnicode at all -> encoding -> glyph name -> AGL.
    font = _build_simple(with_to_unicode=False)
    assert font.to_unicode(0x41) == "A"  # WinAnsi 'A' -> U+0041
    assert font.to_unicode(0x80) == "€"  # WinAnsi 'Euro' -> U+20AC
    assert font.to_unicode(0x7F) == "•"  # WinAnsi 'bullet' -> U+2022


def test_simple_to_unicode_wins_over_encoding() -> None:
    font = _build_simple(with_to_unicode=True, cmap_text=_SIMPLE_OVERRIDE_CMAP)
    # 0x41 is in /ToUnicode -> PUA, overriding the encoding 'A'.
    assert font.to_unicode(0x41) == "\ue001"
    # 0x42 is absent from /ToUnicode -> encoding fallback 'B'.
    assert font.to_unicode(0x42) == "B"


def test_simple_no_mapping_anywhere_is_none() -> None:
    # 0x00 has no glyph in WinAnsi and no /ToUnicode -> None (not ""). The
    # 0x80-0x9F "undefined" slots fall back to WinAnsi's bullet glyph, so they
    # would NOT be None; a control code with no glyph name is the true gap.
    font = _build_simple(with_to_unicode=False)
    assert font.to_unicode(0x00) is None
    assert font.to_unicode(0x01) is None


def test_simple_ligature_via_to_unicode() -> None:
    cmap_text = (
        _cmap_header(csr="<00> <FF>")
        + "1 beginbfchar\n<46> <006600660069>\nendbfchar\n"
        + _cmap_footer()
    )
    font = _build_simple(with_to_unicode=True, cmap_text=cmap_text)
    assert font.to_unicode(0x46) == "ffi"


def test_simple_surrogate_pair_via_to_unicode() -> None:
    cmap_text = (
        _cmap_header(csr="<00> <FF>")
        + "1 beginbfchar\n<47> <D83DDE00>\nendbfchar\n"
        + _cmap_footer()
    )
    font = _build_simple(with_to_unicode=True, cmap_text=cmap_text)
    assert font.to_unicode(0x47) == "\U0001f600"


def test_simple_identity_named_to_unicode_with_real_mappings_uses_them() -> None:
    # A /ToUnicode stream CMap literally named /Identity-H but carrying real
    # bf-mappings must use them — NOT the chr(code) Identity fixup.
    cmap_text = (
        _cmap_header(name="Identity-H", csr="<00> <FF>")
        + "1 beginbfchar\n<41> <2660>\nendbfchar\n"
        + _cmap_footer()
    )
    font = _build_simple(with_to_unicode=True, cmap_text=cmap_text)
    assert font.to_unicode(0x41) == "♠"  # spade, not 'A'


def test_simple_identity_named_to_unicode_no_mappings_is_chr_code() -> None:
    # An Identity-named /ToUnicode stream with NO bf-mappings triggers the
    # PDFBOX-3123 fixup: each code maps to chr(code).
    cmap_text = _cmap_header(name="Identity-H", csr="<00> <FF>") + _cmap_footer()
    font = _build_simple(with_to_unicode=True, cmap_text=cmap_text)
    assert font.to_unicode(0x41) == "A"
    assert font.to_unicode(0x80) == "\x80"


# --------------------------------------------------------------------------- #
# (C) Type0 resolution via the embedded /ToUnicode.
# --------------------------------------------------------------------------- #


def _build_type0(to_unicode_text: str, *, ordering: str = "Identity") -> object:
    cid = COSDictionary()
    cid.set_name(_TYPE, "Font")
    cid.set_name(_SUBTYPE, "CIDFontType2")
    cid.set_name(_BASE_FONT, "ABCDEF+TestFont")
    si = COSDictionary()
    si.set_string(_name("Registry"), "Adobe")
    si.set_string(_name("Ordering"), ordering)
    si.set_int(_name("Supplement"), 0)
    cid.set_item(_name("CIDSystemInfo"), si)
    cid.set_int(_name("DW"), 1000)

    font = COSDictionary()
    font.set_name(_TYPE, "Font")
    font.set_name(_SUBTYPE, "Type0")
    font.set_name(_BASE_FONT, "ABCDEF+TestFont")
    font.set_name(_ENCODING, "Identity-H")
    arr = COSArray()
    arr.add(cid)
    font.set_item(_DESCENDANT_FONTS, arr)
    font.set_item(_TO_UNICODE, _make_stream(to_unicode_text))
    return PDFontFactory.create_font(font)


def test_type0_to_unicode_present() -> None:
    font = _build_type0(_RICH_CMAP)
    assert font.to_unicode(0x0041) == "A"
    assert font.to_unicode(0x0042) == "ffi"
    assert font.to_unicode(0x0043) == "\U0001f600"


def test_type0_to_unicode_absent_is_none() -> None:
    # A code with no /ToUnicode and no UCS2 / embedded fallback -> None.
    font = _build_type0(_RICH_CMAP)
    assert font.to_unicode(0x7FFF) is None


def test_type0_to_unicode_nul_destination() -> None:
    font = _build_type0(_RICH_CMAP)
    assert font.to_unicode(0x0044) == "\x00"


def test_type0_identity_named_to_unicode_with_mappings_uses_them() -> None:
    # Type0 has its own to_unicode that short-circuits on has_unicode_mappings;
    # an Identity-named /ToUnicode stream with real mappings still wins.
    cmap_text = (
        _cmap_header(name="Identity-H")
        + "1 beginbfchar\n<0041> <2660>\nendbfchar\n"
        + _cmap_footer()
    )
    font = _build_type0(cmap_text)
    assert font.to_unicode(0x0041) == "♠"


def test_type0_to_unicode_array_bfrange() -> None:
    font = _build_type0(_RICH_CMAP)
    assert font.to_unicode(0x0060) == "x"
    assert font.to_unicode(0x0061) == "yz"
    assert font.to_unicode(0x0062) == "X"
