"""Wave 1368 — :class:`DataInput.read_offset` parity across offSize 1/2/3/4.

The CFF spec (Adobe TN5176 §5) defines INDEX offsets as ``offSize``
bytes wide, big-endian, where ``offSize`` is in ``[1, 4]``. Exercises
the assembled value for each width plus the boundary big-endian cases.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray


@pytest.mark.parametrize(
    ("off_size", "payload", "expected"),
    [
        (1, b"\x00", 0),
        (1, b"\xff", 255),
        (2, b"\x01\x02", 0x0102),
        (2, b"\xff\xff", 0xFFFF),
        (3, b"\x00\x00\x00", 0),
        (3, b"\xab\xcd\xef", 0xABCDEF),
        (3, b"\xff\xff\xff", 0xFFFFFF),
        (4, b"\x00\x00\x00\x01", 1),
        (4, b"\x7f\xff\xff\xff", 0x7FFFFFFF),
        (4, b"\xff\xff\xff\xff", 0xFFFFFFFF),
    ],
    ids=[
        "off1_min",
        "off1_max",
        "off2_mid",
        "off2_max",
        "off3_zero",
        "off3_mid",
        "off3_max",
        "off4_min_nonzero",
        "off4_signed_max",
        "off4_unsigned_max",
    ],
)
def test_read_offset_parametrized(
    off_size: int, payload: bytes, expected: int
) -> None:
    inp = DataInputByteArray(payload)
    assert inp.read_offset(off_size) == expected
    # Cursor must be exactly at end after a full read.
    assert inp.get_position() == off_size


def test_read_offset_advances_position_per_byte() -> None:
    # Three back-to-back offset reads at offSize=2: advance must be 6.
    inp = DataInputByteArray(b"\x00\x01\x00\x02\x00\x03")
    assert inp.read_offset(2) == 1
    assert inp.get_position() == 2
    assert inp.read_offset(2) == 2
    assert inp.get_position() == 4
    assert inp.read_offset(2) == 3
    assert inp.get_position() == 6


def test_read_offset_zero_width_returns_zero_no_advance() -> None:
    # The helper does not validate the offSize range (caller does).
    # An offSize of 0 must return 0 and leave the cursor untouched —
    # mirrors upstream's loop-from-1-to-offSize semantics.
    inp = DataInputByteArray(b"\xaa\xbb")
    assert inp.read_offset(0) == 0
    assert inp.get_position() == 0


def test_read_offset_treats_bytes_big_endian_not_native() -> None:
    # 0x01_02_03_04 must decode as 16909060 (big-endian) on every
    # platform — CFF is always big-endian.
    inp = DataInputByteArray(b"\x01\x02\x03\x04")
    assert inp.read_offset(4) == 0x01020304


def test_read_int_returns_signed_java_semantics_at_extremes() -> None:
    # Java ``int`` is signed: 0xFFFFFFFF must read back as -1, and
    # 0x80000000 must read back as Integer.MIN_VALUE.
    inp = DataInputByteArray(b"\xff\xff\xff\xff\x80\x00\x00\x00")
    assert inp.read_int() == -1
    assert inp.read_int() == -2147483648


def test_read_short_returns_signed_java_semantics_at_extremes() -> None:
    inp = DataInputByteArray(b"\x80\x00\x7f\xff")
    assert inp.read_short() == -32768
    assert inp.read_short() == 32767


def test_read_unsigned_short_returns_unsigned() -> None:
    inp = DataInputByteArray(b"\xff\xfe\x00\x01")
    assert inp.read_unsigned_short() == 0xFFFE
    assert inp.read_unsigned_short() == 1


def test_peek_unsigned_byte_does_not_advance_position() -> None:
    inp = DataInputByteArray(b"\xaa\xbb\xcc\xdd")
    inp.set_position(1)
    assert inp.peek_unsigned_byte(0) == 0xBB
    assert inp.peek_unsigned_byte(1) == 0xCC
    assert inp.peek_unsigned_byte(2) == 0xDD
    # Position must still be 1.
    assert inp.get_position() == 1


def test_peek_unsigned_byte_rejects_negative_offset() -> None:
    inp = DataInputByteArray(b"\xaa")
    with pytest.raises(OSError, match="offset is negative"):
        inp.peek_unsigned_byte(-1)


def test_peek_unsigned_byte_rejects_out_of_range_offset() -> None:
    inp = DataInputByteArray(b"\xaa")
    with pytest.raises(OSError, match="Offset position is out of range"):
        inp.peek_unsigned_byte(1)


def test_read_bytes_negative_length_raises() -> None:
    inp = DataInputByteArray(b"\xaa\xbb")
    with pytest.raises(OSError, match="length is negative"):
        inp.read_bytes(-1)


def test_read_bytes_premature_eof_raises() -> None:
    inp = DataInputByteArray(b"\xaa\xbb")
    with pytest.raises(OSError, match="Premature end of buffer"):
        inp.read_bytes(3)


def test_set_position_rejects_negative_and_at_length() -> None:
    inp = DataInputByteArray(b"\xaa\xbb")
    with pytest.raises(OSError, match="position is negative"):
        inp.set_position(-1)
    # ``>=`` is strict; setting position to length is rejected.
    with pytest.raises(OSError, match="out of range"):
        inp.set_position(2)
    # But within range is fine.
    inp.set_position(1)
    assert inp.get_position() == 1
