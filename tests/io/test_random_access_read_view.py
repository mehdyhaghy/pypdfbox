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


def test_seek_negative_raises() -> None:
    p = _parent()
    v = RandomAccessReadView(p, start_position=2, length=4)
    with pytest.raises(OSError):
        v.seek(-1)


def test_seek_past_end_clamps_to_eof() -> None:
    p = _parent()
    v = RandomAccessReadView(p, start_position=2, length=4)
    v.seek(99)
    assert v.is_eof()
    assert v.get_position() == 4


def test_construction_validates_bounds() -> None:
    p = _parent()
    with pytest.raises(ValueError):
        RandomAccessReadView(p, start_position=-1, length=2)
    with pytest.raises(ValueError):
        RandomAccessReadView(p, start_position=0, length=-1)


def test_construction_allows_view_past_parent_end() -> None:
    # Upstream PDFBox does not validate: view length is a logical window
    # and reads simply return -1 once the parent reaches EOF.
    p = _parent()  # 10 bytes
    v = RandomAccessReadView(p, start_position=8, length=10)
    assert v.length() == 10
    # Only 2 bytes are actually readable from parent[8:].
    buf = bytearray(10)
    n = v.read_into(buf)
    assert n == 2
    assert bytes(buf[:2]) == b"ij"


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


def test_view_of_view_is_forbidden() -> None:
    # Upstream PDFBox raises IOException when create_view is invoked on a view.
    p = _parent()
    v1 = p.create_view(2, 6)
    with pytest.raises(OSError):
        v1.create_view(1, 4)


def test_camelcase_aliases_on_view() -> None:
    # The Java aliases (getPosition / isEOF / isClosed / createView) are
    # inherited from the RandomAccessRead ABC and must work on the view too.
    p = _parent()
    v = RandomAccessReadView(p, start_position=2, length=4)
    assert v.getPosition() == 0
    assert not v.isEOF()
    assert not v.isClosed()
    v.seek(4)
    assert v.isEOF()
    # createView on a view is forbidden upstream — the alias preserves that.
    with pytest.raises(OSError):
        v.createView(0, 1)
