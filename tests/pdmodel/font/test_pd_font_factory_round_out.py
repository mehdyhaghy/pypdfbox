"""Wave 259 round-out tests for ``PDFontFactory`` — covers the
program-header inspection / Type 0 subtype-repair surface added in this
wave:

* ``get_font_program_header(font_descriptor)`` — first 4 bytes of the
  embedded font program reachable from the descriptor (``/FontFile``
  preferred, then ``/FontFile2``, then ``/FontFile3``).
* ``get_font_program_kind(header)`` — header-bytes-to-label classifier
  matching the upstream ``getFontTypeFromFont`` dispatch chain (TTF /
  TTC / OpenType / Type1 / PFB / CFF, with CFF tried last because it
  is permissive).
* ``fix_type0_subtype(descendant_font, font_descriptor, new_subtype)``
  — shuffles ``/FontFile2`` <-> ``/FontFile3`` to match a
  ``CIDFontType0`` / ``CIDFontType2`` repair, mirroring upstream's
  private ``fixType0Subtype``.
* The new ``/Type`` warning emitted by :meth:`PDFontFactory.create_font`
  when the dictionary's ``/Type`` is present but isn't ``/Font``.

These mirror the upstream private helpers used by
``PDFontFactory.createFont`` to repair malformed Type 0 chains. None of
this changes the existing dispatch behaviour exercised in the other
factory test files.
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_FONT: COSName = COSName.get_pdf_name("Font")
_FONT_FILE: COSName = COSName.get_pdf_name("FontFile")
_FONT_FILE2: COSName = COSName.get_pdf_name("FontFile2")
_FONT_FILE3: COSName = COSName.get_pdf_name("FontFile3")
_FONT_NAME: COSName = COSName.get_pdf_name("FontName")


# ---------- KIND_* string constants ----------


def test_kind_constants_match_program_labels() -> None:
    # Hard-coded so callers can pattern-match without importing the
    # module-level names. Mirrors upstream's private string constants.
    assert PDFontFactory.KIND_TRUE_TYPE == "TrueType"
    assert PDFontFactory.KIND_TRUE_TYPE_COLLECTION == "TrueTypeCollection"
    assert PDFontFactory.KIND_OPEN_TYPE == "OpenType"
    assert PDFontFactory.KIND_TYPE1 == "Type1"
    assert PDFontFactory.KIND_PFB == "PFB"
    assert PDFontFactory.KIND_CFF == "CFF"


# ---------- get_font_program_kind ----------


def test_get_font_program_kind_true_type_sfnt() -> None:
    assert (
        PDFontFactory.get_font_program_kind(b"\x00\x01\x00\x00")
        == PDFontFactory.KIND_TRUE_TYPE
    )


def test_get_font_program_kind_true_type_apple_tag() -> None:
    assert (
        PDFontFactory.get_font_program_kind(b"true")
        == PDFontFactory.KIND_TRUE_TYPE
    )


def test_get_font_program_kind_true_type_collection() -> None:
    assert (
        PDFontFactory.get_font_program_kind(b"ttcf")
        == PDFontFactory.KIND_TRUE_TYPE_COLLECTION
    )


def test_get_font_program_kind_open_type() -> None:
    assert (
        PDFontFactory.get_font_program_kind(b"OTTO")
        == PDFontFactory.KIND_OPEN_TYPE
    )


def test_get_font_program_kind_type1() -> None:
    assert (
        PDFontFactory.get_font_program_kind(b"%!PS")
        == PDFontFactory.KIND_TYPE1
    )


def test_get_font_program_kind_pfb_segment_one() -> None:
    assert (
        PDFontFactory.get_font_program_kind(b"\x80\x01\x00\x00")
        == PDFontFactory.KIND_PFB
    )


def test_get_font_program_kind_pfb_segment_two() -> None:
    assert (
        PDFontFactory.get_font_program_kind(b"\x80\x02\x00\x00")
        == PDFontFactory.KIND_PFB
    )


def test_get_font_program_kind_cff_typical() -> None:
    # major=1, offset_size=2 — typical CFF, must be classified as CFF
    # only after the more specific predicates have run.
    assert (
        PDFontFactory.get_font_program_kind(b"\x01\x00\x04\x02")
        == PDFontFactory.KIND_CFF
    )


def test_get_font_program_kind_unknown_returns_none() -> None:
    # Not a valid header for any recognised format.
    assert PDFontFactory.get_font_program_kind(b"XXXX") is None


def test_get_font_program_kind_too_short_returns_none() -> None:
    assert PDFontFactory.get_font_program_kind(b"%!P") is None


def test_get_font_program_kind_none_returns_none() -> None:
    assert PDFontFactory.get_font_program_kind(None) is None


def test_get_font_program_kind_bytearray_accepted() -> None:
    assert (
        PDFontFactory.get_font_program_kind(bytearray(b"OTTO"))
        == PDFontFactory.KIND_OPEN_TYPE
    )


def test_get_font_program_kind_memoryview_accepted() -> None:
    assert (
        PDFontFactory.get_font_program_kind(memoryview(b"\x00\x01\x00\x00"))
        == PDFontFactory.KIND_TRUE_TYPE
    )


def test_get_font_program_kind_ttf_does_not_classify_as_cff() -> None:
    # Regression for the ordering rule: a TTF sfnt header (\x00\x01\x00\x00)
    # would also satisfy the permissive CFF check (major>=1 fails since
    # major=0), so this is a non-overlap; harden anyway.
    out = PDFontFactory.get_font_program_kind(b"\x00\x01\x00\x00")
    assert out == PDFontFactory.KIND_TRUE_TYPE
    assert out != PDFontFactory.KIND_CFF


def test_get_font_program_kind_otto_takes_precedence_over_cff() -> None:
    # OTTO = 0x4F 0x54 0x54 0x4F — header[0]=0x4F is >=1 and offset_size
    # 0x4F (79) is NOT in [1, 4], so CFF check would fail; double-check
    # that the explicit OpenType label wins regardless.
    assert (
        PDFontFactory.get_font_program_kind(b"OTTO")
        == PDFontFactory.KIND_OPEN_TYPE
    )


def test_get_font_program_kind_pfb_takes_precedence_over_cff() -> None:
    # 0x80 0x01 0x00 0x02: PFB matches first, CFF would also match
    # (major=0x80 >= 1, offset_size=0x02 in [1,4]). PFB must win because
    # it comes earlier in the chain.
    out = PDFontFactory.get_font_program_kind(b"\x80\x01\x00\x02")
    assert out == PDFontFactory.KIND_PFB


# ---------- get_font_program_header ----------


def _make_descriptor_with_stream(
    key: COSName, payload: bytes
) -> tuple[COSDictionary, COSStream]:
    descriptor = COSDictionary()
    stream = COSStream()
    stream.set_raw_data(payload)
    descriptor.set_item(key, stream)
    return descriptor, stream


def test_get_font_program_header_reads_font_file_first() -> None:
    descriptor, _ = _make_descriptor_with_stream(
        _FONT_FILE, b"%!PS-AdobeFont-1.0\n"
    )
    out = PDFontFactory.get_font_program_header(descriptor)
    assert out == b"%!PS"


def test_get_font_program_header_reads_font_file2() -> None:
    descriptor, _ = _make_descriptor_with_stream(
        _FONT_FILE2, b"\x00\x01\x00\x00\xab\xcd"
    )
    out = PDFontFactory.get_font_program_header(descriptor)
    assert out == b"\x00\x01\x00\x00"


def test_get_font_program_header_reads_font_file3() -> None:
    descriptor, _ = _make_descriptor_with_stream(_FONT_FILE3, b"OTTO\xff")
    out = PDFontFactory.get_font_program_header(descriptor)
    assert out == b"OTTO"


def test_get_font_program_header_prefers_font_file_over_font_file2() -> None:
    # When both /FontFile and /FontFile2 are set, the one-true /FontFile
    # wins (matches upstream's getFontHeader preference order).
    descriptor = COSDictionary()
    ff = COSStream()
    ff.set_raw_data(b"%!ASCII\n")
    descriptor.set_item(_FONT_FILE, ff)
    ff2 = COSStream()
    ff2.set_raw_data(b"\x00\x01\x00\x00")
    descriptor.set_item(_FONT_FILE2, ff2)
    assert PDFontFactory.get_font_program_header(descriptor) == b"%!AS"


def test_get_font_program_header_prefers_font_file2_over_font_file3() -> None:
    descriptor = COSDictionary()
    ff2 = COSStream()
    ff2.set_raw_data(b"\x00\x01\x00\x00")
    descriptor.set_item(_FONT_FILE2, ff2)
    ff3 = COSStream()
    ff3.set_raw_data(b"OTTO")
    descriptor.set_item(_FONT_FILE3, ff3)
    assert (
        PDFontFactory.get_font_program_header(descriptor)
        == b"\x00\x01\x00\x00"
    )


def test_get_font_program_header_returns_none_for_no_streams() -> None:
    descriptor = COSDictionary()
    descriptor.set_name(COSName.get_pdf_name("FontName"), "Whatever")
    assert PDFontFactory.get_font_program_header(descriptor) is None


def test_get_font_program_header_returns_none_for_short_stream() -> None:
    descriptor, _ = _make_descriptor_with_stream(_FONT_FILE2, b"\x00\x01")
    assert PDFontFactory.get_font_program_header(descriptor) is None


def test_get_font_program_header_returns_none_for_non_stream_value() -> None:
    # Malformed: /FontFile3 set to a name rather than a stream.
    descriptor = COSDictionary()
    descriptor.set_item(_FONT_FILE3, COSName.get_pdf_name("Bogus"))
    assert PDFontFactory.get_font_program_header(descriptor) is None


def test_get_font_program_header_returns_none_for_none_descriptor() -> None:
    assert PDFontFactory.get_font_program_header(None) is None


def test_get_font_program_header_raises_for_non_dictionary() -> None:
    with pytest.raises(TypeError):
        PDFontFactory.get_font_program_header(42)  # type: ignore[arg-type]


def test_get_font_program_header_combo_with_kind_dispatch() -> None:
    # Realistic round-trip: read header from descriptor and feed to the
    # classifier. Equivalent to upstream's getFontTypeFromFont up to
    # the point it constructs a FontType.
    descriptor, _ = _make_descriptor_with_stream(
        _FONT_FILE3, b"OTTO\x00\x10"
    )
    header = PDFontFactory.get_font_program_header(descriptor)
    assert header is not None
    assert (
        PDFontFactory.get_font_program_kind(header)
        == PDFontFactory.KIND_OPEN_TYPE
    )


# ---------- fix_type0_subtype ----------


def _build_repair_inputs(
    descendant_subtype: str,
    file_key: COSName,
) -> tuple[COSDictionary, COSDictionary]:
    descendant = COSDictionary()
    descendant.set_item(_TYPE, _FONT)
    descendant.set_name(_SUBTYPE, descendant_subtype)
    descriptor = COSDictionary()
    descriptor.set_name(_FONT_NAME, "TestFont")
    descriptor.set_item(file_key, COSStream())
    return descendant, descriptor


def test_fix_type0_subtype_to_cid_font_type0_moves_font_file2_to_font_file3() -> None:
    descendant, descriptor = _build_repair_inputs(
        "CIDFontType2", _FONT_FILE2
    )
    original_stream = descriptor.get_item(_FONT_FILE2)
    PDFontFactory.fix_type0_subtype(descendant, descriptor, "CIDFontType0")
    assert descendant.get_name(_SUBTYPE) == "CIDFontType0"
    assert descriptor.contains_key(_FONT_FILE3)
    assert not descriptor.contains_key(_FONT_FILE2)
    # The actual stream object is preserved — the repair only re-keys.
    assert descriptor.get_item(_FONT_FILE3) is original_stream


def test_fix_type0_subtype_to_cid_font_type2_moves_font_file3_to_font_file2() -> None:
    descendant, descriptor = _build_repair_inputs(
        "CIDFontType0", _FONT_FILE3
    )
    original_stream = descriptor.get_item(_FONT_FILE3)
    PDFontFactory.fix_type0_subtype(descendant, descriptor, "CIDFontType2")
    assert descendant.get_name(_SUBTYPE) == "CIDFontType2"
    assert descriptor.contains_key(_FONT_FILE2)
    assert not descriptor.contains_key(_FONT_FILE3)
    assert descriptor.get_item(_FONT_FILE2) is original_stream


def test_fix_type0_subtype_to_cid_font_type0_when_font_file3_already_present() -> None:
    # Both /FontFile2 and /FontFile3 already set — upstream only moves
    # the stream when /FontFile3 is *missing*. Make sure we honour that.
    descendant, descriptor = _build_repair_inputs(
        "CIDFontType2", _FONT_FILE2
    )
    pre_existing = COSStream()
    descriptor.set_item(_FONT_FILE3, pre_existing)
    PDFontFactory.fix_type0_subtype(descendant, descriptor, "CIDFontType0")
    # /FontFile2 is left in place; /FontFile3 unchanged.
    assert descriptor.contains_key(_FONT_FILE2)
    assert descriptor.get_item(_FONT_FILE3) is pre_existing
    # /Subtype is still updated.
    assert descendant.get_name(_SUBTYPE) == "CIDFontType0"


def test_fix_type0_subtype_to_cid_font_type2_when_font_file2_already_present() -> None:
    descendant, descriptor = _build_repair_inputs(
        "CIDFontType0", _FONT_FILE3
    )
    pre_existing = COSStream()
    descriptor.set_item(_FONT_FILE2, pre_existing)
    PDFontFactory.fix_type0_subtype(descendant, descriptor, "CIDFontType2")
    assert descriptor.contains_key(_FONT_FILE3)
    assert descriptor.get_item(_FONT_FILE2) is pre_existing
    assert descendant.get_name(_SUBTYPE) == "CIDFontType2"


def test_fix_type0_subtype_accepts_cos_name() -> None:
    descendant, descriptor = _build_repair_inputs(
        "CIDFontType2", _FONT_FILE2
    )
    PDFontFactory.fix_type0_subtype(
        descendant, descriptor, COSName.get_pdf_name("CIDFontType0")
    )
    assert descendant.get_name(_SUBTYPE) == "CIDFontType0"
    assert descriptor.contains_key(_FONT_FILE3)


def test_fix_type0_subtype_other_subtype_only_updates_name() -> None:
    # An unrelated subtype string still updates /Subtype but doesn't
    # shuffle FontFile* entries — matches upstream's narrow scope.
    descendant, descriptor = _build_repair_inputs(
        "CIDFontType0", _FONT_FILE3
    )
    PDFontFactory.fix_type0_subtype(descendant, descriptor, "CIDFontType9")
    assert descendant.get_name(_SUBTYPE) == "CIDFontType9"
    assert descriptor.contains_key(_FONT_FILE3)
    assert not descriptor.contains_key(_FONT_FILE2)


def test_fix_type0_subtype_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    descendant, descriptor = _build_repair_inputs(
        "CIDFontType2", _FONT_FILE2
    )
    with caplog.at_level(
        logging.WARNING, logger="pypdfbox.pdmodel.font.pd_font_factory"
    ):
        PDFontFactory.fix_type0_subtype(
            descendant, descriptor, PDCIDFontType0.SUB_TYPE
        )
    joined = "\n".join(rec.message for rec in caplog.records)
    assert "TestFont" in joined
    assert "fix" in joined.lower()


def test_fix_type0_subtype_uses_subtype_constants() -> None:
    # Hard pin: the repair is keyed off the subclass SUB_TYPE constants —
    # passing those constants directly must produce the same result as
    # passing the literal strings.
    descendant, descriptor = _build_repair_inputs(
        "CIDFontType2", _FONT_FILE2
    )
    PDFontFactory.fix_type0_subtype(
        descendant, descriptor, PDCIDFontType0.SUB_TYPE
    )
    assert descendant.get_name(_SUBTYPE) == PDCIDFontType0.SUB_TYPE

    descendant2, descriptor2 = _build_repair_inputs(
        "CIDFontType0", _FONT_FILE3
    )
    PDFontFactory.fix_type0_subtype(
        descendant2, descriptor2, PDCIDFontType2.SUB_TYPE
    )
    assert descendant2.get_name(_SUBTYPE) == PDCIDFontType2.SUB_TYPE


def test_fix_type0_subtype_raises_for_non_dict_descendant() -> None:
    with pytest.raises(TypeError):
        PDFontFactory.fix_type0_subtype(
            "not a dict",  # type: ignore[arg-type]
            COSDictionary(),
            "CIDFontType0",
        )


def test_fix_type0_subtype_raises_for_non_dict_descriptor() -> None:
    with pytest.raises(TypeError):
        PDFontFactory.fix_type0_subtype(
            COSDictionary(),
            "not a dict",  # type: ignore[arg-type]
            "CIDFontType0",
        )


def test_fix_type0_subtype_raises_for_bad_subtype_type() -> None:
    with pytest.raises(TypeError):
        PDFontFactory.fix_type0_subtype(
            COSDictionary(),
            COSDictionary(),
            42,  # type: ignore[arg-type]
        )


# ---------- /Type entry warning in create_font ----------


def test_create_font_logs_error_when_type_is_not_font(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw = COSDictionary()
    raw.set_name(_TYPE, "Catalog")  # wrong type
    raw.set_name(_SUBTYPE, "Type1")
    with caplog.at_level(
        logging.ERROR, logger="pypdfbox.pdmodel.font.pd_font_factory"
    ):
        out = PDFontFactory.create_font(raw)
    # Dispatch still proceeds — upstream's check is informational.
    assert isinstance(out, PDType1Font)
    joined = "\n".join(rec.message for rec in caplog.records)
    assert "Font" in joined
    assert "Catalog" in joined


def test_create_font_no_error_when_type_is_font(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw = COSDictionary()
    raw.set_name(_TYPE, "Font")
    raw.set_name(_SUBTYPE, "Type1")
    with caplog.at_level(
        logging.ERROR, logger="pypdfbox.pdmodel.font.pd_font_factory"
    ):
        out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1Font)
    assert caplog.records == []


def test_create_font_no_error_when_type_absent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Missing /Type is permissive — upstream defaults to /Font and no
    # error is emitted. We mirror that (the warning is only raised when
    # /Type is *present and wrong*).
    raw = COSDictionary()
    raw.set_name(_SUBTYPE, "Type1")
    with caplog.at_level(
        logging.ERROR, logger="pypdfbox.pdmodel.font.pd_font_factory"
    ):
        out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1Font)
    assert caplog.records == []
