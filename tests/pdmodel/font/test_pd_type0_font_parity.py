"""Parity tests for PDType0Font upstream-named accessors.

Covers ``get_descendant_font``, ``code_to_cid``, ``code_to_gid``,
``read_code``, ``get_glyph_width``, ``is_vertical``, ``get_cmap``,
``get_to_unicode_cmap``, ``to_unicode``, and ``is_embedded``.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

_DESCENDANT_FONTS: COSName = COSName.get_pdf_name("DescendantFonts")
_ENCODING: COSName = COSName.get_pdf_name("Encoding")
_TO_UNICODE: COSName = COSName.get_pdf_name("ToUnicode")
_DW: COSName = COSName.get_pdf_name("DW")
_W: COSName = COSName.get_pdf_name("W")


# ---------- shared fixtures ----------


def _build_type2_descendant(
    *, with_font_file: bool = False, dw: int | None = None
) -> COSDictionary:
    """Build a minimal CIDFontType2 dictionary suitable for embedding
    inside a Type0 ``/DescendantFonts`` array."""
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("Type"), "Font")
    raw.set_name(COSName.SUBTYPE, "CIDFontType2")  # type: ignore[attr-defined]
    raw.set_name(COSName.get_pdf_name("BaseFont"), "TestCID")
    if dw is not None:
        raw.set_int(_DW, dw)
    if with_font_file:
        fd = PDFontDescriptor()
        fd.set_font_file2(COSStream())
        raw.set_item(COSName.get_pdf_name("FontDescriptor"), fd.get_cos_object())
    return raw


def _build_type0_font(
    descendant: COSDictionary | None,
    *,
    encoding_name: str | None = "Identity-H",
    to_unicode_stream_text: str | None = None,
    encoding_stream_text: str | None = None,
) -> PDType0Font:
    """Build a PDType0Font dictionary wired with the given descendant
    + encoding entry (named CMap by default)."""
    font_dict = COSDictionary()
    font_dict.set_name(COSName.SUBTYPE, "Type0")  # type: ignore[attr-defined]
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "TestType0")
    if descendant is not None:
        arr = COSArray()
        arr.add(descendant)
        font_dict.set_item(_DESCENDANT_FONTS, arr)
    if encoding_stream_text is not None:
        stream = COSStream()
        with stream.create_output_stream() as out:
            out.write(encoding_stream_text.encode("ascii"))
        font_dict.set_item(_ENCODING, stream)
    elif encoding_name is not None:
        font_dict.set_name(_ENCODING, encoding_name)
    if to_unicode_stream_text is not None:
        stream = COSStream()
        with stream.create_output_stream() as out:
            out.write(to_unicode_stream_text.encode("ascii"))
        font_dict.set_item(_TO_UNICODE, stream)
    return PDType0Font(font_dict)


# ---------- get_descendant_font ----------


def test_get_descendant_font_returns_none_when_array_missing() -> None:
    font = PDType0Font()
    assert font.get_descendant_font() is None


def test_get_descendant_font_returns_none_for_empty_array() -> None:
    font_dict = COSDictionary()
    font_dict.set_item(_DESCENDANT_FONTS, COSArray())
    font = PDType0Font(font_dict)
    assert font.get_descendant_font() is None


def test_get_descendant_font_round_trip_for_cid_font_type2() -> None:
    desc = _build_type2_descendant()
    font = _build_type0_font(desc)
    wrapper = font.get_descendant_font()
    assert isinstance(wrapper, PDCIDFontType2)
    assert wrapper.get_cos_object() is desc
    # Parent linkage preserved.
    assert wrapper.get_parent() is font


def test_get_descendant_font_round_trip_for_cid_font_type0() -> None:
    desc = COSDictionary()
    desc.set_name(COSName.SUBTYPE, "CIDFontType0")  # type: ignore[attr-defined]
    font = _build_type0_font(desc)
    wrapper = font.get_descendant_font()
    assert isinstance(wrapper, PDCIDFontType0)


# ---------- get_cmap ----------


def test_get_cmap_returns_identity_h_for_named_encoding() -> None:
    font = _build_type0_font(_build_type2_descendant(), encoding_name="Identity-H")
    cmap = font.get_cmap()
    assert cmap is not None
    # Identity CMap defines the full BMP codespace.
    assert cmap.get_wmode() == 0


def test_get_cmap_returns_none_for_missing_encoding() -> None:
    font = _build_type0_font(_build_type2_descendant(), encoding_name=None)
    assert font.get_cmap() is None


def test_get_cmap_caches_result() -> None:
    font = _build_type0_font(_build_type2_descendant(), encoding_name="Identity-H")
    first = font.get_cmap()
    second = font.get_cmap()
    assert first is second


# ---------- code_to_cid ----------


def test_code_to_cid_identity_h_passes_through() -> None:
    # Identity-H: input code == output CID for any 2-byte value.
    font = _build_type0_font(_build_type2_descendant(), encoding_name="Identity-H")
    assert font.code_to_cid(0x0041) == 0x0041
    assert font.code_to_cid(0x4E2D) == 0x4E2D


def test_code_to_cid_no_cmap_falls_back_to_descendant() -> None:
    # No /Encoding -> fall through to descendant.code_to_cid (= identity).
    font = _build_type0_font(_build_type2_descendant(), encoding_name=None)
    assert font.code_to_cid(0x42) == 0x42


def test_code_to_cid_no_cmap_no_descendant_returns_code() -> None:
    font = _build_type0_font(None, encoding_name=None)
    assert font.code_to_cid(0x99) == 0x99


# ---------- code_to_gid ----------


def test_code_to_gid_identity_for_type2_without_cidtogid_map() -> None:
    # No /CIDToGIDMap on the descendant -> CID == GID.
    font = _build_type0_font(_build_type2_descendant(), encoding_name="Identity-H")
    assert font.code_to_gid(0x4E2D) == 0x4E2D


def test_code_to_gid_uses_cidtogid_stream() -> None:
    desc = _build_type2_descendant()
    # CID 0 -> GID 0, CID 1 -> GID 5, CID 2 -> GID 9 (big-endian shorts).
    cid_to_gid_stream = COSStream()
    with cid_to_gid_stream.create_output_stream() as out:
        out.write(b"\x00\x00\x00\x05\x00\x09")
    desc.set_item(COSName.get_pdf_name("CIDToGIDMap"), cid_to_gid_stream)
    font = _build_type0_font(desc, encoding_name="Identity-H")
    assert font.code_to_gid(1) == 5
    assert font.code_to_gid(2) == 9


def test_code_to_gid_no_descendant_returns_code() -> None:
    font = _build_type0_font(None, encoding_name="Identity-H")
    assert font.code_to_gid(0x42) == 0x42


# ---------- read_code ----------


def test_read_code_two_byte_via_identity_h() -> None:
    font = _build_type0_font(_build_type2_descendant(), encoding_name="Identity-H")
    code, consumed = font.read_code(b"\x4E\x2D\xFF", 0)
    assert code == 0x4E2D
    assert consumed == 2


def test_read_code_with_offset() -> None:
    font = _build_type0_font(_build_type2_descendant(), encoding_name="Identity-H")
    code, consumed = font.read_code(b"\x00\x00\x4E\x2D", 2)
    assert code == 0x4E2D
    assert consumed == 2


def test_read_code_falls_back_to_single_byte_without_cmap() -> None:
    font = _build_type0_font(_build_type2_descendant(), encoding_name=None)
    code, consumed = font.read_code(b"\x41\x42", 0)
    assert code == 0x41
    assert consumed == 1


def test_read_code_handles_offset_past_end() -> None:
    font = _build_type0_font(_build_type2_descendant(), encoding_name="Identity-H")
    assert font.read_code(b"\x00", 5) == (0, 0)


# ---------- get_glyph_width ----------


def test_get_glyph_width_uses_descendant_default_width() -> None:
    desc = _build_type2_descendant(dw=1234)
    font = _build_type0_font(desc, encoding_name="Identity-H")
    assert font.get_glyph_width(0x0041) == 1234.0


def test_get_glyph_width_uses_descendant_w_table() -> None:
    desc = _build_type2_descendant(dw=500)
    # /W: range CID 65..65 -> 750
    w = COSArray()
    w.add(COSInteger.get(65))
    w.add(COSInteger.get(65))
    w.add(COSInteger.get(750))
    desc.set_item(_W, w)
    font = _build_type0_font(desc, encoding_name="Identity-H")
    # Identity-H -> CID == code; width table has CID 65.
    assert font.get_glyph_width(65) == 750.0
    # Unmapped CID falls back to /DW.
    assert font.get_glyph_width(66) == 500.0


def test_get_glyph_width_zero_without_descendant() -> None:
    font = _build_type0_font(None, encoding_name="Identity-H")
    assert font.get_glyph_width(0x0041) == 0.0


# ---------- is_vertical ----------


def test_is_vertical_false_for_identity_h() -> None:
    font = _build_type0_font(_build_type2_descendant(), encoding_name="Identity-H")
    assert font.is_vertical() is False


def test_is_vertical_true_for_identity_v() -> None:
    font = _build_type0_font(_build_type2_descendant(), encoding_name="Identity-V")
    assert font.is_vertical() is True


def test_is_vertical_true_for_wmode_1_in_cmap_stream() -> None:
    cmap_text = (
        "/CIDInit /ProcSet findresource begin\n"
        "12 dict begin\n"
        "begincmap\n"
        "/CMapName /Test-V def\n"
        "/CMapType 1 def\n"
        "/WMode 1 def\n"
        "1 begincodespacerange <00> <FF> endcodespacerange\n"
        "endcmap\n"
        "CMapName currentdict /CMap defineresource pop\n"
        "end\n"
        "end\n"
    )
    font = _build_type0_font(
        _build_type2_descendant(),
        encoding_name=None,
        encoding_stream_text=cmap_text,
    )
    assert font.is_vertical() is True


def test_is_vertical_false_when_no_cmap() -> None:
    font = _build_type0_font(_build_type2_descendant(), encoding_name=None)
    assert font.is_vertical() is False


# ---------- get_to_unicode_cmap / to_unicode ----------


def test_get_to_unicode_cmap_none_when_absent() -> None:
    font = _build_type0_font(_build_type2_descendant(), encoding_name="Identity-H")
    assert font.get_to_unicode_cmap() is None


def test_to_unicode_via_to_unicode_stream() -> None:
    cmap_text = (
        "/CIDInit /ProcSet findresource begin\n"
        "12 dict begin\n"
        "begincmap\n"
        "/CMapName /Adobe-Identity-UCS def\n"
        "/CMapType 2 def\n"
        "1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
        "1 beginbfchar <0041> <0041> endbfchar\n"
        "endcmap\n"
        "CMapName currentdict /CMap defineresource pop\n"
        "end\n"
        "end\n"
    )
    font = _build_type0_font(
        _build_type2_descendant(),
        encoding_name="Identity-H",
        to_unicode_stream_text=cmap_text,
    )
    assert font.get_to_unicode_cmap() is not None
    assert font.to_unicode(0x0041) == "A"


def test_to_unicode_returns_none_without_any_mapping() -> None:
    font = _build_type0_font(_build_type2_descendant(), encoding_name="Identity-H")
    # Identity-H has no unicode mapping; no /ToUnicode either.
    assert font.to_unicode(0x0041) is None


# ---------- is_embedded ----------


def test_is_embedded_false_without_descendant() -> None:
    font = _build_type0_font(None, encoding_name="Identity-H")
    assert font.is_embedded() is False


def test_is_embedded_false_when_descendant_not_embedded() -> None:
    font = _build_type0_font(
        _build_type2_descendant(with_font_file=False), encoding_name="Identity-H"
    )
    assert font.is_embedded() is False


def test_is_embedded_true_when_descendant_embedded() -> None:
    font = _build_type0_font(
        _build_type2_descendant(with_font_file=True), encoding_name="Identity-H"
    )
    assert font.is_embedded() is True
