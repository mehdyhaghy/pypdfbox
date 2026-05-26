from __future__ import annotations

import pytest

from pypdfbox.jbig2.io.image_input_stream import EOF, ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream


def _wrapped(data: bytes) -> ImageInputStream:
    return ImageInputStream(data)


def test_construction_validation() -> None:
    iis = _wrapped(b"\x00")
    with pytest.raises(ValueError):
        SubInputStream(None, 0, 1)
    with pytest.raises(ValueError):
        SubInputStream(iis, -1, 1)
    with pytest.raises(ValueError):
        SubInputStream(iis, 0, -1)


def test_length_is_window_length() -> None:
    iis = _wrapped(b"\x00\x01\x02\x03\x04\x05")
    sub = SubInputStream(iis, 2, 3)
    assert sub.length() == 3


def test_windowed_byte_reads() -> None:
    # window covers bytes [2..5): 0x22 0x33 0x44
    iis = _wrapped(b"\x00\x11\x22\x33\x44\x55\x66")
    sub = SubInputStream(iis, 2, 3)
    assert sub.read() == 0x22
    assert sub.read() == 0x33
    assert sub.read() == 0x44
    assert sub.read() == EOF  # window exhausted before underlying stream


def test_window_positions_are_relative() -> None:
    iis = _wrapped(b"\x00\x11\x22\x33\x44\x55")
    sub = SubInputStream(iis, 2, 3)
    assert sub.get_stream_position() == 0
    sub.read()
    assert sub.get_stream_position() == 1


def test_windowed_read_full() -> None:
    iis = _wrapped(b"\x00\x11\x22\x33\x44\x55\x66")
    sub = SubInputStream(iis, 2, 3)
    buf = bytearray(10)
    n = sub.read_full(buf, 0, 10)
    assert n == 3  # clamped to window length
    assert bytes(buf[:3]) == b"\x22\x33\x44"


def test_windowed_bit_reads_inherited() -> None:
    # window over a single byte 0xB2 = 1011 0010
    iis = _wrapped(b"\x00\x00\xb2\xff")
    sub = SubInputStream(iis, 2, 1)
    bits = [sub.read_bit() for _ in range(8)]
    assert bits == [1, 0, 1, 1, 0, 0, 1, 0]


def test_windowed_read_bits_across_boundary() -> None:
    # window over 0xB2 0x6C
    iis = _wrapped(b"\xff\xb2\x6c\xff")
    sub = SubInputStream(iis, 1, 2)
    assert sub.read_bits(6) == 0b101100
    assert sub.read_bits(6) == 0b100110


def test_skip_bits() -> None:
    iis = _wrapped(b"\xff\x00\xaa")
    sub = SubInputStream(iis, 0, 3)
    sub.read_bits(3)
    assert sub.get_bit_offset() == 3
    sub.skip_bits()
    assert sub.get_bit_offset() == 0
    assert sub.get_stream_position() == 1
    assert sub.read() == 0x00


def test_skip_bits_noop_when_aligned() -> None:
    iis = _wrapped(b"\xff\x00")
    sub = SubInputStream(iis, 0, 2)
    sub.read()
    pos = sub.get_stream_position()
    sub.skip_bits()
    assert sub.get_stream_position() == pos


def test_buffer_reuse_across_large_window() -> None:
    # Window larger than the 4096-byte buffer forces a refill.
    data = bytes((i * 7) & 0xFF for i in range(9000))
    iis = _wrapped(data)
    sub = SubInputStream(iis, 100, 8000)
    out = bytearray()
    while True:
        b = sub.read()
        if b == EOF:
            break
        out.append(b)
    assert bytes(out) == data[100:8100]


def test_seek_within_window() -> None:
    iis = _wrapped(b"\x00\x11\x22\x33\x44\x55")
    sub = SubInputStream(iis, 1, 4)  # bytes 0x11 0x22 0x33 0x44
    sub.seek(2)
    assert sub.read() == 0x33
    sub.seek(0)
    assert sub.read() == 0x11


def test_two_subs_over_same_wrapped_stream() -> None:
    # Reads interleaved across two windows of the same wrapped stream remain
    # correct thanks to the seek-before-read discipline.
    iis = _wrapped(b"\x00\x11\x22\x33\x44\x55\x66\x77")
    a = SubInputStream(iis, 0, 4)
    b = SubInputStream(iis, 4, 4)
    assert a.read() == 0x00
    assert b.read() == 0x44
    assert a.read() == 0x11
    assert b.read() == 0x55
