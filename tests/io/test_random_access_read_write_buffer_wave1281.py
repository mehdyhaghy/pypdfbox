"""Wave 1281: RandomAccessReadWriteBuffer port."""

from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadWriteBuffer


def test_empty_buffer_starts_zero_length() -> None:
    buf = RandomAccessReadWriteBuffer()
    assert buf.length() == 0


def test_write_then_read_roundtrip() -> None:
    buf = RandomAccessReadWriteBuffer()
    buf.write(b"hello")
    assert buf.length() == 5
    buf.seek(0)
    out = bytearray(5)
    buf.read_into(out)
    assert bytes(out) == b"hello"


def test_clear_resets_buffer() -> None:
    buf = RandomAccessReadWriteBuffer()
    buf.write(b"abc")
    buf.clear()
    assert buf.length() == 0


def test_write_int_byte() -> None:
    buf = RandomAccessReadWriteBuffer()
    buf.write(0x7F)
    buf.seek(0)
    assert buf.read() == 0x7F


def test_write_int_byte_validates_range() -> None:
    buf = RandomAccessReadWriteBuffer()
    with pytest.raises(ValueError):
        buf.write(256)


def test_write_bytes_offset_length() -> None:
    buf = RandomAccessReadWriteBuffer()
    buf.write_bytes(b"hello world", 6, 5)
    assert buf.length() == 5
    buf.seek(0)
    out = bytearray(5)
    buf.read_into(out)
    assert bytes(out) == b"world"
