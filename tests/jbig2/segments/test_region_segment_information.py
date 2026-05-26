"""Hand-written tests for the JBIG2 RegionSegmentInformation field (7.4.1).

Crafted 17-byte region-segment-information data part:

* bitmapWidth  = 100 (00000064)
* bitmapHeight = 200 (000000c8)
* xLocation    = 10  (0000000a)
* yLocation    = 20  (00000014)
* flags byte = 0x01:
    bit3-7 reserved (dirty read of 5 bits) = 0
    bit0-2 combinationOperator = 001b = 1 -> AND
"""

from __future__ import annotations

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.region_segment_information import RegionSegmentInformation
from pypdfbox.jbig2.util.combination_operator import CombinationOperator

_DATA = bytes.fromhex("00000064000000c80000000a0000001401")


def _parse(data: bytes) -> RegionSegmentInformation:
    sis = SubInputStream(ImageInputStream(data), 0, len(data))
    region_info = RegionSegmentInformation(sis)
    region_info.parse_header()
    return region_info


def test_bitmap_dimensions():
    region_info = _parse(_DATA)
    assert region_info.get_bitmap_width() == 100
    assert region_info.get_bitmap_height() == 200


def test_location():
    region_info = _parse(_DATA)
    assert region_info.get_x_location() == 10
    assert region_info.get_y_location() == 20


def test_combination_operator():
    region_info = _parse(_DATA)
    assert region_info.get_combination_operator() == CombinationOperator.AND


def test_combination_operator_or():
    # flags byte 0x00 -> combination operator code 0 -> OR.
    data = bytes.fromhex("0000000100000002000000030000000400")
    region_info = _parse(data)
    assert region_info.get_bitmap_width() == 1
    assert region_info.get_bitmap_height() == 2
    assert region_info.get_x_location() == 3
    assert region_info.get_y_location() == 4
    assert region_info.get_combination_operator() == CombinationOperator.OR


def test_reserved_bits_are_skipped():
    # flags byte 0xFA = 0b11111010 -> reserved bits (3-7) set, op bits = 010b = 2
    # -> XOR. The reserved bits must be skipped (dirty read), not affect the op.
    data = bytes.fromhex("0000000500000006000000070000000800")[:-1] + bytes([0xFA])
    region_info = _parse(data)
    assert region_info.get_combination_operator() == CombinationOperator.XOR


def test_setters():
    region_info = RegionSegmentInformation()
    region_info.set_bitmap_width(42)
    region_info.set_bitmap_height(24)
    assert region_info.get_bitmap_width() == 42
    assert region_info.get_bitmap_height() == 24


def test_init_is_noop():
    # init() is intentionally empty upstream; constructing + init must not raise
    # and must leave fields at their defaults.
    region_info = RegionSegmentInformation()
    region_info.init(None, None)
    assert region_info.get_bitmap_width() == 0
    assert region_info.get_combination_operator() is None
