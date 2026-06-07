"""Hand-written tests for the JBIG2 PageInformation segment (7.4.8).

Crafted 19-byte page-information data part:

* width  = 64   (00000040)
* height = 48   (00000030)
* resX   = 300  (0000012c)
* resY   = 300  (0000012c)
* flags byte = 0x55 = 0b01010101:
    bit7 (dirty)            = 0
    bit6 combOverrideAllow  = 1
    bit5 requiresAuxBuffer  = 0
    bit4-3 combinationOp    = 10b = 2 -> XOR
    bit2 defaultPixelValue  = 1
    bit1 mightContainRefine = 0
    bit0 isLossless         = 1
* striping (2 bytes) = 0x8064:
    bit15 isStriped         = 1
    bit0-14 maxStripeSize   = 100
"""

from __future__ import annotations

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.page_information import PageInformation
from pypdfbox.jbig2.util.combination_operator import CombinationOperator

_DATA = bytes.fromhex("00000040000000300000012c0000012c558064")


def _parse(data: bytes) -> PageInformation:
    sis = SubInputStream(ImageInputStream(data), 0, len(data))
    page_info = PageInformation()
    page_info.init(None, sis)
    return page_info


def test_width_and_height():
    page_info = _parse(_DATA)
    assert page_info.get_width() == 64
    assert page_info.get_height() == 48


def test_resolution():
    page_info = _parse(_DATA)
    assert page_info.get_resolution_x() == 300
    assert page_info.get_resolution_y() == 300


def test_bitmap_width_and_height_accessors():
    # ``_get_bitmap_width`` / ``_get_bitmap_height`` mirror upstream's
    # ``getBitmapWidth`` / ``getBitmapHeight`` — they return the same parsed
    # 7.4.8.1/7.4.8.2 dimensions exposed by ``get_width`` / ``get_height``.
    page_info = _parse(_DATA)
    assert page_info._get_bitmap_width() == 64
    assert page_info._get_bitmap_height() == 48
    assert page_info._get_bitmap_width() == page_info.get_width()
    assert page_info._get_bitmap_height() == page_info.get_height()


def test_flag_bits():
    page_info = _parse(_DATA)
    assert page_info.is_combination_operator_override_allowed() is True
    assert page_info.is_auxiliary_buffer_required() is False
    assert page_info.get_combination_operator() == CombinationOperator.XOR
    assert page_info.get_default_pixel_value() == 1
    assert page_info.might_contain_refinements() is False
    assert page_info.is_lossless() is True


def test_striping():
    page_info = _parse(_DATA)
    assert page_info.is_striped() is True
    assert page_info.get_max_stripe_size() == 100


def test_all_flags_clear():
    # flags byte 0x00, striping 0x0000 -> every boolean false, op = OR (code 0).
    data = bytes.fromhex("0000000a00000014000000000000000000") + bytes([0x00, 0x00])
    page_info = _parse(data)
    assert page_info.get_width() == 10
    assert page_info.get_height() == 20
    assert page_info.is_combination_operator_override_allowed() is False
    assert page_info.is_auxiliary_buffer_required() is False
    assert page_info.get_combination_operator() == CombinationOperator.OR
    assert page_info.get_default_pixel_value() == 0
    assert page_info.might_contain_refinements() is False
    assert page_info.is_lossless() is False
    assert page_info.is_striped() is False
    assert page_info.get_max_stripe_size() == 0


def test_max_stripe_size_uses_15_bits():
    # striping = 0x7fff -> not striped (bit15 = 0), maxStripeSize = 0x7fff.
    data = bytes.fromhex("0000000100000001000000000000000000") + bytes([0x7F, 0xFF])
    page_info = _parse(data)
    assert page_info.is_striped() is False
    assert page_info.get_max_stripe_size() == 0x7FFF
