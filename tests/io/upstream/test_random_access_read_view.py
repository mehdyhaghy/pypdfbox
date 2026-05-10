"""
Ported from
io/src/test/java/org/apache/pdfbox/io/RandomAccessReadViewTest.java
(Apache PDFBox 3.0).
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.io import RandomAccessReadBuffer, RandomAccessReadView


def _values() -> bytes:
    # 0..20 inclusive
    return bytes(range(21))


def test_position_skip() -> None:
    with (
        RandomAccessReadBuffer(io.BytesIO(_values())) as parent,
        RandomAccessReadView(parent, 10, 20) as view,
    ):
        assert view.get_position() == 0
        assert view.peek() == 10
        view.skip(5)
        assert view.get_position() == 5
        assert view.peek() == 15


def test_position_read() -> None:
    with RandomAccessReadBuffer(io.BytesIO(_values())) as parent:
        view = RandomAccessReadView(parent, 10, 20)
        assert view.get_position() == 0
        assert view.read() == 10
        assert view.read() == 11
        assert view.read() == 12
        assert view.get_position() == 3
        # also test double close
        assert not view.is_closed()
        view.close()
        assert view.is_closed()
        view.close()  # idempotent


def test_seek_eof() -> None:
    parent = RandomAccessReadBuffer(io.BytesIO(_values()))
    view = RandomAccessReadView(parent, 10, 20)
    view.seek(3)
    assert view.get_position() == 3
    with pytest.raises(OSError):
        view.seek(-1)
    assert not view.is_eof()
    view.seek(20)
    assert view.is_eof()
    assert view.read() == -1
    assert view.read_into(bytearray(1), 0, 1) == -1
    view.close()
    parent.close()
    with pytest.raises(OSError):
        view.read()


def test_position_read_bytes() -> None:
    with (
        RandomAccessReadBuffer(io.BytesIO(_values())) as parent,
        RandomAccessReadView(parent, 10, 20) as view,
    ):
        assert view.get_position() == 0
        buf = bytearray(4)
        view.read_into(buf)
        assert buf[0] == 10
        assert buf[3] == 13
        assert view.get_position() == 4

        view.read_into(buf, 1, 2)
        assert buf[0] == 10
        assert buf[1] == 14
        assert buf[2] == 15
        assert buf[3] == 13
        assert view.get_position() == 6


def test_position_peek() -> None:
    with (
        RandomAccessReadBuffer(io.BytesIO(_values())) as parent,
        RandomAccessReadView(parent, 10, 20) as view,
    ):
        assert view.get_position() == 0
        view.skip(6)
        assert view.get_position() == 6
        assert view.peek() == 16
        assert view.get_position() == 6


def test_position_unread_bytes() -> None:
    with (
        RandomAccessReadBuffer(io.BytesIO(_values())) as parent,
        RandomAccessReadView(parent, 10, 20) as view,
    ):
        assert view.get_position() == 0
        view.read()
        view.read()
        read_bytes = bytearray(6)
        assert view.read_into(read_bytes) == len(read_bytes)
        assert view.get_position() == 8
        view.rewind(len(read_bytes))
        assert view.get_position() == 2
        assert view.read() == 12
        assert view.get_position() == 3
        view.read_into(read_bytes, 2, 4)
        assert read_bytes[0] == 12
        assert read_bytes[2] == 13
        assert read_bytes[5] == 16
        assert view.get_position() == 7
        view.rewind(4)
        assert view.get_position() == 3


def test_create_view() -> None:
    with (
        RandomAccessReadBuffer(io.BytesIO(_values())) as parent,
        RandomAccessReadView(parent, 10, 20) as view,
        pytest.raises(OSError),
    ):
        view.create_view(0, 20)
