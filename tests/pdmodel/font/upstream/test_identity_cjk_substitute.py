"""Ported upstream test ``IdentityCJKSubstituteTest`` (PDFBOX-6249 /
PDFBOX-6293).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/
IdentityCJKSubstituteTest.java`` and its helper ``IdentityCJKFixture.java``
(PDFBox 3.0 branch, unreleased 3.0.9, commit e4011543).

Non-embedded Adobe-GB1 CID fonts substituted by an Adobe-Identity-0 CID-keyed
font (Noto CJK, Source Han). The PDF's CIDs are not glyph indices in such a
substitute, so glyphs must be resolved via Unicode: PDFBOX-6249 for
CIDFontType0, PDFBOX-6293 for CIDFontType2.

Upstream's fixture is a Noto Sans CJK SC subset (SIL OFL 1.1). It is not
copied here (OFL test fonts are kept out of the repo, as with the Lohit
fonts); instead an Adobe-Identity-0 OpenType/CFF font is built in memory with
fontTools. As in upstream's subset, U+4E2D resolves to a real glyph while
its Adobe-GB1 CID (4559) used as a GID hits nothing.
"""

import io
from collections.abc import Iterator
from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.fontbox.cid_font_mapping import CIDFontMapping
from pypdfbox.fontbox.font_mapper import DefaultFontMapper
from pypdfbox.fontbox.font_mappers import FontMappers
from pypdfbox.fontbox.ttf.otf_parser import OTFParser
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

# U+4E2D: GID 3 in the in-memory substitute, CID 4559 in Adobe-GB1
ZHONG = 0x4E2D
ZHONG_GID = 3

_ASCENT = COSName.get_pdf_name("Ascent")
_BASE_FONT = COSName.get_pdf_name("BaseFont")
_CAP_HEIGHT = COSName.get_pdf_name("CapHeight")
_CIDSYSTEMINFO = COSName.get_pdf_name("CIDSystemInfo")
_CID_FONT_TYPE0 = COSName.get_pdf_name("CIDFontType0")
_CID_FONT_TYPE2 = COSName.get_pdf_name("CIDFontType2")
_DESCENDANT_FONTS = COSName.get_pdf_name("DescendantFonts")
_DESCENT = COSName.get_pdf_name("Descent")
_DW = COSName.get_pdf_name("DW")
_ENCODING = COSName.get_pdf_name("Encoding")
_FLAGS = COSName.get_pdf_name("Flags")
_FONT = COSName.get_pdf_name("Font")
_FONT_BBOX = COSName.get_pdf_name("FontBBox")
_FONT_DESC = COSName.get_pdf_name("FontDescriptor")
_FONT_NAME = COSName.get_pdf_name("FontName")
_ITALIC_ANGLE = COSName.get_pdf_name("ItalicAngle")
_ORDERING = COSName.get_pdf_name("Ordering")
_REGISTRY = COSName.get_pdf_name("Registry")
_STEM_V = COSName.get_pdf_name("StemV")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_SUPPLEMENT = COSName.get_pdf_name("Supplement")
_TYPE = COSName.get_pdf_name("Type")
_TYPE0 = COSName.get_pdf_name("Type0")


def _build_substitute() -> Any:
    """An OpenType font with a CID-keyed CFF (Adobe-Identity-0) covering
    space and U+4E2D; far fewer glyphs than CID 4559."""
    from fontTools.cffLib import FDArrayIndex, FDSelect, FontDict
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString

    def _cs(program: list[Any]) -> T2CharString:
        cs = T2CharString()
        cs.program = program
        return cs

    order = [".notdef", "cid00001", "cid00002", "cid00003"]
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({0x20: "cid00001", ZHONG: "cid00003"})
    fb.setupCFF(
        psName="FakeNotoSansCJKsc-Regular",
        fontInfo={"FullName": "FakeNotoSansCJKsc"},
        charStringsDict={
            ".notdef": _cs([500, "endchar"]),
            "cid00001": _cs([224, "endchar"]),
            "cid00002": _cs([500, "endchar"]),
            "cid00003": _cs(
                [1000, 50, -60, "rmoveto", 880, "vlineto", 900, "hlineto",
                 -880, "vlineto", "endchar"]
            ),
        },
        privateDict={},
    )
    fb.setupHorizontalMetrics(
        {".notdef": (500, 0), "cid00001": (224, 0), "cid00002": (500, 0),
         "cid00003": (1000, 50)}
    )
    fb.setupHorizontalHeader(ascent=880, descent=-120)
    fb.setupOS2()
    fb.setupNameTable(
        {"familyName": "FakeNotoSansCJKsc", "styleName": "Regular",
         "psName": "FakeNotoSansCJKsc-Regular"}
    )
    fb.setupPost()
    top = fb.font["CFF "].cff.topDictIndex[0]
    top.ROS = ("Adobe", "Identity", 0)
    top.CIDCount = len(order)
    font_dict = FontDict()
    font_dict.setCFF2(False)
    font_dict.Private = top.Private
    fd_array = FDArrayIndex()
    fd_array.append(font_dict)
    top.FDArray = fd_array
    fd_select = FDSelect()
    fd_select.format = 3
    fd_select.gidArray = [0] * len(order)
    top.FDSelect = fd_select
    del top.Private
    buf = io.BytesIO()
    fb.font.save(buf)
    return OTFParser().parse(buf.getvalue())


class _FixtureMapper(DefaultFontMapper):
    """Upstream ``IdentityCJKFixture.FixtureMapper``: every CID font maps to
    the Identity substitute."""

    def __init__(self, substitute: Any) -> None:
        super().__init__()
        self._substitute = substitute

    def get_cid_font(self, base_font, font_descriptor, cid_system_info):  # type: ignore[override]
        return CIDFontMapping(self._substitute, None, True)


def type0(base_font: str, subtype: COSName, encoding: str) -> COSDictionary:
    """A non-embedded Adobe-GB1 Type0 font dictionary."""
    ros = COSDictionary()
    ros.set_item(_REGISTRY, COSString("Adobe"))
    ros.set_item(_ORDERING, COSString("GB1"))
    ros.set_int(_SUPPLEMENT, 2)

    fd = COSDictionary()
    fd.set_item(_TYPE, _FONT_DESC)
    fd.set_name(_FONT_NAME, base_font)
    fd.set_int(_FLAGS, 6)
    bbox = COSArray()
    for v in (0, -141, 996, 855):
        bbox.add(COSInteger.get(v))
    fd.set_item(_FONT_BBOX, bbox)
    fd.set_int(_ITALIC_ANGLE, 0)
    fd.set_int(_ASCENT, 859)
    fd.set_int(_DESCENT, -141)
    fd.set_int(_CAP_HEIGHT, 859)
    fd.set_int(_STEM_V, 80)

    cid = COSDictionary()
    cid.set_item(_TYPE, _FONT)
    cid.set_item(_SUBTYPE, subtype)
    cid.set_name(_BASE_FONT, base_font)
    cid.set_item(_CIDSYSTEMINFO, ros)
    cid.set_item(_FONT_DESC, fd)
    cid.set_int(_DW, 1000)

    descendants = COSArray()
    descendants.add(cid)
    font = COSDictionary()
    font.set_item(_TYPE, _FONT)
    font.set_item(_SUBTYPE, _TYPE0)
    font.set_name(_BASE_FONT, base_font)
    font.set_name(_ENCODING, encoding)
    font.set_item(_DESCENDANT_FONTS, descendants)
    return font


@pytest.fixture
def substitute() -> Iterator[Any]:
    otf = _build_substitute()
    cff = otf.get_cff()
    if cff.get_ordering() != "Identity":
        raise AssertionError("fixture is not Adobe-Identity-0")
    FontMappers.set(_FixtureMapper(otf))
    try:
        yield otf
    finally:
        FontMappers.reset()


def _bounds(path: list[tuple[Any, ...]]) -> tuple[float, float, float, float]:
    xs = [v for cmd in path for v in cmd[1::2]]
    ys = [v for cmd in path for v in cmd[2::2]]
    return (min(xs), min(ys), max(xs), max(ys))


def _assert_same_glyph(substitute: Any, path: list[tuple[Any, ...]]) -> None:
    # with the CID used as a GID, the fixture yields an empty glyph
    assert path, "glyph for U+4E2D has an empty path"
    expected = substitute.get_cff().get_type2_char_string(ZHONG_GID).get_path()
    assert _bounds(path) == _bounds(expected)
    x0, _, x1, _ = _bounds(path)
    assert x1 - x0 > 0


def test_cid_font_type2_resolves_via_unicode(substitute: Any) -> None:
    font = PDType0Font(type0("SimSun", _CID_FONT_TYPE2, "UniGB-UCS2-H"))
    cid_font = font.get_descendant_font()
    assert isinstance(cid_font, PDCIDFontType2)

    assert cid_font.code_to_gid(ZHONG) == ZHONG_GID, (
        "GID must be resolved via Unicode, not used as a CID"
    )
    _assert_same_glyph(substitute, cid_font.get_path(ZHONG))


def test_cid_font_type0_resolves_via_unicode(substitute: Any) -> None:
    font = PDType0Font(
        type0("AdobeSongStd-Light", _CID_FONT_TYPE0, "UniGB-UCS2-H")
    )
    cid_font = font.get_descendant_font()
    assert isinstance(cid_font, PDCIDFontType0)

    assert cid_font.code_to_gid(ZHONG) == ZHONG_GID, (
        "GID must be resolved via Unicode, not used as a CID"
    )
    _assert_same_glyph(substitute, cid_font.get_path(ZHONG))
