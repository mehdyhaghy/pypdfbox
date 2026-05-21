from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadBuffer, RandomAccessReadView


def _parent(data: bytes = b"abcdefghij") -> RandomAccessReadBuffer:
    return RandomAccessReadBuffer(data)


def test_basic_read_within_view() -> None:
    p = _parent()
    v = RandomAccessReadView(p, 2, 4)  # b"cdef"
    assert v.length() == 4
    assert v.read() == ord("c")
    assert v.read() == ord("d")
    assert v.get_position() == 2


def test_read_into_within_view() -> None:
    p = _parent()
    v = RandomAccessReadView(p, 3, 5)  # b"defgh"
    buf = bytearray(10)
    n = v.read_into(buf, offset=0, length=5)
    assert n == 5
    assert bytes(buf[:5]) == b"defgh"


def test_read_into_clipped_at_view_end() -> None:
    p = _parent()
    v = RandomAccessReadView(p, 8, 2)  # b"ij"
    buf = bytearray(10)
    n = v.read_into(buf)
    assert n == 2
    assert bytes(buf[:2]) == b"ij"


def test_zero_length_read_into_is_noop_for_view() -> None:
    # Upstream Java's read(b, off, 0) returns 0 — zero-length probes should
    # not mutate the view position and should not be confused with EOF.
    p = _parent()
    v = RandomAccessReadView(p, 2, 4)
    v.seek(1)
    assert v.read_into(bytearray(), offset=0, length=0) == 0
    assert v.get_position() == 1


def test_read_at_eof_returns_minus_one() -> None:
    p = _parent()
    v = RandomAccessReadView(p, 0, 3)
    v.seek(3)
    assert v.read() == -1


def test_seek_within_view() -> None:
    p = _parent()
    v = RandomAccessReadView(p, 2, 4)
    v.seek(3)
    assert v.read() == ord("f")


def test_seek_negative_raises() -> None:
    p = _parent()
    v = RandomAccessReadView(p, 2, 4)
    with pytest.raises(OSError):
        v.seek(-1)


def test_seek_past_end_clamps_parent_but_view_keeps_offset() -> None:
    # Upstream behavior: parent gets clamped to start+streamLength but
    # currentPosition is set to the raw new_offset, leaving the view EOF.
    p = _parent()
    v = RandomAccessReadView(p, 2, 4)
    v.seek(99)
    assert v.is_eof()
    assert v.get_position() == 99


def test_construction_validates_bounds() -> None:
    p = _parent()
    with pytest.raises(ValueError):
        RandomAccessReadView(p, -1, 2)
    with pytest.raises(ValueError):
        RandomAccessReadView(p, 0, -1)


def test_construction_allows_view_past_parent_end() -> None:
    # Upstream PDFBox does not validate: view length is a logical window
    # and reads simply return -1 once the parent reaches EOF.
    p = _parent()  # 10 bytes
    v = RandomAccessReadView(p, 8, 10)
    assert v.length() == 10
    # Only 2 bytes are actually readable from parent[8:].
    buf = bytearray(10)
    n = v.read_into(buf)
    assert n == 2
    assert bytes(buf[:2]) == b"ij"


def test_close_does_not_close_parent_by_default() -> None:
    p = _parent()
    v = RandomAccessReadView(p, 0, 3)
    v.close()
    assert v.is_closed()
    assert not p.is_closed()


def test_close_propagates_when_close_input_true() -> None:
    p = _parent()
    v = RandomAccessReadView(p, 0, 3, close_input=True)
    v.close()
    assert p.is_closed()


def test_close_is_idempotent() -> None:
    p = _parent()
    v = RandomAccessReadView(p, 0, 3)
    v.close()
    v.close()  # must not raise
    assert v.is_closed()


def test_create_view_factory_on_abc_returns_view() -> None:
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


def test_rewind_overrides_base_and_keeps_parent_in_sync() -> None:
    # Upstream rewind override (line 165) seeks the parent before rewinding
    # so a view rewind is observable on the parent's cursor.
    p = _parent()
    v = RandomAccessReadView(p, 2, 6)
    v.read()
    v.read()
    v.read()
    assert v.get_position() == 3
    v.rewind(2)
    assert v.get_position() == 1
    # Parent should now sit at start_position + (3 - 2) - 1 = 2 since the
    # parent's own rewind moved it back by 2 from position 5 to position 3.
    # Reading the parent next yields 'd' (index 3 of the buffer).
    assert p.read() == ord("d")


def test_check_closed_helper_raises_after_close() -> None:
    p = _parent()
    v = RandomAccessReadView(p, 0, 3)
    v.close()
    with pytest.raises(OSError):
        v.check_closed()
    with pytest.raises(OSError):
        v.length()
    with pytest.raises(OSError):
        v.get_position()


def test_restore_position_seeks_parent_to_start_plus_current() -> None:
    p = _parent()
    v = RandomAccessReadView(p, 4, 4)
    v.seek(1)
    # Move the parent independently to confirm restore_position reseats it.
    p.seek(0)
    v.restore_position()
    assert p.get_position() == 5
