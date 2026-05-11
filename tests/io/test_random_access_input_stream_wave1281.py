"""Wave 1281: RandomAccessInputStream adapter port."""

from __future__ import annotations

from pypdfbox.io import RandomAccessInputStream, RandomAccessReadBuffer


def test_read_byte_advances_position() -> None:
    raw = RandomAccessReadBuffer(b"hello")
    stream = RandomAccessInputStream(raw)
    assert stream.read(2) == b"he"
    assert stream.tell() == 2


def test_read_to_eof_returns_remaining() -> None:
    raw = RandomAccessReadBuffer(b"abc")
    stream = RandomAccessInputStream(raw)
    assert stream.read() == b"abc"
    # EOF — further reads should yield empty.
    assert stream.read() == b""


def test_available_decreases_with_reads() -> None:
    raw = RandomAccessReadBuffer(b"abcdef")
    stream = RandomAccessInputStream(raw)
    assert stream.available() == 6
    stream.read(2)
    assert stream.available() == 4


def test_skip_advances_position() -> None:
    raw = RandomAccessReadBuffer(b"01234567")
    stream = RandomAccessInputStream(raw)
    assert stream.skip(3) == 3
    assert stream.read(2) == b"34"


def test_skip_zero_returns_zero() -> None:
    raw = RandomAccessReadBuffer(b"abc")
    stream = RandomAccessInputStream(raw)
    assert stream.skip(0) == 0


def test_restore_position_re_seeks_source() -> None:
    raw = RandomAccessReadBuffer(b"abcdef")
    stream = RandomAccessInputStream(raw)
    stream.read(2)  # advance to 2
    raw.seek(5)  # external interference
    stream.restore_position()
    assert raw.get_position() == 2
