"""Wave 1273: parity coverage for ``CCITTFaxFilter.invert_bitmap`` and
``CCITTFaxFilter.read_from_decoder_stream`` helpers (promoted from the
upstream ``private``/package-private statics ``invertBitmap`` /
``readFromDecoderStream``)."""

from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

from pypdfbox.filter.ccitt_fax_filter import CCITTFaxFilter


def test_invert_bitmap_flips_every_bit_in_place() -> None:
    buf = bytearray(b"\x00\xff\xaa\x55\x01\xfe")
    CCITTFaxFilter.invert_bitmap(buf)
    assert buf == bytearray(b"\xff\x00\x55\xaa\xfe\x01")


def test_invert_bitmap_is_involutive() -> None:
    original = bytes(range(256))
    buf = bytearray(original)
    CCITTFaxFilter.invert_bitmap(buf)
    CCITTFaxFilter.invert_bitmap(buf)
    assert bytes(buf) == original


def test_invert_bitmap_empty_buffer_is_noop() -> None:
    buf = bytearray()
    CCITTFaxFilter.invert_bitmap(buf)
    assert buf == bytearray()


def test_invert_bitmap_mutates_caller_buffer() -> None:
    buf = bytearray(b"\xa5\xa5")
    # Pass-by-reference semantics: caller observes the mutation.
    CCITTFaxFilter.invert_bitmap(buf)
    assert bytes(buf) == b"\x5a\x5a"


def test_read_from_decoder_stream_fills_buffer() -> None:
    src = BytesIO(b"\x01\x02\x03\x04\x05\x06\x07\x08")
    result = bytearray(8)
    CCITTFaxFilter.read_from_decoder_stream(src, result)
    assert bytes(result) == b"\x01\x02\x03\x04\x05\x06\x07\x08"


def test_read_from_decoder_stream_stops_on_eof() -> None:
    # Source has fewer bytes than the buffer; the unread tail stays
    # at its zero-initialised value, matching the upstream contract
    # of writing only what the decoder yielded.
    src = BytesIO(b"\xab\xcd")
    result = bytearray(b"\x99\x99\x99\x99")
    CCITTFaxFilter.read_from_decoder_stream(src, result)
    assert bytes(result) == b"\xab\xcd\x99\x99"


def test_read_from_decoder_stream_tolerates_short_reads() -> None:
    """The upstream loop keeps calling ``read`` until the buffer is
    full; mirror that by exercising a stream that hands back one byte
    at a time."""

    class OneByteStream:
        def __init__(self, data: bytes) -> None:
            self._data = data
            self._pos = 0

        def read(self, size: int = -1) -> bytes:
            if self._pos >= len(self._data):
                return b""
            chunk = self._data[self._pos : self._pos + 1]
            self._pos += 1
            return chunk

    src: BinaryIO = OneByteStream(b"abcdef")  # type: ignore[assignment]
    result = bytearray(6)
    CCITTFaxFilter.read_from_decoder_stream(src, result)
    assert bytes(result) == b"abcdef"


def test_read_from_decoder_stream_empty_target_is_noop() -> None:
    src = BytesIO(b"ignored")
    result = bytearray()
    CCITTFaxFilter.read_from_decoder_stream(src, result)
    assert result == bytearray()
    # Underlying stream not consumed.
    assert src.tell() == 0


def test_helpers_callable_on_instance() -> None:
    # Static methods must also resolve via instance access — matches
    # the upstream Java static-method semantics.
    filt = CCITTFaxFilter()
    buf = bytearray(b"\x00")
    filt.invert_bitmap(buf)
    assert bytes(buf) == b"\xff"

    src = BytesIO(b"x")
    out = bytearray(1)
    filt.read_from_decoder_stream(src, out)
    assert bytes(out) == b"x"
