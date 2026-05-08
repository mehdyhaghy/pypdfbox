from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.fontbox.ttf.ttf_data_stream import (
    MemoryTTFDataStream,
    RandomAccessReadDataStream,
    TTFDataStream,
)
from pypdfbox.io import RandomAccessReadBuffer


class _IntermittentEOFStream(TTFDataStream):
    """Test stream that can return EOF before later byte values."""

    def __init__(self, reads: list[int]) -> None:
        self._reads = reads
        self._pos = 0

    def read(self) -> int:
        if self._pos >= len(self._reads):
            return -1
        value = self._reads[self._pos]
        self._pos += 1
        return value

    def read_long(self) -> int:
        raise NotImplementedError

    def read_into(self, buf: bytearray, offset: int, length: int) -> int:
        raise NotImplementedError

    def seek(self, pos: int) -> None:
        self._pos = pos

    def get_current_position(self) -> int:
        return self._pos

    def get_original_data(self) -> bytes:
        return b""

    def get_original_data_size(self) -> int:
        return 0

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# MemoryTTFDataStream
# ---------------------------------------------------------------------------


def test_memory_ttf_data_stream_initial_state() -> None:
    s = MemoryTTFDataStream(b"abcde")
    assert s.get_current_position() == 0
    assert s.get_original_data() == b"abcde"
    assert s.get_original_data_size() == 5


def test_memory_ttf_data_stream_accepts_bytearray() -> None:
    s = MemoryTTFDataStream(bytearray(b"\x01\x02\x03"))
    assert s.get_original_data() == b"\x01\x02\x03"
    assert isinstance(s.get_original_data(), bytes)


def test_memory_ttf_data_stream_read_returns_bytes_then_eof() -> None:
    s = MemoryTTFDataStream(b"AB")
    assert s.read() == 0x41
    assert s.read() == 0x42
    assert s.read() == -1  # EOF


def test_memory_ttf_data_stream_read_into_partial_then_eof() -> None:
    s = MemoryTTFDataStream(b"abcdef")
    buf = bytearray(4)
    n = s.read_into(buf, 0, 4)
    assert n == 4
    assert bytes(buf) == b"abcd"
    n = s.read_into(buf, 0, 4)
    assert n == 2
    assert bytes(buf[:2]) == b"ef"
    n = s.read_into(buf, 0, 4)
    assert n == -1


def test_memory_ttf_data_stream_read_into_with_offset() -> None:
    s = MemoryTTFDataStream(b"0123456789")
    buf = bytearray(b"....##....")
    n = s.read_into(buf, 4, 2)
    assert n == 2
    assert bytes(buf) == b"....01...."
    assert s.get_current_position() == 2


def test_wave323_memory_read_into_zero_length_is_noop_at_eof() -> None:
    s = MemoryTTFDataStream(b"")
    buf = bytearray(b"abc")

    assert s.read_into(buf, 1, 0) == 0
    assert bytes(buf) == b"abc"
    assert s.get_current_position() == 0


def test_wave323_memory_read_into_rejects_invalid_range() -> None:
    s = MemoryTTFDataStream(b"abc")
    buf = bytearray(2)

    with pytest.raises(IndexError, match="out of bounds"):
        s.read_into(buf, 2, 1)

    assert s.get_current_position() == 0


def test_memory_ttf_data_stream_seek_and_position() -> None:
    s = MemoryTTFDataStream(b"abcdef")
    s.seek(3)
    assert s.get_current_position() == 3
    assert s.read() == ord("d")
    s.seek(0)
    assert s.read() == ord("a")


def test_memory_ttf_data_stream_seek_negative_raises() -> None:
    s = MemoryTTFDataStream(b"abc")
    with pytest.raises(OSError):
        s.seek(-1)


def test_memory_ttf_data_stream_seek_past_eof_then_read_returns_eof() -> None:
    s = MemoryTTFDataStream(b"abc")
    s.seek(100)
    assert s.read() == -1


def test_memory_ttf_data_stream_close_is_idempotent() -> None:
    s = MemoryTTFDataStream(b"x")
    s.close()
    s.close()  # second call must not raise


def test_memory_ttf_data_stream_read_long_signed() -> None:
    # 0xFFFFFFFFFFFFFFFF == -1 signed
    s = MemoryTTFDataStream(b"\xff" * 8)
    assert s.read_long() == -1
    s2 = MemoryTTFDataStream(b"\x00\x00\x00\x00\x00\x00\x00\x01")
    assert s2.read_long() == 1
    # Largest positive signed 64
    s3 = MemoryTTFDataStream(b"\x7f\xff\xff\xff\xff\xff\xff\xff")
    assert s3.read_long() == (1 << 63) - 1


def test_memory_ttf_data_stream_read_long_short_raises() -> None:
    s = MemoryTTFDataStream(b"\x00\x00\x00\x00")  # only 4 bytes
    with pytest.raises(EOFError):
        s.read_long()


# ---------------------------------------------------------------------------
# RandomAccessReadDataStream  (wraps a RandomAccessReadBuffer)
# ---------------------------------------------------------------------------


def _ra(data: bytes) -> RandomAccessReadDataStream:
    return RandomAccessReadDataStream(RandomAccessReadBuffer(data))


def test_random_access_read_data_stream_initial_state() -> None:
    s = _ra(b"hello")
    assert s.get_current_position() == 0
    assert s.get_original_data() == b"hello"
    assert s.get_original_data_size() == 5


def test_random_access_read_data_stream_read_then_eof() -> None:
    s = _ra(b"AB")
    assert s.read() == ord("A")
    assert s.read() == ord("B")
    assert s.read() == -1


def test_random_access_read_data_stream_read_into_partial_then_eof() -> None:
    s = _ra(b"abcdef")
    buf = bytearray(4)
    assert s.read_into(buf, 0, 4) == 4
    assert bytes(buf) == b"abcd"
    assert s.read_into(buf, 0, 4) == 2
    assert bytes(buf[:2]) == b"ef"
    assert s.read_into(buf, 0, 4) == -1


def test_wave323_random_access_read_into_zero_length_is_noop_at_eof() -> None:
    s = _ra(b"")
    buf = bytearray(b"abc")

    assert s.read_into(buf, 1, 0) == 0
    assert bytes(buf) == b"abc"
    assert s.get_current_position() == 0


def test_wave323_random_access_read_into_rejects_invalid_range() -> None:
    s = _ra(b"abc")
    buf = bytearray(2)

    with pytest.raises(IndexError, match="out of bounds"):
        s.read_into(buf, 2, 1)

    assert s.get_current_position() == 0


def test_random_access_read_data_stream_seek_and_position() -> None:
    s = _ra(b"abcdef")
    s.seek(2)
    assert s.get_current_position() == 2
    assert s.read() == ord("c")


def test_random_access_read_data_stream_seek_negative_raises() -> None:
    s = _ra(b"x")
    with pytest.raises(OSError):
        s.seek(-1)


def test_random_access_read_data_stream_close_idempotent() -> None:
    s = _ra(b"x")
    s.close()
    s.close()


def test_random_access_read_data_stream_read_long() -> None:
    s = _ra(b"\x00\x00\x00\x00\x00\x00\x00\x2a")
    assert s.read_long() == 42


# ---------------------------------------------------------------------------
# Helper readers (exercised through MemoryTTFDataStream — base-class behavior)
# ---------------------------------------------------------------------------


def test_read_signed_byte_positive_and_negative() -> None:
    s = MemoryTTFDataStream(b"\x01\xff\x80\x7f")
    assert s.read_signed_byte() == 1
    assert s.read_signed_byte() == -1
    assert s.read_signed_byte() == -128
    assert s.read_signed_byte() == 127


def test_read_signed_byte_eof() -> None:
    s = MemoryTTFDataStream(b"")
    with pytest.raises(EOFError):
        s.read_signed_byte()


def test_read_unsigned_byte_range_and_eof() -> None:
    s = MemoryTTFDataStream(b"\x00\xff")
    assert s.read_unsigned_byte() == 0
    assert s.read_unsigned_byte() == 255
    with pytest.raises(EOFError):
        s.read_unsigned_byte()


def test_read_unsigned_short_big_endian() -> None:
    s = MemoryTTFDataStream(b"\x01\x02\xff\xff")
    assert s.read_unsigned_short() == 0x0102
    assert s.read_unsigned_short() == 0xFFFF


def test_read_unsigned_short_eof() -> None:
    s = MemoryTTFDataStream(b"\x01")  # only one byte
    with pytest.raises(EOFError):
        s.read_unsigned_short()


def test_read_signed_short_negative_boundary() -> None:
    # 0x8000 -> -32768
    s = MemoryTTFDataStream(b"\x80\x00\x7f\xff\xff\xff")
    assert s.read_signed_short() == -32768
    assert s.read_signed_short() == 32767
    assert s.read_signed_short() == -1


def test_read_unsigned_int_full_range() -> None:
    s = MemoryTTFDataStream(b"\x00\x00\x00\x01\xff\xff\xff\xff")
    assert s.read_unsigned_int() == 1
    assert s.read_unsigned_int() == 0xFFFFFFFF


def test_read_unsigned_int_eof() -> None:
    s = MemoryTTFDataStream(b"\x00\x00\x00")  # only 3 bytes
    with pytest.raises(EOFError):
        s.read_unsigned_int()


def test_read_unsigned_int_treats_any_negative_byte_as_eof() -> None:
    s = _IntermittentEOFStream([-1, 0, 0, 0])
    with pytest.raises(EOFError):
        s.read_unsigned_int()


def test_read_32_fixed_one_point_zero() -> None:
    s = MemoryTTFDataStream(b"\x00\x01\x00\x00")  # 1.0
    assert s.read_32_fixed() == pytest.approx(1.0)


def test_read_32_fixed_fractional() -> None:
    # 0.5 == 0x0000_8000
    s = MemoryTTFDataStream(b"\x00\x00\x80\x00")
    assert s.read_32_fixed() == pytest.approx(0.5)


def test_read_32_fixed_negative() -> None:
    # -1.0 == 0xFFFF_0000
    s = MemoryTTFDataStream(b"\xff\xff\x00\x00")
    assert s.read_32_fixed() == pytest.approx(-1.0)


def test_read_tag_ascii_four_bytes() -> None:
    s = MemoryTTFDataStream(b"cmap")
    assert s.read_tag() == "cmap"


def test_read_tag_eof_raises() -> None:
    s = MemoryTTFDataStream(b"abc")  # only 3 bytes
    with pytest.raises(OSError):
        s.read_tag()


def test_read_string_default_encoding_iso_8859_1() -> None:
    s = MemoryTTFDataStream(b"\xe9\xe8")  # é è in ISO-8859-1
    assert s.read_string(2) == "éè"


def test_read_string_explicit_encoding() -> None:
    s = MemoryTTFDataStream("héllo".encode("utf-8"))
    assert s.read_string(6, encoding="utf-8") == "héllo"


def test_read_bytes_returns_exact_length() -> None:
    s = MemoryTTFDataStream(b"abcdef")
    assert s.read_bytes(3) == b"abc"
    assert s.get_current_position() == 3


def test_read_bytes_short_raises() -> None:
    s = MemoryTTFDataStream(b"ab")
    with pytest.raises(OSError):
        s.read_bytes(5)


def test_read_unsigned_byte_array() -> None:
    s = MemoryTTFDataStream(b"\x00\x10\x20\x30")
    assert s.read_unsigned_byte_array(4) == [0, 16, 32, 48]


def test_read_unsigned_short_array() -> None:
    s = MemoryTTFDataStream(b"\x00\x01\x00\x02\x00\x03")
    assert s.read_unsigned_short_array(3) == [1, 2, 3]


def test_read_long_date_time_epoch() -> None:
    # 0 seconds since 1904-01-01 00:00:00 UTC
    s = MemoryTTFDataStream(b"\x00" * 8)
    assert s.read_long_date_time() == datetime(1904, 1, 1, tzinfo=UTC)


def test_read_long_date_time_one_day() -> None:
    s = MemoryTTFDataStream((86400).to_bytes(8, "big", signed=True))
    assert s.read_long_date_time() == datetime(1904, 1, 2, tzinfo=UTC)


def test_helpers_via_random_access_read_data_stream() -> None:
    # Smoke-test that helpers also work through the RandomAccessRead-backed
    # subclass (since they live on the base class).
    s = _ra(b"\x01\x02\x03\x04")
    assert s.read_unsigned_short() == 0x0102
    assert s.read_unsigned_short() == 0x0304


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


def test_ttf_data_stream_is_abstract() -> None:
    with pytest.raises(TypeError):
        TTFDataStream()  # type: ignore[abstract]
