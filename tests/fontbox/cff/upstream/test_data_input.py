"""Port of org.apache.fontbox.cff.DataInputTest (PDFBox 3.0.x)."""
from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray

# Java byte literals like ``-1`` are unsigned 0xFF when promoted to int.
_DATA = bytes([0, 0xFF, 2, 0xFD, 4, 0xFB, 6, 0xF9, 8, 0xF7])


def test_read_bytes():
    data_input = DataInputByteArray(_DATA)
    with pytest.raises(OSError):
        data_input.read_bytes(20)
    assert data_input.read_bytes(1) == bytes([0])
    assert data_input.read_bytes(3) == bytes([0xFF, 2, 0xFD])
    data_input.set_position(6)
    assert data_input.read_bytes(3) == bytes([6, 0xF9, 8])
    with pytest.raises(OSError):
        data_input.read_bytes(-1)
    with pytest.raises(OSError):
        data_input.read_bytes(5)


def test_read_byte():
    data_input = DataInputByteArray(_DATA)
    assert data_input.read_byte() == 0
    assert data_input.read_byte() == -1
    data_input.set_position(6)
    assert data_input.read_byte() == 6
    assert data_input.read_byte() == -7
    data_input.set_position(data_input.length() - 1)
    assert data_input.read_byte() == -9
    with pytest.raises(OSError):
        data_input.read_byte()


def test_read_unsigned_byte():
    data_input = DataInputByteArray(_DATA)
    assert data_input.read_unsigned_byte() == 0
    assert data_input.read_unsigned_byte() == 255
    data_input.set_position(6)
    assert data_input.read_unsigned_byte() == 6
    assert data_input.read_unsigned_byte() == 249
    data_input.set_position(data_input.length() - 1)
    assert data_input.read_unsigned_byte() == 247
    with pytest.raises(OSError):
        data_input.read_unsigned_byte()


def test_basics():
    data_input = DataInputByteArray(_DATA)
    assert data_input.length() == 10
    assert data_input.has_remaining() is True
    with pytest.raises(OSError):
        data_input.set_position(-1)
    length = data_input.length()
    with pytest.raises(OSError):
        data_input.set_position(length)


def test_peek():
    data_input = DataInputByteArray(_DATA)
    assert data_input.peek_unsigned_byte(0) == 0
    assert data_input.peek_unsigned_byte(5) == 251
    with pytest.raises(OSError):
        data_input.peek_unsigned_byte(-1)
    length = data_input.length()
    with pytest.raises(OSError):
        data_input.peek_unsigned_byte(length)


def test_read_short():
    data_input = DataInputByteArray(bytes([0x00, 0x0F, 0xAA, 0, 0xFE, 0xFF]))
    # Java ``(short) 0x000F`` == 15
    assert data_input.read_short() == 0x000F
    # Java ``(short) 0xAA00`` == -22016
    assert data_input.read_short() == -22016
    # Java ``(short) 0xFEFF`` == -257
    assert data_input.read_short() == -257
    with pytest.raises(OSError):
        data_input.read_short()


def test_read_unsigned_short():
    data_input = DataInputByteArray(bytes([0x00, 0x0F, 0xAA, 0, 0xFE, 0xFF]))
    assert data_input.read_unsigned_short() == 0x000F
    assert data_input.read_unsigned_short() == 0xAA00
    assert data_input.read_unsigned_short() == 0xFEFF
    with pytest.raises(OSError):
        data_input.read_unsigned_short()
    data_input2 = DataInputByteArray(bytes([0x00]))
    with pytest.raises(OSError):
        data_input2.read_unsigned_short()


def test_read_int():
    data_input = DataInputByteArray(
        bytes([0x00, 0x0F, 0xAA, 0, 0xFE, 0xFF, 0x30, 0x50])
    )
    assert data_input.read_int() == 0x000FAA00
    # Java signed-int ``0xFEFF3050`` == -16830384
    assert data_input.read_int() == 0xFEFF3050 - 0x1_0000_0000
    with pytest.raises(OSError):
        data_input.read_int()
    data_input2 = DataInputByteArray(bytes([0x00, 0x0F, 0xAA]))
    with pytest.raises(OSError):
        data_input2.read_int()
