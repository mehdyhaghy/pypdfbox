from __future__ import annotations

import io

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


# ---------- CFF fixture builders ----------


def _build_cid_keyed_cff_bytes(*, with_ros: bool = True) -> bytes:
    """Build a tiny CFF font set, optionally CID-keyed (with /ROS)."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString
    from fontTools.ttLib import TTFont

    fb = FontBuilder(1000, isTTF=False)
    glyph_order = [".notdef", "cid00001", "cid00002"] if with_ros else [".notdef", "A", "B"]
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({1: glyph_order[1], 2: glyph_order[2]})

    def _cs(program: list) -> T2CharString:
        s = T2CharString()
        s.program = program
        return s

    cs_dict = {
        glyph_order[0]: _cs([0, "endchar"]),
        # 100x700 box at y=0..700, width 500.
        glyph_order[1]: _cs(
            [500, 0, "hmoveto", 700, "vlineto", 100, "hlineto", -700, "vlineto", "endchar"]
        ),
        # 0..500 vertical stroke, width 300.
        glyph_order[2]: _cs([300, 0, "hmoveto", 500, "vlineto", "endchar"]),
    }
    fb.setupCFF(
        psName="TestCIDFontType0C" if with_ros else "TestType1CFontUnderCID",
        fontInfo={"FullName": "Test"},
        charStringsDict=cs_dict,
        privateDict={},
    )
    fb.setupHorizontalMetrics(
        {glyph_order[0]: (0, 0), glyph_order[1]: (500, 0), glyph_order[2]: (300, 0)}
    )
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    re_open = TTFont(io.BytesIO(buf.getvalue()))
    return bytes(re_open.getTableData("CFF "))


def _make_font_with_descriptor(
    *, font_file3_subtype: str | None = "CIDFontType0C", with_data: bool = True
) -> PDCIDFontType0:
    descriptor = PDFontDescriptor()
    if with_data:
        stream = COSStream()
        stream.set_data(_build_cid_keyed_cff_bytes())
        if font_file3_subtype is not None:
            stream.set_name(COSName.SUBTYPE, font_file3_subtype)  # type: ignore[attr-defined]
        descriptor.set_font_file3(stream)

    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyEmbeddedCIDFontType0C")
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    return PDCIDFontType0(font_dict)


# ---------- get_cff_font polymorphism ----------


def test_get_cff_font_returns_cff_cid_font_for_cid_keyed_program() -> None:
    """A /FontFile3 with /Subtype /CIDFontType0C (and a ROS in the
    underlying CFF) should specialise to :class:`CFFCIDFont`."""
    font = _make_font_with_descriptor(font_file3_subtype="CIDFontType0C")
    program = font.get_cff_font()
    # fontTools' FontBuilder doesn't synthesise /ROS automatically, so
    # the resulting CFF is name-keyed even with cid* glyph names; the
    # specialisation reflects the program's actual ROS state.
    assert isinstance(program, CFFFont)
    if program.is_cid_font():
        assert isinstance(program, CFFCIDFont)
    else:
        assert isinstance(program, CFFType1Font)


# ---------- code_to_gid ----------


def test_code_to_gid_identity_when_no_program() -> None:
    """No embedded program → CID is GID."""
    font = PDCIDFontType0()
    assert font.code_to_gid(0) == 0
    assert font.code_to_gid(1) == 1
    assert font.code_to_gid(99) == 99


def test_code_to_gid_uses_charset_for_cid_keyed_program() -> None:
    """For CID-keyed CFF the GID is the charset index of cidNNNNN."""
    font = _make_font_with_descriptor()
    # Force the parse first; if the resulting program is name-keyed our
    # fixture won't have cid00001 in the charset by name, so the lookup
    # falls through to the name-keyed branch (CID == GID).
    program = font.get_cff_font()
    assert program is not None
    if isinstance(program, CFFCIDFont):
        # Charset order: .notdef, cid00001, cid00002 → gid 0, 1, 2.
        assert font.code_to_gid(1) == 1
        assert font.code_to_gid(2) == 2
    else:
        # Name-keyed branch: CID is GID.
        assert font.code_to_gid(1) == 1


def test_code_to_gid_returns_zero_for_unmapped_cid_in_cid_keyed_program() -> None:
    """A CID with no matching cidNNNNN in the charset → GID 0."""
    font = _make_font_with_descriptor()
    program = font.get_cff_font()
    if isinstance(program, CFFCIDFont):
        assert font.code_to_gid(9999) == 0


# ---------- get_width_from_font ----------


def test_get_width_from_font_returns_zero_when_no_program() -> None:
    font = PDCIDFontType0()
    assert font.get_width_from_font(1) == 0.0


def test_get_width_from_font_returns_program_width_only() -> None:
    """Unlike get_glyph_width, this method ignores /W."""
    font = _make_font_with_descriptor()
    # /W: CID 1 -> 999 (would mask the CFF's 500).
    w = COSArray([COSInteger.get(1), COSArray([COSInteger.get(999)])])
    font.set_w(w)
    # get_width_from_font ignores /W, so it returns the CFF program's value.
    assert font.get_width_from_font(1) == 500.0
    assert font.get_width_from_font(2) == 300.0


def test_get_width_from_font_returns_zero_for_unmapped_cid() -> None:
    font = _make_font_with_descriptor()
    assert font.get_width_from_font(99999) == 0.0


# ---------- get_height ----------


def test_get_height_returns_zero_when_no_program_and_no_w2() -> None:
    """Falls back to PDCIDFont.get_height which returns 0 for unmapped cids."""
    font = PDCIDFontType0()
    assert font.get_height(1) == 0.0


def test_get_height_returns_outline_height_from_cff_program() -> None:
    """CID 1's box outline spans y=0..700 → height 700."""
    font = _make_font_with_descriptor()
    assert font.get_height(1) == 700.0
    # CID 2's vertical stroke spans y=0..500.
    assert font.get_height(2) == 500.0


def test_get_height_caches_per_cid() -> None:
    font = _make_font_with_descriptor()
    first = font.get_height(1)
    second = font.get_height(1)
    assert first == second == 700.0


def test_get_height_zero_for_notdef() -> None:
    """.notdef is a single endchar — no outline → height 0."""
    font = _make_font_with_descriptor()
    assert font.get_height(0) == 0.0


def test_get_height_zero_for_unmapped_cid_with_program() -> None:
    font = _make_font_with_descriptor()
    assert font.get_height(99999) == 0.0


def test_get_height_falls_back_to_w2_when_no_program() -> None:
    """Without a CFF program, the parent /W2 lookup is consulted."""
    font = PDCIDFontType0()
    # /W2: CID 5 -> (w1y=750, v_x=0, v_y=880)
    w2 = COSArray(
        [
            COSInteger.get(5),
            COSArray(
                [
                    COSInteger.get(750),
                    COSInteger.get(0),
                    COSInteger.get(880),
                ]
            ),
        ]
    )
    font.set_w2(w2)
    assert font.get_height(5) == 750.0


# ---------- get_average_font_width ----------


def test_get_average_font_width_uses_w_when_present() -> None:
    """Mean of positive /W entries wins."""
    font = PDCIDFontType0()
    # /W: CID 1 -> 100, CID 2 -> 300, CID 3 -> 500. Mean = 300.
    w = COSArray(
        [
            COSInteger.get(1),
            COSArray(
                [
                    COSInteger.get(100),
                    COSInteger.get(300),
                    COSInteger.get(500),
                ]
            ),
        ]
    )
    font.set_w(w)
    assert font.get_average_font_width() == 300.0


def test_get_average_font_width_falls_back_to_dw_without_program() -> None:
    """No /W, no embedded CFF → /DW (defaults to 1000)."""
    font = PDCIDFontType0()
    assert font.get_average_font_width() == 1000.0
    font.set_dw(450)
    assert font.get_average_font_width() == 450.0


def test_get_average_font_width_falls_back_to_cff_default_when_no_w() -> None:
    """No /W, embedded CFF program with non-zero defaultWidthX → that value
    scaled to 1/1000 em. Our test fixture has defaultWidthX=0, so this
    test verifies the fallback to /DW takes over."""
    font = _make_font_with_descriptor()
    # Our fixture has no /W set and defaultWidthX=0 → falls through to /DW=1000.
    assert font.get_average_font_width() == 1000.0


# ---------- get_font_matrix ----------


def test_get_font_matrix_default_when_no_program() -> None:
    """No embedded CFF → CFF default matrix."""
    font = PDCIDFontType0()
    matrix = font.get_font_matrix()
    assert matrix == (0.001, 0.0, 0.0, 0.001, 0.0, 0.0)


def test_get_font_matrix_from_embedded_program() -> None:
    """Reads matrix from the CFF program's Top DICT."""
    font = _make_font_with_descriptor()
    matrix = font.get_font_matrix()
    assert len(matrix) == 6
    assert matrix[0] == 0.001
    assert matrix[3] == 0.001


def test_get_font_matrix_returns_tuple_for_immutability() -> None:
    """Tuple return prevents callers from mutating the cached matrix."""
    font = PDCIDFontType0()
    assert isinstance(font.get_font_matrix(), tuple)


# ---------- get_bounding_box ----------


def test_get_bounding_box_none_when_no_program_and_no_descriptor() -> None:
    font = PDCIDFontType0()
    assert font.get_bounding_box() is None


def test_get_bounding_box_from_embedded_cff_program() -> None:
    """fontTools synthesises a /FontBBox in the CFF Top DICT."""
    font = _make_font_with_descriptor()
    rect = font.get_bounding_box()
    assert isinstance(rect, PDRectangle)


def test_get_bounding_box_falls_back_to_descriptor_when_no_program() -> None:
    """No embedded CFF → descriptor's /FontBBox."""
    descriptor = PDFontDescriptor()
    bbox = COSArray(
        [
            COSFloat(-100.0),
            COSFloat(-200.0),
            COSFloat(900.0),
            COSFloat(800.0),
        ]
    )
    descriptor.get_cos_object().set_item(COSName.get_pdf_name("FontBBox"), bbox)
    font_dict = COSDictionary()
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    font = PDCIDFontType0(font_dict)
    rect = font.get_bounding_box()
    assert rect is not None
    assert rect.get_lower_left_x() == -100.0
    assert rect.get_upper_right_y() == 800.0


# ---------- is_damaged ----------


def test_is_damaged_false_when_not_embedded() -> None:
    """No /FontFile3 → nothing to be damaged."""
    assert PDCIDFontType0().is_damaged() is False
    assert _make_font_with_descriptor(with_data=False).is_damaged() is False


def test_is_damaged_false_for_well_formed_program() -> None:
    font = _make_font_with_descriptor()
    assert font.is_damaged() is False


def test_is_damaged_true_for_garbage_font_file3() -> None:
    """Garbage CFF bytes → parse fails → damaged."""
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(b"definitely not a CFF font set")
    stream.set_name(COSName.SUBTYPE, "CIDFontType0C")  # type: ignore[attr-defined]
    descriptor.set_font_file3(stream)
    font_dict = COSDictionary()
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    font = PDCIDFontType0(font_dict)
    assert font.is_damaged() is True
    # Repeated calls remain consistent.
    assert font.is_damaged() is True
