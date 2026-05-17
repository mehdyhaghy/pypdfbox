"""Wave 1341 coverage-boost tests for ``pypdfbox.pdmodel.font.pd_font_factory``.

Targets the still-uncovered branches in the wave-1332 snapshot:

* The :class:`_FontType` constructor's string-subtype dispatch arms
  (``Type1`` / ``Type1C`` -> ``CIDFontType0``; bare strings outside the
  CID alias sets -> ``None``) and the matching
  :meth:`is_cid_subtype` predicate when the parent type is ``Type0``.
* The remaining ``get_font_type_from_font`` arms — OpenType (``OTTO``),
  Type 1 (``%!``), PFB-wrapped Type 1 (``0x80`` + 0x01/0x02) and CFF
  (permissive header) — each in both the composite and non-composite
  routing branches plus the MMType1 carve-out and the final
  classification-failed fallthrough.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory, _FontType

# ---------- _FontType constructor branches --------------------------------


def test_font_type_string_subtype_type1_routes_to_cid_font_type0() -> None:
    """``Type1`` is in ``_CID_TYPE0_TYPES`` -> /CIDFontType0 subtype."""
    ft = _FontType(COSName.get_pdf_name("Type0"), "Type1")
    assert ft.subtype == COSName.get_pdf_name("CIDFontType0")


def test_font_type_string_subtype_type1c_routes_to_cid_font_type0() -> None:
    ft = _FontType(COSName.get_pdf_name("Type0"), "Type1C")
    assert ft.subtype == COSName.get_pdf_name("CIDFontType0")


def test_font_type_string_subtype_unknown_resolves_to_none() -> None:
    """A string subtype outside the CID alias sets -> ``None`` subtype."""
    ft = _FontType(COSName.get_pdf_name("Type0"), "RandomName")
    assert ft.subtype is None


def test_font_type_is_cid_subtype_true_for_matching_subtype_under_type0() -> None:
    """The ``Type0`` + matching descendant subtype path returns True."""
    ft = _FontType(COSName.get_pdf_name("Type0"), "TrueType")
    assert ft.is_cid_subtype(COSName.get_pdf_name("CIDFontType2")) is True


def test_font_type_is_cid_subtype_false_when_top_type_is_not_type0() -> None:
    """Non-Type0 top-level types short-circuit to ``False``."""
    ft = _FontType(COSName.get_pdf_name("TrueType"))
    assert ft.is_cid_subtype(COSName.get_pdf_name("CIDFontType2")) is False


# ---------- helpers for get_font_type_from_font ----------------------------


def _descriptor_with_font_file2(magic: bytes) -> COSDictionary:
    fd = COSDictionary()
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(magic + b"padding-bytes")
    fd.set_item(COSName.get_pdf_name("FontFile2"), stream)
    return fd


def _descriptor_with_font_file(magic: bytes) -> COSDictionary:
    fd = COSDictionary()
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(magic + b"padding-bytes")
    fd.set_item(COSName.get_pdf_name("FontFile"), stream)
    return fd


def _descriptor_with_font_file3(magic: bytes) -> COSDictionary:
    fd = COSDictionary()
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(magic + b"padding-bytes")
    fd.set_item(COSName.get_pdf_name("FontFile3"), stream)
    return fd


# ---------- get_font_type_from_font: OpenType -----------------------------


def test_get_font_type_from_font_open_type_non_composite() -> None:
    fd = _descriptor_with_font_file2(b"OTTO")
    out = PDFontFactory.get_font_type_from_font(
        fd, COSName.get_pdf_name("TrueType")
    )
    assert out is not None
    assert out.type == COSName.get_pdf_name("OpenType")
    assert out.get_subtype() is None


def test_get_font_type_from_font_open_type_composite() -> None:
    fd = _descriptor_with_font_file2(b"OTTO")
    out = PDFontFactory.get_font_type_from_font(
        fd, COSName.get_pdf_name("Type0")
    )
    assert out is not None
    # Composite OpenType routes through /Type0 with a non-CID descendant
    # subtype label ("OpenType").
    assert out.type == COSName.get_pdf_name("Type0")


# ---------- get_font_type_from_font: Type 1 (raw + PFB) -------------------


def test_get_font_type_from_font_type1_non_composite() -> None:
    fd = _descriptor_with_font_file(b"%!PS")
    out = PDFontFactory.get_font_type_from_font(
        fd, COSName.get_pdf_name("Type1")
    )
    assert out is not None
    assert out.type == COSName.get_pdf_name("Type1")


def test_get_font_type_from_font_type1_composite() -> None:
    fd = _descriptor_with_font_file(b"%!PS")
    out = PDFontFactory.get_font_type_from_font(
        fd, COSName.get_pdf_name("Type0")
    )
    assert out is not None
    # Composite raw Type1 -> /CIDFontType0.
    assert out.is_cid_subtype(COSName.get_pdf_name("CIDFontType0")) is True


def test_get_font_type_from_font_type1_mmtype1_preserves_mm_type1_routing() -> None:
    fd = _descriptor_with_font_file(b"%!PS")
    out = PDFontFactory.get_font_type_from_font(
        fd, COSName.get_pdf_name("MMType1")
    )
    assert out is not None
    assert out.type == COSName.get_pdf_name("MMType1")


def test_get_font_type_from_font_pfb_non_composite() -> None:
    # PFB segment marker 0x80 0x01 (ASCII segment) — same routing as Type 1.
    fd = _descriptor_with_font_file(b"\x80\x01\x00\x10")
    out = PDFontFactory.get_font_type_from_font(
        fd, COSName.get_pdf_name("Type1")
    )
    assert out is not None
    assert out.type == COSName.get_pdf_name("Type1")


# ---------- get_font_type_from_font: CFF ----------------------------------


def test_get_font_type_from_font_cff_non_composite() -> None:
    # CFF header: major>=1, hdr_size, offset_size in [1,4]. Use 01 00 04 02.
    fd = _descriptor_with_font_file3(b"\x01\x00\x04\x02")
    out = PDFontFactory.get_font_type_from_font(
        fd, COSName.get_pdf_name("Type1")
    )
    assert out is not None
    # CFF non-composite + non-MMType1 -> /Type1.
    assert out.type == COSName.get_pdf_name("Type1")


def test_get_font_type_from_font_cff_mmtype1() -> None:
    fd = _descriptor_with_font_file3(b"\x01\x00\x04\x02")
    out = PDFontFactory.get_font_type_from_font(
        fd, COSName.get_pdf_name("MMType1")
    )
    assert out is not None
    assert out.type == COSName.get_pdf_name("MMType1")


def test_get_font_type_from_font_cff_composite() -> None:
    fd = _descriptor_with_font_file3(b"\x01\x00\x04\x02")
    out = PDFontFactory.get_font_type_from_font(
        fd, COSName.get_pdf_name("Type0")
    )
    assert out is not None
    # Composite CFF -> /Type0 with /CIDFontType0 descendant subtype.
    assert out.is_cid_subtype(COSName.get_pdf_name("CIDFontType0")) is True


# ---------- get_font_type_from_font: classification fallthrough ----------


def test_get_font_type_from_font_unrecognised_header_returns_none() -> None:
    # 4 bytes that match no sniffer -> classifier returns None.
    fd = _descriptor_with_font_file2(b"ZZZZ")
    out = PDFontFactory.get_font_type_from_font(
        fd, COSName.get_pdf_name("TrueType")
    )
    assert out is None
