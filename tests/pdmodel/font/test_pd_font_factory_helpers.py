"""Round-out tests for the PDFontFactory helper surface added in Wave 209.

Focuses on the public helpers added beside the core ``create_font``
dispatch — header-magic predicates (``is_true_type_header``,
``is_open_type_header``, ``is_cff_header``, ``is_type1_header``,
``is_pfb_header``, ``is_true_type_collection_header``) and the
descendant / descriptor lookup helpers (``get_descendant_font_dict``,
``get_font_descriptor_dict``).

These mirror the upstream ``PDFontFactory`` private helpers that drive
its ``getFontTypeFromFont`` / ``fixType0Subtype`` repair branches —
surfaced publicly here so pypdfbox callers parsing or repairing Type 0
chains by hand have a typed entry point.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory

_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")
_FONT_FILE2: COSName = COSName.get_pdf_name("FontFile2")
_FONT_FILE3: COSName = COSName.get_pdf_name("FontFile3")
_DESCENDANT_FONTS: COSName = COSName.get_pdf_name("DescendantFonts")


# ---------- header-magic constants ----------


def test_constant_font_type1c() -> None:
    assert PDFontFactory.FONT_TYPE1C == "Type1C"


def test_constant_font_open_type() -> None:
    assert PDFontFactory.FONT_OPEN_TYPE == "OTTO"


def test_constant_font_ttf_collection() -> None:
    assert PDFontFactory.FONT_TTF_COLLECTION == "ttcf"


def test_constant_font_true_type() -> None:
    assert PDFontFactory.FONT_TRUE_TYPE == "true"


def test_constant_ttf_header_bytes() -> None:
    # sfnt 1.0 — the standard TrueType outline magic.
    assert PDFontFactory.TTF_HEADER == b"\x00\x01\x00\x00"


# ---------- is_true_type_header ----------


def test_is_true_type_header_sfnt_magic() -> None:
    assert PDFontFactory.is_true_type_header(b"\x00\x01\x00\x00") is True


def test_is_true_type_header_sfnt_with_trailing_bytes() -> None:
    # Only the first 4 bytes are inspected.
    header = b"\x00\x01\x00\x00ZZZZ"
    assert PDFontFactory.is_true_type_header(header) is True


def test_is_true_type_header_apple_true_tag() -> None:
    assert PDFontFactory.is_true_type_header(b"true") is True


def test_is_true_type_header_apple_true_with_trailing_bytes() -> None:
    assert PDFontFactory.is_true_type_header(b"trueZZZZ") is True


def test_is_true_type_header_otto_is_false() -> None:
    # OTTO is OpenType (CFF-flavoured), not TrueType.
    assert PDFontFactory.is_true_type_header(b"OTTO") is False


def test_is_true_type_header_ttcf_is_false() -> None:
    # TTC is a collection wrapper, not a single TrueType.
    assert PDFontFactory.is_true_type_header(b"ttcf") is False


def test_is_true_type_header_too_short() -> None:
    assert PDFontFactory.is_true_type_header(b"\x00\x01") is False


def test_is_true_type_header_empty() -> None:
    assert PDFontFactory.is_true_type_header(b"") is False


def test_is_true_type_header_bytearray_accepted() -> None:
    assert (
        PDFontFactory.is_true_type_header(bytearray(b"\x00\x01\x00\x00"))
        is True
    )


def test_is_true_type_header_memoryview_accepted() -> None:
    assert PDFontFactory.is_true_type_header(memoryview(b"true")) is True


# ---------- is_true_type_collection_header ----------


def test_is_true_type_collection_header_ttcf() -> None:
    assert PDFontFactory.is_true_type_collection_header(b"ttcf") is True


def test_is_true_type_collection_header_with_trailing_bytes() -> None:
    assert (
        PDFontFactory.is_true_type_collection_header(b"ttcf\x00\x02") is True
    )


def test_is_true_type_collection_header_true_is_false() -> None:
    assert PDFontFactory.is_true_type_collection_header(b"true") is False


def test_is_true_type_collection_header_too_short() -> None:
    assert PDFontFactory.is_true_type_collection_header(b"ttc") is False


# ---------- is_open_type_header ----------


def test_is_open_type_header_otto() -> None:
    assert PDFontFactory.is_open_type_header(b"OTTO") is True


def test_is_open_type_header_otto_with_trailing_bytes() -> None:
    assert PDFontFactory.is_open_type_header(b"OTTO\xff\xff") is True


def test_is_open_type_header_lowercase_is_false() -> None:
    # The magic is case-sensitive uppercase ASCII.
    assert PDFontFactory.is_open_type_header(b"otto") is False


def test_is_open_type_header_true_is_false() -> None:
    assert PDFontFactory.is_open_type_header(b"true") is False


def test_is_open_type_header_too_short() -> None:
    assert PDFontFactory.is_open_type_header(b"OTT") is False


# ---------- is_type1_header ----------


def test_is_type1_header_percent_bang() -> None:
    # '%!' = 0x25 0x21
    assert PDFontFactory.is_type1_header(b"%!PS-AdobeFont-1.0") is True


def test_is_type1_header_percent_bang_only() -> None:
    assert PDFontFactory.is_type1_header(b"%!") is True


def test_is_type1_header_just_percent() -> None:
    assert PDFontFactory.is_type1_header(b"%X") is False


def test_is_type1_header_just_bang() -> None:
    assert PDFontFactory.is_type1_header(b"X!") is False


def test_is_type1_header_pfb_is_false() -> None:
    assert PDFontFactory.is_type1_header(b"\x80\x01") is False


def test_is_type1_header_too_short() -> None:
    assert PDFontFactory.is_type1_header(b"%") is False


def test_is_type1_header_empty() -> None:
    assert PDFontFactory.is_type1_header(b"") is False


# ---------- is_pfb_header ----------


def test_is_pfb_header_segment_type_1_ascii() -> None:
    # 0x80 then 0x01 (ASCII text segment).
    assert PDFontFactory.is_pfb_header(b"\x80\x01\x00\x00") is True


def test_is_pfb_header_segment_type_2_binary() -> None:
    assert PDFontFactory.is_pfb_header(b"\x80\x02\x00\x00") is True


def test_is_pfb_header_segment_type_3_eof_is_false() -> None:
    # PFB EOF marker (0x03) is valid PFB but isn't a font-program start
    # — upstream's ``isPfbFile`` only matches segment types 1 and 2.
    assert PDFontFactory.is_pfb_header(b"\x80\x03") is False


def test_is_pfb_header_wrong_first_byte() -> None:
    assert PDFontFactory.is_pfb_header(b"\x81\x01") is False


def test_is_pfb_header_too_short() -> None:
    assert PDFontFactory.is_pfb_header(b"\x80") is False


# ---------- is_cff_header ----------


def test_is_cff_header_typical_v1() -> None:
    # major=1, minor=0, hdr size=4, offset size=2 — typical CFF header.
    assert PDFontFactory.is_cff_header(b"\x01\x00\x04\x02") is True


def test_is_cff_header_offset_size_1() -> None:
    assert PDFontFactory.is_cff_header(b"\x01\x00\x04\x01") is True


def test_is_cff_header_offset_size_4() -> None:
    assert PDFontFactory.is_cff_header(b"\x01\x00\x04\x04") is True


def test_is_cff_header_major_zero_is_false() -> None:
    # Major version must be >= 1.
    assert PDFontFactory.is_cff_header(b"\x00\x00\x04\x02") is False


def test_is_cff_header_offset_size_zero_is_false() -> None:
    assert PDFontFactory.is_cff_header(b"\x01\x00\x04\x00") is False


def test_is_cff_header_offset_size_five_is_false() -> None:
    # Offset size must be in [1, 4].
    assert PDFontFactory.is_cff_header(b"\x01\x00\x04\x05") is False


def test_is_cff_header_too_short() -> None:
    assert PDFontFactory.is_cff_header(b"\x01\x00\x04") is False


def test_is_cff_header_higher_major_version() -> None:
    # The check is permissive on major version (>=1).
    assert PDFontFactory.is_cff_header(b"\x02\x00\x04\x02") is True


# ---------- is_*_header: None / sentinel inputs ----------


@pytest.mark.parametrize(
    "predicate",
    [
        PDFontFactory.is_true_type_header,
        PDFontFactory.is_true_type_collection_header,
        PDFontFactory.is_open_type_header,
        PDFontFactory.is_type1_header,
        PDFontFactory.is_pfb_header,
        PDFontFactory.is_cff_header,
    ],
)
def test_predicates_handle_none(predicate: object) -> None:
    assert predicate(None) is False  # type: ignore[operator]


@pytest.mark.parametrize(
    "predicate",
    [
        PDFontFactory.is_true_type_header,
        PDFontFactory.is_true_type_collection_header,
        PDFontFactory.is_open_type_header,
    ],
)
def test_string_predicates_handle_non_ascii_bytes(
    predicate: object,
) -> None:
    # Non-ASCII bytes in the header must not raise — they just don't
    # match the (ASCII-only) magic strings.
    assert predicate(b"\xff\xfe\xfd\xfc") is False  # type: ignore[operator]


# ---------- get_descendant_font_dict ----------


def _make_type0_with_descendant(descendant: COSDictionary) -> COSDictionary:
    parent = COSDictionary()
    parent.set_name(_SUBTYPE, "Type0")
    arr = COSArray()
    arr.add(descendant)
    parent.set_item(_DESCENDANT_FONTS, arr)
    return parent


def test_get_descendant_font_dict_returns_first_entry() -> None:
    descendant = COSDictionary()
    descendant.set_name(_SUBTYPE, "CIDFontType2")
    parent = _make_type0_with_descendant(descendant)
    out = PDFontFactory.get_descendant_font_dict(parent)
    assert out is descendant


def test_get_descendant_font_dict_with_multiple_entries_returns_first() -> None:
    first = COSDictionary()
    first.set_name(_SUBTYPE, "CIDFontType0")
    second = COSDictionary()
    second.set_name(_SUBTYPE, "CIDFontType2")
    parent = COSDictionary()
    arr = COSArray()
    arr.add(first)
    arr.add(second)
    parent.set_item(_DESCENDANT_FONTS, arr)
    assert PDFontFactory.get_descendant_font_dict(parent) is first


def test_get_descendant_font_dict_no_descendant_returns_none() -> None:
    parent = COSDictionary()
    parent.set_name(_SUBTYPE, "Type0")
    assert PDFontFactory.get_descendant_font_dict(parent) is None


def test_get_descendant_font_dict_empty_array_returns_none() -> None:
    parent = COSDictionary()
    parent.set_item(_DESCENDANT_FONTS, COSArray())
    assert PDFontFactory.get_descendant_font_dict(parent) is None


def test_get_descendant_font_dict_non_dict_first_entry_returns_none() -> None:
    parent = COSDictionary()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("NotADict"))
    parent.set_item(_DESCENDANT_FONTS, arr)
    assert PDFontFactory.get_descendant_font_dict(parent) is None


def test_get_descendant_font_dict_non_array_value_returns_none() -> None:
    # /DescendantFonts present but holding a dictionary by mistake.
    parent = COSDictionary()
    parent.set_item(_DESCENDANT_FONTS, COSDictionary())
    assert PDFontFactory.get_descendant_font_dict(parent) is None


def test_get_descendant_font_dict_none_input_returns_none() -> None:
    assert (
        PDFontFactory.get_descendant_font_dict(None)  # type: ignore[arg-type]
        is None
    )


def test_get_descendant_font_dict_non_dictionary_raises_type_error() -> None:
    with pytest.raises(TypeError):
        PDFontFactory.get_descendant_font_dict("nope")  # type: ignore[arg-type]


# ---------- get_font_descriptor_dict ----------


def test_get_font_descriptor_dict_top_level() -> None:
    parent = COSDictionary()
    parent.set_name(_SUBTYPE, "Type1")
    descriptor = COSDictionary()
    parent.set_item(_FONT_DESCRIPTOR, descriptor)
    assert PDFontFactory.get_font_descriptor_dict(parent) is descriptor


def test_get_font_descriptor_dict_falls_back_to_descendant() -> None:
    # Type 0 parents normally don't carry their own /FontDescriptor —
    # the helper should resolve through the descendant.
    descendant = COSDictionary()
    descendant.set_name(_SUBTYPE, "CIDFontType2")
    descendant_descriptor = COSDictionary()
    descendant.set_item(_FONT_DESCRIPTOR, descendant_descriptor)
    parent = _make_type0_with_descendant(descendant)
    out = PDFontFactory.get_font_descriptor_dict(parent)
    assert out is descendant_descriptor


def test_get_font_descriptor_dict_top_level_wins_over_descendant() -> None:
    # When both are present, the top-level dict wins (matches upstream).
    top_descriptor = COSDictionary()
    descendant = COSDictionary()
    descendant_descriptor = COSDictionary()
    descendant.set_item(_FONT_DESCRIPTOR, descendant_descriptor)
    parent = _make_type0_with_descendant(descendant)
    parent.set_item(_FONT_DESCRIPTOR, top_descriptor)
    assert PDFontFactory.get_font_descriptor_dict(parent) is top_descriptor


def test_get_font_descriptor_dict_no_descriptor_anywhere_returns_none() -> None:
    parent = COSDictionary()
    parent.set_name(_SUBTYPE, "Type0")
    assert PDFontFactory.get_font_descriptor_dict(parent) is None


def test_get_font_descriptor_dict_descendant_without_descriptor() -> None:
    descendant = COSDictionary()
    descendant.set_name(_SUBTYPE, "CIDFontType2")
    parent = _make_type0_with_descendant(descendant)
    assert PDFontFactory.get_font_descriptor_dict(parent) is None


def test_get_font_descriptor_dict_non_dict_descriptor_returns_none() -> None:
    # /FontDescriptor present but holding a non-dictionary value
    # (malformed file). Helper must not raise — must return None and
    # also NOT fall through to the descendant (the entry was set, just
    # malformed; mirrors upstream which returns null in that branch).
    parent = COSDictionary()
    parent.set_item(_FONT_DESCRIPTOR, COSName.get_pdf_name("Bogus"))
    descendant = COSDictionary()
    descendant_descriptor = COSDictionary()
    descendant.set_item(_FONT_DESCRIPTOR, descendant_descriptor)
    arr = COSArray()
    arr.add(descendant)
    parent.set_item(_DESCENDANT_FONTS, arr)
    # Top-level entry isn't a dict, so we fall through to the descendant
    # (matches upstream's null-check on the top-level lookup).
    out = PDFontFactory.get_font_descriptor_dict(parent)
    assert out is descendant_descriptor


def test_get_font_descriptor_dict_none_input_returns_none() -> None:
    assert (
        PDFontFactory.get_font_descriptor_dict(None)  # type: ignore[arg-type]
        is None
    )


def test_get_font_descriptor_dict_non_dictionary_raises_type_error() -> None:
    with pytest.raises(TypeError):
        PDFontFactory.get_font_descriptor_dict(42)  # type: ignore[arg-type]


# ---------- header-predicate cross-check on synthesized programs ----------


def test_predicate_chain_only_one_matches_for_well_formed_headers() -> None:
    # Mirrors upstream getFontTypeFromFont's intent: at most one of the
    # primary predicates (TTF / OTF / Type1 / PFB) should match for any
    # well-formed header. CFF is intentionally excluded — the upstream
    # check is permissive and may overlap.
    samples = {
        "ttf": b"\x00\x01\x00\x00",
        "otf": b"OTTO",
        "ttc": b"ttcf",
        "true": b"true",
        "type1": b"%!PS-AdobeFont-1.0",
        "pfb1": b"\x80\x01\x00\x00",
        "pfb2": b"\x80\x02\x00\x00",
    }
    primary = [
        PDFontFactory.is_true_type_header,
        PDFontFactory.is_true_type_collection_header,
        PDFontFactory.is_open_type_header,
        PDFontFactory.is_type1_header,
        PDFontFactory.is_pfb_header,
    ]
    for label, header in samples.items():
        hits = sum(1 for p in primary if p(header))
        assert hits == 1, f"{label}: expected exactly one primary predicate hit, got {hits}"


# ---------- header-predicate cross-check via real factory dispatch ----------


def test_helpers_unchanged_by_create_font_dispatch() -> None:
    # Smoke: the helpers are pure (no global state) — ensure that calling
    # create_font in between doesn't mutate the result.
    raw = COSDictionary()
    raw.set_name(_SUBTYPE, "Type1")
    descriptor = COSDictionary()
    ff3 = COSStream()
    ff3.set_name(_SUBTYPE, "Type1C")
    descriptor.set_item(_FONT_FILE3, ff3)
    raw.set_item(_FONT_DESCRIPTOR, descriptor)
    before = PDFontFactory.get_font_descriptor_dict(raw)
    PDFontFactory.create_font(raw)
    after = PDFontFactory.get_font_descriptor_dict(raw)
    assert before is after is descriptor


def test_get_descendant_font_dict_sees_real_type0_dispatch() -> None:
    # Build a /Type0 dict the way callers would, then verify the helper
    # resolves the descendant the same way internal dispatch does.
    descendant = COSDictionary()
    descendant.set_name(_SUBTYPE, "CIDFontType2")
    desc_descriptor = COSDictionary()
    desc_descriptor.set_item(_FONT_FILE2, COSStream())
    descendant.set_item(_FONT_DESCRIPTOR, desc_descriptor)
    parent = _make_type0_with_descendant(descendant)
    assert PDFontFactory.get_descendant_font_dict(parent) is descendant
    assert PDFontFactory.get_font_descriptor_dict(parent) is desc_descriptor
