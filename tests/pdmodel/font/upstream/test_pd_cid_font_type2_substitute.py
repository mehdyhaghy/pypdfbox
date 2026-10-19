"""Ported upstream test ``PDCIDFontType2SubstituteTest`` (PDFBOX-5953) plus the
PDFBOX-6251 non-embedded OpenType/CFF substitute case.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/
PDCIDFontType2SubstituteTest.java`` (PDFBox 3.0 branch, unreleased 3.0.9,
commit 5a329b3772).

Upstream's fixture is a 2 MB real-world bank receipt form (JIRA attachment
``PDFBOX-5953-test.pdf``) whose AcroForm ``/DR`` font ``SimSun`` is a
non-embedded Type0/CIDFontType2 with ``/Encoding /UniGB-UTF16-H``; the test
also relies on the host offering a CJK substitute for U+767E. Neither is
reproducible offline or across machines, so the font is built in memory here
with the same shape (non-embedded CIDFontType2, Adobe-GB1, UniGB-UTF16-H) and
a test :class:`FontMapper` hands out a deterministic substitute. The asserted
round trip is upstream's: ``encode(unicode)`` must yield a code that
``codeToGID`` maps back to the substitute's glyph for that Unicode value.
"""

import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.fontbox.cid_font_mapping import CIDFontMapping
from pypdfbox.fontbox.font_mapper import DefaultFontMapper
from pypdfbox.fontbox.font_mappers import FontMappers
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_cid_system_info import PDCIDSystemInfo
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

_DEJAVU = (
    Path(__file__).resolve().parents[4] / "pypdfbox" / "resources" / "ttf" / "DejaVuSans.ttf"
)


class _SubstituteMapper(DefaultFontMapper):
    """FontMapper whose ``get_cid_font`` returns a fixed substitute, the way
    upstream's ``FontMapperImpl`` returns a host font for a non-embedded
    CID font."""

    def __init__(self, font: Any) -> None:
        super().__init__()
        self._font = font

    def get_cid_font(self, base_font, font_descriptor, cid_system_info):  # type: ignore[override]
        return CIDFontMapping(None, self._font, True)


@pytest.fixture
def substitute_mapper() -> Iterator[Any]:
    def install(font: Any) -> None:
        FontMappers.set(_SubstituteMapper(font))

    try:
        yield install
    finally:
        FontMappers.reset()


def _build_type0(
    encoding: str,
    registry: str,
    ordering: str,
    to_unicode: str | None = None,
) -> PDType0Font:
    """A non-embedded Type0/CIDFontType2 (no /FontFile*)."""
    descendant = COSDictionary()
    descendant.set_name(COSName.TYPE, "Font")  # type: ignore[attr-defined]
    descendant.set_name(COSName.SUBTYPE, "CIDFontType2")  # type: ignore[attr-defined]
    descendant.set_name(COSName.get_pdf_name("BaseFont"), "SimSun")
    info = PDCIDSystemInfo()
    info.set_registry(registry)
    info.set_ordering(ordering)
    info.set_supplement(0)
    descendant.set_item(COSName.get_pdf_name("CIDSystemInfo"), info.get_cos_object())
    fd = PDFontDescriptor()
    fd.set_font_name("SimSun")
    descendant.set_item(COSName.get_pdf_name("FontDescriptor"), fd.get_cos_object())

    font_dict = COSDictionary()
    font_dict.set_name(COSName.SUBTYPE, "Type0")  # type: ignore[attr-defined]
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "SimSun")
    font_dict.set_name(COSName.get_pdf_name("Encoding"), encoding)
    arr = COSArray()
    arr.add(descendant)
    font_dict.set_item(COSName.get_pdf_name("DescendantFonts"), arr)
    if to_unicode is not None:
        stream = COSStream()
        with stream.create_output_stream() as out:
            out.write(to_unicode.encode("ascii"))
        font_dict.set_item(COSName.get_pdf_name("ToUnicode"), stream)
    return PDType0Font(font_dict)


@pytest.mark.parametrize("unicode", [0x41, 0x7A], ids=["A", "z"])
def test_encode_non_embedded_predefined_unicode_encoding(
    substitute_mapper: Any, unicode: int
) -> None:
    """Upstream ``testEncodeNonEmbeddedPredefinedUnicodeEncoding``."""
    substitute = TrueTypeFont.from_bytes(_DEJAVU.read_bytes())
    substitute_mapper(substitute)
    font = _build_type0("UniGB-UTF16-H", "Adobe", "GB1")
    cid_font = font.get_descendant_font()
    assert isinstance(cid_font, PDCIDFontType2)
    assert not cid_font.is_embedded()
    assert font.get_cmap().get_name().startswith("Uni")

    substitute_cmap = cid_font._resolve_program().get_unicode_cmap_lookup(False)
    expected_gid = substitute_cmap.get_glyph_id(unicode)
    assert expected_gid != 0

    data = cid_font.encode(unicode, font)
    assert len(data) == 2
    code = (data[0] << 8) | data[1]
    # the code is the raw Unicode value (the UniGB-UTF16-H codespace) ...
    assert code == unicode
    # ... which decodes back to the substitute font's glyph for it; before
    # PDFBOX-5953 the substitute's own GID was written and decoded to a
    # wrong, arbitrary glyph
    assert cid_font.code_to_gid(code, font) == expected_gid
    # the Type0 entry point writes the same code
    assert font.encode(chr(unicode)) == data


def test_encode_non_embedded_identity_uses_substitute_gid(substitute_mapper: Any) -> None:
    """The PDFBOX-5953 branch is limited to predefined ``Uni...`` CMaps: under
    Identity-H the substitute's glyph index is still written."""
    substitute = TrueTypeFont.from_bytes(_DEJAVU.read_bytes())
    substitute_mapper(substitute)
    font = _build_type0("Identity-H", "Adobe", "Identity")
    cid_font = font.get_descendant_font()
    gid = substitute.get_unicode_cmap_lookup(False).get_glyph_id(0x41)
    assert gid != 0x41
    assert cid_font.encode(0x41, font) == gid.to_bytes(2, "big")


def _otf_cff_bytes() -> bytes:
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString

    def cs(program: list) -> T2CharString:
        s = T2CharString()
        s.program = program
        return s

    order = [".notdef", "A", "B"]
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({0x41: "A", 0x42: "B"})
    fb.setupCFF(
        psName="OtfCff",
        fontInfo={"FullName": "OtfCff"},
        charStringsDict={
            ".notdef": cs([0, "endchar"]),
            "A": cs([500, 0, "hmoveto", 700, "vlineto", "endchar"]),
            "B": cs([300, 0, "hmoveto", 500, "vlineto", "endchar"]),
        },
        privateDict={},
    )
    fb.setupHorizontalMetrics(dict.fromkeys(order, (500, 0)))
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2()
    fb.setupNameTable({"familyName": "OtfCff", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    return buf.getvalue()


_TO_UNICODE_7_TO_A = """/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CMapName /Test-UCS def
/CMapType 2 def
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
1 beginbfchar
<0007> <0041>
endbfchar
endcmap
CMapName currentdict /CMap defineresource pop
end
end
"""


def test_pdfbox6251_cff_substitute_uses_cid_as_gid(substitute_mapper: Any) -> None:
    """PDFBOX-6251 (3.0 branch commit 6dfa7d3aa4): for a non-embedded font whose
    substitute is a CFF-based OpenType font, "Identity" is the default, so
    codeToGID returns the CID even when a Unicode mapping exists (as in the
    embedded case)."""
    raw = _otf_cff_bytes()
    otf = PDCIDFontType2.get_parser(raw, is_embedded=False).parse_embedded(raw)
    assert otf.is_post_script()
    substitute_mapper(otf)
    font = _build_type0("Identity-H", "Adobe", "Identity", to_unicode=_TO_UNICODE_7_TO_A)
    cid_font = font.get_descendant_font()
    assert not cid_font.is_embedded()
    assert font.to_unicode(7) == "A"
    # without PDFBOX-6251 this would be the cmap GID of "A" (1)
    assert cid_font.code_to_gid(7, font) == 7
    assert font.code_to_gid(7) == 7


def test_truetype_substitute_resolves_through_to_unicode(substitute_mapper: Any) -> None:
    """Non-embedded + TrueType substitute: code -> /ToUnicode -> substitute
    cmap (PDFBOX-1422 / PDFBOX-2560); a code without a Unicode mapping uses
    the CID as the GID (PDFBOX-2599)."""
    substitute = TrueTypeFont.from_bytes(_DEJAVU.read_bytes())
    substitute_mapper(substitute)
    font = _build_type0("Identity-H", "Adobe", "Identity", to_unicode=_TO_UNICODE_7_TO_A)
    cid_font = font.get_descendant_font()
    gid_a = substitute.get_unicode_cmap_lookup(False).get_glyph_id(0x41)
    assert cid_font.code_to_gid(7, font) == gid_a
    assert cid_font.code_to_gid(9, font) == 9
    assert cid_font.get_width_from_font(7, font) > 0.0
    assert cid_font.get_path(7, font)
