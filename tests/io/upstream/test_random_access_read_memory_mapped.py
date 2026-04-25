"""
Ported from
io/src/test/java/org/apache/pdfbox/io/RandomAccessReadMemoryMappedFileTest.java
(Apache PDFBox 3.0).

pypdfbox's class is named ``RandomAccessReadMemoryMapped`` (no trailing
``File``); upstream uses ``RandomAccessReadMemoryMappedFile``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.io import RandomAccessReadMemoryMapped

_FIXTURES = Path(__file__).parent / "fixtures"
_FILE1 = _FIXTURES / "RandomAccessReadFile1.txt"
_EMPTY = _FIXTURES / "RandomAccessReadEmptyFile.txt"


def test_position_skip() -> None:
    with RandomAccessReadMemoryMapped(_FILE1) as r:
        assert r.get_position() == 0
        r.skip(5)
        assert r.read() == ord("5")
        assert r.get_position() == 6


def test_path_constructor() -> None:
    with RandomAccessReadMemoryMapped(_FILE1) as r:
        assert r.length() == 130


def test_position_read() -> None:
    r = RandomAccessReadMemoryMapped(_FILE1)
    assert r.get_position() == 0
    assert r.read() == ord("0")
    assert r.read() == ord("1")
    assert r.read() == ord("2")
    assert r.get_position() == 3
    assert not r.is_closed()
    r.close()
    assert r.is_closed()


def test_seek_eof() -> None:
    r = RandomAccessReadMemoryMapped(_FILE1)
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
    with RandomAccessReadMemoryMapped(_FILE1) as r:
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
    with RandomAccessReadMemoryMapped(_FILE1) as r:
        assert r.get_position() == 0
        r.skip(6)
        assert r.get_position() == 6
        assert r.peek() == ord("6")
        assert r.get_position() == 6


def test_position_unread_bytes() -> None:
    with RandomAccessReadMemoryMapped(_FILE1) as r:
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
    with RandomAccessReadMemoryMapped(_EMPTY) as r:
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


def test_unmapping(tmp_path: Path) -> None:
    # Upstream PDFBOX special case for Windows mmap-unmapping bug
    # (https://bugs.openjdk.java.net/browse/JDK-4724038). We exercise the same
    # construct/read/close cycle.
    p = tmp_path / "pdfbox_unmap.txt"
    p.write_text("Apache PDFBox test", encoding="ascii")
    with RandomAccessReadMemoryMapped(p) as r:
        assert r.read() == ord("A")  # 65


def test_view() -> None:
    with (
        RandomAccessReadMemoryMapped(_FILE1) as r,
        r.create_view(3, 10) as view,
    ):
        assert view.get_position() == 0
        assert view.read() == ord("3")
        assert view.read() == ord("4")
        assert view.read() == ord("5")
        assert view.get_position() == 3
