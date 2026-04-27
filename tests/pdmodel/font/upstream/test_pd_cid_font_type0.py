"""Ported from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDCIDFontType0Test.java``
(PDFBox 3.0.x).

Upstream's ``PDCIDFontType0Test`` is a thin smoke test for the
embedded CFF round-trip: it loads a CIDFontType0 font from a real
PDF fixture and asserts that ``getCFFFont()`` returns a non-null
program of the expected polymorphic type, that ``codeToCID`` /
``codeToGID`` are well-defined for at least one code in the font,
and that the embedded program reports its own ``isEmbedded`` /
``isDamaged`` correctly.

Tests that depend on a binary PDF fixture we don't ship (e.g.
``testPDFBox4892``) are skipped with a one-line note. The remaining
tests are translated to use the same in-memory CFF fixture pattern
as the hand-written tests in :mod:`tests.pdmodel.font.test_pd_cid_font_type0`.
"""
from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor


def _build_cff_bytes() -> bytes:
    """In-memory CFF program whose Top DICT exposes a /FontMatrix and
    whose /CharStrings contains one cidNNNNN-shaped glyph — enough to
    exercise the round-trip checks below without an external PDF."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString
    from fontTools.ttLib import TTFont

    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder([".notdef", "cid00001"])
    fb.setupCharacterMap({1: "cid00001"})

    def _cs(program: list) -> T2CharString:
        s = T2CharString()
        s.program = program
        return s

    cs_dict = {
        ".notdef": _cs([0, "endchar"]),
        "cid00001": _cs(
            [400, 0, "hmoveto", 600, "vlineto", 200, "hlineto", -600, "vlineto", "endchar"]
        ),
    }
    fb.setupCFF(
        psName="Test",
        fontInfo={"FullName": "Test"},
        charStringsDict=cs_dict,
        privateDict={},
    )
    fb.setupHorizontalMetrics({".notdef": (0, 0), "cid00001": (400, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    return bytes(TTFont(io.BytesIO(buf.getvalue())).getTableData("CFF "))


def _make_embedded_font() -> PDCIDFontType0:
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(_build_cff_bytes())
    stream.set_name(COSName.SUBTYPE, "CIDFontType0C")  # type: ignore[attr-defined]
    descriptor.set_font_file3(stream)
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "Test")
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    return PDCIDFontType0(font_dict)


# Upstream: testEmbeddedFontProgramIsAccessible
def test_get_cff_font_is_accessible_for_embedded_program() -> None:
    """``getCFFFont`` must return a non-null CFF program for a
    well-formed embedded /FontFile3 stream."""
    font = _make_embedded_font()
    program = font.get_cff_font()
    assert program is not None
    assert isinstance(program, CFFFont)


# Upstream: testIsEmbedded
def test_is_embedded_for_well_formed_program() -> None:
    """A descriptor with /FontFile3 (/Subtype /CIDFontType0C) is embedded."""
    font = _make_embedded_font()
    assert font.is_embedded() is True
    assert font.is_cff_embedded() is True


# Upstream: testIsDamaged
def test_is_damaged_false_for_well_formed_program() -> None:
    font = _make_embedded_font()
    assert font.is_damaged() is False


# Upstream: testCodeToCID
def test_code_to_cid_is_identity() -> None:
    font = _make_embedded_font()
    # The parent Type0 font has already CMap-decoded the code into a CID
    # by the time PDCIDFontType0.codeToCID is called; identity here
    # mirrors PDCIDFontType0.codeToCID upstream.
    assert font.code_to_cid(1) == 1
    assert font.code_to_cid(0) == 0


# Upstream: testCodeToGID — when the embedded CFF is name-keyed
# fontTools synthesises (FontBuilder doesn't materialise /ROS), CID is
# returned as GID.
def test_code_to_gid_well_defined() -> None:
    font = _make_embedded_font()
    # Either path (CID-keyed charset lookup or name-keyed CID-as-GID)
    # yields a non-negative integer.
    assert font.code_to_gid(1) >= 0


# Upstream: testGetWidthFromFont — the embedded CFF program reports the
# advance unaffected by /W.
def test_get_width_from_font_reads_program_advance() -> None:
    font = _make_embedded_font()
    # Our cid00001 charstring carries width 400.
    assert font.get_width_from_font(1) == 400.0


# Upstream: testGetGlyphHeight — height derived from outline bbox.
def test_get_height_from_program_outline() -> None:
    font = _make_embedded_font()
    # cid00001's outline spans y=0..600 → height 600.
    assert font.get_height(1) == 600.0


# Upstream: testGetFontMatrix — embedded CFF Top DICT FontMatrix.
def test_get_font_matrix_from_embedded_program() -> None:
    font = _make_embedded_font()
    matrix = font.get_font_matrix()
    assert len(matrix) == 6
    # CFF default font matrix.
    assert matrix[0] == 0.001
    assert matrix[3] == 0.001


# Upstream: testGetBoundingBox — present and 4-element.
def test_get_bounding_box_present_for_embedded_program() -> None:
    font = _make_embedded_font()
    rect = font.get_bounding_box()
    assert rect is not None


# ---------------- skipped tests ----------------

# Skipped: upstream ``testPDFBox4892`` requires the binary fixture
# ``PDFBOX-4892.pdf`` which we don't ship; it asserts a damaged-CFF
# detection on a real-world malformed font. Our :func:`test_is_damaged`
# in ``test_pd_cid_font_type0`` covers the same code path with an
# in-memory garbage stream.

# Skipped: upstream ``testCIDToGIDMap`` belongs to PDCIDFontType2 (TTF)
# in the upstream test class hierarchy; our PDCIDFontType0 cluster does
# not own that path (PDCIDFont.get_cid_to_gid_map is the parent-level
# accessor).
