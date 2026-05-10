from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.fontbox.type1.type1_font import Type1Font
from pypdfbox.pdmodel.font.encoding import StandardEncoding
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_mm_type1_font import PDMMType1Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont

# ---------- helpers ----------


def _build_minimal_cff_bytes() -> bytes:
    """Build a tiny in-memory CFF font set with three glyphs:
    ``.notdef`` (width 0), ``A`` (width 500, simple rectangle),
    ``B`` (width 300, single vertical stroke). Returns the raw CFF
    table bytes — exactly the byte form a PDF ``/FontFile3`` stream
    with ``/Subtype /Type1C`` carries.
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
        # Width 500 prefix (since nominalWidthX=0 and width != defaultWidthX(0),
        # this will end up encoded as defaultWidthX=500). Outline = 100x700 box.
        "A": _cs([500, 0, "hmoveto", 700, "vlineto", 100, "hlineto", -700, "vlineto", "endchar"]),
        # Width 300 prefix, outline = single vertical line up 500 units.
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

    # Extract the CFF table from the OTF wrapper — that's what PDF /FontFile3 carries.
    re_open = TTFont(io.BytesIO(buf.getvalue()))
    return bytes(re_open.getTableData("CFF "))


def _build_minimal_type1_program() -> Type1Font:
    """Build a tiny in-memory Type 1 font program by hand — three glyphs
    (``.notdef``, ``A`` width 500, ``B`` width 300), no outline (Type 1
    .notdef-style charstrings whose advance comes from the ``hsbw``
    operator). Returns a ready-to-use :class:`Type1Font` instance.

    Generating valid PFB-format Type 1 bytes from scratch is a nontrivial
    bring-up — the real test fixture path is ``set_font_program(...)``
    just like the TTF cluster does. We construct the Type1Font through
    the public injector by hand-rolling the minimal attribute surface
    the wrapper uses.
    """
    program = Type1Font()

    class _StubCharString:
        def __init__(self, width: float, commands: list) -> None:
            self.width = width
            self._commands = commands

        def draw(self, pen) -> None:  # noqa: ANN001 — pen protocol
            for cmd in self._commands:
                if cmd[0] == "moveTo":
                    pen.moveTo(cmd[1])
                elif cmd[0] == "lineTo":
                    pen.lineTo(cmd[1])
                elif cmd[0] == "closePath":
                    pen.closePath()

    program._charstrings = {
        ".notdef": _StubCharString(0.0, []),
        "A": _StubCharString(
            500.0,
            [
                ("moveTo", (0.0, 0.0)),
                ("lineTo", (0.0, 700.0)),
                ("lineTo", (100.0, 700.0)),
                ("lineTo", (100.0, 0.0)),
                ("closePath",),
            ],
        ),
        "B": _StubCharString(300.0, []),
    }
    program._font_matrix = [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    program._units_per_em = 1000
    return program


# ---------- Type1Font (fontbox wrapper) ----------


def test_type1_font_parses_widths_and_paths_via_injected_program() -> None:
    program = _build_minimal_type1_program()
    assert program.has_glyph("A")
    assert not program.has_glyph("Z")
    assert program.get_width("A") == 500.0
    assert program.get_width("B") == 300.0
    assert program.get_width(".notdef") == 0.0
    assert program.units_per_em == 1000


def test_type1_font_path_format_matches_contract() -> None:
    program = _build_minimal_type1_program()
    path = program.get_path("A")
    # Rectangle outline: moveto + 3 linetos + closepath.
    assert path[0] == ("moveto", 0.0, 0.0)
    assert path[1] == ("lineto", 0.0, 700.0)
    assert path[2] == ("lineto", 100.0, 700.0)
    assert path[3] == ("lineto", 100.0, 0.0)
    assert path[4] == ("closepath",)


def test_type1_font_get_path_missing_glyph_returns_empty() -> None:
    program = _build_minimal_type1_program()
    assert program.get_path("nonexistent") == []
    assert program.get_width("nonexistent") == 0.0


# ---------- CFFFont (fontbox wrapper) ----------


def test_cff_font_from_bytes_parses_widths() -> None:
    cff = CFFFont.from_bytes(_build_minimal_cff_bytes())
    assert cff.name == "TestType1C"
    assert cff.units_per_em == 1000
    assert cff.has_glyph("A")
    assert cff.has_glyph("B")
    assert not cff.has_glyph("Z")
    assert cff.get_width("A") == 500.0
    assert cff.get_width("B") == 300.0


def test_cff_font_get_path_returns_correct_command_sequence() -> None:
    cff = CFFFont.from_bytes(_build_minimal_cff_bytes())
    path = cff.get_path("A")
    # The CFF-side rectangle: moveto + 3 linetos + closepath.
    assert path[0][0] == "moveto"
    assert path[-1] == ("closepath",)
    # All intermediate commands are linetos.
    for cmd in path[1:-1]:
        assert cmd[0] == "lineto"


def test_cff_font_missing_glyph_returns_empty_path() -> None:
    cff = CFFFont.from_bytes(_build_minimal_cff_bytes())
    assert cff.get_path("nonexistent") == []
    assert cff.get_width("nonexistent") == 0.0


def test_cff_font_from_bytes_rejects_garbage() -> None:
    with pytest.raises(Exception):  # noqa: B017 — fontTools surfaces several
        CFFFont.from_bytes(b"not a CFF font set")


# ---------- PDType1Font (pdmodel) ----------


def _make_type1_font_with_program(program: Type1Font) -> PDType1Font:
    font_dict = COSDictionary()
    # Make the font non-Standard-14 so we don't get AFM fallback noise.
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyEmbeddedType1")
    # WinAnsi /Encoding so codes 65/66 map to A/B.
    font_dict.set_item(COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding"))
    font = PDType1Font(font_dict)
    font.set_font_program(program)
    return font


def test_pd_type1_font_get_glyph_width_uses_program() -> None:
    font = _make_type1_font_with_program(_build_minimal_type1_program())
    assert font.get_glyph_width(65) == 500.0  # 'A'
    assert font.get_glyph_width(66) == 300.0  # 'B'


def test_pd_type1_font_widths_array_overrides_program() -> None:
    program = _build_minimal_type1_program()
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyEmbeddedType1")
    font_dict.set_item(COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding"))
    font_dict.set_int(COSName.get_pdf_name("FirstChar"), 65)
    font_dict.set_int(COSName.get_pdf_name("LastChar"), 65)
    widths = COSArray()
    widths.add(COSInteger(999))
    font_dict.set_item(COSName.get_pdf_name("Widths"), widths)
    font = PDType1Font(font_dict)
    font.set_font_program(program)
    assert font.get_glyph_width(65) == 999.0          # /Widths wins
    assert font.get_glyph_width(66) == 300.0          # program fallback


def test_pd_type1_font_no_program_no_widths_returns_zero() -> None:
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyEmbeddedType1")
    font_dict.set_item(COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding"))
    font = PDType1Font(font_dict)
    assert font.get_glyph_width(65) == 0.0


def test_pd_type1_font_get_glyph_path_uses_program() -> None:
    font = _make_type1_font_with_program(_build_minimal_type1_program())
    path = font.get_glyph_path(65)
    assert path[0] == ("moveto", 0.0, 0.0)
    assert path[-1] == ("closepath",)


def test_pd_type1_font_get_glyph_path_missing_returns_empty() -> None:
    font = _make_type1_font_with_program(_build_minimal_type1_program())
    # Code 90 ('Z') has WinAnsi mapping but no program glyph.
    assert font.get_glyph_path(90) == []


def test_pd_type1_font_unmapped_code_returns_zero_and_empty() -> None:
    font = _make_type1_font_with_program(_build_minimal_type1_program())
    # Code 0x00 maps to .notdef in WinAnsi → no glyph.
    # /Widths empty + program rejects → 0.0
    assert font.get_glyph_width(0) == 0.0
    assert font.get_glyph_path(0) == []


def test_pd_type1_font_set_font_program_none_clears_cache() -> None:
    font = _make_type1_font_with_program(_build_minimal_type1_program())
    assert font.get_glyph_width(65) == 500.0
    font.set_font_program(None)
    # Now the program path returns nothing; with no /Widths and a
    # non-Standard-14 base name, the answer is 0.
    assert font.get_glyph_width(65) == 0.0


# ---------- PDType1CFont (pdmodel) ----------


def _make_type1c_font_with_program(program: CFFFont) -> PDType1CFont:
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyEmbeddedType1C")
    font_dict.set_item(COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding"))
    font = PDType1CFont(font_dict)
    font.set_font_program(program)
    return font


def test_pd_type1c_font_get_glyph_width_uses_cff_program() -> None:
    cff = CFFFont.from_bytes(_build_minimal_cff_bytes())
    font = _make_type1c_font_with_program(cff)
    assert font.get_glyph_width(65) == 500.0  # 'A'
    assert font.get_glyph_width(66) == 300.0  # 'B'


def test_pd_type1c_font_widths_array_overrides_cff_program() -> None:
    cff = CFFFont.from_bytes(_build_minimal_cff_bytes())
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyEmbeddedType1C")
    font_dict.set_item(COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding"))
    font_dict.set_int(COSName.get_pdf_name("FirstChar"), 65)
    font_dict.set_int(COSName.get_pdf_name("LastChar"), 65)
    widths = COSArray()
    widths.add(COSInteger(888))
    font_dict.set_item(COSName.get_pdf_name("Widths"), widths)
    font = PDType1CFont(font_dict)
    font.set_font_program(cff)
    assert font.get_glyph_width(65) == 888.0          # /Widths wins
    assert font.get_glyph_width(66) == 300.0          # CFF fallback


def test_pd_type1c_font_no_cff_no_widths_returns_zero() -> None:
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyEmbeddedType1C")
    font_dict.set_item(COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding"))
    font = PDType1CFont(font_dict)
    assert font.get_glyph_width(65) == 0.0
    assert font.get_glyph_path(65) == []


def test_pd_type1c_font_get_glyph_path_uses_cff_program() -> None:
    cff = CFFFont.from_bytes(_build_minimal_cff_bytes())
    font = _make_type1c_font_with_program(cff)
    path = font.get_glyph_path(65)
    assert len(path) >= 2
    assert path[0][0] == "moveto"
    assert path[-1] == ("closepath",)


def test_pd_type1c_font_parses_real_fontfile3_stream() -> None:
    """End-to-end: build /FontDescriptor with /FontFile3 stream and
    verify the CFF parse path lights up without ``set_font_program``."""
    cff_bytes = _build_minimal_cff_bytes()
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(cff_bytes)
    stream.set_name(COSName.SUBTYPE, "Type1C")  # type: ignore[attr-defined]
    descriptor.set_font_file3(stream)

    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyEmbeddedType1C")
    font_dict.set_item(COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding"))
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    font = PDType1CFont(font_dict)
    assert font.get_glyph_width(65) == 500.0
    assert font.get_glyph_path(65)[0][0] == "moveto"


# ---------- PDMMType1Font ----------


def test_pd_mm_type1_font_inherits_glyph_apis() -> None:
    """PDMMType1Font is a marker subclass — it should pick up
    set_font_program / get_glyph_width / get_glyph_path from
    PDType1Font without overriding them."""
    program = _build_minimal_type1_program()
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyMMFont")
    font_dict.set_item(COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding"))
    font = PDMMType1Font(font_dict)
    font.set_font_program(program)
    assert font.get_glyph_width(65) == 500.0
    assert font.get_glyph_path(65)[0] == ("moveto", 0.0, 0.0)


# ---------- StandardEncoding parity (sanity) ----------


def test_pd_type1_font_with_standard_encoding_resolves_glyph_names() -> None:
    """StandardEncoding 0x41 -> 'A' (same as WinAnsi for the ASCII range)."""
    program = _build_minimal_type1_program()
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyEmbeddedType1")
    font_dict.set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("StandardEncoding")
    )
    font = PDType1Font(font_dict)
    font.set_font_program(program)
    assert font.get_encoding_typed() is StandardEncoding.INSTANCE
    assert font.get_glyph_width(65) == 500.0
