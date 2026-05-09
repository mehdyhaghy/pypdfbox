"""
Ported from
io/src/test/java/org/apache/pdfbox/io/RandomAccessReadBufferTest.java
(Apache PDFBox 3.0).

Tracks upstream test method names: camelCase -> snake_case, drop "test" prefix.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.io import RandomAccessReadBuffer


def _values() -> bytes:
    return bytes([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])


def test_position_skip() -> None:
    with RandomAccessReadBuffer(io.BytesIO(_values())) as r:
        assert r.get_position() == 0
        r.skip(5)
        assert r.read() == 5
        assert r.get_position() == 6


def test_position_read() -> None:
    r = RandomAccessReadBuffer(io.BytesIO(_values()))
    assert r.get_position() == 0
    assert r.read() == 0
    assert r.read() == 1
    assert r.read() == 2
    assert r.get_position() == 3
    assert not r.is_closed()
    r.close()
    assert r.is_closed()


def test_seek_eof() -> None:
    r = RandomAccessReadBuffer(io.BytesIO(_values()))
    r.seek(3)
    assert r.get_position() == 3
    with pytest.raises(OSError):
        r.seek(-1)
    assert not r.is_eof()
    r.seek(20)
    assert r.is_eof()
    assert r.read() == -1
    assert r.read_into(bytearray(1), 0, 1) == -1
    r.close()
    with pytest.raises(ValueError):
        # check_closed: subsequent operations on a closed reader raise
        r.read()


def test_position_read_bytes() -> None:
    with RandomAccessReadBuffer(io.BytesIO(_values())) as r:
        assert r.get_position() == 0
        buf = bytearray(4)
        r.read_into(buf)
        assert buf[0] == 0
        assert buf[3] == 3
        assert r.get_position() == 4

        r.read_into(buf, 1, 2)
        assert buf[0] == 0
        assert buf[1] == 4
        assert buf[2] == 5
        assert buf[3] == 3
        assert r.get_position() == 6


def test_position_peek() -> None:
    with RandomAccessReadBuffer(io.BytesIO(_values())) as r:
        assert r.get_position() == 0
        r.skip(6)
        assert r.get_position() == 6
        assert r.peek() == 6
        assert r.get_position() == 6


def test_position_unread_bytes() -> None:
    with RandomAccessReadBuffer(io.BytesIO(_values())) as r:
        assert r.get_position() == 0
        r.read()
        r.read()
        read_bytes = bytearray(6)
        assert r.read_into(read_bytes) == len(read_bytes)
        assert r.get_position() == 8
        r.rewind(len(read_bytes))
        assert r.get_position() == 2
        assert r.read() == 2
        assert r.get_position() == 3
        r.read_into(read_bytes, 2, 4)
        assert r.get_position() == 7
        r.rewind(4)
        assert r.get_position() == 3


def test_empty_buffer() -> None:
    with RandomAccessReadBuffer(b"") as r:
        assert r.read() == -1
        assert r.peek() == -1
        read_bytes = bytearray(6)
        assert r.read_into(read_bytes) == -1
        r.seek(0)
        assert r.get_position() == 0
        r.seek(6)
        assert r.get_position() == 0
        assert r.is_eof()
        with pytest.raises(OSError):
            r.rewind(3)


def test_view() -> None:
    with (
        RandomAccessReadBuffer(io.BytesIO(_values())) as r,
        r.create_view(3, 5) as view,
    ):
        assert view.get_position() == 0
        assert view.read() == 3
        assert view.read() == 4
        assert view.read() == 5
        assert view.get_position() == 3


# skipped: testPDFBOX5111 fetches a PDF over the network from issues.apache.org


# skipped: testPDFBOX5158 covers a Java FileInputStream-specific endless-loop bug
# (PDFBox-5158) that does not apply to CPython's BufferedReader.


def test_pdfbox5161() -> None:
    # PDFBOX-5161: failure to read bytes after reading a multiple of 4096.
    with RandomAccessReadBuffer(io.BytesIO(bytes(4099))) as r:
        buf = bytearray(4096)
        assert r.read_into(buf) == 4096
        assert r.read_into(buf, 0, 3) == 3


def test_pdfbox5764_sliced_memoryview_limit() -> None:
    # PDFBOX-5764: the reader must not expose bytes beyond the caller's
    # ByteBuffer limit. A sliced memoryview is Python's equivalent input.
    with RandomAccessReadBuffer(memoryview(b"0123456789")[2:7]) as r:
        assert r.length() == 5
        assert r.read_fully(5) == b"23456"
        assert r.read() == -1

        r.seek(0)
        r.skip(2)
        assert r.read() == ord("4")
        r.skip(99)
        assert r.get_position() == 5
        assert r.is_eof()
