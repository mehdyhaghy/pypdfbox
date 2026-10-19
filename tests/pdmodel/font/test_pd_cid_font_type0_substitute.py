"""Hand-written pins for the non-embedded ``PDCIDFontType0`` port (upstream
constructor's substitute branch) and its PDFBOX-6249 forward-port (3.0
branch, unreleased 3.0.9): Unicode-resolved glyphs for an Adobe-Identity-0
CID-keyed substitute of a font from another character collection.

Every substitute is either built in memory or bundled with pypdfbox, so no
assertion depends on host-installed fonts. Upstream test:
``tests/pdmodel/font/upstream/test_pd_cid_font_type0_substitute.py``.
"""

import io
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.fontbox.cid_font_mapping import CIDFontMapping
from pypdfbox.fontbox.font_mapper import DefaultFontMapper
from pypdfbox.fontbox.font_mappers import FontMappers
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.fontbox.ttf.otf_parser import OTFParser
from pypdfbox.pdmodel.font import pd_cid_font_type0
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_system_info import PDCIDSystemInfo
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

_DEJAVU = (
    Path(__file__).resolve().parents[3] / "pypdfbox" / "resources" / "ttf" / "DejaVuSans.ttf"
)

# Adobe-CNS1 CIDs under UniCNS-UCS2-H: 'H' (U+0048) -> 41, U+4E2D -> 661
_CID_H = 41


def _build_cff_otf(
    ros: tuple[str, str, int] | None,
    glyphs: dict[str, tuple[int, int]],
) -> Any:
    """OpenType/CFF font. ``glyphs`` maps glyph name -> (unicode, advance);
    each glyph is a 100-wide box of height ``advance``. ``ros`` turns the CFF
    CID-keyed (glyph names must then be ``cidNNNNN``)."""
    from fontTools.cffLib import FDArrayIndex, FDSelect, FontDict
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString

    def _cs(program: list[Any]) -> T2CharString:
        cs = T2CharString()
        cs.program = program
        return cs

    order = [".notdef", *glyphs]
    charstrings = {".notdef": _cs([500, "endchar"])}
    for name, (_uni, advance) in glyphs.items():
        charstrings[name] = _cs(
            [advance, 0, "hmoveto", advance, "vlineto", 100, "hlineto", -advance,
             "vlineto", "endchar"]
        )
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({uni: name for name, (uni, _adv) in glyphs.items()})
    fb.setupCFF(
        psName="FakeCJK-Regular",
        fontInfo={"FullName": "FakeCJK"},
        charStringsDict=charstrings,
        privateDict={},
    )
    fb.setupHorizontalMetrics(dict.fromkeys(order, (500, 0)))
    fb.setupHorizontalHeader(ascent=880, descent=-120)
    fb.setupOS2()
    fb.setupNameTable(
        {"familyName": "FakeCJK", "styleName": "Regular", "psName": "FakeCJK-Regular"}
    )
    fb.setupPost()
    if ros is not None:
        top = fb.font["CFF "].cff.topDictIndex[0]
        top.ROS = ros
        top.CIDCount = 65535
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


def _identity_otf() -> Any:
    return _build_cff_otf(
        ("Adobe", "Identity", 0),
        {"cid00001": (0x48, 700), "cid00002": (0x4E2D, 900)},
    )


class _Mapper(DefaultFontMapper):
    def __init__(self, mapping: CIDFontMapping | None) -> None:
        super().__init__()
        self._mapping = mapping
        self.calls = 0

    def get_cid_font(self, base_font, font_descriptor, cid_system_info):  # type: ignore[override]
        self.calls += 1
        return self._mapping


@pytest.fixture
def mapper() -> Iterator[Any]:
    def install(mapping: CIDFontMapping | None) -> _Mapper:
        m = _Mapper(mapping)
        FontMappers.set(m)
        return m

    try:
        yield install
    finally:
        FontMappers.reset()


def _type0(
    *,
    ordering: str = "CNS1",
    encoding: str = "UniCNS-UCS2-H",
    font_file3: bytes | None = None,
    bbox: list[float] | None = None,
) -> PDType0Font:
    descendant = COSDictionary()
    descendant.set_name(COSName.TYPE, "Font")  # type: ignore[attr-defined]
    descendant.set_name(COSName.SUBTYPE, "CIDFontType0")  # type: ignore[attr-defined]
    descendant.set_name(COSName.get_pdf_name("BaseFont"), "MSungStd-Light-Acro")
    info = PDCIDSystemInfo()
    info.set_registry("Adobe")
    info.set_ordering(ordering)
    info.set_supplement(0)
    descendant.set_item(COSName.get_pdf_name("CIDSystemInfo"), info.get_cos_object())
    fd = PDFontDescriptor()
    fd.set_font_name("MSungStd-Light-Acro")
    if bbox is not None:
        arr = COSArray()
        for v in bbox:
            arr.add(COSFloat(float(v)))
        fd.get_cos_object().set_item(COSName.get_pdf_name("FontBBox"), arr)
    if font_file3 is not None:
        stream = COSStream()
        stream.set_data(font_file3)
        stream.set_name(COSName.SUBTYPE, "CIDFontType0C")  # type: ignore[attr-defined]
        fd.set_font_file3(stream)
    descendant.set_item(COSName.get_pdf_name("FontDescriptor"), fd.get_cos_object())
    font_dict = COSDictionary()
    font_dict.set_name(COSName.SUBTYPE, "Type0")  # type: ignore[attr-defined]
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MSungStd-Light-Acro")
    font_dict.set_name(COSName.get_pdf_name("Encoding"), encoding)
    arr = COSArray()
    arr.add(descendant)
    font_dict.set_item(COSName.get_pdf_name("DescendantFonts"), arr)
    return PDType0Font(font_dict)


def _descendant(font: PDType0Font) -> PDCIDFontType0:
    d = font.get_descendant_font()
    assert isinstance(d, PDCIDFontType0)
    return d


# ---------- PDFBOX-6249: Identity substitute of another collection ----------


def test_identity_substitute_resolves_glyphs_via_unicode(mapper: Any) -> None:
    otf = _identity_otf()
    mapper(CIDFontMapping(otf, None, True))
    font = _type0()
    d = _descendant(font)
    assert not d.is_embedded()
    assert isinstance(d.get_font_box_font(), CFFCIDFont)
    assert d.code_to_cid(0x48, font) == _CID_H
    # GID 1 is 'H', found through toUnicode + the substitute's Unicode cmap
    assert d.code_to_gid(0x48, font) == 1
    assert d.code_to_gid(0x4E2D, font) == 2
    assert d.has_glyph(0x48, font)
    assert d.get_path(0x48, font) == d.get_type2_char_string(1).get_path()
    assert d.get_normalized_path(0x48, font) == d.get_path(0x48, font)
    assert d.get_width_from_font(0x48, font) == pytest.approx(700.0)
    assert d.get_width_from_font(0x4E2D, font) == pytest.approx(900.0)
    # the Type 0 entry points forward the raw code
    assert font.code_to_gid(0x48) == 1
    assert font.has_glyph(0x48)
    assert font.get_width_from_font(0x48) == pytest.approx(700.0)
    assert font.get_path(0x48) == d.get_path(0x48, font)
    assert font.get_normalized_path(0x48) == d.get_path(0x48, font)


def test_identity_substitute_unmapped_unicode_is_notdef(mapper: Any) -> None:
    mapper(CIDFontMapping(_identity_otf(), None, True))
    font = _type0()
    d = _descendant(font)
    # 'e' (U+0065) has a Unicode value but no glyph in the substitute
    assert d.code_to_gid(0x65, font) == 0
    assert not d.has_glyph(0x65, font)
    notdef = d.get_type2_char_string(0)
    assert d.get_path(0x65, font) == notdef.get_path()
    assert d.get_width_from_font(0x65, font) == pytest.approx(notdef.get_width())


def test_identity_substitute_code_without_unicode_is_notdef(
    mapper: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A code with no Unicode value resolves to GID 0 (upstream
    ``codeToSubstituteGID`` returns -1)."""
    mapper(CIDFontMapping(_identity_otf(), None, True))
    font = _type0()
    d = _descendant(font)
    # PDFBOX-6175: the descendant holds no parent reference
    assert not hasattr(d, "get_parent")
    monkeypatch.setattr(font, "to_unicode", lambda code: None)
    assert d._code_to_substitute_gid(0x48, font) == -1
    assert d.code_to_gid(0x48, font) == 0
    assert not d.has_glyph(0x48, font)


def test_matching_collection_substitute_uses_cids(mapper: Any) -> None:
    """A CID-keyed substitute of the same collection keeps the CID lookup
    through its charset (no Unicode cmap)."""
    otf = _build_cff_otf(("Adobe", "CNS1", 0), {f"cid{_CID_H:05d}": (0x48, 650)})
    mapper(CIDFontMapping(otf, None, False))
    font = _type0()
    d = _descendant(font)
    assert d._get_substitute_unicode_cmap() is None
    assert d.code_to_gid(0x48, font) == 1  # charset index of cid00041
    assert d.has_glyph(0x48, font)
    assert d.get_width_from_font(0x48, font) == pytest.approx(650.0)
    assert d.get_path(0x48, font) == d.get_type2_char_string(_CID_H).get_path()


def test_non_identity_other_collection_keeps_cids(mapper: Any) -> None:
    """Only an ``Identity`` ordering triggers the Unicode lookup: an
    Adobe-Japan1 substitute of an Adobe-CNS1 font still gets the CIDs."""
    otf = _build_cff_otf(("Adobe", "Japan1", 0), {"cid00001": (0x48, 700)})
    mapper(CIDFontMapping(otf, None, False))
    font = _type0()
    d = _descendant(font)
    assert d._get_substitute_unicode_cmap() is None
    assert d.code_to_gid(0x48, font) == 0  # CID 41 is not in the charset
    assert not d.has_glyph(0x48, font)


def test_character_collection_match() -> None:
    font = _type0()
    d = _descendant(font)
    cns1 = CFFCIDFont()
    cns1.set_registry("Adobe")
    cns1.set_ordering("CNS1")
    identity = CFFCIDFont()
    identity.set_registry("Adobe")
    identity.set_ordering("Identity")
    assert d._is_character_collection_match(cns1)
    assert not d._is_character_collection_match(identity)


# ---------- other substitute shapes ----------


def test_name_keyed_cff_substitute_is_t1_font(mapper: Any) -> None:
    """PDFBOX-3515: a name-keyed CFF OpenType substitute loads as
    ``CFFType1Font``; its charstrings are addressed with the CID as GID."""
    otf = _build_cff_otf(None, {"H": (0x48, 600)})
    mapper(CIDFontMapping(otf, None, False))
    font = _type0()
    d = _descendant(font)
    assert isinstance(d.get_font_box_font(), CFFType1Font)
    assert d.code_to_gid(0x48, font) == _CID_H
    # CID 41 as a GID is past the end of the two-glyph font: like upstream
    # ``CFFType1Font.getType2CharString(gid)``, the .notdef charstring is
    # used but keeps the requested GID, so hasGlyph (GID != 0) is true
    cs = d.get_type2_char_string(_CID_H)
    assert cs.get_gid() == _CID_H
    assert d.has_glyph(0x48, font)


def test_true_type_substitute_uses_uni_glyph_names(mapper: Any) -> None:
    ttf = TrueTypeFont.from_bytes(_DEJAVU.read_bytes())
    mapper(CIDFontMapping(None, ttf, False))
    font = _type0()
    d = _descendant(font)
    assert d.get_font_box_font() is ttf
    assert d.get_type2_char_string(_CID_H) is None
    gid = ttf.name_to_gid("uni0048")
    assert gid > 0
    upem = ttf.get_units_per_em()
    assert d.get_font_matrix() == pytest.approx((1 / upem, 0.0, 0.0, 1 / upem, 0.0, 0.0))
    assert d.has_glyph(0x48, font)
    assert d.get_path(0x48, font)
    assert d.get_width_from_font(0x48, font) == pytest.approx(
        ttf.get_advance_width(gid) * 1000.0 / upem
    )
    # the CID is the GID for a TrueType substitute
    assert d.code_to_gid(0x48, font) == _CID_H


def test_default_mapper_uses_bundled_last_resort(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The default pypdfbox mapper has no CID font scanner: the bundled
    last-resort font stands in, as upstream's mapper's last resort does,
    and the fallback warning is logged only once per font."""
    FontMappers.reset()
    pd_cid_font_type0._WARNED_FALLBACKS.clear()
    font = _type0()
    with caplog.at_level(logging.WARNING, logger=pd_cid_font_type0.__name__):
        d = _descendant(font)
        program = d.get_font_box_font()
        assert isinstance(program, TrueTypeFont)
        assert d.has_glyph(0x48, font)
        assert d.get_path(0x48, font)
        assert d.get_width_from_font(0x48, font) > 0.0
        _descendant(font).get_font_box_font()
    warnings = [r for r in caplog.records if "Using fallback" in r.getMessage()]
    assert len(warnings) == 1
    assert "MSungStd-Light-Acro" in warnings[0].getMessage()


def test_substitute_resolved_once_per_descendant(mapper: Any) -> None:
    m = mapper(CIDFontMapping(_identity_otf(), None, True))
    font = _type0()
    d = _descendant(font)
    d.has_glyph(0x48, font)
    d.get_path(0x48, font)
    d.get_width_from_font(0x48, font)
    assert m.calls == 1


def test_bare_descendant_resolves_substitute(mapper: Any) -> None:
    """PDFBOX-6175: the descendant no longer knows its parent, so a bare
    non-embedded descendant resolves its substitute too (trunk has no
    parent gate). Without a parent there is no ToUnicode, so the
    Unicode-resolved Identity substitute answers ``.notdef`` (GID 0)."""
    m = mapper(CIDFontMapping(_identity_otf(), None, True))
    d = PDCIDFontType0(COSDictionary())
    assert isinstance(d.get_font_box_font(), CFFCIDFont)
    assert d.code_to_gid(1, None) == 0
    assert not d.has_glyph(1, None)
    notdef = d.get_type2_char_string(0)
    assert d.get_path(1, None) == notdef.get_path()
    assert d.get_width_from_font(1, None) == pytest.approx(notdef.get_width())
    assert m.calls == 1


def test_bounding_box_falls_back_to_substitute(mapper: Any) -> None:
    mapper(CIDFontMapping(_identity_otf(), None, True))
    font = _type0(bbox=[0, 0, 0, 0])
    d = _descendant(font)
    rect = d.get_bounding_box()
    expected = [float(v) for v in d.get_font_box_font().get_font_b_box()]
    assert expected != [0.0, 0.0, 0.0, 0.0]
    assert [
        rect.get_lower_left_x(),
        rect.get_lower_left_y(),
        rect.get_upper_right_x(),
        rect.get_upper_right_y(),
    ] == expected


def test_height_from_cff_substitute(mapper: Any) -> None:
    otf = _build_cff_otf(("Adobe", "CNS1", 0), {f"cid{_CID_H:05d}": (0x48, 650)})
    mapper(CIDFontMapping(otf, None, False))
    font = _type0()
    d = _descendant(font)
    assert d.get_height(0x48, font) == pytest.approx(650.0)


# ---------- embedded / damaged ----------


def test_damaged_font_file3_uses_substitute(mapper: Any) -> None:
    mapper(CIDFontMapping(_identity_otf(), None, True))
    font = _type0(font_file3=b"%!PS-AdobeFont-1.0 not a CFF")
    d = _descendant(font)
    assert d.is_damaged()
    assert not d.is_embedded()
    assert d.has_glyph(0x48, font)
    assert d.code_to_gid(0x48, font) == 1


def test_embedded_font_ignores_mapper(mapper: Any) -> None:
    m = mapper(CIDFontMapping(_identity_otf(), None, True))
    otf = _build_cff_otf(("Adobe", "CNS1", 0), {f"cid{_CID_H:05d}": (0x48, 650)})
    cff_bytes = otf._tt.getTableData("CFF ")
    font = _type0(font_file3=cff_bytes)
    d = _descendant(font)
    assert d.is_embedded()
    assert not d.is_damaged()
    assert d.has_glyph(0x48, font)
    assert d.code_to_gid(0x48, font) == 1
    assert d.get_width_from_font(0x48, font) == pytest.approx(650.0)
    assert m.calls == 0
