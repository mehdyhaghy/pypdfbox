from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.data_input import DataInput
from pypdfbox.fontbox.cff.data_input_random_access_read import (
    DataInputRandomAccessRead,
)
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer


def _data() -> bytes:
    return bytes([0, 0xFF, 2, 0xFD, 4, 0xFB, 6, 0xF9, 8, 0xF7])


def _make(buf: bytes) -> DataInputRandomAccessRead:
    return DataInputRandomAccessRead(RandomAccessReadBuffer(buf))


def test_is_data_input():
    assert isinstance(_make(b""), DataInput)


def test_basics():
    di = _make(_data())
    assert di.length() == 10
    assert di.has_remaining() is True
    with pytest.raises(OSError):
        di.set_position(-1)
    length = di.length()
    with pytest.raises(OSError):
        di.set_position(length)


def test_read_byte_signed():
    di = _make(_data())
    assert di.read_byte() == 0
    assert di.read_byte() == -1
    di.set_position(6)
    assert di.read_byte() == 6
    assert di.read_byte() == -7
    di.set_position(di.length() - 1)
    assert di.read_byte() == -9
    with pytest.raises(OSError):
        di.read_byte()


def test_read_unsigned_byte():
    di = _make(_data())
    assert di.read_unsigned_byte() == 0
    assert di.read_unsigned_byte() == 255
    di.set_position(6)
    assert di.read_unsigned_byte() == 6
    assert di.read_unsigned_byte() == 249
    di.set_position(di.length() - 1)
    assert di.read_unsigned_byte() == 247
    with pytest.raises(OSError):
        di.read_unsigned_byte()


def test_peek_unsigned_byte_zero_offset():
    di = _make(_data())
    assert di.peek_unsigned_byte(0) == 0
    assert di.get_position() == 0


def test_peek_unsigned_byte_with_offset():
    di = _make(_data())
    assert di.peek_unsigned_byte(5) == 251
    # Position is restored.
    assert di.get_position() == 0


def test_peek_unsigned_byte_negative_raises():
    di = _make(_data())
    with pytest.raises(OSError):
        di.peek_unsigned_byte(-1)


def test_peek_unsigned_byte_past_end_raises():
    di = _make(_data())
    with pytest.raises(OSError):
        di.peek_unsigned_byte(di.length())


def test_read_short():
    di = _make(bytes([0x00, 0x0F, 0xAA, 0x00, 0xFE, 0xFF]))
    assert di.read_short() == 0x000F
    assert di.read_short() == -22016
    assert di.read_short() == -257
    with pytest.raises(OSError):
        di.read_short()


def test_read_unsigned_short():
    di = _make(bytes([0x00, 0x0F, 0xAA, 0x00, 0xFE, 0xFF]))
    assert di.read_unsigned_short() == 0x000F
    assert di.read_unsigned_short() == 0xAA00
    assert di.read_unsigned_short() == 0xFEFF
    with pytest.raises(OSError):
        di.read_unsigned_short()
    di2 = _make(bytes([0x00]))
    with pytest.raises(OSError):
        di2.read_unsigned_short()


def test_read_int_signed():
    di = _make(bytes([0x00, 0x0F, 0xAA, 0x00, 0xFE, 0xFF, 0x30, 0x50]))
    assert di.read_int() == 0x000FAA00
    assert di.read_int() == 0xFEFF3050 - 0x1_0000_0000
    with pytest.raises(OSError):
        di.read_int()
    di2 = _make(bytes([0x00, 0x0F, 0xAA]))
    with pytest.raises(OSError):
        di2.read_int()


def test_read_bytes_basic_and_errors():
    di = _make(_data())
    with pytest.raises(OSError):
        di.read_bytes(20)
    assert di.read_bytes(1) == bytes([0])
    assert di.read_bytes(3) == bytes([0xFF, 2, 0xFD])
    di.set_position(6)
    assert di.read_bytes(3) == bytes([6, 0xF9, 8])
    with pytest.raises(OSError):
        di.read_bytes(-1)
    with pytest.raises(OSError):
        di.read_bytes(5)


def test_read_offset_big_endian():
    di = _make(bytes([0x12, 0x34, 0x56, 0x78]))
    assert di.read_offset(1) == 0x12
    di.set_position(0)
    assert di.read_offset(2) == 0x1234
    di.set_position(0)
    assert di.read_offset(3) == 0x123456
    di.set_position(0)
    assert di.read_offset(4) == 0x12345678


def test_get_position_tracks_random_access():
    di = _make(_data())
    di.read_bytes(4)
    assert di.get_position() == 4
    di.set_position(7)
    assert di.get_position() == 7


def test_has_remaining_after_full_read():
    di = _make(b"abc")
    di.read_bytes(3)
    assert di.has_remaining() is False
