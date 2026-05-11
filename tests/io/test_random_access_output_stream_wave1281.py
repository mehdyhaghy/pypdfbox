"""Wave 1281: RandomAccessOutputStream adapter port."""

from __future__ import annotations

from pypdfbox.io import RandomAccessOutputStream, RandomAccessReadWriteBuffer


def test_write_int_byte() -> None:
    buf = RandomAccessReadWriteBuffer()
    stream = RandomAccessOutputStream(buf)
    stream.write(0x41)
    buf.seek(0)
    assert buf.read() == ord("A")


def test_write_bytes() -> None:
    buf = RandomAccessReadWriteBuffer()
    stream = RandomAccessOutputStream(buf)
    stream.write(b"hello")
    buf.seek(0)
    out = bytearray(5)
    buf.read_into(out)
    assert bytes(out) == b"hello"


def test_write_with_offset_helper() -> None:
    buf = RandomAccessReadWriteBuffer()
    stream = RandomAccessOutputStream(buf)
    stream.write_with_offset(b"hello world", 6, 5)
    buf.seek(0)
    out = bytearray(5)
    buf.read_into(out)
    assert bytes(out) == b"world"
