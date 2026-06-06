"""Wave 1495 — behaviour-anchored coverage for ``ASCIIHexDecode.decode``'s
end-of-data edge branches that the existing ``test_ascii_hex_decode`` suite
doesn't reach:

* a whitespace-only tail after a complete pair (the inner ``first = -1`` break);
* an odd trailing nibble at EOF with **no** ``>`` marker (the ``i >= n`` pad);
* a ``>`` marker appearing as the *second* nibble of a pair (``second == _EOD``);
* a decode sink that exposes no ``flush`` attribute.

All four mirror upstream ``org.apache.pdfbox.filter.ASCIIHexFilter.decode``.
"""

from __future__ import annotations

import io

from pypdfbox.filter.ascii_hex_decode import ASCIIHexDecode


def _decode(encoded: bytes) -> bytes:
    out = io.BytesIO()
    ASCIIHexDecode().decode(io.BytesIO(encoded), out)
    return out.getvalue()


def test_trailing_whitespace_after_complete_pair_stops_cleanly() -> None:
    # "41" decodes to 'A'; the trailing spaces are consumed as the leading
    # whitespace of the next (nonexistent) pair, hitting the EOF break.
    assert _decode(b"41   ") == b"A"


def test_trailing_whitespace_only_decodes_to_empty() -> None:
    assert _decode(b"   \t\r\n") == b""


def test_odd_trailing_nibble_at_eof_without_marker_pads_low_zero() -> None:
    # No ``>`` marker: the lone 'F' hits the ``i >= n`` branch and pads the
    # low nibble with 0 -> 0xF0.
    assert _decode(b"F") == b"\xf0"


def test_odd_trailing_nibble_after_full_byte_without_marker() -> None:
    # "41" -> 'A', then 'C' alone -> 0xC0.
    assert _decode(b"41C") == b"A\xc0"


def test_eod_marker_as_second_nibble_pads_low_zero() -> None:
    # '4' then '>' as the second nibble: the high nibble is written with a
    # low of 0 (0x40) and decoding stops at the marker.
    assert _decode(b"4>") == b"\x40"


def test_eod_marker_as_second_nibble_after_full_byte() -> None:
    assert _decode(b"414>") == b"A\x40"


def test_decode_sink_without_flush_attribute_is_tolerated() -> None:
    class _NoFlushSink:
        def __init__(self) -> None:
            self.data = bytearray()

        def write(self, b: bytes) -> int:
            self.data.extend(b)
            return len(b)

    sink = _NoFlushSink()
    result = ASCIIHexDecode().decode(io.BytesIO(b"4142>"), sink)
    assert bytes(sink.data) == b"AB"
    assert result.bytes_written == 2
