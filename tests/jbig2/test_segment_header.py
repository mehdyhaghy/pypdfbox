"""Hand-written tests for the JBIG2 SegmentHeader parser.

The crafted byte stream contains three concatenated segments:

* Header A: type 48 (PageInformation), segNr 0, short page-assoc = 1,
  0 referred-to segments, dataLen 19.
* Header B: type 38 (GenericRegion, not yet ported), segNr 1, retain flag set,
  long (4-byte) page-assoc = 2, 0 referred-to segments, dataLen 5.
* Header C: type 50 (EndOfStripe), segNr 2, short page-assoc = 1,
  0 referred-to segments, dataLen 4.

Every expected value below is hand-computed from the bit/byte layout in 7.2 and
cross-checked against the upstream PDFBox oracle (oracle/probes/SegHeaderProbe.java).
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segment_header import (
    RANDOM,
    SEGMENT_TYPE_MAP,
    SEQUENTIAL,
    SegmentHeader,
)
from pypdfbox.jbig2.segments.end_of_stripe import EndOfStripe
from pypdfbox.jbig2.segments.page_information import PageInformation

# The full crafted stream: three headers each followed by its data part.
_FULL = bytes.fromhex(
    "0000000030000100000013"  # header A (11 bytes)
    "00000000000000000000000000000000000000"  # data A (19 bytes)
    "00000001e6000000000200000005"  # header B (14 bytes)
    "0000000000"  # data B (5 bytes)
    "0000000232000100000004"  # header C (11 bytes)
    "00003039"  # data C (4 bytes): line number 12345
)


def _parse_all(stream: bytes, count: int, organisation_type: int = SEQUENTIAL):
    sis = SubInputStream(ImageInputStream(stream), 0, len(stream))
    headers = []
    offset = 0
    for _ in range(count):
        header = SegmentHeader(None, sis, offset, organisation_type)
        headers.append(header)
        offset = header.get_segment_data_start_offset() + header.get_segment_data_length()
    return headers


def test_organisation_type_constants():
    assert RANDOM == 0
    assert SEQUENTIAL == 1


def test_header_a_page_information():
    a, _b, _c = _parse_all(_FULL, 3)
    assert a.get_segment_nr() == 0
    assert a.get_segment_type() == 48
    assert a.get_page_association() == 1
    assert a.get_retain_flag() == 0
    assert a.get_segment_header_length() == 11
    assert a.get_segment_data_length() == 19
    assert a.get_segment_data_start_offset() == 11
    assert a.get_rt_segments() is None


def test_header_b_long_page_assoc_and_retain_flag():
    _a, b, _c = _parse_all(_FULL, 3)
    assert b.get_segment_nr() == 1
    assert b.get_segment_type() == 38
    # Long (4-byte) page association format because flag bit 6 is set.
    assert b.get_page_association() == 2
    assert b.get_retain_flag() == 1
    assert b.get_segment_header_length() == 14
    assert b.get_segment_data_length() == 5
    assert b.get_segment_data_start_offset() == 44


def test_header_c_end_of_stripe():
    _a, _b, c = _parse_all(_FULL, 3)
    assert c.get_segment_nr() == 2
    assert c.get_segment_type() == 50
    assert c.get_page_association() == 1
    assert c.get_retain_flag() == 0
    assert c.get_segment_header_length() == 11
    assert c.get_segment_data_length() == 4
    assert c.get_segment_data_start_offset() == 60


def test_data_start_offset_not_set_when_random():
    # With RANDOM organisation, the data start offset stays at its default (0).
    sis = SubInputStream(ImageInputStream(_FULL), 0, len(_FULL))
    header = SegmentHeader(None, sis, 0, RANDOM)
    assert header.get_segment_data_start_offset() == 0
    # The rest of the header is still parsed correctly.
    assert header.get_segment_nr() == 0
    assert header.get_segment_type() == 48
    assert header.get_segment_header_length() == 11


def test_get_segment_data_returns_concrete_page_information():
    a, _b, _c = _parse_all(_FULL, 3)
    # Replace the zero data of header A with a real PageInformation payload so
    # the data part parses cleanly.
    page_info_data = bytes.fromhex("00000040000000300000012c0000012c558064")
    header_a = struct.pack(">I", 0) + bytes([48]) + bytes([0x00]) + bytes([0x01]) + struct.pack(
        ">I", 19
    )
    stream = header_a + page_info_data
    sis = SubInputStream(ImageInputStream(stream), 0, len(stream))
    header = SegmentHeader(None, sis, 0, SEQUENTIAL)

    data = header.get_segment_data()
    assert isinstance(data, PageInformation)
    assert data.get_width() == 64
    assert data.get_height() == 48
    # Cached: a second call returns the same instance.
    assert header.get_segment_data() is data


def test_get_segment_data_for_end_of_stripe():
    header_c = struct.pack(">I", 2) + bytes([50]) + bytes([0x00]) + bytes([0x01]) + struct.pack(
        ">I", 4
    )
    stream = header_c + struct.pack(">I", 12345)
    sis = SubInputStream(ImageInputStream(stream), 0, len(stream))
    header = SegmentHeader(None, sis, 0, SEQUENTIAL)

    data = header.get_segment_data()
    assert isinstance(data, EndOfStripe)
    assert data.get_line_number() == 12345


def test_get_segment_data_not_yet_ported_raises():
    # Type 38 (GenericRegion) is not yet ported -> NotImplementedError.
    header_b = struct.pack(">I", 1) + bytes([38]) + bytes([0x00]) + bytes([0x01]) + struct.pack(
        ">I", 5
    )
    stream = header_b + bytes(5)
    sis = SubInputStream(ImageInputStream(stream), 0, len(stream))
    header = SegmentHeader(None, sis, 0, SEQUENTIAL)

    with pytest.raises(NotImplementedError) as exc:
        header.get_segment_data()
    assert "38" in str(exc.value)
    assert "GenericRegion" in str(exc.value)


def test_get_segment_data_unknown_type_raises_value_error():
    # Type 1 is not a real JBIG2 segment type and not in the not-yet-ported set.
    header = struct.pack(">I", 9) + bytes([1]) + bytes([0x00]) + bytes([0x01]) + struct.pack(
        ">I", 0
    )
    sis = SubInputStream(ImageInputStream(header), 0, len(header))
    sh = SegmentHeader(None, sis, 0, SEQUENTIAL)
    with pytest.raises(ValueError):
        sh.get_segment_data()


def test_clean_segment_data_drops_cache():
    header_c = struct.pack(">I", 2) + bytes([50]) + bytes([0x00]) + bytes([0x01]) + struct.pack(
        ">I", 4
    )
    stream = header_c + struct.pack(">I", 99)
    sis = SubInputStream(ImageInputStream(stream), 0, len(stream))
    header = SegmentHeader(None, sis, 0, SEQUENTIAL)

    first = header.get_segment_data()
    header.clean_segment_data()
    # After cleaning, a fresh instance is re-parsed (not the same object).
    second = header.get_segment_data()
    assert isinstance(second, EndOfStripe)
    assert second is not first
    assert second.get_line_number() == 99


def test_get_data_input_stream_is_windowed_view():
    header_c = struct.pack(">I", 2) + bytes([50]) + bytes([0x00]) + bytes([0x01]) + struct.pack(
        ">I", 4
    )
    stream = header_c + struct.pack(">I", 777)
    sis = SubInputStream(ImageInputStream(stream), 0, len(stream))
    header = SegmentHeader(None, sis, 0, SEQUENTIAL)

    data_stream = header.get_data_input_stream()
    assert data_stream.length() == 4
    assert data_stream.read_bits(32) == 777


def test_referred_to_segments_short_format():
    # Header with 2 referred-to segments (short format, count <= 4), segNr small
    # so rts_size == 1. segNr=5, type=0 (SymbolDictionary), page short=1.
    # RTS count byte: count=2 -> bits7-5 = 010 -> 0x40; retain bits 0.
    referred = bytes([10, 20])  # two 1-byte referred-to numbers
    header = (
        struct.pack(">I", 5)
        + bytes([0x00])  # flags: retain 0, pageAssocFieldSize 0, type 0
        + bytes([0x40])  # RTS count = 2 (short format)
        + referred
        + bytes([0x01])  # page association = 1
        + struct.pack(">I", 0)  # data length 0
    )
    sis = SubInputStream(ImageInputStream(header), 0, len(header))
    sh = SegmentHeader(None, sis, 0, SEQUENTIAL)
    assert sh.get_segment_nr() == 5
    assert sh.get_segment_type() == 0
    assert sh.get_page_association() == 1
    rt = sh.get_rt_segments()
    assert rt is not None
    assert len(rt) == 2
    # document is None, so referred-to headers are unresolved (left as None),
    # but the numbers were consumed to keep the bit position correct.
    assert rt == [None, None]
    # Header length: 4 (nr) + 1 (flags) + 1 (rts) + 2 (referred) + 1 (page) + 4 (len) = 13
    assert sh.get_segment_header_length() == 13


def test_segment_type_map_has_ported_types():
    assert SEGMENT_TYPE_MAP[48] is PageInformation
    assert SEGMENT_TYPE_MAP[50] is EndOfStripe


def test_str_contains_segment_fields():
    a, _b, _c = _parse_all(_FULL, 3)
    text = str(a)
    assert "SegmentNr: 0" in text
    assert "SegmentType: 48" in text
    assert "PageAssociation: 1" in text
