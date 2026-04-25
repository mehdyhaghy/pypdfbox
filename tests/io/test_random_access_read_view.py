from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadBuffer, RandomAccessReadView


def _parent(data: bytes = b"abcdefghij") -> RandomAccessReadBuffer:
    return RandomAccessReadBuffer(data)


def test_basic_read_within_view() -> None:
    p = _parent()
    v = RandomAccessReadView(p, start_position=2, length=4)  # b"cdef"
    assert v.length() == 4
    assert v.read() == ord("c")
    assert v.read() == ord("d")
    assert v.get_position() == 2


def test_read_into_within_view() -> None:
    p = _parent()
    v = RandomAccessReadView(p, start_position=3, length=5)  # b"defgh"
    buf = bytearray(10)
    n = v.read_into(buf, offset=0, length=5)
    assert n == 5
    assert bytes(buf[:5]) == b"defgh"


def test_read_into_clipped_at_view_end() -> None:
    p = _parent()
    v = RandomAccessReadView(p, start_position=8, length=2)  # b"ij"
    buf = bytearray(10)
    n = v.read_into(buf)
    assert n == 2
    assert bytes(buf[:2]) == b"ij"


def test_read_at_eof_returns_minus_one() -> None:
    p = _parent()
    v = RandomAccessReadView(p, start_position=0, length=3)
    v.seek(3)
    assert v.read() == -1


def test_seek_within_view() -> None:
    p = _parent()
    v = RandomAccessReadView(p, start_position=2, length=4)
    v.seek(3)
    assert v.read() == ord("f")


def test_seek_out_of_view_range_raises() -> None:
    p = _parent()
    v = RandomAccessReadView(p, start_position=2, length=4)
    with pytest.raises(ValueError):
        v.seek(-1)
    with pytest.raises(ValueError):
        v.seek(5)


def test_construction_validates_bounds() -> None:
    p = _parent()
    with pytest.raises(ValueError):
        RandomAccessReadView(p, start_position=-1, length=2)
    with pytest.raises(ValueError):
        RandomAccessReadView(p, start_position=0, length=-1)
    with pytest.raises(ValueError):
        RandomAccessReadView(p, start_position=8, length=10)  # past end


def test_close_does_not_close_parent_by_default() -> None:
    p = _parent()
    v = RandomAccessReadView(p, start_position=0, length=3)
    v.close()
    assert v.is_closed()
    assert not p.is_closed()


def test_close_propagates_when_close_parent_true() -> None:
    p = _parent()
    v = RandomAccessReadView(p, 0, 3, close_parent=True)
    v.close()
    assert p.is_closed()


def test_create_view_factory_on_abc() -> None:
    p = _parent()
    v = p.create_view(2, 4)
    assert v.length() == 4
    assert v.read() == ord("c")


def test_view_of_view() -> None:
    p = _parent()  # b"abcdefghij"
    v1 = p.create_view(2, 6)  # b"cdefgh"
    v2 = v1.create_view(1, 4)  # b"defg"
    assert v2.length() == 4
    buf = bytearray(4)
    assert v2.read_into(buf) == 4
    assert bytes(buf) == b"defg"
