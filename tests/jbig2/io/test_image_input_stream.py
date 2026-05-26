from __future__ import annotations

import io

import pytest

from pypdfbox.jbig2.io.image_input_stream import EOF, ImageInputStream


def test_initial_state() -> None:
    s = ImageInputStream(b"\x00\x01\x02")
    assert s.get_stream_position() == 0
    assert s.get_bit_offset() == 0
    assert s.length() == 3


def test_accepts_file_like() -> None:
    s = ImageInputStream(io.BytesIO(b"\xde\xad\xbe\xef"))
    assert s.length() == 4
    assert s.read() == 0xDE


def test_read_unsigned_bytes_sequence() -> None:
    s = ImageInputStream(b"\x00\x7f\x80\xff")
    assert s.read() == 0x00
    assert s.read() == 0x7F
    assert s.read() == 0x80
    assert s.read() == 0xFF
    assert s.read() == EOF  # past end


def test_read_byte_signed() -> None:
    s = ImageInputStream(b"\x00\x7f\x80\xff")
    assert s.read_byte() == 0
    assert s.read_byte() == 127
    assert s.read_byte() == -128
    assert s.read_byte() == -1


def test_read_byte_eof_raises() -> None:
    s = ImageInputStream(b"")
    with pytest.raises(EOFError):
        s.read_byte()


def test_read_unsigned_byte() -> None:
    s = ImageInputStream(b"\x80\xff")
    assert s.read_unsigned_byte() == 128
    assert s.read_unsigned_byte() == 255


def test_read_unsigned_int() -> None:
    # 0x12345678
    s = ImageInputStream(b"\x12\x34\x56\x78")
    assert s.read_unsigned_int() == 0x12345678
    assert s.get_stream_position() == 4


def test_read_unsigned_int_high_bit() -> None:
    s = ImageInputStream(b"\xff\xff\xff\xff")
    assert s.read_unsigned_int() == 0xFFFFFFFF  # unsigned, not -1


def test_read_short_signed() -> None:
    s = ImageInputStream(b"\xff\xfe")
    assert s.read_short() == -2


def test_read_unsigned_short() -> None:
    s = ImageInputStream(b"\xff\xfe")
    assert s.read_unsigned_short() == 0xFFFE


def test_read_int_signed() -> None:
    s = ImageInputStream(b"\xff\xff\xff\xff")
    assert s.read_int() == -1


# ------------------------------------------------------------------ #
# Bit-level reads
# ------------------------------------------------------------------ #
def test_read_bit_msb_first() -> None:
    # 0b10110010 = 0xB2
    s = ImageInputStream(b"\xb2")
    bits = [s.read_bit() for _ in range(8)]
    assert bits == [1, 0, 1, 1, 0, 0, 1, 0]
    # After consuming 8 bits, position advanced to next byte, offset wrapped.
    assert s.get_stream_position() == 1
    assert s.get_bit_offset() == 0


def test_read_bit_offset_tracking() -> None:
    s = ImageInputStream(b"\xff")
    assert s.get_bit_offset() == 0
    s.read_bit()
    assert s.get_stream_position() == 0  # still in same byte
    assert s.get_bit_offset() == 1
    for _ in range(6):
        s.read_bit()
    assert s.get_bit_offset() == 7
    s.read_bit()  # 8th bit -> wraps
    assert s.get_bit_offset() == 0
    assert s.get_stream_position() == 1


def test_read_bit_across_byte_boundary() -> None:
    # 0xAA = 10101010, 0x55 = 01010101
    s = ImageInputStream(b"\xaa\x55")
    bits = [s.read_bit() for _ in range(16)]
    assert bits == [1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 1]


def test_read_bit_eof() -> None:
    s = ImageInputStream(b"")
    with pytest.raises(EOFError):
        s.read_bit()


def test_read_bits_within_byte() -> None:
    # 0xB2 = 1011 0010 ; first 4 bits MSB-first = 0b1011 = 11
    s = ImageInputStream(b"\xb2")
    assert s.read_bits(4) == 0b1011
    assert s.get_bit_offset() == 4
    assert s.get_stream_position() == 0
    assert s.read_bits(4) == 0b0010
    assert s.get_bit_offset() == 0
    assert s.get_stream_position() == 1


def test_read_bits_zero() -> None:
    s = ImageInputStream(b"\xff")
    assert s.read_bits(0) == 0
    assert s.get_stream_position() == 0
    assert s.get_bit_offset() == 0


def test_read_bits_across_byte_boundary() -> None:
    # 0xB2 0x6C = 10110010 01101100
    # read 6 bits: 101100 = 0b101100 = 44
    s = ImageInputStream(b"\xb2\x6c")
    assert s.read_bits(6) == 0b101100
    assert s.get_bit_offset() == 6
    # next 6 bits: bits 6,7 of byte0 (1,0) + bits 0..3 of byte1 (0,1,1,0)
    # = 100110 = 0b100110 = 38
    assert s.read_bits(6) == 0b100110
    assert s.get_bit_offset() == 4
    assert s.get_stream_position() == 1


def test_read_bits_full_byte_aligned() -> None:
    s = ImageInputStream(b"\x12\x34")
    assert s.read_bits(8) == 0x12
    assert s.get_bit_offset() == 0
    assert s.get_stream_position() == 1
    assert s.read_bits(8) == 0x34


def test_read_bits_32() -> None:
    s = ImageInputStream(b"\xde\xad\xbe\xef")
    assert s.read_bits(32) == 0xDEADBEEF
    assert s.get_stream_position() == 4
    assert s.get_bit_offset() == 0


def test_read_bits_then_byte_mixed() -> None:
    # SegmentHeader-style: read a few bits then read whole bytes.
    s = ImageInputStream(b"\xb2\xde\xad")
    assert s.read_bits(3) == 0b101  # top 3 of 0xB2
    assert s.get_bit_offset() == 3


def test_read_bits_eof() -> None:
    s = ImageInputStream(b"\x01")
    with pytest.raises(EOFError):
        s.read_bits(16)  # only 8 bits available


def test_read_bits_invalid_count() -> None:
    s = ImageInputStream(b"\x01")
    with pytest.raises(ValueError):
        s.read_bits(-1)
    with pytest.raises(ValueError):
        s.read_bits(65)


# ------------------------------------------------------------------ #
# Seek / position / bit-offset manipulation
# ------------------------------------------------------------------ #
def test_seek_resets_bit_offset() -> None:
    s = ImageInputStream(b"\xff\x00")
    s.read_bit()
    assert s.get_bit_offset() == 1
    s.seek(1)
    assert s.get_stream_position() == 1
    assert s.get_bit_offset() == 0


def test_seek_negative_raises() -> None:
    s = ImageInputStream(b"\xff")
    with pytest.raises(OSError):
        s.seek(-1)


def test_set_bit_offset() -> None:
    s = ImageInputStream(b"\xb2")
    s.set_bit_offset(4)
    assert s.get_bit_offset() == 4
    # reading bits now starts at bit 4: 0010
    assert s.read_bits(4) == 0b0010


def test_set_bit_offset_out_of_range() -> None:
    s = ImageInputStream(b"\xff")
    with pytest.raises(ValueError):
        s.set_bit_offset(8)
    with pytest.raises(ValueError):
        s.set_bit_offset(-1)


def test_align_partial_byte() -> None:
    s = ImageInputStream(b"\xff\x00\xaa")
    s.read_bits(3)
    assert s.get_bit_offset() == 3
    s.align()
    assert s.get_bit_offset() == 0
    assert s.get_stream_position() == 1
    assert s.read() == 0x00


def test_align_already_aligned_noop() -> None:
    s = ImageInputStream(b"\xff\x00")
    s.read()  # aligned read, offset stays 0
    pos = s.get_stream_position()
    s.align()
    assert s.get_stream_position() == pos
    assert s.get_bit_offset() == 0


# ------------------------------------------------------------------ #
# mark / reset
# ------------------------------------------------------------------ #
def test_mark_reset_byte_position() -> None:
    s = ImageInputStream(b"\x01\x02\x03\x04")
    s.read()
    s.mark()
    assert s.read() == 0x02
    assert s.read() == 0x03
    s.reset()
    assert s.read() == 0x02  # back to the marked position


def test_mark_reset_restores_bit_offset() -> None:
    s = ImageInputStream(b"\xff\x00")
    s.read_bits(3)
    s.mark()
    s.read_bits(2)
    assert s.get_bit_offset() == 5
    s.reset()
    assert s.get_bit_offset() == 3
    assert s.get_stream_position() == 0


def test_nested_marks() -> None:
    s = ImageInputStream(b"\x01\x02\x03\x04\x05")
    s.read()  # pos 1
    s.mark()  # mark at 1
    s.read()  # pos 2
    s.mark()  # mark at 2
    s.read()  # pos 3
    s.reset()  # back to 2
    assert s.get_stream_position() == 2
    s.reset()  # back to 1
    assert s.get_stream_position() == 1


def test_reset_without_mark_noop() -> None:
    s = ImageInputStream(b"\x01\x02")
    s.read()
    s.reset()  # no mark set -> position unchanged
    assert s.get_stream_position() == 1


# ------------------------------------------------------------------ #
# read_full / read_fully / skip_bytes
# ------------------------------------------------------------------ #
def test_read_full_partial() -> None:
    s = ImageInputStream(b"\x01\x02\x03")
    buf = bytearray(5)
    n = s.read_full(buf, 0, 5)
    assert n == 3
    assert bytes(buf[:3]) == b"\x01\x02\x03"


def test_read_full_eof() -> None:
    s = ImageInputStream(b"")
    buf = bytearray(4)
    assert s.read_full(buf) == EOF


def test_read_fully_exact() -> None:
    s = ImageInputStream(b"\xaa\xbb\xcc\xdd")
    buf = bytearray(4)
    s.read_fully(buf, 0, 4)
    assert bytes(buf) == b"\xaa\xbb\xcc\xdd"


def test_read_fully_short_raises() -> None:
    s = ImageInputStream(b"\xaa\xbb")
    buf = bytearray(4)
    with pytest.raises(EOFError):
        s.read_fully(buf, 0, 4)


def test_skip_bytes() -> None:
    s = ImageInputStream(b"\x01\x02\x03\x04")
    assert s.skip_bytes(2) == 2
    assert s.get_stream_position() == 2
    assert s.read() == 0x03
    assert s.skip_bytes(100) == 1  # only one byte left
    assert s.read() == EOF


# ------------------------------------------------------------------ #
# close
# ------------------------------------------------------------------ #
def test_close_blocks_ops() -> None:
    s = ImageInputStream(b"\x01")
    assert not s.is_closed()
    s.close()
    assert s.is_closed()
    with pytest.raises(OSError):
        s.read()
    with pytest.raises(OSError):
        s.read_bit()
    with pytest.raises(OSError):
        s.get_stream_position()


def test_double_close_raises() -> None:
    s = ImageInputStream(b"\x01")
    s.close()
    with pytest.raises(OSError):
        s.close()
