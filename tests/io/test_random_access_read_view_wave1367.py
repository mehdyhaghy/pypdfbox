"""Wave 1367 — :class:`RandomAccessReadView` boundary coverage.

Targets branches in :mod:`pypdfbox.io.random_access_read_view` that
existing tests miss: nested-view rejection, parent-EOF before view-EOF,
``read_into(buf, 0, 0)`` zero-length probe semantics, ``rewind`` arithmetic
against the parent, ``close_input=True`` propagation, and the legacy
``close_parent=`` kwarg alias.
"""

from __future__ import annotations

import pytest

from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.io.random_access_read_view import RandomAccessReadView


def _make_view(data: bytes, start: int, length: int, **kw: object) -> RandomAccessReadView:
    parent = RandomAccessReadBuffer(data)
    return RandomAccessReadView(parent, start, length, **kw)  # type: ignore[arg-type]


def test_negative_start_position_raises() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    with pytest.raises(ValueError):
        RandomAccessReadView(rar, -1, 2)


def test_negative_stream_length_raises() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    with pytest.raises(ValueError):
        RandomAccessReadView(rar, 0, -1)


def test_seek_negative_raises_oserror() -> None:
    v = _make_view(b"abcdef", 1, 4)
    with pytest.raises(OSError):
        v.seek(-1)


def test_seek_past_view_end_clamps_parent_to_view_end() -> None:
    v = _make_view(b"abcdef", 1, 3)  # window = "bcd"
    v.seek(99)
    # current_position reflects the requested offset (mirrors upstream).
    assert v.get_position() == 99
    assert v.is_eof() is True
    assert v.read() == v.EOF


def test_read_into_zero_length_returns_zero_at_eof() -> None:
    v = _make_view(b"abc", 0, 3)
    v.seek(3)
    assert v.read_into(bytearray(4), 0, 0) == 0


def test_read_into_negative_length_raises() -> None:
    v = _make_view(b"abc", 0, 3)
    with pytest.raises(ValueError):
        v.read_into(bytearray(4), 0, -1)


def test_read_into_bad_offset_raises() -> None:
    v = _make_view(b"abc", 0, 3)
    with pytest.raises(ValueError):
        v.read_into(bytearray(2), 0, 3)


def test_read_into_clipped_to_available() -> None:
    v = _make_view(b"abcdef", 2, 3)  # "cde"
    v.seek(1)
    out = bytearray(10)
    n = v.read_into(out)
    assert n == 2  # remaining inside the view
    assert bytes(out[:2]) == b"de"


def test_view_beyond_parent_length_returns_parent_eof() -> None:
    # View claims 100 bytes but parent only has 4.
    v = _make_view(b"abcd", 0, 100)
    out = bytearray(50)
    n = v.read_into(out)
    # First read returns whatever the parent yields (4 bytes).
    assert n == 4
    assert bytes(out[:4]) == b"abcd"


def test_rewind_keeps_parent_in_sync() -> None:
    v = _make_view(b"0123456789", 2, 6)  # window = "234567"
    out = bytearray(4)
    v.read_into(out)  # read "2345", pos=4
    v.rewind(2)  # pos=2
    assert v.get_position() == 2
    out2 = bytearray(2)
    n = v.read_into(out2)
    assert n == 2
    assert bytes(out2) == b"45"


def test_close_input_true_closes_parent() -> None:
    parent = RandomAccessReadBuffer(b"abc")
    v = RandomAccessReadView(parent, 0, 3, close_input=True)
    v.close()
    assert parent.is_closed() is True
    assert v.is_closed() is True


def test_close_input_false_leaves_parent_open() -> None:
    parent = RandomAccessReadBuffer(b"abc")
    v = RandomAccessReadView(parent, 0, 3, close_input=False)
    v.close()
    assert parent.is_closed() is False


def test_close_parent_kwarg_alias_takes_precedence() -> None:
    # close_parent=True overrides the default close_input=False.
    parent = RandomAccessReadBuffer(b"abc")
    v = RandomAccessReadView(parent, 0, 3, close_parent=True)
    v.close()
    assert parent.is_closed() is True


def test_nested_create_view_raises() -> None:
    v = _make_view(b"abcdef", 0, 6)
    with pytest.raises(OSError):
        v.create_view(0, 2)


def test_operations_after_close_raise() -> None:
    v = _make_view(b"abc", 0, 3, close_input=True)
    v.close()
    with pytest.raises(OSError):
        v.get_position()
    with pytest.raises(OSError):
        v.seek(0)
    with pytest.raises(OSError):
        v.length()
    with pytest.raises(OSError):
        v.is_eof()
    with pytest.raises(OSError):
        v.rewind(0)


def test_read_single_byte_eof() -> None:
    v = _make_view(b"a", 0, 1)
    assert v.read() == ord("a")
    assert v.read() == v.EOF


def test_read_advances_only_when_byte_returned() -> None:
    # Parent shorter than the view length; once parent EOFs, the view does too.
    v = _make_view(b"ab", 0, 4)
    assert v.read() == ord("a")
    assert v.read() == ord("b")
    # Parent EOF; view should return -1, position unchanged.
    pos_before = v.get_position()
    assert v.read() == v.EOF
    assert v.get_position() == pos_before


def test_length_after_close_raises_via_parent_closed() -> None:
    parent = RandomAccessReadBuffer(b"abc")
    v = RandomAccessReadView(parent, 0, 3)
    parent.close()
    # View follows parent closed state.
    assert v.is_closed() is True
    with pytest.raises(OSError):
        v.length()
