"""Wave 1585 fuzz/parity battery for the JBIG2 ``SegmentHeader`` parser.

Drives :class:`pypdfbox.jbig2.segment_header.SegmentHeader` over crafted byte
streams that exercise every branch of the §7.2 header layout (ITU-T T.88):

* §7.2.2 segment number (4 bytes, big-endian);
* §7.2.3 segment header flags byte — segment-type extraction (low 6 bits),
  the page-association-field-size flag (bit 6) and the deferred/retain flag
  (bit 7);
* §7.2.4 amount-of-referred-to-segments — the short form (3-bit count 0..4 +
  5 retain bits in a single byte) vs the long form (count field == 7 → a
  29-bit count + an 8-bit-aligned retain bitmap). The reserved-illegal count
  values 5 and 6 raise ``IntegerMaxValueException`` (the wave-1585 fix);
* §7.2.5 referred-to segment number byte size — 1 byte when ``segment_nr`` ≤
  256, 2 bytes when ≤ 65536, otherwise 4 bytes;
* §7.2.6 segment page association — 1 byte (short) vs 4 bytes (long) per the
  bit-6 flag;
* §7.2.7 segment data length (4 bytes) including the ``0xFFFFFFFF`` unknown
  length used by an immediate generic region;
* the §7.3 segment-type → SegmentData dispatch constants.

Every byte stream is hand-computed from the §7.2 bit layout, matching the
conventions already established in ``test_segment_header.py`` /
``test_segment_header_wave1510.py``.
"""

from __future__ import annotations

import struct

import pytest

import pypdfbox.jbig2.segment_header as segment_header_module
from pypdfbox.jbig2.err.integer_max_value_exception import IntegerMaxValueException
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segment_header import SEQUENTIAL, SegmentHeader


def _header(stream: bytes, document: object = None) -> SegmentHeader:
    sis = SubInputStream(ImageInputStream(stream), 0, len(stream))
    return SegmentHeader(document, sis, 0, SEQUENTIAL)


def _flags(segment_type: int, page_assoc_4: int = 0, retain: int = 0) -> int:
    """Build the §7.2.3 flags byte.

    Bit 7 = retain/deferred, bit 6 = page-association-field-size, bits 5..0 =
    segment type.
    """
    return ((retain & 1) << 7) | ((page_assoc_4 & 1) << 6) | (segment_type & 0x3F)


def _short_rts(count: int, retain_bits: int = 0) -> bytes:
    """Build the §7.2.4 short-form referred-to count byte (count in top 3
    bits, 5 retain bits below)."""
    assert 0 <= count <= 4
    return bytes([((count & 0x7) << 5) | (retain_bits & 0x1F)])


# ---------------------------------------------------------------------------
# §7.2.2 segment number
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "segment_nr",
    [0, 1, 255, 256, 257, 65535, 65536, 65537, 0x7FFFFFFF, 0xFFFFFFFF],
)
def test_segment_number_roundtrip(segment_nr: int) -> None:
    stream = (
        struct.pack(">I", segment_nr)
        + bytes([_flags(48)])  # PageInformation, short page assoc, count 0
        + _short_rts(0)
        + bytes([0x01])  # page association 1
        + struct.pack(">I", 0)
    )
    sh = _header(stream)
    assert sh.get_segment_nr() == segment_nr


# ---------------------------------------------------------------------------
# §7.2.3 flags byte: segment type (low 6 bits)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "segment_type",
    [0, 4, 6, 7, 16, 20, 22, 23, 36, 38, 39, 40, 42, 43, 48, 50, 52, 53],
)
def test_segment_type_extraction(segment_type: int) -> None:
    stream = (
        struct.pack(">I", 0)
        + bytes([_flags(segment_type)])
        + _short_rts(0)
        + bytes([0x01])
        + struct.pack(">I", 0)
    )
    sh = _header(stream)
    assert sh.get_segment_type() == segment_type


def test_segment_type_mask_ignores_high_bits() -> None:
    """The type comes from bits 5..0 only; the retain (bit 7) and page-assoc
    (bit 6) flags must not bleed into the type value."""
    # type 50 with both top flags set: raw byte = 0b11_110010 = 0xF2.
    stream = (
        struct.pack(">I", 0)
        + bytes([0xF2])
        + _short_rts(0)
        + struct.pack(">I", 7)  # 4-byte page assoc (bit 6 set)
        + struct.pack(">I", 0)
    )
    sh = _header(stream)
    assert sh.get_segment_type() == 50
    assert sh.get_retain_flag() == 1
    assert sh.get_page_association() == 7


def test_retain_flag_bit7() -> None:
    stream_set = (
        struct.pack(">I", 0)
        + bytes([_flags(48, retain=1)])
        + _short_rts(0)
        + bytes([0x01])
        + struct.pack(">I", 0)
    )
    stream_clear = (
        struct.pack(">I", 0)
        + bytes([_flags(48, retain=0)])
        + _short_rts(0)
        + bytes([0x01])
        + struct.pack(">I", 0)
    )
    assert _header(stream_set).get_retain_flag() == 1
    assert _header(stream_clear).get_retain_flag() == 0


# ---------------------------------------------------------------------------
# §7.2.6 page association field size (1 vs 4 bytes per bit 6)
# ---------------------------------------------------------------------------


def test_page_association_short_one_byte() -> None:
    stream = (
        struct.pack(">I", 0)
        + bytes([_flags(48, page_assoc_4=0)])
        + _short_rts(0)
        + bytes([0xFD])  # page association 253, single byte
        + struct.pack(">I", 0)
    )
    sh = _header(stream)
    assert sh.get_page_association() == 253
    # 4(nr) + 1(flags) + 1(rts) + 1(page) + 4(len) = 11
    assert sh.get_segment_header_length() == 11


def test_page_association_long_four_bytes() -> None:
    stream = (
        struct.pack(">I", 0)
        + bytes([_flags(48, page_assoc_4=1)])
        + _short_rts(0)
        + struct.pack(">I", 0x00012345)  # 4-byte page association
        + struct.pack(">I", 0)
    )
    sh = _header(stream)
    assert sh.get_page_association() == 0x00012345
    # 4 + 1 + 1 + 4 + 4 = 14
    assert sh.get_segment_header_length() == 14


# ---------------------------------------------------------------------------
# §7.2.4 referred-to count short / long form boundary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("count", [0, 1, 2, 3, 4])
def test_short_form_counts_zero_through_four(count: int) -> None:
    referred = bytes(range(1, count + 1))  # count 1-byte numbers
    stream = (
        struct.pack(">I", 0)
        + bytes([_flags(48)])
        + _short_rts(count)
        + referred
        + bytes([0x01])
        + struct.pack(">I", 0)
    )
    sh = _header(stream)
    rt = sh.get_rt_segments()
    if count == 0:
        assert rt is None
    else:
        assert rt is not None
        assert len(rt) == count
    expected_len = 4 + 1 + 1 + count + 1 + 4
    assert sh.get_segment_header_length() == expected_len


@pytest.mark.parametrize("count", [5, 6, 7, 8, 100])
def test_long_form_count_field_seven(count: int) -> None:
    """The 3-bit count field value 7 signals the long form: a 29-bit count
    follows, then an 8-bit-aligned retain bitmap."""
    rts_field = struct.pack(">I", (0b111 << 29) | count)
    array_length = ((count + 8) >> 3) << 3  # bits
    retain_bytes = bytes(array_length // 8)
    referred = bytes((i % 200) + 1 for i in range(count))
    stream = (
        struct.pack(">I", 0)  # segment_nr 0 -> rts_size 1
        + bytes([_flags(48)])
        + rts_field
        + retain_bytes
        + referred
        + bytes([0x01])
        + struct.pack(">I", 0)
    )
    sh = _header(stream)
    rt = sh.get_rt_segments()
    assert rt is not None
    assert len(rt) == count
    expected_len = (
        4 + 1 + 4 + len(retain_bytes) + count + 1 + 4
    )
    assert sh.get_segment_header_length() == expected_len


@pytest.mark.parametrize("bad_count", [5, 6])
def test_reserved_count_values_raise(bad_count: int) -> None:
    """§7.2.4: a 3-bit count field of 5 or 6 is reserved/illegal and must
    raise ``IntegerMaxValueException`` (the wave-1585 fix). Previously these
    were mis-parsed as the long form, reading a bogus 29-bit count."""
    stream = (
        struct.pack(">I", 0)
        + bytes([_flags(48)])
        + bytes([(bad_count & 0x7) << 5])  # count field 5 or 6, retain bits 0
        + b"\x00" * 8  # whatever follows; should never be reached
        + bytes([0x01])
        + struct.pack(">I", 0)
    )
    with pytest.raises(IntegerMaxValueException):
        _header(stream)


def test_long_form_count_field_seven_exact_count_five() -> None:
    """Regression pin: count == 5 must use the long form (count field 7 with a
    29-bit body of 5), NOT be reachable as a short-form 3-bit value."""
    rts_field = struct.pack(">I", (0b111 << 29) | 5) + bytes([0x00])
    referred = bytes([1, 2, 3, 4, 5])
    stream = (
        struct.pack(">I", 0)
        + bytes([_flags(48)])
        + rts_field
        + referred
        + bytes([0x01])
        + struct.pack(">I", 0)
    )
    sh = _header(stream)
    rt = sh.get_rt_segments()
    assert rt is not None
    assert len(rt) == 5


# ---------------------------------------------------------------------------
# §7.2.5 referred-to segment number byte size
# ---------------------------------------------------------------------------


def test_rts_size_one_byte_at_segment_nr_256() -> None:
    """Boundary: segment_nr == 256 still uses 1-byte referred numbers
    (the threshold is ``> 256``)."""
    referred = bytes([7])
    stream = (
        struct.pack(">I", 256)
        + bytes([_flags(48)])
        + _short_rts(1)
        + referred
        + bytes([0x01])
        + struct.pack(">I", 0)
    )
    sh = _header(stream)
    assert sh.get_rt_segments() == [None]
    # 4 + 1 + 1 + 1(referred) + 1 + 4 = 12
    assert sh.get_segment_header_length() == 12


def test_rts_size_two_bytes_at_segment_nr_257() -> None:
    referred = struct.pack(">H", 9)
    stream = (
        struct.pack(">I", 257)
        + bytes([_flags(48)])
        + _short_rts(1)
        + referred
        + bytes([0x01])
        + struct.pack(">I", 0)
    )
    sh = _header(stream)
    assert sh.get_rt_segments() == [None]
    # 4 + 1 + 1 + 2(referred) + 1 + 4 = 13
    assert sh.get_segment_header_length() == 13


def test_rts_size_two_bytes_at_segment_nr_65536() -> None:
    """Boundary: segment_nr == 65536 still uses 2-byte referred numbers
    (threshold is ``> 65536``)."""
    referred = struct.pack(">H", 11)
    stream = (
        struct.pack(">I", 65536)
        + bytes([_flags(48)])
        + _short_rts(1)
        + referred
        + bytes([0x01])
        + struct.pack(">I", 0)
    )
    sh = _header(stream)
    assert sh.get_rt_segments() == [None]
    assert sh.get_segment_header_length() == 13


def test_rts_size_four_bytes_at_segment_nr_65537() -> None:
    referred = struct.pack(">I", 0x0001ABCD)
    stream = (
        struct.pack(">I", 65537)
        + bytes([_flags(48)])
        + _short_rts(1)
        + referred
        + bytes([0x01])
        + struct.pack(">I", 0)
    )
    sh = _header(stream)
    assert sh.get_rt_segments() == [None]
    # 4 + 1 + 1 + 4(referred) + 1 + 4 = 15
    assert sh.get_segment_header_length() == 15


def test_rts_numbers_resolved_through_document() -> None:
    """The referred numbers themselves are honoured: with a document context
    whose page yields the segment, the numbers parsed at the chosen byte width
    drive the lookup."""

    class _Seg:
        def __init__(self, n: int) -> None:
            self.segment_nr = n

    class _Page:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def get_segment(self, n: int) -> _Seg:
            self.calls.append(n)
            return _Seg(n)

    class _Doc:
        def __init__(self, page: _Page) -> None:
            self._page = page

        def get_page(self, _pa: int) -> _Page:
            return self._page

    referred = struct.pack(">H", 4242) + struct.pack(">H", 99)
    stream = (
        struct.pack(">I", 1000)  # > 256 -> 2-byte numbers
        + bytes([_flags(48)])
        + _short_rts(2)
        + referred
        + bytes([0x05])
        + struct.pack(">I", 0)
    )
    page = _Page()
    sh = _header(stream, _Doc(page))
    assert page.calls == [4242, 99]
    assert [s.segment_nr for s in sh.get_rt_segments()] == [4242, 99]


# ---------------------------------------------------------------------------
# §7.2.7 segment data length, incl. unknown-length special case
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("data_length", [0, 1, 19, 0x7FFFFFFF])
def test_segment_data_length(data_length: int) -> None:
    stream = (
        struct.pack(">I", 0)
        + bytes([_flags(48)])
        + _short_rts(0)
        + bytes([0x01])
        + struct.pack(">I", data_length)
    )
    sh = _header(stream)
    assert sh.get_segment_data_length() == data_length


def test_segment_data_length_unknown_ffffffff() -> None:
    """0xFFFFFFFF is the unknown-length sentinel an immediate generic region
    may use; the header stores it verbatim (the region decoder interprets it)."""
    stream = (
        struct.pack(">I", 0)
        + bytes([_flags(38)])  # GenericRegion
        + _short_rts(0)
        + bytes([0x01])
        + struct.pack(">I", 0xFFFFFFFF)
    )
    sh = _header(stream)
    assert sh.get_segment_data_length() == 0xFFFFFFFF


def test_data_start_offset_sequential_set_after_header() -> None:
    """In SEQUENTIAL organisation the data start offset is the stream position
    immediately after the header bytes."""
    stream = (
        struct.pack(">I", 0)
        + bytes([_flags(48)])
        + _short_rts(0)
        + bytes([0x01])
        + struct.pack(">I", 0)
        + b"\xaa\xbb"  # data
    )
    sh = _header(stream)
    assert sh.get_segment_data_start_offset() == sh.get_segment_header_length()
    assert sh.get_segment_data_start_offset() == 11


# ---------------------------------------------------------------------------
# §7.3 segment-type dispatch constants
# ---------------------------------------------------------------------------


def test_segment_type_dispatch_map_contents() -> None:
    segment_header_module.SEGMENT_TYPE_MAP.clear()
    segment_header_module.SEGMENT_TYPE_MAP.update(
        segment_header_module._build_segment_type_map()
    )
    m = segment_header_module.SEGMENT_TYPE_MAP
    from pypdfbox.jbig2.segments.end_of_stripe import EndOfStripe
    from pypdfbox.jbig2.segments.generic_refinement_region import (
        GenericRefinementRegion,
    )
    from pypdfbox.jbig2.segments.generic_region import GenericRegion
    from pypdfbox.jbig2.segments.halftone_region import HalftoneRegion
    from pypdfbox.jbig2.segments.page_information import PageInformation
    from pypdfbox.jbig2.segments.pattern_dictionary import PatternDictionary
    from pypdfbox.jbig2.segments.symbol_dictionary import SymbolDictionary
    from pypdfbox.jbig2.segments.text_region import TextRegion

    assert m[0] is SymbolDictionary
    assert m[4] is TextRegion and m[6] is TextRegion and m[7] is TextRegion
    assert m[16] is PatternDictionary
    assert m[20] is HalftoneRegion
    assert m[36] is GenericRegion
    assert m[40] is GenericRefinementRegion
    assert m[48] is PageInformation
    assert m[50] is EndOfStripe


def test_unknown_segment_type_has_no_dispatch() -> None:
    """A type with no SegmentData mapping (e.g. 62) raises on get_segment_data."""
    stream = (
        struct.pack(">I", 0)
        + bytes([_flags(62)])
        + _short_rts(0)
        + bytes([0x01])
        + struct.pack(">I", 0)
    )
    sh = _header(stream)
    assert sh.get_segment_type() == 62
    segment_header_module.SEGMENT_TYPE_MAP.clear()
    segment_header_module.SEGMENT_TYPE_MAP.update(
        segment_header_module._build_segment_type_map()
    )
    with pytest.raises(ValueError, match="No segment class for type 62"):
        sh.get_segment_data()


# ---------------------------------------------------------------------------
# combined / multi-field interactions
# ---------------------------------------------------------------------------


def test_combined_long_page_assoc_and_long_rts_count() -> None:
    """Long page-association (4 bytes) combined with a long-form RTS count of
    6 and 1-byte referred numbers."""
    count = 6
    rts_field = struct.pack(">I", (0b111 << 29) | count)
    array_length = ((count + 8) >> 3) << 3
    retain_bytes = bytes(array_length // 8)
    referred = bytes(range(1, count + 1))
    stream = (
        struct.pack(">I", 0)
        + bytes([_flags(38, page_assoc_4=1, retain=1)])
        + rts_field
        + retain_bytes
        + referred
        + struct.pack(">I", 0xDEAD)
        + struct.pack(">I", 12)
    )
    sh = _header(stream)
    assert sh.get_retain_flag() == 1
    assert sh.get_page_association() == 0xDEAD
    assert sh.get_segment_type() == 38
    assert sh.get_segment_data_length() == 12
    assert len(sh.get_rt_segments()) == count
    expected_len = 4 + 1 + 4 + len(retain_bytes) + count + 4 + 4
    assert sh.get_segment_header_length() == expected_len
