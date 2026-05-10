"""Ported upstream tests for ``PDFontFactory.createFont`` dispatch.

PDFBox 3.0.x has no dedicated ``PDFontFactoryTest.java`` — the factory
is exercised through ``PDFontTest`` (the relevant cases live in
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDFontTest.java``,
methods ``testPDFontFactory*``). The cases ported here are the
subtype-dispatch ones; non-dispatch tests live alongside their
respective subtype implementations.

Skipped (one-line reason each):
* ``testPDFontFactoryReadFont*`` — those exercise full font-loading
  (binary FontFile parsing); covered by the subtype-specific upstream
  tests, not by the factory wrapper.
* ``testCachedFonts`` — depends on ``ResourceCache`` round-tripping,
  which our factory accepts as a parity kwarg but does not consult
  (cache is owned by the parser, not the factory).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_mm_type1_font import PDMMType1Font
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font

_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]


def _font_dict(subtype: str | None) -> COSDictionary:
    raw = COSDictionary()
    if subtype is not None:
        raw.set_name(_SUBTYPE, subtype)
    return raw


# Mirrors PDFontTest#testPDFontFactoryType1.
def test_pd_font_factory_type1() -> None:
    out = PDFontFactory.create_font(_font_dict("Type1"))
    assert isinstance(out, PDType1Font)


# Mirrors PDFontTest#testPDFontFactoryMMType1.
def test_pd_font_factory_mm_type1() -> None:
    out = PDFontFactory.create_font(_font_dict("MMType1"))
    assert isinstance(out, PDMMType1Font)
    # MMType1 extends Type1 in PDFBox; preserve that here.
    assert isinstance(out, PDType1Font)


# Mirrors PDFontTest#testPDFontFactoryTrueType.
def test_pd_font_factory_true_type() -> None:
    out = PDFontFactory.create_font(_font_dict("TrueType"))
    assert isinstance(out, PDTrueTypeFont)


# Mirrors PDFontTest#testPDFontFactoryType3.
def test_pd_font_factory_type3() -> None:
    out = PDFontFactory.create_font(_font_dict("Type3"))
    assert isinstance(out, PDType3Font)


# Mirrors PDFontTest#testPDFontFactoryType0.
def test_pd_font_factory_type0() -> None:
    out = PDFontFactory.create_font(_font_dict("Type0"))
    assert isinstance(out, PDType0Font)


# Mirrors PDFontTest#testPDFontFactoryUnknownSubtype: a font dict with
# no /Subtype must not throw — upstream logs a warning and returns a
# PDType1Font wrapping the (malformed) dict.
def test_pd_font_factory_missing_subtype_falls_back_to_type1() -> None:
    out = PDFontFactory.create_font(_font_dict(None))
    assert isinstance(out, PDType1Font)


# Mirrors the IllegalArgumentException check upstream performs by
# refusing non-dictionary inputs at the API boundary.
def test_pd_font_factory_non_dictionary_raises() -> None:
    with pytest.raises(TypeError):
        PDFontFactory.create_font("not a dict")  # type: ignore[arg-type]


# Mirrors PDFontTest's null-input handling: createFont(null) returns
# null in upstream (it short-circuits before the dispatch).
def test_pd_font_factory_none_returns_none() -> None:
    assert PDFontFactory.create_font(None) is None  # type: ignore[arg-type]


# Mirrors PDFontTest#testPDFontFactoryResourceCacheKwarg-style cases:
# the second argument is accepted for signature parity but does not
# alter dispatch.
def test_pd_font_factory_resource_cache_kwarg_does_not_alter_dispatch() -> None:
    raw = _font_dict("TrueType")
    sentinel = object()
    out = PDFontFactory.create_font(raw, resource_cache=sentinel)
    assert isinstance(out, PDTrueTypeFont)


# ---------- header-sniffer 1:1 ports ----------
#
# PDFBox keeps these as private helpers; the cases below assert the
# upstream-named snake_case ports return the same answer as the
# pypdfbox-native ``is_*_header`` set on the same magic-byte inputs.


def test_is_true_type_file_recognises_sfnt_header() -> None:
    # 0x00010000 is the version sfnt-tag for TrueType outlines.
    assert PDFontFactory.is_true_type_file(b"\x00\x01\x00\x00") is True
    # ASCII "true" is also accepted (Apple TrueType marker).
    assert PDFontFactory.is_true_type_file(b"true") is True
    # OpenType ("OTTO") is NOT a TrueType marker.
    assert PDFontFactory.is_true_type_file(b"OTTO") is False


def test_is_true_type_collection_file_recognises_ttcf() -> None:
    assert PDFontFactory.is_true_type_collection_file(b"ttcf") is True
    assert PDFontFactory.is_true_type_collection_file(b"true") is False


def test_is_open_type_file_recognises_otto() -> None:
    assert PDFontFactory.is_open_type_file(b"OTTO") is True
    assert PDFontFactory.is_open_type_file(b"\x00\x01\x00\x00") is False


def test_is_type1_file_recognises_pct_bang_prologue() -> None:
    # Type 1 programs begin with %! (0x25 0x21).
    assert PDFontFactory.is_type1_file(b"%!PS") is True
    assert PDFontFactory.is_type1_file(b"OTTO") is False


def test_is_pfb_file_recognises_segment_marker() -> None:
    # PFB segment markers: 0x80 followed by 0x01 (ASCII) or 0x02 (binary).
    assert PDFontFactory.is_pfb_file(b"\x80\x01\x00\x00") is True
    assert PDFontFactory.is_pfb_file(b"\x80\x02\x00\x00") is True
    # 0x80 followed by 0x03 is the EOF marker, not a data segment.
    assert PDFontFactory.is_pfb_file(b"\x80\x03\x00\x00") is False
    assert PDFontFactory.is_pfb_file(b"OTTO") is False


def test_is_cff_file_recognises_plausible_header() -> None:
    # CFF header: major>=1, offset_size in [1,4]. No fixed magic.
    assert PDFontFactory.is_cff_file(b"\x01\x00\x04\x01") is True
    assert PDFontFactory.is_cff_file(b"\x01\x00\x04\x04") is True
    # Offset size 5 is out of range.
    assert PDFontFactory.is_cff_file(b"\x01\x00\x04\x05") is False
    # Major version 0 is out of range.
    assert PDFontFactory.is_cff_file(b"\x00\x00\x04\x01") is False


# ---------- get_descendant_font / get_font_descriptor / get_font_header ----------


def test_get_descendant_font_returns_first_dict_entry() -> None:
    from pypdfbox.cos import COSArray

    parent = COSDictionary()
    desc = COSDictionary()
    desc.set_name(_SUBTYPE, "CIDFontType2")
    arr = COSArray()
    arr.add(desc)
    parent.set_item(COSName.get_pdf_name("DescendantFonts"), arr)
    out = PDFontFactory.get_descendant_font(parent)
    assert out is desc


def test_get_descendant_font_none_when_missing() -> None:
    assert PDFontFactory.get_descendant_font(COSDictionary()) is None


def test_get_font_descriptor_uses_parent_descriptor_first() -> None:
    parent = COSDictionary()
    fd = COSDictionary()
    parent.set_item(COSName.get_pdf_name("FontDescriptor"), fd)
    assert PDFontFactory.get_font_descriptor(parent) is fd


def test_get_font_descriptor_falls_back_to_descendant_descriptor() -> None:
    from pypdfbox.cos import COSArray

    parent = COSDictionary()
    descendant = COSDictionary()
    fd = COSDictionary()
    descendant.set_item(COSName.get_pdf_name("FontDescriptor"), fd)
    arr = COSArray()
    arr.add(descendant)
    parent.set_item(COSName.get_pdf_name("DescendantFonts"), arr)
    assert PDFontFactory.get_font_descriptor(parent) is fd


def test_get_font_header_reads_first_four_bytes_of_font_file2() -> None:
    from pypdfbox.cos import COSStream

    fd = COSDictionary()
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"\x00\x01\x00\x00rest-of-the-program")
    fd.set_item(COSName.get_pdf_name("FontFile2"), stream)
    assert PDFontFactory.get_font_header(fd) == b"\x00\x01\x00\x00"


def test_get_font_header_returns_none_for_missing_descriptor() -> None:
    assert PDFontFactory.get_font_header(None) is None
    assert PDFontFactory.get_font_header(COSDictionary()) is None


# ---------- get_font_type_from_font ----------


def _descriptor_with_font_file2(magic: bytes) -> COSDictionary:
    from pypdfbox.cos import COSStream

    fd = COSDictionary()
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(magic + b"padding-bytes")
    fd.set_item(COSName.get_pdf_name("FontFile2"), stream)
    return fd


def test_get_font_type_from_font_classifies_truetype_as_simple() -> None:
    fd = _descriptor_with_font_file2(b"\x00\x01\x00\x00")
    out = PDFontFactory.get_font_type_from_font(
        fd, COSName.get_pdf_name("TrueType")
    )
    assert out is not None
    assert out.get_subtype() is None
    assert out.type == COSName.get_pdf_name("TrueType")


def test_get_font_type_from_font_classifies_truetype_as_composite() -> None:
    fd = _descriptor_with_font_file2(b"\x00\x01\x00\x00")
    out = PDFontFactory.get_font_type_from_font(
        fd, COSName.get_pdf_name("Type0")
    )
    assert out is not None
    # Composite TrueType maps to /CIDFontType2 via the FontType mapping.
    assert out.get_subtype() == COSName.get_pdf_name("CIDFontType2")
    assert out.is_cid_subtype(COSName.get_pdf_name("CIDFontType2")) is True
    assert out.is_cid_subtype(COSName.get_pdf_name("CIDFontType0")) is False


def test_get_font_type_from_font_returns_none_when_no_font_file() -> None:
    out = PDFontFactory.get_font_type_from_font(
        None, COSName.get_pdf_name("TrueType")
    )
    assert out is None
