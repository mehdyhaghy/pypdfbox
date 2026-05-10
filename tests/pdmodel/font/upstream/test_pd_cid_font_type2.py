"""Tests ported from upstream ``PDCIDFontType2Test``.

Upstream Java path:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDCIDFontType2Test.java``.

Upstream coverage focuses on three loading paths:
* identity ``/CIDToGIDMap`` round-trip via ``codeToGID`` / ``codeToCID``,
* descriptor-driven embedding via ``/FontFile2`` (``isEmbedded`` /
  ``getTrueTypeFont``), and
* metric retrieval (``getHeight``, ``getWidthFromFont``,
  ``getAverageFontWidth``, ``getFontMatrix``, ``getBoundingBox``)
  with and without an embedded program.

The two upstream tests that exercise actual SFNT bytes
(``testCIDToGIDMapWithGlyphsThroughLoad``,
``testHorizontalMetricsViaCmap``) are skipped here — they require a
full TTF fixture sync from ``pdfbox/src/test/resources`` which is
tracked separately under the fontbox/ttf cluster. Hand-written
metric tests in ``tests/pdmodel/font/test_pd_cid_font_type2.py``
exercise the same code paths via a stubbed TTF.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.fontbox.ttf import OTFParser, TTFParser
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor

# ---------- /CIDToGIDMap ----------


def test_identity_cid_to_gid_when_absent() -> None:
    font = PDCIDFontType2()
    assert font.is_identity_cid_to_gid_map() is True
    assert font.get_cid_to_gid_map_bytes() is None


def test_identity_cid_to_gid_when_named_identity() -> None:
    font = PDCIDFontType2()
    font.set_cid_to_gid_map("Identity")
    assert font.is_identity_cid_to_gid_map() is True
    # Upstream collapses /Identity to null bytes — callers fall back
    # to identity CID->GID mapping.
    assert font.get_cid_to_gid_map_bytes() is None


def test_explicit_cid_to_gid_map_bytes_roundtrip() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    payload = b"\x00\x00\x00\x10\x00\x20\x00\x30"
    stream.set_data(payload)
    font.set_cid_to_gid_map(stream)
    assert font.is_identity_cid_to_gid_map() is False
    assert font.get_cid_to_gid_map_bytes() == payload
    # CID 0 -> GID 0, CID 1 -> 16, CID 2 -> 32, CID 3 -> 48.
    assert font.code_to_gid(0) == 0
    assert font.code_to_gid(1) == 16
    assert font.code_to_gid(2) == 32
    assert font.code_to_gid(3) == 48


def test_code_to_cid_is_identity() -> None:
    # PDCIDFontType2.codeToCID is identity — the parent Type 0 font's
    # /Encoding CMap has already converted the byte to a CID.
    font = PDCIDFontType2()
    for code in (0, 1, 65, 256, 0xFFFF):
        assert font.code_to_cid(code) == code


# ---------- isEmbedded ----------


def test_is_embedded_false_when_no_descriptor() -> None:
    font = PDCIDFontType2()
    assert font.is_embedded() is False


def test_is_embedded_false_with_empty_descriptor() -> None:
    font = PDCIDFontType2()
    font.set_font_descriptor(PDFontDescriptor())
    assert font.is_embedded() is False


def test_is_embedded_true_when_font_file2_present() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    fd.set_font_file2(COSStream())
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


def test_is_embedded_true_for_open_type_font_file3() -> None:
    # PDFBox 3.0 added /FontFile3 /OpenType acceptance for CIDFontType2
    # so OpenType-flavoured TrueType programs can ride along.
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "OpenType")  # type: ignore[attr-defined]
    fd.set_font_file3(stream)
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


# ---------- getTrueTypeFont (lazy parse) ----------


def test_get_true_type_font_none_without_descriptor() -> None:
    font = PDCIDFontType2()
    assert font.get_true_type_font() is None


def test_get_true_type_font_none_when_unparseable() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(b"not-a-real-ttf")
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    assert font.get_true_type_font() is None


# ---------- isDamaged ----------


def test_is_damaged_false_when_not_embedded() -> None:
    font = PDCIDFontType2()
    assert font.is_damaged() is False


def test_is_damaged_true_when_embedded_program_unparseable() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(b"definitely-not-a-ttf")
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    assert font.is_damaged() is True


# ---------- getFontMatrix (default 1/1000 when no program) ----------


def test_get_font_matrix_default_when_no_program() -> None:
    font = PDCIDFontType2()
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


# ---------- getBoundingBox / getHeight / getAverageFontWidth fall-throughs ----------


def test_get_bounding_box_none_when_neither_program_nor_descriptor() -> None:
    font = PDCIDFontType2()
    assert font.get_bounding_box() is None


def test_get_height_zero_when_no_program_no_w2() -> None:
    font = PDCIDFontType2()
    assert font.get_height(65) == 0.0


def test_get_average_font_width_falls_through_to_dw() -> None:
    font = PDCIDFontType2()
    font.set_dw(750)
    assert font.get_average_font_width() == pytest.approx(750.0)


def test_get_width_from_font_zero_when_no_program() -> None:
    font = PDCIDFontType2()
    assert font.get_width_from_font(65) == 0.0


# ---------- glyph-path entry points (no embedded program) ----------


def test_get_path_empty_when_no_program() -> None:
    # Upstream getPath() returns an empty GeneralPath when the embedded
    # program cannot be located — pypdfbox returns the equivalent empty
    # command list.
    font = PDCIDFontType2()
    assert font.get_path(65) == []


def test_get_path_from_outlines_none_when_not_open_type_post_script() -> None:
    # The CFF charstring branch only fires when otf != null && isPostScript().
    # No embedded program → no OTF → guard returns None.
    font = PDCIDFontType2()
    assert font.get_path_from_outlines(65) is None


# ---------- find_font_or_substitute ----------


def test_find_font_or_substitute_falls_through_when_no_mapper_override() -> None:
    # Upstream consults FontMappers.instance().getCIDFont(...). pypdfbox's
    # bundled DefaultFontMapper has no on-disk CID font scanner so the
    # default response is a None CIDFontMapping — we surface that without
    # raising. (Real CID-aware mappers override get_cid_font.)
    font = PDCIDFontType2()
    # With no FontMapper override registered the call should not raise
    # and should return either None or a CIDFontMapping object — the
    # exact class depends on whether a host-system mapper is wired up.
    result = font.find_font_or_substitute()
    assert result is None or hasattr(result, "is_cid_font")


# ---------- encode (unicode -> bytes) ----------


def test_encode_raises_when_no_glyph_available() -> None:
    # Upstream throws IllegalArgumentException("No glyph for U+%04X ...");
    # pypdfbox surfaces ValueError. Here the font has no embedded program
    # and no parent / cmap, so no glyph can be located for any codepoint.
    font = PDCIDFontType2()
    with pytest.raises(ValueError, match=r"No glyph for U\+0041"):
        font.encode(0x41)


# ---------- get_parser (TTF vs OTF SFNT-magic dispatch) ----------


def test_get_parser_returns_otf_for_otto_magic() -> None:
    # Upstream sniffs the first four bytes of the embedded program for
    # the OpenType OTTO sfnt-version tag and dispatches to OTFParser.
    parser = PDCIDFontType2.get_parser(b"OTTO\x00\x10\x00\x00")
    assert isinstance(parser, OTFParser)


def test_get_parser_returns_ttf_for_truetype_magic() -> None:
    # TrueType programs use \x00\x01\x00\x00 (alongside legacy 'true' /
    # 'typ1' tags) — anything that isn't OTTO falls through to TTFParser.
    parser = PDCIDFontType2.get_parser(b"\x00\x01\x00\x00")
    assert isinstance(parser, TTFParser)
    # OTFParser inherits TTFParser so the identity check matters.
    assert not isinstance(parser, OTFParser)


def test_get_parser_returns_ttf_for_short_or_empty_data() -> None:
    parser = PDCIDFontType2.get_parser(b"")
    assert isinstance(parser, TTFParser)
    assert not isinstance(parser, OTFParser)


def test_get_parser_propagates_is_embedded_flag() -> None:
    embedded = PDCIDFontType2.get_parser(b"\x00\x01\x00\x00", is_embedded=True)
    standalone = PDCIDFontType2.get_parser(
        b"\x00\x01\x00\x00", is_embedded=False
    )
    assert embedded.is_embedded is True
    assert standalone.is_embedded is False


# ---------- generate_bounding_box (descriptor-first, non-zero only) ----------


def test_generate_bounding_box_uses_descriptor_when_non_zero() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    bbox_arr = COSArray()
    for v in (-50, -25, 1050, 950):
        bbox_arr.add(COSFloat(v))
    fd.set_font_b_box(bbox_arr)
    font.set_font_descriptor(fd)
    bbox = font.generate_bounding_box()
    assert bbox is not None
    assert bbox.lower_left_x == pytest.approx(-50.0)
    assert bbox.upper_right_y == pytest.approx(950.0)


def test_generate_bounding_box_none_when_no_sources() -> None:
    font = PDCIDFontType2()
    assert font.generate_bounding_box() is None


# ---------- skipped: SFNT-fixture-bound tests ----------


@pytest.mark.skip(
    reason="upstream test reads pdfbox/src/test/resources/ttf — fixture sync "
    "tracked under the fontbox/ttf cluster"
)
def test_horizontal_metrics_via_cmap() -> None:  # pragma: no cover
    pass


@pytest.mark.skip(
    reason="upstream test parses an embedded TTF and asserts /CIDToGIDMap "
    "round-trips against the cmap — fixture sync deferred"
)
def test_cid_to_gid_map_with_glyphs_through_load() -> None:  # pragma: no cover
    pass
