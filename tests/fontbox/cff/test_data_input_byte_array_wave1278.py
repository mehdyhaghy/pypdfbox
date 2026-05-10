from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.data_input import DataInput
from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray


def _data() -> bytes:
    # Hand-written counterpart of the upstream test fixture
    # ``new byte[] { 0, -1, 2, -3, 4, -5, 6, -7, 8, -9 }``.
    return bytes([0, 0xFF, 2, 0xFD, 4, 0xFB, 6, 0xF9, 8, 0xF7])


def test_is_data_input():
    assert isinstance(DataInputByteArray(b""), DataInput)


def test_basics():
    di = DataInputByteArray(_data())
    assert di.length() == 10
    assert di.has_remaining() is True
    assert di.get_position() == 0


def test_set_position_negative_raises():
    di = DataInputByteArray(_data())
    with pytest.raises(OSError):
        di.set_position(-1)


def test_set_position_at_length_raises():
    # Strict ``>=`` semantics (upstream).
    di = DataInputByteArray(_data())
    with pytest.raises(OSError):
        di.set_position(di.length())


def test_set_position_in_range():
    di = DataInputByteArray(_data())
    di.set_position(6)
    assert di.get_position() == 6


def test_read_byte_signed():
    di = DataInputByteArray(_data())
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
    di = DataInputByteArray(_data())
    assert di.read_unsigned_byte() == 0
    assert di.read_unsigned_byte() == 255
    di.set_position(6)
    assert di.read_unsigned_byte() == 6
    assert di.read_unsigned_byte() == 249
    di.set_position(di.length() - 1)
    assert di.read_unsigned_byte() == 247
    with pytest.raises(OSError):
        di.read_unsigned_byte()


def test_peek_unsigned_byte():
    di = DataInputByteArray(_data())
    assert di.peek_unsigned_byte(0) == 0
    assert di.peek_unsigned_byte(5) == 251
    # Peeking does not advance.
    assert di.get_position() == 0
    with pytest.raises(OSError):
        di.peek_unsigned_byte(-1)
    with pytest.raises(OSError):
        di.peek_unsigned_byte(di.length())


def test_read_short():
    di = DataInputByteArray(bytes([0x00, 0x0F, 0xAA, 0x00, 0xFE, 0xFF]))
    # 0x000F as signed 16 bit = 15
    assert di.read_short() == 0x000F
    # 0xAA00 as signed 16 bit = -22016
    assert di.read_short() == -22016
    # 0xFEFF as signed 16 bit = -257
    assert di.read_short() == -257
    with pytest.raises(OSError):
        di.read_short()


def test_read_unsigned_short():
    di = DataInputByteArray(bytes([0x00, 0x0F, 0xAA, 0x00, 0xFE, 0xFF]))
    assert di.read_unsigned_short() == 0x000F
    assert di.read_unsigned_short() == 0xAA00
    assert di.read_unsigned_short() == 0xFEFF
    with pytest.raises(OSError):
        di.read_unsigned_short()
    di2 = DataInputByteArray(bytes([0x00]))
    with pytest.raises(OSError):
        di2.read_unsigned_short()


def test_read_int_signed_overflow():
    di = DataInputByteArray(
        bytes([0x00, 0x0F, 0xAA, 0x00, 0xFE, 0xFF, 0x30, 0x50])
    )
    assert di.read_int() == 0x000FAA00
    # 0xFEFF3050 read as signed 32-bit Java int.
    assert di.read_int() == 0xFEFF3050 - 0x1_0000_0000
    with pytest.raises(OSError):
        di.read_int()
    di2 = DataInputByteArray(bytes([0x00, 0x0F, 0xAA]))
    with pytest.raises(OSError):
        di2.read_int()


def test_read_bytes_basic_and_errors():
    di = DataInputByteArray(_data())
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


def test_read_offset_assembles_big_endian():
    di = DataInputByteArray(bytes([0x12, 0x34, 0x56, 0x78]))
    assert di.read_offset(1) == 0x12
    di.set_position(0)
    assert di.read_offset(2) == 0x1234
    di.set_position(0)
    assert di.read_offset(3) == 0x123456
    di.set_position(0)
    assert di.read_offset(4) == 0x12345678


def test_read_bytes_returns_bytes_type():
    di = DataInputByteArray(b"\x01\x02\x03")
    out = di.read_bytes(3)
    assert isinstance(out, bytes)
    assert out == b"\x01\x02\x03"


def test_constructor_defensively_copies():
    buf = bytearray(b"abc")
    di = DataInputByteArray(buf)
    buf[0] = ord("Z")
    assert di.read_byte() == ord("a")


def test_has_remaining_at_eof():
    di = DataInputByteArray(b"x")
    assert di.has_remaining() is True
    assert di.read_byte() == ord("x")
    assert di.has_remaining() is False
