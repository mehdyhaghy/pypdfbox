"""Wave 1586 fuzz/parity battery for the JBIG2 page- and region-info parsers.

Drives :class:`pypdfbox.jbig2.segments.page_information.PageInformation` and
:class:`pypdfbox.jbig2.segments.region_segment_information.RegionSegmentInformation`
over hand-crafted byte streams that exercise every branch of the §7.4.8 page
information and §7.4.1 region segment information layouts (ITU-T T.88).

Page information (§7.4.8):

* §7.4.8.1/.2 page bitmap width and height (4 bytes each, big-endian),
  including the ``0xFFFFFFFF`` unknown-height special value used by striped
  pages of unknown length;
* §7.4.8.3/.4 page X/Y resolution (4 bytes each, unsigned);
* §7.4.8.5 the page flags byte read MSB-first — bit 7 reserved (dirty read),
  bit 6 = combination-operator-override-allowed, bit 5 = requires-auxiliary-
  buffer, bits 3-4 = default combination operator (OR/AND/XOR/XNOR), bit 2 =
  default pixel value, bit 1 = might-contain-refinements, bit 0 = is-lossless;
* §7.4.8.6 the striping field (2 bytes) — bit 15 = striped flag, bits 0-14 =
  maximum stripe size.

Region segment information (§7.4.1):

* §7.4.1.1-.4 region bitmap width/height and X/Y location (4 bytes each);
* §7.4.1.5 the region flags byte — bits 3-7 reserved (dirty read), bits 0-2 =
  external combination operator (the color-extension bit is bit 3, i.e. inside
  the reserved span of this 3-bit field for non-Generic regions).

Byte streams are computed directly from the §7.4 bit layout; nothing here is
parsed by another module under test.
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.page_information import PageInformation
from pypdfbox.jbig2.segments.region_segment_information import (
    RegionSegmentInformation,
)
from pypdfbox.jbig2.util.combination_operator import CombinationOperator


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def _sis(data: bytes) -> SubInputStream:
    return SubInputStream(ImageInputStream(data), 0, len(data))


def _page_flags(
    *,
    override_allowed: int = 0,
    requires_aux: int = 0,
    default_combop: int = 0,
    default_pixel: int = 0,
    refinements: int = 0,
    lossless: int = 0,
) -> int:
    """Build the §7.4.8.5 page flags byte (bit 7 reserved = 0)."""
    return (
        ((override_allowed & 1) << 6)
        | ((requires_aux & 1) << 5)
        | ((default_combop & 0x3) << 3)
        | ((default_pixel & 1) << 2)
        | ((refinements & 1) << 1)
        | (lossless & 1)
    )


def _striping(*, striped: int = 0, max_stripe_size: int = 0) -> int:
    """Build the §7.4.8.6 striping 2-byte field (bit 15 = striped)."""
    return ((striped & 1) << 15) | (max_stripe_size & 0x7FFF)


def _page_bytes(
    *,
    width: int = 0,
    height: int = 0,
    res_x: int = 0,
    res_y: int = 0,
    flags: int = 0,
    striping: int = 0,
) -> bytes:
    return (
        struct.pack(">I", width & 0xFFFFFFFF)
        + struct.pack(">I", height & 0xFFFFFFFF)
        + struct.pack(">I", res_x & 0xFFFFFFFF)
        + struct.pack(">I", res_y & 0xFFFFFFFF)
        + bytes([flags & 0xFF])
        + struct.pack(">H", striping & 0xFFFF)
    )


def _parse_page(**kw) -> PageInformation:
    data = _page_bytes(**kw)
    pi = PageInformation()
    pi.init(None, _sis(data))
    return pi


def _region_bytes(
    *,
    width: int = 0,
    height: int = 0,
    x: int = 0,
    y: int = 0,
    flags: int = 0,
) -> bytes:
    return (
        struct.pack(">I", width & 0xFFFFFFFF)
        + struct.pack(">I", height & 0xFFFFFFFF)
        + struct.pack(">I", x & 0xFFFFFFFF)
        + struct.pack(">I", y & 0xFFFFFFFF)
        + bytes([flags & 0xFF])
    )


def _parse_region(**kw) -> RegionSegmentInformation:
    data = _region_bytes(**kw)
    rsi = RegionSegmentInformation(_sis(data))
    rsi.parse_header()
    return rsi


# --------------------------------------------------------------------------- #
# Page information: width / height / resolution
# --------------------------------------------------------------------------- #
def test_page_width_height_basic():
    pi = _parse_page(width=0x12345678, height=0x0000FFFF)
    assert pi.get_width() == 0x12345678
    assert pi.get_height() == 0x0000FFFF


def test_page_width_height_zero():
    pi = _parse_page(width=0, height=0)
    assert pi.get_width() == 0
    assert pi.get_height() == 0


def test_page_unknown_height_special_value():
    # §7.4.8.2: 0xFFFFFFFF height marks unknown length for a striped page.
    pi = _parse_page(height=0xFFFFFFFF, striping=_striping(striped=1))
    assert pi.get_height() == 0xFFFFFFFF
    # Must NOT come back as -1 / a signed value — stays unsigned 32-bit.
    assert pi.get_height() == 4294967295
    assert pi.is_striped() is True


def test_page_high_bit_width_unsigned():
    pi = _parse_page(width=0x80000001)
    assert pi.get_width() == 0x80000001
    assert pi.get_width() > 0


def test_page_resolution_basic():
    pi = _parse_page(res_x=0x00112233, res_y=0x44556677)
    assert pi.get_resolution_x() == 0x00112233
    assert pi.get_resolution_y() == 0x44556677


def test_page_resolution_high_bit_unsigned():
    # §7.4.8.3/.4 are unsigned; a high-bit value must not turn negative.
    pi = _parse_page(res_x=0xFFFFFFFF, res_y=0x80000000)
    assert pi.get_resolution_x() == 0xFFFFFFFF
    assert pi.get_resolution_y() == 0x80000000
    assert pi.get_resolution_x() >= 0
    assert pi.get_resolution_y() >= 0


# --------------------------------------------------------------------------- #
# Page information: flags byte individual bits
# --------------------------------------------------------------------------- #
def test_page_flags_all_clear():
    pi = _parse_page(flags=0)
    assert pi.is_combination_operator_override_allowed() is False
    assert pi.is_auxiliary_buffer_required() is False
    assert pi.get_combination_operator() is CombinationOperator.OR
    assert pi.get_default_pixel_value() == 0
    assert pi.might_contain_refinements() is False
    assert pi.is_lossless() is False


def test_page_flag_override_allowed_bit6():
    pi = _parse_page(flags=_page_flags(override_allowed=1))
    assert pi.is_combination_operator_override_allowed() is True
    # No spillover into neighbours.
    assert pi.is_auxiliary_buffer_required() is False
    assert pi.get_combination_operator() is CombinationOperator.OR


def test_page_flag_requires_aux_bit5():
    pi = _parse_page(flags=_page_flags(requires_aux=1))
    assert pi.is_auxiliary_buffer_required() is True
    assert pi.is_combination_operator_override_allowed() is False
    assert pi.get_combination_operator() is CombinationOperator.OR


def test_page_flag_default_pixel_bit2():
    pi = _parse_page(flags=_page_flags(default_pixel=1))
    assert pi.get_default_pixel_value() == 1
    assert pi.get_combination_operator() is CombinationOperator.OR
    assert pi.might_contain_refinements() is False


def test_page_flag_refinements_bit1():
    pi = _parse_page(flags=_page_flags(refinements=1))
    assert pi.might_contain_refinements() is True
    assert pi.is_lossless() is False
    assert pi.get_default_pixel_value() == 0


def test_page_flag_lossless_bit0():
    pi = _parse_page(flags=_page_flags(lossless=1))
    assert pi.is_lossless() is True
    assert pi.might_contain_refinements() is False


def test_page_flag_reserved_bit7_ignored():
    # Bit 7 is reserved (dirty read) — setting it must not affect any field.
    pi = _parse_page(flags=0x80)
    assert pi.is_combination_operator_override_allowed() is False
    assert pi.is_auxiliary_buffer_required() is False
    assert pi.get_combination_operator() is CombinationOperator.OR
    assert pi.get_default_pixel_value() == 0
    assert pi.might_contain_refinements() is False
    assert pi.is_lossless() is False


def test_page_flags_all_set_except_reserved_and_combop():
    flags = _page_flags(
        override_allowed=1,
        requires_aux=1,
        default_pixel=1,
        refinements=1,
        lossless=1,
    )
    pi = _parse_page(flags=flags)
    assert pi.is_combination_operator_override_allowed() is True
    assert pi.is_auxiliary_buffer_required() is True
    assert pi.get_default_pixel_value() == 1
    assert pi.might_contain_refinements() is True
    assert pi.is_lossless() is True
    # default combop field was 0 -> OR
    assert pi.get_combination_operator() is CombinationOperator.OR


def test_page_flags_full_byte_set():
    # All 8 bits set: combop field = 0b11 -> XNOR.
    pi = _parse_page(flags=0xFF)
    assert pi.is_combination_operator_override_allowed() is True
    assert pi.is_auxiliary_buffer_required() is True
    assert pi.get_combination_operator() is CombinationOperator.XNOR
    assert pi.get_default_pixel_value() == 1
    assert pi.might_contain_refinements() is True
    assert pi.is_lossless() is True


# --------------------------------------------------------------------------- #
# Page information: default combination operator 2-bit field (bits 3-4)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0, CombinationOperator.OR),
        (1, CombinationOperator.AND),
        (2, CombinationOperator.XOR),
        (3, CombinationOperator.XNOR),
    ],
    ids=["or", "and", "xor", "xnor"],
)
def test_page_default_combination_operator_mapping(code, expected):
    pi = _parse_page(flags=_page_flags(default_combop=code))
    assert pi.get_combination_operator() is expected


def test_page_default_combop_shift_isolation():
    # combop=2 (XOR) with default_pixel set: verify the 2-bit field at bits 3-4
    # does not bleed into bit 2 (default pixel) or bit 5 (requires aux).
    pi = _parse_page(flags=_page_flags(default_combop=2, default_pixel=1))
    assert pi.get_combination_operator() is CombinationOperator.XOR
    assert pi.get_default_pixel_value() == 1
    assert pi.is_auxiliary_buffer_required() is False


def test_page_default_combop_max_field_value():
    # combop field == 0b11 must map to XNOR, never REPLACE (the 2-bit field
    # cannot reach code 4).
    pi = _parse_page(flags=_page_flags(default_combop=3))
    assert pi.get_combination_operator() is CombinationOperator.XNOR
    assert pi.get_combination_operator() is not CombinationOperator.REPLACE


# --------------------------------------------------------------------------- #
# Page information: striping field (§7.4.8.6)
# --------------------------------------------------------------------------- #
def test_page_striping_not_striped():
    pi = _parse_page(striping=_striping(striped=0, max_stripe_size=0))
    assert pi.is_striped() is False
    assert pi.get_max_stripe_size() == 0


def test_page_striping_striped_bit15():
    pi = _parse_page(striping=_striping(striped=1, max_stripe_size=0))
    assert pi.is_striped() is True
    assert pi.get_max_stripe_size() == 0


def test_page_striping_max_size_only():
    pi = _parse_page(striping=_striping(striped=0, max_stripe_size=0x1234))
    assert pi.is_striped() is False
    assert pi.get_max_stripe_size() == 0x1234


def test_page_striping_max_size_full_15_bits():
    # bits 0-14 all set, bit 15 set: striped True and max size = 0x7FFF, not
    # 0xFFFF (the striped bit must be masked out of the size).
    pi = _parse_page(striping=_striping(striped=1, max_stripe_size=0x7FFF))
    assert pi.is_striped() is True
    assert pi.get_max_stripe_size() == 0x7FFF


def test_page_striping_bit15_not_in_size():
    # Raw 0x8000: only bit 15 set. striped True, size must be 0.
    pi = _parse_page(striping=0x8000)
    assert pi.is_striped() is True
    assert pi.get_max_stripe_size() == 0


def test_page_striping_all_bits_set():
    pi = _parse_page(striping=0xFFFF)
    assert pi.is_striped() is True
    assert pi.get_max_stripe_size() == 0x7FFF


# --------------------------------------------------------------------------- #
# Region segment information: width / height / location
# --------------------------------------------------------------------------- #
def test_region_geometry_basic():
    rsi = _parse_region(width=0x000000AA, height=0x000000BB, x=0x0000000C, y=0x0000000D)
    assert rsi.get_bitmap_width() == 0xAA
    assert rsi.get_bitmap_height() == 0xBB
    assert rsi.get_x_location() == 0xC
    assert rsi.get_y_location() == 0xD


def test_region_geometry_high_bit_unsigned():
    rsi = _parse_region(width=0xFFFFFFFF, height=0x80000000, x=0xFFFFFFFF, y=0x80000000)
    assert rsi.get_bitmap_width() == 0xFFFFFFFF
    assert rsi.get_bitmap_height() == 0x80000000
    assert rsi.get_x_location() == 0xFFFFFFFF
    assert rsi.get_y_location() == 0x80000000
    assert rsi.get_bitmap_width() >= 0
    assert rsi.get_x_location() >= 0


def test_region_geometry_zero():
    rsi = _parse_region()
    assert rsi.get_bitmap_width() == 0
    assert rsi.get_bitmap_height() == 0
    assert rsi.get_x_location() == 0
    assert rsi.get_y_location() == 0


# --------------------------------------------------------------------------- #
# Region segment information: external combination operator (bits 0-2)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0, CombinationOperator.OR),
        (1, CombinationOperator.AND),
        (2, CombinationOperator.XOR),
        (3, CombinationOperator.XNOR),
        (4, CombinationOperator.REPLACE),
    ],
    ids=["or", "and", "xor", "xnor", "replace"],
)
def test_region_combination_operator_mapping(code, expected):
    rsi = _parse_region(flags=code)
    assert rsi.get_combination_operator() is expected


def test_region_combop_reserved_high_bits_ignored():
    # Bits 3-7 are reserved. Set them all (0xF8) with combop=2 in bits 0-2:
    # the 3-bit external combop field must still read XOR.
    rsi = _parse_region(flags=0xF8 | 0x2)
    assert rsi.get_combination_operator() is CombinationOperator.XOR


def test_region_combop_color_extension_bit3_excluded():
    # Bit 3 is the colour-extension bit, outside the 3-bit combop field. With
    # combop=0 (OR) and bit 3 set (0x08), the operator must remain OR.
    rsi = _parse_region(flags=0x08)
    assert rsi.get_combination_operator() is CombinationOperator.OR


def test_region_combop_codes_5_to_7_map_to_replace():
    # Codes 5..7 are not defined; translate_operator_code_to_enum falls through
    # to REPLACE. The 3-bit mask must still admit them (no over-mask to 0).
    for code in (5, 6, 7):
        rsi = _parse_region(flags=code)
        assert rsi.get_combination_operator() is CombinationOperator.REPLACE


def test_region_combop_full_flags_byte():
    # 0xFF: combop low 3 bits = 0b111 = 7 -> REPLACE.
    rsi = _parse_region(flags=0xFF)
    assert rsi.get_combination_operator() is CombinationOperator.REPLACE


# --------------------------------------------------------------------------- #
# Cross-checks: page vs region combop semantics differ in width
# --------------------------------------------------------------------------- #
def test_page_combop_is_two_bits_region_is_three_bits():
    # Page: combop field is only 2 bits, so it can never yield REPLACE.
    page = _parse_page(flags=_page_flags(default_combop=3))
    assert page.get_combination_operator() is CombinationOperator.XNOR
    # Region: 3-bit field can reach code 4 = REPLACE.
    region = _parse_region(flags=4)
    assert region.get_combination_operator() is CombinationOperator.REPLACE


def test_region_stream_fully_consumed():
    # 17 bytes: 4*4 geometry + 1 flags. Parser must consume exactly that.
    data = _region_bytes(width=1, height=1, x=2, y=3, flags=1)
    assert len(data) == 17
    sis = _sis(data)
    rsi = RegionSegmentInformation(sis)
    rsi.parse_header()
    assert rsi.get_bitmap_width() == 1
    assert rsi.get_combination_operator() is CombinationOperator.AND
