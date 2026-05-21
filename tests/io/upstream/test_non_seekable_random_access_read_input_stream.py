"""
Ported from
io/src/test/java/org/apache/pdfbox/io/NonSeekableRandomAccessReadInputStreamTest.java
(Apache PDFBox 3.0.x).

Covers position/seek/skip/peek/rewind/EOF, view rejection, buffer rotation,
parameter validation on ``read_into``, and the PDFBOX-5158/5161 regressions
that the upstream test pinned down for streams that are an exact multiple of
the 4 KiB internal buffer size.
"""

from __future__ import annotations

import io
import os
import random
import tempfile

import pytest

from pypdfbox.io.non_seekable_random_access_read_input_stream import (
    NonSeekableRandomAccessReadInputStream,
)


def _inputs(*values: int) -> bytes:
    return bytes(values)


def test_position_skip() -> None:
    bais = io.BytesIO(_inputs(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10))
    with NonSeekableRandomAccessReadInputStream(bais) as rar:
        assert rar.get_position() == 0
        rar.skip(5)
        assert rar.read() == 5
        assert rar.get_position() == 6


def test_position_read() -> None:
    bais = io.BytesIO(_inputs(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10))
    rar = NonSeekableRandomAccessReadInputStream(bais)

    assert rar.get_position() == 0
    assert rar.read() == 0
    assert rar.read() == 1
    assert rar.read() == 2
    assert rar.get_position() == 3

    assert not rar.is_closed()
    rar.close()
    assert rar.is_closed()


def test_seek_eof() -> None:
    bais = io.BytesIO(_inputs(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10))
    with NonSeekableRandomAccessReadInputStream(bais) as rar, pytest.raises(OSError):
        rar.seek(3)


def test_position_read_bytes() -> None:
    bais = io.BytesIO(_inputs(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10))
    with NonSeekableRandomAccessReadInputStream(bais) as rar:
        assert rar.get_position() == 0
        buffer = bytearray(4)
        rar.read_into(buffer)
        assert buffer[0] == 0
        assert buffer[3] == 3
        assert rar.get_position() == 4

        rar.read_into(buffer, 1, 2)
        assert buffer[0] == 0
        assert buffer[1] == 4
        assert buffer[2] == 5
        assert buffer[3] == 3
        assert rar.get_position() == 6


def test_position_peek() -> None:
    bais = io.BytesIO(_inputs(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10))
    with NonSeekableRandomAccessReadInputStream(bais) as rar:
        assert rar.get_position() == 0
        rar.skip(6)
        assert rar.get_position() == 6

        assert rar.peek() == 6
        assert rar.get_position() == 6


def test_position_unread_bytes() -> None:
    bais = io.BytesIO(_inputs(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10))
    with NonSeekableRandomAccessReadInputStream(bais) as rar:
        assert rar.get_position() == 0
        rar.read()
        rar.read()
        read_bytes = bytearray(6)
        assert rar.read_into(read_bytes) == len(read_bytes)
        assert rar.get_position() == 8
        rar.rewind(len(read_bytes))
        assert rar.get_position() == 2
        assert rar.read() == 2
        assert rar.get_position() == 3
        rar.read_into(read_bytes, 2, 4)
        assert rar.get_position() == 7
        rar.rewind(4)
        assert rar.get_position() == 3

        # PDFBOX-5965: check that it also works near EOF
        assert rar.read() == 3
        assert rar.read() == 4
        assert rar.read() == 5
        assert rar.read() == 6
        assert rar.read() == 7
        assert rar.read() == 8
        assert rar.read() == 9
        assert rar.read() == 10
        assert rar.read() == -1
        assert rar.is_eof()
        rar.rewind(4)
        assert not rar.is_eof()
        assert rar.read() == 7
        assert rar.read() == 8
        assert rar.read() == 9
        assert rar.read() == 10
        assert rar.read() == -1


def test_view() -> None:
    bais = io.BytesIO(_inputs(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10))
    with NonSeekableRandomAccessReadInputStream(bais) as rar, pytest.raises(OSError):
        rar.create_view(3, 5)


def _create_random_data() -> bytes:
    seed = random.Random().randrange(1 << 63)
    rng = random.Random(seed)
    num_bytes = 10000 + rng.randrange(20000)
    buf = bytearray(num_bytes)
    upto = 0
    while upto < num_bytes:
        left = num_bytes - upto
        if rng.choice((True, False)) or left < 2:
            end = upto + min(left, 10 + rng.randrange(100))
            while upto < end:
                buf[upto] = rng.randrange(256)
                upto += 1
        else:
            end = upto + min(left, 2 + rng.randrange(10))
            value = rng.randrange(4)
            while upto < end:
                buf[upto] = value
                upto += 1
    return bytes(buf)


def test_buffer_switch() -> None:
    original = _create_random_data()
    bais = io.BytesIO(original)
    with NonSeekableRandomAccessReadInputStream(bais) as rar:
        rar.skip(4098)
        assert rar.get_position() == 4098
        rar.rewind(4)
        assert rar.get_position() == 4094
        assert rar.read() == (original[4094] & 0xFF)


def test_rewind_exception() -> None:
    bais = io.BytesIO(_create_random_data())
    with NonSeekableRandomAccessReadInputStream(bais) as rar:
        rar.skip(10000)
        assert rar.get_position() == 10000
        rar.rewind(4096)
        assert rar.get_position() == 5904
        with pytest.raises(OSError):
            rar.rewind(4096)


def test_rewind_across_buffers() -> None:
    ba = bytearray(4096 + 5)
    rew_size = 7
    test_val = 123
    ba[len(ba) - rew_size] = test_val
    bais = io.BytesIO(bytes(ba))
    with NonSeekableRandomAccessReadInputStream(bais) as rar:
        n = rar.read_into(bytearray(len(ba) - rew_size))
        assert n == len(ba) - rew_size
        n = rar.read_into(bytearray(rew_size))
        assert n == rew_size
        by = rar.read()
        assert by == -1
        assert rar.is_eof()
        rar.rewind(n)
        by = rar.read()  # used to raise IndexOutOfBounds upstream
        assert by == test_val


def test_rewind_across_buffers_2() -> None:
    ba = bytearray(4096 * 2)
    ba[4095] = 1
    ba[4096] = 2
    ba[4097] = 3
    ba[4096 * 2 - 1] = 4
    bais = io.BytesIO(bytes(ba))
    with NonSeekableRandomAccessReadInputStream(bais) as rar:
        assert rar.length() == 4096 * 2
        n = rar.read_into(bytearray(4096 + 1))
        assert rar.length() == 4096 * 2
        assert n == 4096 + 1
        rar.rewind(2)
        assert rar.read() == 1
        assert rar.read() == 2
        assert rar.read() == 3
        assert rar.length() == 4096 * 2

        buf = bytearray(4096)
        n = rar.read_into(buf)
        assert n == 4096 - 2
        assert buf[n - 1] == 4
        assert rar.read() == -1
        assert rar.read_into(bytearray(1)) == -1


def test_access_closed() -> None:
    bais = io.BytesIO(bytes([1]))
    rar = NonSeekableRandomAccessReadInputStream(bais)
    assert rar.read() == 1
    assert rar.read() == -1
    rar.close()
    with pytest.raises(OSError):
        rar.read()


def test_closed_stream_methods() -> None:
    bais = io.BytesIO(bytes([1, 2, 3]))
    rar = NonSeekableRandomAccessReadInputStream(bais)
    rar.close()

    with pytest.raises(OSError):
        rar.read()
    with pytest.raises(OSError):
        rar.read_into(bytearray(1), 0, 1)
    with pytest.raises(OSError):
        rar.read_fully(bytearray(1), 0, 1)
    with pytest.raises(OSError):
        rar.get_position()
    with pytest.raises(OSError):
        rar.available()
    with pytest.raises(OSError):
        rar.length()
    with pytest.raises(OSError):
        rar.is_eof()


def test_read_bytes_parameter_validation() -> None:
    bais = io.BytesIO(_inputs(0, 1, 2, 3, 4))
    with NonSeekableRandomAccessReadInputStream(bais) as rar:
        # length == 0 must return 0 immediately without advancing position
        buf = bytearray(4)
        assert rar.read_into(buf, 0, 0) == 0
        assert rar.get_position() == 0

        # negative offset / length / out-of-range slot all raise.
        # Upstream throws IndexOutOfBoundsException; Python's parity is IndexError.
        with pytest.raises(IndexError):
            rar.read_into(buf, -1, 2)
        with pytest.raises(IndexError):
            rar.read_into(buf, 0, -1)
        with pytest.raises(IndexError):
            rar.read_into(buf, 2, 4)


def test_read_fully() -> None:
    inputs = bytes(range(10))
    bais = io.BytesIO(inputs)
    with NonSeekableRandomAccessReadInputStream(bais) as rar:
        buf = bytearray(10)
        rar.read_fully(buf, 0, 10)
        for i in range(10):
            assert buf[i] == i
        assert rar.get_position() == 10


def test_read_fully_eof() -> None:
    bais = io.BytesIO(_inputs(0, 1, 2))
    with NonSeekableRandomAccessReadInputStream(bais) as rar, pytest.raises(EOFError):
        rar.read_fully(bytearray(10), 0, 10)


def test_skip_past_eof() -> None:
    bais = io.BytesIO(_inputs(0, 1, 2, 3, 4))
    with NonSeekableRandomAccessReadInputStream(bais) as rar:
        # skipping far beyond the end of the stream should not throw
        rar.skip(100)
        assert rar.get_position() == 5
        assert rar.is_eof()


def test_available() -> None:
    inputs = bytes(10)
    bais = io.BytesIO(inputs)
    with NonSeekableRandomAccessReadInputStream(bais) as rar:
        # before any read, available() reflects is.available()-equivalent
        # since nothing is buffered yet (mirrors upstream BAIS.available()).
        assert rar.available() == 10

        # read one byte: the fetch pulls all 10 bytes into the internal
        # buffer, so available = 9 buffered + 0 remaining in the underlying.
        rar.read()
        assert rar.available() == 9

        # consume all remaining bytes
        while rar.read() != -1:
            pass
        assert rar.available() == 0


def test_length_after_full_consumption() -> None:
    inputs = bytes(100)
    bais = io.BytesIO(inputs)
    with NonSeekableRandomAccessReadInputStream(bais) as rar:
        while rar.read() != -1:
            pass
        assert rar.is_eof()
        assert rar.length() == 100


def test_pdfbox_5158() -> None:
    """PDFBOX-5158: endless loop reading a stream of a multiple of 4096
    bytes from a FileInputStream.
    """
    fd, path = tempfile.mkstemp(prefix="len4096", suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(bytes(4096))
        assert os.path.getsize(path) == 4096
        with open(path, "rb") as fh_in, \
                NonSeekableRandomAccessReadInputStream(fh_in) as rar:
            assert rar.read() == 0
    finally:
        os.unlink(path)


def test_pdfbox_5161() -> None:
    """PDFBOX-5161: failure to read bytes after reading a multiple of 4096."""
    with NonSeekableRandomAccessReadInputStream(io.BytesIO(bytes(4099))) as rar:
        buf = bytearray(4096)
        bytes_read = rar.read_into(buf)
        assert bytes_read == 4096
        bytes_read = rar.read_into(buf, 0, 3)
        assert bytes_read == 3
