"""
Ported from
io/src/test/java/org/apache/pdfbox/io/RandomAccessReadBufferedFileTest.java
(Apache PDFBox 3.0).

The fixture file ``RandomAccessReadFile1.txt`` matches upstream byte-for-byte
(``"0123456789" * 13``, 130 bytes, no trailing newline).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.io import RandomAccessReadBufferedFile

_FIXTURES = Path(__file__).parent / "fixtures"
_FILE1 = _FIXTURES / "RandomAccessReadFile1.txt"
_EMPTY = _FIXTURES / "RandomAccessReadEmptyFile.txt"


def test_position_skip() -> None:
    with RandomAccessReadBufferedFile(_FILE1) as r:
        assert r.get_position() == 0
        r.skip(5)
        assert r.read() == ord("5")
        assert r.get_position() == 6


def test_position_read() -> None:
    r = RandomAccessReadBufferedFile(_FILE1)
    assert r.get_position() == 0
    assert r.read() == ord("0")
    assert r.read() == ord("1")
    assert r.read() == ord("2")
    assert r.get_position() == 3
    assert not r.is_closed()
    r.close()
    assert r.is_closed()


def test_seek_eof() -> None:
    r = RandomAccessReadBufferedFile(_FILE1)
    r.seek(3)
    assert r.get_position() == 3
    with pytest.raises(OSError):
        r.seek(-1)
    assert not r.is_eof()
    r.seek(r.length())
    assert r.is_eof()
    assert r.read() == -1
    assert r.read_into(bytearray(1), 0, 1) == -1
    r.close()
    with pytest.raises(ValueError):
        r.read()


def test_position_read_bytes() -> None:
    with RandomAccessReadBufferedFile(_FILE1) as r:
        assert r.get_position() == 0
        buf = bytearray(4)
        r.read_into(buf)
        assert buf[0] == ord("0")
        assert buf[3] == ord("3")
        assert r.get_position() == 4

        r.read_into(buf, 1, 2)
        assert buf[0] == ord("0")
        assert buf[1] == ord("4")
        assert buf[2] == ord("5")
        assert buf[3] == ord("3")
        assert r.get_position() == 6


def test_position_peek() -> None:
    with RandomAccessReadBufferedFile(_FILE1) as r:
        assert r.get_position() == 0
        r.skip(6)
        assert r.get_position() == 6
        assert r.peek() == ord("6")
        assert r.get_position() == 6


def test_path_constructor() -> None:
    with RandomAccessReadBufferedFile(_FILE1) as r:
        assert r.length() == 130


def test_position_unread_bytes() -> None:
    with RandomAccessReadBufferedFile(_FILE1) as r:
        assert r.get_position() == 0
        r.read()
        r.read()
        read_bytes = bytearray(6)
        assert r.read_into(read_bytes) == len(read_bytes)
        assert r.get_position() == 8
        r.rewind(len(read_bytes))
        assert r.get_position() == 2
        assert r.read() == ord("2")
        assert r.get_position() == 3
        r.read_into(read_bytes, 2, 4)
        assert r.get_position() == 7
        r.rewind(4)
        assert r.get_position() == 3


def test_empty_buffer() -> None:
    with RandomAccessReadBufferedFile(_EMPTY) as r:
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
        RandomAccessReadBufferedFile(_FILE1) as r,
        r.create_view(3, 10) as view,
    ):
        assert view.get_position() == 0
        assert view.read() == ord("3")
        assert view.read() == ord("4")
        assert view.read() == ord("5")
        assert view.get_position() == 3


def test_read_fully1() -> None:
    with RandomAccessReadBufferedFile(_FILE1) as r:
        b = bytearray(10)
        r.seek(1)
        r.read_fully(b)
        assert b.decode("ascii") == "1234567890"


def test_read_fully2() -> None:
    with RandomAccessReadBufferedFile(_FILE1) as r:
        b = bytearray(10)
        r.read_fully(b, 2, 8)
        assert bytes(b[2:10]).decode("ascii") == "01234567"
        assert b[0] == 0
        assert b[1] == 0


def test_read_fully3() -> None:
    with RandomAccessReadBufferedFile(_FILE1) as r:
        b = bytearray(10)
        r.seek(r.length() - len(b))
        r.read_fully(b)
        assert b.decode("ascii") == "0123456789"


def test_read_fully_eof() -> None:
    with RandomAccessReadBufferedFile(_FILE1) as r:
        b = bytearray(10)
        r.seek(r.length() - len(b) + 1)
        with pytest.raises(EOFError):
            r.read_fully(b)


def test_read_fully_exact() -> None:
    with RandomAccessReadBufferedFile(_FILE1) as r:
        length = r.length()
        b = bytearray(length)
        r.read_fully(b)
        assert bytes(b) == _FILE1.read_bytes()


def test_read_fully_across_buffers(tmp_path: Path) -> None:
    payload = bytes(range(251)) * 100
    path = tmp_path / "across-buffers.bin"
    path.write_bytes(payload)

    buffer_len = 64
    expected = bytearray(buffer_len * 2)
    expected[1:] = payload[buffer_len // 2 : buffer_len // 2 + len(expected) - 1]

    with RandomAccessReadBufferedFile(path, buffer_size=buffer_len) as r:
        assert buffer_len * 2 < r.length()
        r.seek(buffer_len // 2)

        data = bytearray(buffer_len * 2)
        r.read_fully(data, 1, len(data) - 1)

        assert data == expected
        assert r.get_position() == buffer_len // 2 + len(data) - 1


def test_read_fully_nothing() -> None:
    with RandomAccessReadBufferedFile(_FILE1) as r:
        assert r.get_position() == 0
        b = bytearray(0)
        r.read_fully(b)
        assert r.get_position() == 0
