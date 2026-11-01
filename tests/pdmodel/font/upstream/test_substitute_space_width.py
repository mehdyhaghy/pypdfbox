"""Ported upstream test ``SubstituteSpaceWidthTest`` (PDFBOX-6292).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/
SubstituteSpaceWidthTest.java`` (PDFBox 3.0 branch, unreleased 3.0.9,
commit 45b614dc).

The space width of a non-embedded Identity-H CIDFontType2 without ToUnicode
must come from the PDF, not from whichever substitute is installed.
"""

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

_ASCENT = COSName.get_pdf_name("Ascent")
_BASE_FONT = COSName.get_pdf_name("BaseFont")
_CAP_HEIGHT = COSName.get_pdf_name("CapHeight")
_CIDSYSTEMINFO = COSName.get_pdf_name("CIDSystemInfo")
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
_W = COSName.get_pdf_name("W")


def _sim_sun_identity_h() -> COSDictionary:
    ros = COSDictionary()
    ros.set_item(_REGISTRY, COSString("Adobe"))
    ros.set_item(_ORDERING, COSString("GB1"))
    ros.set_int(_SUPPLEMENT, 2)

    fd = COSDictionary()
    fd.set_item(_TYPE, _FONT_DESC)
    fd.set_name(_FONT_NAME, "SimSun")
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

    # widths for codes 0-31 only: the substitute's space GID lands here if it
    # is wrongly used as a code, while the PDF's code 32 falls back to /DW
    widths = COSArray()
    for _ in range(32):
        widths.add(COSInteger.get(500))
    w = COSArray()
    w.add(COSInteger.get(0))
    w.add(widths)

    cid = COSDictionary()
    cid.set_item(_TYPE, _FONT)
    cid.set_item(_SUBTYPE, _CID_FONT_TYPE2)
    cid.set_name(_BASE_FONT, "SimSun")
    cid.set_item(_CIDSYSTEMINFO, ros)
    cid.set_item(_FONT_DESC, fd)
    cid.set_int(_DW, 1000)
    cid.set_item(_W, w)

    descendants = COSArray()
    descendants.add(cid)
    type0 = COSDictionary()
    type0.set_item(_TYPE, _FONT)
    type0.set_item(_SUBTYPE, _TYPE0)
    type0.set_name(_BASE_FONT, "SimSun")
    type0.set_name(_ENCODING, "Identity-H")
    type0.set_item(_DESCENDANT_FONTS, descendants)
    return type0


def test_space_width_independent_of_substitute() -> None:
    font = PDType0Font(_sim_sun_identity_h())
    cid_font = font.get_descendant_font()
    assert isinstance(cid_font, PDCIDFontType2)
    # any substitute works, down to the bundled last-resort font, as long as
    # its space GID lands in the /W range below. pypdfbox keeps the
    # substitute apart from the embedded-program accessor
    # (``get_true_type_font``), hence ``_get_substitute_font``.
    substitute = cid_font._get_substitute_font()
    assert substitute is not None
    substitute_space_gid = substitute.get_unicode_cmap_lookup().get_glyph_id(ord(" "))
    if not 0 < substitute_space_gid < 32:
        pytest.skip("substitute's space GID outside the test's /W range")

    # an Identity CMap without ToUnicode says nothing about which code is a
    # space; the answer must not depend on which substitute happens to be
    # installed
    assert font.get_space_width() == font.get_width(32)
