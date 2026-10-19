"""Ported upstream test ``PDCIDFontType0SubstituteTest`` (PDFBOX-6249).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/
PDCIDFontType0SubstituteTest.java`` (PDFBox 3.0 branch, unreleased 3.0.9,
commit efa041c295).

A non-embedded Adobe-CNS1 CIDFontType0 must render real glyphs when a
CID-keyed substitute is available, even when the substitute uses a different
character collection (modern CJK fonts such as Noto CJK are Adobe-Identity-0).

Upstream's test depends on the host offering a CID-keyed CJK font and is
skipped (``assumeTrue``) otherwise. Here a test :class:`FontMapper` hands out a
deterministic Adobe-Identity-0 OpenType/CFF font built in memory, so the
assertions always run and never depend on host-installed fonts. The fixture
PDF is upstream's own ``PDFBOX-6249-cns1-nonembedded-latin.pdf``.
"""

import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import COSName
from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cid_font_mapping import CIDFontMapping
from pypdfbox.fontbox.font_mapper import DefaultFontMapper
from pypdfbox.fontbox.font_mappers import FontMappers
from pypdfbox.fontbox.ttf.otf_parser import OTFParser
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument

_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "pdmodel"
    / "font"
    / "PDFBOX-6249-cns1-nonembedded-latin.pdf"
)


def _build_identity_cid_otf() -> Any:
    """An OpenType font with a CID-keyed CFF (Adobe-Identity-0): GID 1 is
    'H', GID 2 is 'e', GID 3 is U+4E2D. Fewer than 42 glyphs, so CID 41
    (Adobe-CNS1 'H') used as an Identity GID would hit nothing."""
    from fontTools.cffLib import FDArrayIndex, FDSelect, FontDict
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString

    def _cs(program: list[Any]) -> T2CharString:
        cs = T2CharString()
        cs.program = program
        return cs

    def _box(width: int, height: int) -> T2CharString:
        return _cs(
            [width, 0, "hmoveto", height, "vlineto", 100, "hlineto", -height,
             "vlineto", "endchar"]
        )

    order = [".notdef", "cid00001", "cid00002", "cid00003"]
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({0x48: "cid00001", 0x65: "cid00002", 0x4E2D: "cid00003"})
    fb.setupCFF(
        psName="FakeIdentityCJK-Regular",
        fontInfo={"FullName": "FakeIdentityCJK"},
        charStringsDict={
            ".notdef": _cs([500, "endchar"]),
            "cid00001": _box(700, 700),
            "cid00002": _box(550, 500),
            "cid00003": _box(1000, 800),
        },
        privateDict={},
    )
    fb.setupHorizontalMetrics(dict.fromkeys(order, (500, 0)))
    fb.setupHorizontalHeader(ascent=880, descent=-120)
    fb.setupOS2()
    fb.setupNameTable(
        {"familyName": "FakeIdentityCJK", "styleName": "Regular",
         "psName": "FakeIdentityCJK-Regular"}
    )
    fb.setupPost()
    # turn the name-keyed CFF into a CID-keyed one (Adobe-Identity-0)
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


class _CIDSubstituteMapper(DefaultFontMapper):
    """FontMapper whose ``get_cid_font`` returns a CID-keyed OpenType font,
    the way upstream's ``FontMapperImpl`` returns a host CJK font."""

    def __init__(self, otf: Any) -> None:
        super().__init__()
        self._otf = otf

    def get_cid_font(self, base_font, font_descriptor, cid_system_info):  # type: ignore[override]
        return CIDFontMapping(self._otf, None, True)


@pytest.fixture
def cid_substitute() -> Iterator[Any]:
    otf = _build_identity_cid_otf()
    FontMappers.set(_CIDSubstituteMapper(otf))
    try:
        yield otf
    finally:
        FontMappers.reset()


def test_latin_via_cns1_non_embedded(cid_substitute: Any) -> None:
    doc = PDDocument.load(str(_FIXTURE))
    try:
        page = doc.get_page(0)
        font = page.get_resources().get_font(COSName.get_pdf_name("F1"))
        assert isinstance(font, PDType0Font)
        cid_font = font.get_descendant_font()
        assert isinstance(cid_font, PDCIDFontType0)

        mapping = FontMappers.instance().get_cid_font(
            cid_font.get_base_font(),
            cid_font.get_font_descriptor(),
            cid_font.get_cid_system_info(),
        )
        # upstream: assumeTrue(mapping.isCIDFont(), ...); always true here
        assert mapping.is_cid_font()

        # 0x48 is "H": the CMap maps it to CID 41, which is not a valid glyph
        # index in an Adobe-Identity-0 substitute; it must be resolved via
        # Unicode
        assert cid_font.code_to_cid(0x48, font) == 41
        assert cid_font.has_glyph(0x48, font), "glyph for 'H' not found in substitute"
        path = cid_font.get_path(0x48, font)
        assert path, "glyph for 'H' has an empty path"

        # Skipped: the "regular weight should be preferred over Bold on a
        # weightless descriptor" assertion exercises FontMapperImpl's scoring
        # (the FontMapperImpl half of PDFBOX-6249), not PDCIDFontType0; the
        # test mapper here returns a fixed font.

        cff = mapping.get_font().get_cff()
        if isinstance(cff, CFFCIDFont) and cff.get_ordering() == "Identity":
            # ASCII GIDs happen to line up with Adobe CIDs in Noto/Source Han,
            # so assert on an ideograph, where using the CID as a GID yields
            # the wrong glyph
            expected = mapping.get_font().get_unicode_cmap_lookup().get_glyph_id(0x4E2D)
            assert expected > 0
            assert cid_font.code_to_gid(0x4E2D, font) == expected, (
                "GID must be resolved via Unicode, not used as a CID"
            )
    finally:
        doc.close()
