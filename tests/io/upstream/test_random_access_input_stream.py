"""
Ported from
io/src/test/java/org/apache/pdfbox/io/RandomAccessInputStreamTest.java
(Apache PDFBox 3.0.x).

Exercises the ``InputStream`` view layered over a ``RandomAccessRead``:
position-based ``skip`` / ``read`` / ``read_into`` / ``available`` and
behavior at and past EOF.
"""

from __future__ import annotations

import io

from pypdfbox.io.random_access_input_stream import RandomAccessInputStream
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer


def _inputs(*values: int) -> bytes:
    return bytes(values)


def test_position_skip() -> None:
    inputs = _inputs(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    bais = io.BytesIO(inputs)

    with RandomAccessInputStream(RandomAccessReadBuffer(bais)) as stream:
        assert stream.available() == 11
        stream.skip(5)
        assert stream.read(1)[0] == 5
        assert stream.available() == 5
        assert stream.skip(-10) == 0


def test_position_read() -> None:
    inputs = _inputs(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    bais = io.BytesIO(inputs)

    with RandomAccessInputStream(RandomAccessReadBuffer(bais)) as stream:
        assert stream.available() == 11
        assert stream.read(1)[0] == 0
        assert stream.read(1)[0] == 1
        assert stream.read(1)[0] == 2
        assert stream.available() == 8


def test_seek_eof() -> None:
    inputs = _inputs(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    bais = io.BytesIO(inputs)

    with RandomAccessInputStream(RandomAccessReadBuffer(bais)) as stream:
        # skip() returns the requested n (matches upstream behaviour).
        assert stream.skip(len(inputs) + 1) == len(inputs) + 1

        assert stream.available() == 0
        # ``read()`` returning ``b""`` is Python's analogue of ``-1`` from
        # Java's ``int read()`` — upstream asserts the int -1.
        assert stream.read(1) == b""
        # ``read_into`` over a memoryview-backed bytearray of length 1 fails
        # to populate the buffer (n == -1 → 0).
        buf = bytearray(1)
        assert stream.readinto(buf) == 0


def test_position_read_bytes() -> None:
    inputs = _inputs(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    bais = io.BytesIO(inputs)

    with RandomAccessInputStream(RandomAccessReadBuffer(bais)) as stream:
        assert stream.available() == 11
        buffer = bytearray(4)
        stream.readinto(buffer)
        assert buffer[0] == 0
        assert buffer[3] == 3
        assert stream.available() == 7

        # Read 2 bytes into buffer at offset 1; Python's RawIOBase.readinto
        # has no offset/length, so emulate by reading into a slice.
        slot = bytearray(2)
        n = stream.readinto(slot)
        assert n == 2
        buffer[1] = slot[0]
        buffer[2] = slot[1]
        assert buffer[0] == 0
        assert buffer[1] == 4
        assert buffer[2] == 5
        assert buffer[3] == 3
        assert stream.available() == 5


def test_empty_buffer() -> None:
    with RandomAccessInputStream(RandomAccessReadBuffer(b"")) as stream:
        assert stream.read(1) == b""
        assert stream.readinto(bytearray(6)) == 0
        assert stream.available() == 0
