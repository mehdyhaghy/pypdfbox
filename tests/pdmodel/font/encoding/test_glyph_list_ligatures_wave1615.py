"""PDFBOX-6322: AGL underscore ligature names through the public font API."""

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.fontbox.encoding.glyph_list import GlyphList
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font


def test_ligature_result_is_cached_and_stable() -> None:
    agl = GlyphList.get_adobe_glyph_list()
    assert agl.to_unicode("f_f_i") == "ffi"
    assert agl.to_unicode("f_f_i") == "ffi"
    assert agl.to_unicode("f_bogus") is None
    assert agl.to_unicode("f_bogus") is None


def test_ligature_components_are_not_multi_code_point_safe_for_code_point() -> None:
    agl = GlyphList.get_adobe_glyph_list()
    # a multi-character ligature cannot fit a single code point
    assert agl.code_point_for_glyph_name("f_i") is None


def test_zapf_dingbats_list_components() -> None:
    zapf = GlyphList.get_zapf_dingbats()
    # components resolve against the same list
    assert zapf.to_unicode("a1_a2") == zapf.to_unicode("a1") + zapf.to_unicode("a2")


def test_differences_ligature_name_extracts_components() -> None:
    font_dict = COSDictionary()
    font_dict.set_name(COSName.TYPE, "Font")
    font_dict.set_name(COSName.SUBTYPE, "Type1")
    font_dict.set_name(COSName.BASE_FONT, "Helvetica")
    enc = COSDictionary()
    enc.set_name(COSName.TYPE, "Encoding")
    enc.set_item(
        COSName.get_pdf_name("Differences"),
        COSArray([COSInteger.get(200), COSName.get_pdf_name("f_f_i")]),
    )
    font_dict.set_item(COSName.ENCODING, enc)
    font = PDType1Font(font_dict)
    assert font.to_unicode(200) == "ffi"
