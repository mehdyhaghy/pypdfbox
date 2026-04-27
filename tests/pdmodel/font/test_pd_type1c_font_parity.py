"""Parity tests for ``PDType1CFont`` upstream-named accessors.

Companion to :mod:`tests.pdmodel.font.test_type1_cff_glyph` which
exercises the CFF program plumbing end-to-end. These tests focus on
the upstream-named API surface:

* ``getCFFType1Font`` / ``getCFFFont``       — embedded program access
* ``isEmbedded`` / ``isDamaged``             — embed / damage probes
* ``codeToName`` / ``codeToGID`` / ``hasGlyph``
* ``getName``                                — ``/BaseFont`` alias
* ``getUnitsPerEm`` / ``getHeight`` / ``getDisplacement``
* ``getAverageFontWidth``                    — CFF-aware fallback
* ``getPath(name)``                          — name-keyed outline
"""

from __future__ import annotations

import io

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.pdmodel.font import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont

_BASE_FONT = COSName.get_pdf_name("BaseFont")
_ENCODING = COSName.get_pdf_name("Encoding")
_DIFFERENCES = COSName.get_pdf_name("Differences")
_FIRST_CHAR = COSName.get_pdf_name("FirstChar")
_LAST_CHAR = COSName.get_pdf_name("LastChar")
_WIDTHS = COSName.get_pdf_name("Widths")
_FONT_DESCRIPTOR = COSName.get_pdf_name("FontDescriptor")


# ---------- helpers ----------


def _build_minimal_cff_bytes() -> bytes:
    """Build a tiny in-memory CFF font set with three glyphs:
    ``.notdef`` (width 0), ``A`` (width 500, simple rectangle), ``B``
    (width 300, single vertical stroke). Returns the raw CFF table
    bytes — exactly the byte form a PDF ``/FontFile3`` stream with
    ``/Subtype /Type1C`` carries.
    """
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString
    from fontTools.ttLib import TTFont

    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder([".notdef", "A", "B"])
    fb.setupCharacterMap({65: "A", 66: "B"})

    def _cs(program: list) -> T2CharString:
        s = T2CharString()
        s.program = program
        return s

    char_strings = {
        ".notdef": _cs([0, "endchar"]),
        # Width 500 prefix; outline = 100x700 rectangle.
        "A": _cs(
            [500, 0, "hmoveto", 700, "vlineto", 100, "hlineto", -700, "vlineto", "endchar"]
        ),
        # Width 300 prefix; outline = single vertical stroke 500 units high.
        "B": _cs([300, 0, "hmoveto", 500, "vlineto", "endchar"]),
    }
    fb.setupCFF(
        psName="TestType1C",
        fontInfo={"FullName": "Test Type1C"},
        charStringsDict=char_strings,
        privateDict={},
    )
    fb.setupHorizontalMetrics({".notdef": (0, 0), "A": (500, 0), "B": (300, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    re_open = TTFont(io.BytesIO(buf.getvalue()))
    return bytes(re_open.getTableData("CFF "))


def _make_embedded_font() -> PDType1CFont:
    """Build a PDType1CFont with a fully-realised /FontDescriptor +
    /FontFile3 (/Subtype /Type1C) stream — exactly the on-disk layout
    Acrobat would emit for an embedded Type1C font."""
    cff_bytes = _build_minimal_cff_bytes()
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(cff_bytes)
    stream.set_name(COSName.SUBTYPE, "Type1C")  # type: ignore[attr-defined]
    descriptor.set_font_file3(stream)

    font_dict = COSDictionary()
    font_dict.set_name(_BASE_FONT, "MyEmbeddedType1C")
    font_dict.set_item(_ENCODING, COSName.get_pdf_name("WinAnsiEncoding"))
    font_dict.set_item(_FONT_DESCRIPTOR, descriptor.get_cos_object())
    return PDType1CFont(font_dict)


def _make_injected_font() -> PDType1CFont:
    """Build a PDType1CFont with an in-memory CFFFont injected via
    ``set_font_program`` — bypasses /FontFile3 byte-level parsing."""
    cff = CFFFont.from_bytes(_build_minimal_cff_bytes())
    font_dict = COSDictionary()
    font_dict.set_name(_BASE_FONT, "MyEmbeddedType1C")
    font_dict.set_item(_ENCODING, COSName.get_pdf_name("WinAnsiEncoding"))
    font = PDType1CFont(font_dict)
    font.set_font_program(cff)
    return font


# ---------- get_name / get_base_font ----------


def test_get_name_returns_base_font_value() -> None:
    font = PDType1CFont()
    font.get_cos_object().set_name(_BASE_FONT, "MyType1CFont")
    assert font.get_name() == "MyType1CFont"


def test_get_base_font_aliases_get_name() -> None:
    font = PDType1CFont()
    font.get_cos_object().set_name(_BASE_FONT, "MyType1CFont")
    assert font.get_base_font() == "MyType1CFont"
    assert font.get_base_font() == font.get_name()


def test_get_name_none_when_absent() -> None:
    assert PDType1CFont().get_name() is None


# ---------- get_cff_font / get_cff_type1_font ----------


def test_get_cff_font_returns_none_when_not_embedded() -> None:
    assert PDType1CFont().get_cff_font() is None


def test_get_cff_type1_font_aliases_get_cff_font() -> None:
    font = _make_injected_font()
    assert font.get_cff_type1_font() is font.get_cff_font()
    assert isinstance(font.get_cff_font(), CFFFont)


# ---------- is_embedded ----------


def test_is_embedded_false_when_no_descriptor() -> None:
    assert PDType1CFont().is_embedded() is False


def test_is_embedded_false_when_descriptor_has_no_font_file3() -> None:
    font = PDType1CFont()
    font.set_font_descriptor(PDFontDescriptor())
    assert font.is_embedded() is False


def test_is_embedded_false_when_only_font_file_present() -> None:
    """PDType1CFont's embed signal is /FontFile3 specifically — a
    /FontFile (legacy Type 1 PFB) on the descriptor must not trigger
    True for the CFF subtype."""
    font = PDType1CFont()
    fd = PDFontDescriptor()
    fd.set_font_file(COSStream())
    font.set_font_descriptor(fd)
    assert font.is_embedded() is False


def test_is_embedded_true_when_font_file3_present() -> None:
    font = PDType1CFont()
    fd = PDFontDescriptor()
    fd.set_font_file3(COSStream())
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


# ---------- is_damaged ----------


def test_is_damaged_false_when_not_embedded() -> None:
    assert PDType1CFont().is_damaged() is False


def test_is_damaged_false_when_descriptor_has_no_font_file3() -> None:
    font = PDType1CFont()
    font.set_font_descriptor(PDFontDescriptor())
    assert font.is_damaged() is False


def test_is_damaged_true_when_font_file3_unparseable() -> None:
    font = PDType1CFont()
    fd = PDFontDescriptor()
    bogus = COSStream()
    bogus.set_data(b"definitely not a CFF font set")
    fd.set_font_file3(bogus)
    font.set_font_descriptor(fd)
    assert font.is_damaged() is True


def test_is_damaged_false_when_font_file3_parses_cleanly() -> None:
    font = _make_embedded_font()
    assert font.is_damaged() is False
    # Parsing the program once must not flip the damage flag on
    # subsequent reads.
    assert font.get_cff_font() is not None
    assert font.is_damaged() is False


# ---------- code_to_name ----------


def test_code_to_name_via_winansi_encoding() -> None:
    font = _make_injected_font()
    assert font.code_to_name(65) == "A"
    assert font.code_to_name(66) == "B"


def test_code_to_name_via_differences_overlay() -> None:
    enc = COSDictionary()
    enc.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Encoding"))
    enc.set_item(
        COSName.get_pdf_name("BaseEncoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    diffs = COSArray([COSInteger.get(65), COSName.get_pdf_name("Lslash")])
    enc.set_item(_DIFFERENCES, diffs)
    font = PDType1CFont()
    font.get_cos_object().set_item(_ENCODING, enc)
    assert font.code_to_name(65) == "Lslash"
    assert font.code_to_name(66) == "B"


def test_code_to_name_returns_none_when_no_encoding() -> None:
    assert PDType1CFont().code_to_name(65) is None


# ---------- code_to_gid ----------


def test_code_to_gid_returns_zero_when_no_program() -> None:
    font = PDType1CFont()
    font.get_cos_object().set_item(_ENCODING, COSName.get_pdf_name("WinAnsiEncoding"))
    assert font.code_to_gid(65) == 0


def test_code_to_gid_resolves_via_cff_charset() -> None:
    font = _make_injected_font()
    # Charset order from FontBuilder is [".notdef", "A", "B"] — so 'A' (code 65)
    # is GID 1 and 'B' (code 66) is GID 2.
    assert font.code_to_gid(65) == 1
    assert font.code_to_gid(66) == 2


def test_code_to_gid_returns_zero_for_unmapped_code() -> None:
    font = _make_injected_font()
    # Code 90 ('Z') is in WinAnsi but not in the embedded charset.
    assert font.code_to_gid(90) == 0


def test_code_to_gid_returns_zero_when_no_encoding() -> None:
    cff = CFFFont.from_bytes(_build_minimal_cff_bytes())
    font = PDType1CFont()
    font.set_font_program(cff)
    # No /Encoding → code_to_name returns None → GID 0.
    assert font.code_to_gid(65) == 0


# ---------- has_glyph ----------


def test_has_glyph_false_when_no_program() -> None:
    assert PDType1CFont().has_glyph("A") is False


def test_has_glyph_true_for_present_glyph() -> None:
    font = _make_injected_font()
    assert font.has_glyph("A") is True
    assert font.has_glyph("B") is True
    assert font.has_glyph(".notdef") is True


def test_has_glyph_false_for_missing_glyph() -> None:
    font = _make_injected_font()
    assert font.has_glyph("Z") is False
    assert font.has_glyph("nonexistent") is False


# ---------- get_path (name-keyed) ----------


def test_get_path_by_name_returns_outline_for_embedded_glyph() -> None:
    font = _make_injected_font()
    path = font.get_path("A")
    assert path[0][0] == "moveto"
    assert path[-1] == ("closepath",)


def test_get_path_by_name_returns_empty_for_missing_glyph() -> None:
    font = _make_injected_font()
    assert font.get_path("nonexistent") == []


def test_get_path_by_name_returns_empty_when_no_program() -> None:
    assert PDType1CFont().get_path("A") == []


# ---------- get_units_per_em ----------


def test_get_units_per_em_returns_1000_by_default_when_no_program() -> None:
    """CFF defaults to a 1000-unit em (matrix [0.001 0 0 0.001 0 0]).
    With no embedded program we still return 1000 so downstream
    division-by-em never blows up."""
    assert PDType1CFont().get_units_per_em() == 1000


def test_get_units_per_em_reflects_cff_program() -> None:
    font = _make_injected_font()
    # FontBuilder(1000, ...) = 1000-unit em.
    assert font.get_units_per_em() == 1000


# ---------- get_height ----------


def test_get_height_zero_when_no_program() -> None:
    font = PDType1CFont()
    font.get_cos_object().set_item(_ENCODING, COSName.get_pdf_name("WinAnsiEncoding"))
    assert font.get_height(65) == 0.0


def test_get_height_from_cff_outline() -> None:
    font = _make_injected_font()
    # 'A' is a 100x700 rectangle in our minimal CFF — height = 700.
    assert font.get_height(65) == 700.0
    # 'B' is a vertical stroke 500 units high.
    assert font.get_height(66) == 500.0


def test_get_height_zero_for_unmapped_code() -> None:
    font = _make_injected_font()
    assert font.get_height(90) == 0.0  # 'Z' — not in our minimal CFF


def test_get_height_caches_per_glyph() -> None:
    font = _make_injected_font()
    first = font.get_height(65)
    second = font.get_height(65)
    assert first == second == 700.0


# ---------- get_displacement ----------


def test_get_displacement_returns_width_over_1000_horizontal() -> None:
    """Simple Type1C fonts are horizontal; displacement is (width/1000, 0)."""
    font = PDType1CFont()
    cos = font.get_cos_object()
    cos.set_int(_FIRST_CHAR, 65)
    cos.set_int(_LAST_CHAR, 65)
    cos.set_item(_WIDTHS, COSArray([COSInteger.get(750)]))
    dx, dy = font.get_displacement(65)
    assert dx == 0.75
    assert dy == 0.0


def test_get_displacement_uses_cff_program_when_no_widths_array() -> None:
    font = _make_injected_font()
    # 'A' has CFF advance 500 → displacement (0.5, 0).
    dx, dy = font.get_displacement(65)
    assert dx == 0.5
    assert dy == 0.0


def test_get_displacement_zero_for_unmapped_code_with_no_metrics() -> None:
    dx, dy = PDType1CFont().get_displacement(65)
    assert dx == 0.0
    assert dy == 0.0


# ---------- get_average_font_width ----------


def test_get_average_font_width_uses_widths_when_present() -> None:
    font = PDType1CFont()
    cos = font.get_cos_object()
    cos.set_name(_BASE_FONT, "MyEmbeddedType1C")
    cos.set_int(_FIRST_CHAR, 32)
    cos.set_int(_LAST_CHAR, 34)
    cos.set_item(
        _WIDTHS,
        COSArray([COSInteger.get(100), COSInteger.get(200), COSInteger.get(300)]),
    )
    assert font.get_average_font_width() == 200.0


def test_get_average_font_width_zero_when_no_widths_and_no_program() -> None:
    # No /Widths, no /FontFile3, non-Standard-14 /BaseFont → 0.0.
    font = PDType1CFont()
    font.get_cos_object().set_name(_BASE_FONT, "MyEmbeddedType1C")
    assert font.get_average_font_width() == 0.0


def test_get_average_font_width_falls_back_to_afm_for_standard_14() -> None:
    font = PDType1CFont()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    afm_mean = font.get_standard_14_font_metrics().get_average_width()  # type: ignore[union-attr]
    assert font.get_average_font_width() == afm_mean
    assert afm_mean > 0.0


# ---------- end-to-end /FontFile3 round-trip ----------


def test_embedded_font_round_trip_lights_up_full_surface() -> None:
    """One end-to-end sanity check: build a font with a real /FontFile3
    stream and confirm every upstream-named accessor wired in this
    cluster produces a sensible answer without going through
    ``set_font_program``."""
    font = _make_embedded_font()
    assert font.is_embedded() is True
    assert font.is_damaged() is False
    assert font.get_cff_font() is not None
    assert font.get_units_per_em() == 1000
    assert font.has_glyph("A") is True
    assert font.code_to_name(65) == "A"
    assert font.code_to_gid(65) == 1
    assert font.get_height(65) == 700.0
    dx, dy = font.get_displacement(65)
    assert dx == 0.5
    assert dy == 0.0
    assert font.get_path("A")[0][0] == "moveto"
    assert font.get_glyph_path(65)[0][0] == "moveto"
