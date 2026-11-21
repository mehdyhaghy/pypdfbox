"""PDFBOX-6308 subroutine limits through the PD font and rendering API.

A Type1C font carries two glyphs whose outline (a filled square) sits at
the end of a subroutine chain: ``A`` makes exactly 150 calls (the Type 2
limit) and ``B`` makes 151. Upstream's ``Type2CharStringParser`` rejects
``B`` with an ``IOException``: ``PDType1CFont.getPath`` /
``getWidthFromFont`` propagate it, and ``GlyphCache`` logs it and draws an
empty glyph, so the page still renders with only ``A`` painted.
"""

import io

import pytest
from fontTools.cffLib import SubrsIndex
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.psCharStrings import T2CharString

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.fontbox.cff.type2_char_string_parser import MAX_SUBR_NESTING
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.rendering import PDFRenderer

_BIAS = 107  # subr bias for an index with fewer than 1240 entries
_SQUARE = [0, 0, "rmoveto", 700, 0, "rlineto", 0, 700, "rlineto", -700, 0, "rlineto"]


def _compiled(program: list[object]) -> bytes:
    cs = T2CharString(program=program)
    cs.compile()
    return bytes(cs.bytecode)


def _chain(start: int, length: int) -> list[bytes]:
    """``length`` subrs from index ``start`` on, each calling the next; the
    last one draws the square."""
    subrs = [
        _compiled([start + i + 1 - _BIAS, "callsubr", "return"]) for i in range(length - 1)
    ]
    subrs.append(_compiled([*_SQUARE, "return"]))
    return subrs


def _build_cff() -> bytes:
    n = MAX_SUBR_NESTING
    subrs = _chain(0, n) + _chain(n, n + 1)
    glyphs = {
        "A": _compiled([700, 0 - _BIAS, "callsubr", "endchar"]),
        "B": _compiled([700, n - _BIAS, "callsubr", "endchar"]),
    }
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder([".notdef", "A", "B"])
    placeholders = {}
    for name in (".notdef", "A", "B"):
        cs = T2CharString()
        cs.program = ["endchar"]
        placeholders[name] = cs
    fb.setupCFF(psName="LimitTest", fontInfo={}, charStringsDict=placeholders, privateDict={})
    cff = fb.font["CFF "].cff
    top = cff.topDictIndex[0]
    index = SubrsIndex()
    for program in subrs:
        index.append(T2CharString(bytecode=program))
    top.Private.Subrs = index
    for name, program in glyphs.items():
        cs = top.CharStrings[name]
        cs.bytecode = program
        cs.program = None
    fb.font.recalcBBoxes = False
    buf = io.BytesIO()
    cff.compile(buf, fb.font, isCFF2=False)
    return buf.getvalue()


@pytest.fixture(scope="module")
def cff_bytes() -> bytes:
    return _build_cff()


def _type1c(cff_bytes: bytes, *, widths: bool) -> PDType1CFont:
    stream = COSStream()
    stream.set_raw_data(cff_bytes)
    stream.set_name(COSName.SUBTYPE, "Type1C")
    descriptor = PDFontDescriptor(COSDictionary())
    descriptor.set_font_file3(stream)
    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    font_dict.set_item(COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("LimitTest"))
    font_dict.set_item(COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding"))
    font_dict.set_item(COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object())
    if widths:
        font_dict.set_item(COSName.get_pdf_name("FirstChar"), COSInteger.get(65))
        font_dict.set_item(COSName.get_pdf_name("LastChar"), COSInteger.get(66))
        array = COSArray()
        array.add(COSInteger.get(700))
        array.add(COSInteger.get(700))
        font_dict.set_item(COSName.get_pdf_name("Widths"), array)
    return PDType1CFont(font_dict)


def test_type1c_path_at_limit_and_over_limit(cff_bytes: bytes) -> None:
    font = _type1c(cff_bytes, widths=False)
    assert font.get_path("A")[0] == ("moveto", 0.0, 0.0)
    assert font.get_glyph_path(65)[0] == ("moveto", 0.0, 0.0)
    with pytest.raises(OSError, match="nested more than 150 levels deep in font LimitTest"):
        font.get_path("B")
    with pytest.raises(OSError, match="nested more than 150 levels"):
        font.get_glyph_path(66)


def test_type1c_width_from_font_over_limit_raises(cff_bytes: bytes) -> None:
    font = _type1c(cff_bytes, widths=False)
    assert font.get_width_from_font(65) == pytest.approx(700.0)
    with pytest.raises(OSError, match="nested more than 150 levels"):
        font.get_width_from_font(66)


def test_type1c_declared_width_does_not_touch_the_program(cff_bytes: bytes) -> None:
    # upstream PDFont.getWidth answers from /Widths before the font program
    font = _type1c(cff_bytes, widths=True)
    assert font.get_width(66) == pytest.approx(700.0)


def _cid_type0(cff_bytes: bytes) -> PDCIDFontType0:
    stream = COSStream()
    stream.set_raw_data(cff_bytes)
    stream.set_name(COSName.SUBTYPE, "CIDFontType0C")
    descriptor = PDFontDescriptor(COSDictionary())
    descriptor.set_font_file3(stream)
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "LimitTest")
    font_dict.set_item(COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object())
    return PDCIDFontType0(font_dict)


def test_cid_font_type0_with_name_keyed_cff(cff_bytes: bytes) -> None:
    # An embedded name-keyed CFF under a CIDFontType0: the CID is the GID.
    font = _cid_type0(cff_bytes)
    assert font.get_path(1, None)[0] == ("moveto", 0.0, 0.0)
    assert font.get_width_from_font(1, None) == pytest.approx(700.0)
    with pytest.raises(OSError, match="nested more than 150 levels"):
        font.get_path(2, None)
    with pytest.raises(OSError, match="nested more than 150 levels"):
        font.get_width_from_font(2, None)


def _dark_pixels(img, x0: int, x1: int) -> int:
    count = 0
    for y in range(img.size[1]):
        for x in range(x0, x1):
            r, g, b = img.getpixel((x, y))[:3]
            if r < 128 and g < 128 and b < 128:
                count += 1
    return count


def test_render_draws_glyph_at_limit_and_skips_glyph_over_it(cff_bytes: bytes) -> None:
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 100.0))
    doc.add_page(page)
    font = _type1c(cff_bytes, widths=True)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 50.0)
        cs.new_line_at_offset(20.0, 30.0)
        cs.show_text("A")
        cs.end_text()
        cs.begin_text()
        cs.set_font(font, 50.0)
        cs.new_line_at_offset(120.0, 30.0)
        cs.show_text("B")
        cs.end_text()
    img = PDFRenderer(doc).render_image(0)
    assert img.size == (200, 100)
    # A's 35x35 square is painted; B renders as an empty glyph.
    assert _dark_pixels(img, 0, 100) > 900
    assert _dark_pixels(img, 100, 200) == 0
    doc.close()
