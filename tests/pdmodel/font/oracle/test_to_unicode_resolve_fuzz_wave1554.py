"""Live PDFBox differential fuzz for ``PDFont.to_unicode(code)`` edge cases.

The existing ``test_to_unicode_oracle`` / ``test_to_unicode_simple_font_oracle``
modules pin the mainstream shapes (bfchar, contiguous / array bfrange, the two-
and three-char ligature, a single surrogate-pair destination, ToUnicode-wins-
over-encoding, and the encoding -> AGL fallback). This module fuzzes the *edge*
destinations and resolution branches those two miss, comparing every result
against Apache PDFBox 3.0.7 via ``oracle/probes/ToUnicodeResolveFuzzProbe.java``.

Two sub-surfaces, both emitting ``UNI <tag> <code> -> ...`` lines:

(A) RAW CMAP DECODE — a hand-built /ToUnicode program fed straight to the
    CMap parser (font-level fallbacks isolated out):

    * ``<0001> <>``    EMPTY bfchar destination. Java's CMapParser decodes the
      empty UTF-16BE hex string to a single ``U+0000`` (one NUL char), NOT to
      ``""`` and NOT to ``(none)``. pypdfbox matches.
    * ``<0002> <FFFD>``  the U+FFFD replacement char survives verbatim.
    * ``<0003> <0000>``  an explicit ``U+0000`` destination.
    * ``<0004> <E000>``  a Private Use Area codepoint.
    * ``<0005> <0007> <D7FF>``  a bfrange whose destination would increment
      *across* the UTF-16 surrogate block (D7FF, D800, D801). PDFBox does NOT
      emit lone surrogates: the start resolves to ``U+D7FF`` but the next two
      range members (which would be lone high surrogates U+D800 / U+D801)
      collapse to ``U+FFFD``. pypdfbox reproduces this exactly.

(B) FONT-LEVEL RESOLVE — real ``PDFont`` objects:

    * Type0 / Identity-H, edge CMap as /ToUnicode: a code present in ToUnicode
      (PUA ``U+E000``) resolves; a code ABSENT from ToUnicode is the documented
      divergence below.
    * simple Type1 Helvetica / WinAnsiEncoding, NO ToUnicode: pure encoding ->
      glyph name -> Adobe Glyph List. ``0x41`` -> ``U+0041``, ``0x80`` ->
      ``U+20AC`` (WinAnsi "Euro"), ``0x7F`` -> ``U+2022`` (WinAnsi "bullet").
    * simple Type1 WITH a ToUnicode mapping ``0x41 -> U+E001``: ToUnicode wins
      over the encoding's "A"; ``0x42`` (absent) falls back to AGL "B".

Hand-written (not ported from upstream JUnit). Decorated ``@requires_oracle``
so it skips cleanly without the jar / JDK; the value-pin tests run everywhere.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.fontbox.cmap import CMapParser
from pypdfbox.pdmodel.font import PDFontFactory
from tests.oracle.harness import requires_oracle, run_probe_text

# (A) raw CMap program — mirrors the probe's CMAP_TEXT byte-for-byte.
_RAW_CMAP_TEXT = (
    "/CIDInit /ProcSet findresource begin\n"
    "12 dict begin\n"
    "begincmap\n"
    "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
    "/CMapName /Adobe-Identity-UCS def\n"
    "/CMapType 2 def\n"
    "1 begincodespacerange\n"
    "<0000> <FFFF>\n"
    "endcodespacerange\n"
    "4 beginbfchar\n"
    "<0001> <>\n"  # empty destination -> U+0000
    "<0002> <FFFD>\n"  # replacement char
    "<0003> <0000>\n"  # explicit NUL
    "<0004> <E000>\n"  # PUA start
    "endbfchar\n"
    "1 beginbfrange\n"
    "<0005> <0007> <D7FF>\n"  # steps across surrogate boundary
    "endbfrange\n"
    "endcmap\n"
    "CMapName currentdict /CMap defineresource pop\n"
    "end\n"
    "end\n"
)

_RAW_CODES = [1, 2, 3, 4, 5, 6, 7, 8]

# Simple-font ToUnicode that maps 0x41 -> PUA U+E001 (mirrors the probe).
_SIMPLE_CMAP_TEXT = (
    "/CIDInit /ProcSet findresource begin\n"
    "12 dict begin\nbegincmap\n"
    "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
    "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
    "1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
    "1 beginbfchar\n<41> <E001>\nendbfchar\n"
    "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"
)


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _fmt(tag: str, code: int, uni: str | None) -> str:
    """Render one ``UNI`` line exactly as the probe does."""
    if uni is None:
        body = " (none)"
    elif uni == "":
        body = " (empty)"
    else:
        body = "".join(f" U+{ord(ch):04X}" for ch in uni)
    return f"UNI {tag} {code} ->{body}"


def _make_to_unicode_stream(text: str) -> COSStream:
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(text.encode("ascii"))
    return stream


def _build_type0() -> object:
    """Type0 / Identity-H with the edge CMap as /ToUnicode."""
    cid = COSDictionary()
    cid.set_name(_name("Type"), "Font")
    cid.set_name(COSName.SUBTYPE, "CIDFontType2")  # type: ignore[attr-defined]
    cid.set_name(_name("BaseFont"), "ABCDEF+TestFont")
    si = COSDictionary()
    si.set_string(_name("Registry"), "Adobe")
    si.set_string(_name("Ordering"), "Identity")
    si.set_int(_name("Supplement"), 0)
    cid.set_item(_name("CIDSystemInfo"), si)
    cid.set_int(_name("DW"), 1000)

    font = COSDictionary()
    font.set_name(_name("Type"), "Font")
    font.set_name(COSName.SUBTYPE, "Type0")  # type: ignore[attr-defined]
    font.set_name(_name("BaseFont"), "ABCDEF+TestFont")
    font.set_name(_name("Encoding"), "Identity-H")
    arr = COSArray()
    arr.add(cid)
    font.set_item(_name("DescendantFonts"), arr)
    font.set_item(_name("ToUnicode"), _make_to_unicode_stream(_RAW_CMAP_TEXT))
    return PDFontFactory.create_font(font)


def _build_simple(*, with_to_unicode: bool) -> object:
    """Non-embedded Type1 Helvetica / WinAnsiEncoding."""
    font = COSDictionary()
    font.set_name(_name("Type"), "Font")
    font.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    font.set_name(_name("BaseFont"), "Helvetica")
    font.set_name(_name("Encoding"), "WinAnsiEncoding")
    if with_to_unicode:
        font.set_item(_name("ToUnicode"), _make_to_unicode_stream(_SIMPLE_CMAP_TEXT))
    return PDFontFactory.create_font(font)


# --------------------------------------------------------------------------- #
# Value pins (run everywhere) — pypdfbox-internal expectations.
# --------------------------------------------------------------------------- #


def test_raw_cmap_edge_destinations() -> None:
    """The raw /ToUnicode decode path pins the five edge destinations.

    Notably the EMPTY ``<>`` destination decodes to a single ``U+0000`` (not
    ``""`` / ``(none)``), and the surrogate-boundary bfrange yields ``U+D7FF``
    then ``U+FFFD`` ``U+FFFD`` (lone high surrogates are never emitted).
    """
    cmap = CMapParser().parse(_RAW_CMAP_TEXT.encode("ascii"))
    lines = [_fmt("RAW", c, cmap.to_unicode(c)) for c in _RAW_CODES]
    assert lines == [
        "UNI RAW 1 -> U+0000",
        "UNI RAW 2 -> U+FFFD",
        "UNI RAW 3 -> U+0000",
        "UNI RAW 4 -> U+E000",
        "UNI RAW 5 -> U+D7FF",
        "UNI RAW 6 -> U+FFFD",
        "UNI RAW 7 -> U+FFFD",
        "UNI RAW 8 -> (none)",
    ]


def test_font_level_resolution() -> None:
    """Font-level ``to_unicode`` pins ToUnicode-wins, PUA, and encoding->AGL."""
    type0 = _build_type0()
    assert _fmt("T0", 4, type0.to_unicode(4)) == "UNI T0 4 -> U+E000"
    # 0x09 absent from ToUnicode: pypdfbox returns (none) — see divergence note
    # in the oracle test below.
    assert _fmt("T0", 9, type0.to_unicode(9)) == "UNI T0 9 -> (none)"

    enc = _build_simple(with_to_unicode=False)
    assert _fmt("ENC", 0x41, enc.to_unicode(0x41)) == "UNI ENC 65 -> U+0041"
    assert _fmt("ENC", 0x80, enc.to_unicode(0x80)) == "UNI ENC 128 -> U+20AC"
    assert _fmt("ENC", 0x7F, enc.to_unicode(0x7F)) == "UNI ENC 127 -> U+2022"

    ovr = _build_simple(with_to_unicode=True)
    assert _fmt("OVR", 0x41, ovr.to_unicode(0x41)) == "UNI OVR 65 -> U+E001"
    assert _fmt("OVR", 0x42, ovr.to_unicode(0x42)) == "UNI OVR 66 -> U+0042"


# --------------------------------------------------------------------------- #
# Live oracle parity.
# --------------------------------------------------------------------------- #


def _py_all_lines() -> list[str]:
    """Reproduce every probe line except the substitution-dependent T0 9."""
    cmap = CMapParser().parse(_RAW_CMAP_TEXT.encode("ascii"))
    lines = [_fmt("RAW", c, cmap.to_unicode(c)) for c in _RAW_CODES]

    type0 = _build_type0()
    lines.append(_fmt("T0", 4, type0.to_unicode(4)))

    enc = _build_simple(with_to_unicode=False)
    lines.append(_fmt("ENC", 0x41, enc.to_unicode(0x41)))
    lines.append(_fmt("ENC", 0x80, enc.to_unicode(0x80)))
    lines.append(_fmt("ENC", 0x7F, enc.to_unicode(0x7F)))

    ovr = _build_simple(with_to_unicode=True)
    lines.append(_fmt("OVR", 0x41, ovr.to_unicode(0x41)))
    lines.append(_fmt("OVR", 0x42, ovr.to_unicode(0x42)))
    return lines


@requires_oracle
def test_to_unicode_resolve_fuzz_matches_pdfbox() -> None:
    """pypdfbox's resolution must equal Apache PDFBox's for every fuzzed case.

    HONEST DIVERGENCE — ``UNI T0 9`` (a code ABSENT from the Type0 font's
    /ToUnicode CMap) is excluded from the line-by-line comparison. Java resolves
    it to ``U+0026`` because PDFBox loads its bundled LiberationSans as the CID
    substitute font and that font's cmap supplies a mapping; pypdfbox's
    substitution returns no mapping, so ``to_unicode`` yields ``None``. The
    divergence is in *which substitute font is available*, not in the toUnicode
    resolution logic — every code that has an explicit /ToUnicode or encoding
    mapping agrees exactly.
    """
    java_out = run_probe_text("ToUnicodeResolveFuzzProbe")
    java_lines = [
        ln
        for ln in java_out.splitlines()
        if ln.startswith("UNI ") and not ln.startswith("UNI T0 9 ")
    ]
    py_lines = _py_all_lines()
    assert py_lines == java_lines, (
        "to_unicode resolve fuzz parity broken:\n"
        f"  JAVA: {java_lines}\n"
        f"  PY:   {py_lines}"
    )


@requires_oracle
def test_to_unicode_substitution_divergence_is_documented() -> None:
    """Pin the one divergence so a future substitution-font change is noticed.

    Java's ``T0 9`` line is whatever its bundled substitute font supplies
    (``U+0026`` with PDFBox 3.0.7's LiberationSans); pypdfbox returns ``(none)``.
    This asserts the divergence still holds rather than silently regressing.
    """
    java_out = run_probe_text("ToUnicodeResolveFuzzProbe")
    java_t0_9 = next(
        (ln for ln in java_out.splitlines() if ln.startswith("UNI T0 9 ")), None
    )
    assert java_t0_9 is not None
    # Java resolves it via a substitute font; pypdfbox does not.
    assert java_t0_9 != "UNI T0 9 -> (none)"
    type0 = _build_type0()
    assert _fmt("T0", 9, type0.to_unicode(9)) == "UNI T0 9 -> (none)"
