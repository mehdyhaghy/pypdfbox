"""Wave 1510 coverage round-out for ``SegmentHeader`` (ISO/IEC 14492 §7.2).

Drives the header-parse branches not exercised by ``test_segment_header.py``:

* §7.2.4 long-format referred-to-segment count (count field == 7 -> read a
  29-bit count + retain bitmap);
* §7.2.5 wider referred-to-segment numbers when ``segment_nr > 256`` (2-byte
  rts size);
* §7.2.6 the global-segment fallback when the page association resolves to no
  page but a document context is present;
* the ``get_segment_data`` instantiation-failure wrap (RuntimeError chaining);
* the ``__str__`` referred-to-segments branch.

Every crafted byte stream is hand-computed from the §7.2 bit layout, matching
the conventions in ``test_segment_header.py``.
"""

from __future__ import annotations

import struct

import pytest

import pypdfbox.jbig2.segment_header as segment_header_module
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segment_data import SegmentData
from pypdfbox.jbig2.segment_header import SEQUENTIAL, SegmentHeader


def _header(stream: bytes, document: object = None) -> SegmentHeader:
    sis = SubInputStream(ImageInputStream(stream), 0, len(stream))
    return SegmentHeader(document, sis, 0, SEQUENTIAL)


def test_long_format_referred_to_count_over_four() -> None:
    """§7.2.4 long format: a 3-bit count field of ``111`` (7) signals that the
    real count follows in the next 29 bits, then an 8-bit-aligned retain bitmap.

    Layout (count == 5): segment_nr(4) + flags(1) + RTS field(5) +
    five 1-byte referred numbers + page(1) + data_length(4).
    The RTS field is ``111`` ++ 29-bit ``5`` ++ ``array_length`` retain bits,
    where ``array_length = ((5 + 8) >> 3) << 3 == 8`` -> one extra byte.
    """
    rts_field = struct.pack(">I", (0b111 << 29) | 5) + bytes([0x00])
    referred = bytes([1, 2, 3, 4, 5])
    stream = (
        struct.pack(">I", 0)  # segment_nr 0 -> rts_size 1
        + bytes([0x00])  # flags: retain 0, pageAssocFieldSize 0, type 0
        + rts_field
        + referred
        + bytes([0x01])  # page association 1
        + struct.pack(">I", 0)  # data length 0
    )
    sh = _header(stream)

    assert sh.get_segment_nr() == 0
    rt = sh.get_rt_segments()
    assert rt is not None
    assert len(rt) == 5
    # document is None -> referred headers stay unresolved, but the 5 one-byte
    # numbers were consumed to keep the bit position correct.
    assert rt == [None, None, None, None, None]
    # 4 (nr) + 1 (flags) + 5 (rts field) + 5 (referred) + 1 (page) + 4 (len) = 20
    assert sh.get_segment_header_length() == 20


def test_referred_to_numbers_two_byte_size_when_segment_nr_over_256() -> None:
    """§7.2.5: referred-to segment numbers are 2 bytes wide once the segment
    number exceeds 256 (``rts_size`` steps 1 -> 2)."""
    referred = struct.pack(">H", 10) + struct.pack(">H", 20)
    stream = (
        struct.pack(">I", 300)  # segment_nr 300 (> 256) -> rts_size 2
        + bytes([0x00])  # flags
        + bytes([0x40])  # RTS count = 2 (short format)
        + referred
        + bytes([0x01])  # page association 1
        + struct.pack(">I", 0)  # data length 0
    )
    sh = _header(stream)

    assert sh.get_segment_nr() == 300
    assert sh.get_rt_segments() == [None, None]
    # 4 (nr) + 1 (flags) + 1 (rts) + 4 (referred, 2x2) + 1 (page) + 4 (len) = 15
    assert sh.get_segment_header_length() == 15


def test_referred_to_numbers_four_byte_size_when_segment_nr_over_65536() -> None:
    """§7.2.5: referred-to segment numbers widen to 4 bytes once the segment
    number exceeds 65536 (``rts_size`` steps 2 -> 4)."""
    referred = struct.pack(">I", 12345)
    stream = (
        struct.pack(">I", 70000)  # segment_nr 70000 (> 65536) -> rts_size 4
        + bytes([0x00])  # flags
        + bytes([0x20])  # RTS count = 1 (short format)
        + referred
        + bytes([0x01])  # page association 1
        + struct.pack(">I", 0)  # data length 0
    )
    sh = _header(stream)

    assert sh.get_segment_nr() == 70000
    assert sh.get_rt_segments() == [None]
    # 4 (nr) + 1 (flags) + 1 (rts) + 4 (referred, 1x4) + 1 (page) + 4 (len) = 15
    assert sh.get_segment_header_length() == 15


def test_set_segment_data_start_offset_setter() -> None:
    """``set_segment_data_start_offset`` overrides the parsed offset (used by
    the RANDOM-organisation second pass once all headers are allocated)."""
    stream = (
        struct.pack(">I", 0)
        + bytes([48])  # PageInformation
        + bytes([0x00])
        + bytes([0x01])
        + struct.pack(">I", 0)
    )
    sh = _header(stream)
    sh.set_segment_data_start_offset(4242)
    assert sh.get_segment_data_start_offset() == 4242


def test_referred_segments_resolve_via_global_when_page_absent() -> None:
    """§7.2.6: with a document context whose ``get_page`` yields no page, each
    referred-to segment number resolves through ``get_global_segment``.

    Also exercises the ``__str__`` referred-to-segments branch (non-None
    ``rt_segments``)."""

    class _GlobalSegment:
        def __init__(self, number: int) -> None:
            self.segment_nr = number

    class _Document:
        def __init__(self) -> None:
            self.global_calls: list[int] = []

        def get_page(self, _page_association: int) -> None:
            return None

        def get_global_segment(self, number: int) -> _GlobalSegment:
            self.global_calls.append(number)
            return _GlobalSegment(number)

    referred = bytes([10, 20])
    stream = (
        struct.pack(">I", 5)  # small segment_nr -> rts_size 1
        + bytes([0x00])  # flags
        + bytes([0x40])  # RTS count = 2 (short format)
        + referred
        + bytes([0x01])  # page association 1
        + struct.pack(">I", 0)
    )
    document = _Document()
    sh = _header(stream, document)

    assert document.global_calls == [10, 20]
    resolved = sh.get_rt_segments()
    assert resolved is not None
    assert [s.segment_nr for s in resolved] == [10, 20]

    rendered = str(sh)
    assert "Referred-to segments: 10 20 " in rendered


def test_referred_segments_resolve_via_page_when_present() -> None:
    """§7.2.6: when the page association resolves to a real page, each
    referred-to segment number is resolved through ``page.get_segment``."""

    class _PageSegment:
        def __init__(self, number: int) -> None:
            self.segment_nr = number

    class _Page:
        def __init__(self) -> None:
            self.segment_calls: list[int] = []

        def get_segment(self, number: int) -> _PageSegment:
            self.segment_calls.append(number)
            return _PageSegment(number)

    class _Document:
        def __init__(self, page: _Page) -> None:
            self._page = page

        def get_page(self, _page_association: int) -> _Page:
            return self._page

    referred = bytes([10, 20])
    stream = (
        struct.pack(">I", 5)
        + bytes([0x00])  # flags
        + bytes([0x40])  # RTS count = 2 (short format)
        + referred
        + bytes([0x01])  # page association 1
        + struct.pack(">I", 0)
    )
    page = _Page()
    sh = _header(stream, _Document(page))

    assert page.segment_calls == [10, 20]
    resolved = sh.get_rt_segments()
    assert resolved is not None
    assert [s.segment_nr for s in resolved] == [10, 20]


def test_get_segment_data_wraps_instantiation_failure() -> None:
    """When the dispatched segment class fails during ``init`` the original
    exception is re-raised wrapped in a ``RuntimeError`` (chained), matching
    upstream's catch-all in ``getSegmentData``."""

    class _BoomSegment(SegmentData):
        def init(self, _header: SegmentHeader, _sis: SubInputStream) -> None:
            raise ValueError("boom in init")

    stream = (
        struct.pack(">I", 2)
        + bytes([50])  # type 50 (EndOfStripe) -> overridden in the map below
        + bytes([0x00])
        + bytes([0x01])
        + struct.pack(">I", 4)
        + struct.pack(">I", 1)
    )
    sh = _header(stream)

    # Ensure the dispatch cache is populated, then override type 50.
    segment_header_module.SEGMENT_TYPE_MAP.clear()
    segment_header_module.SEGMENT_TYPE_MAP.update(
        segment_header_module._build_segment_type_map()
    )
    original = segment_header_module.SEGMENT_TYPE_MAP[50]
    segment_header_module.SEGMENT_TYPE_MAP[50] = _BoomSegment
    try:
        with pytest.raises(RuntimeError, match="Can't instantiate segment class"):
            sh.get_segment_data()
    finally:
        segment_header_module.SEGMENT_TYPE_MAP[50] = original
