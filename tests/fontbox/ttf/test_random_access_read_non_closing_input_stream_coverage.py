"""Coverage-boost tests for
``pypdfbox.fontbox.ttf.random_access_read_non_closing_input_stream``
(wave 1318).

Pre-wave the module sat at 63%. Uncovered surface was:
  * ``readable`` reporting True,
  * ``read(0)`` early-return,
  * ``readinto`` against a raw ``bytearray`` (no memoryview indirection),
  * ``readinto`` against a memoryview that does NOT alias a full
    bytearray (the temp-copy branch),
  * ``readinto`` against a memoryview that DOES alias a bytearray (the
    fast in-place branch),
  * ``readinto`` short read returning 0,
  * ``seek`` with ``SEEK_CUR`` / ``SEEK_END`` whences, negative clamp,
    invalid whence,
  * ``skip`` no-op for non-positive ``n``,
  * ``skip`` clamped to the underlying stream's remaining length,
  * ``seekable`` reporting True,
  * ``close`` not propagating to the underlying read.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.fontbox.ttf.random_access_read_non_closing_input_stream import (
    RandomAccessReadNonClosingInputStream,
)
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

PAYLOAD = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # 26 bytes


def _wrap(data: bytes = PAYLOAD) -> RandomAccessReadNonClosingInputStream:
    return RandomAccessReadNonClosingInputStream(RandomAccessReadBuffer(data))


# ---------------------------------------------------------------------------
# stdlib flags
# ---------------------------------------------------------------------------
def test_readable_reports_true() -> None:
    assert _wrap().readable() is True


def test_seekable_reports_true() -> None:
    assert _wrap().seekable() is True


# ---------------------------------------------------------------------------
# read() variants
# ---------------------------------------------------------------------------
def test_read_full_remaining_when_size_negative() -> None:
    s = _wrap()
    out = s.read(-1)
    assert out == PAYLOAD


def test_read_none_size_returns_full_remaining() -> None:
    s = _wrap()
    out = s.read(None)  # type: ignore[arg-type]
    assert out == PAYLOAD


def test_read_negative_returns_empty_when_already_at_end() -> None:
    s = _wrap()
    s.seek(0, io.SEEK_END)
    assert s.read(-1) == b""


def test_read_zero_size_returns_empty() -> None:
    s = _wrap()
    assert s.read(0) == b""


def test_read_fixed_size_returns_exact_slice() -> None:
    s = _wrap()
    assert s.read(5) == b"ABCDE"
    assert s.tell() == 5


def test_read_at_eof_returns_empty() -> None:
    s = _wrap(b"abc")
    s.read(3)
    assert s.read(10) == b""


# ---------------------------------------------------------------------------
# readinto() variants
# ---------------------------------------------------------------------------
def test_readinto_bytearray_directly() -> None:
    s = _wrap()
    buf = bytearray(6)
    n = s.readinto(buf)
    assert n == 6
    assert bytes(buf) == b"ABCDEF"


def test_readinto_memoryview_aliasing_bytearray_fast_path() -> None:
    s = _wrap()
    buf = bytearray(7)
    mv = memoryview(buf)
    n = s.readinto(mv)
    assert n == 7
    assert bytes(buf) == b"ABCDEFG"


def test_readinto_memoryview_slice_takes_temp_copy_branch() -> None:
    s = _wrap()
    outer = bytearray(10)
    mv = memoryview(outer)[2:6]  # 4 bytes, not full alias
    n = s.readinto(mv)
    assert n == 4
    assert bytes(outer[2:6]) == b"ABCD"


def test_readinto_returns_zero_when_at_eof() -> None:
    s = _wrap(b"")
    buf = bytearray(4)
    assert s.readinto(buf) == 0


def test_readinto_memoryview_at_eof_returns_zero() -> None:
    s = _wrap(b"")
    outer = bytearray(8)
    mv = memoryview(outer)[0:4]
    assert s.readinto(mv) == 0


# ---------------------------------------------------------------------------
# seek() variants
# ---------------------------------------------------------------------------
def test_seek_set_returns_target_position() -> None:
    s = _wrap()
    assert s.seek(5, io.SEEK_SET) == 5
    assert s.tell() == 5


def test_seek_cur_advances_from_current() -> None:
    s = _wrap()
    s.read(3)
    pos = s.seek(2, io.SEEK_CUR)
    assert pos == 5
    assert s.tell() == 5


def test_seek_cur_backwards() -> None:
    s = _wrap()
    s.read(10)
    pos = s.seek(-4, io.SEEK_CUR)
    assert pos == 6
    assert s.read(2) == b"GH"


def test_seek_end_uses_total_length() -> None:
    s = _wrap()
    pos = s.seek(0, io.SEEK_END)
    assert pos == len(PAYLOAD)
    assert s.read(1) == b""


def test_seek_end_with_negative_offset() -> None:
    s = _wrap()
    pos = s.seek(-3, io.SEEK_END)
    assert pos == len(PAYLOAD) - 3
    assert s.read(3) == b"XYZ"


def test_seek_negative_target_is_clamped_to_zero() -> None:
    s = _wrap()
    pos = s.seek(-99, io.SEEK_SET)
    assert pos == 0
    assert s.read(2) == b"AB"


def test_seek_invalid_whence_raises_value_error() -> None:
    s = _wrap()
    with pytest.raises(ValueError, match="unsupported whence"):
        s.seek(0, 99)


# ---------------------------------------------------------------------------
# skip()
# ---------------------------------------------------------------------------
def test_skip_zero_returns_zero() -> None:
    s = _wrap()
    assert s.skip(0) == 0
    assert s.tell() == 0


def test_skip_negative_returns_zero() -> None:
    s = _wrap()
    assert s.skip(-5) == 0


def test_skip_advances_position_by_n() -> None:
    s = _wrap()
    skipped = s.skip(5)
    assert skipped == 5
    assert s.read(2) == b"FG"


def test_skip_clamped_to_remaining_bytes() -> None:
    s = _wrap()
    s.read(20)
    skipped = s.skip(100)
    assert skipped == len(PAYLOAD) - 20
    assert s.read(1) == b""


def test_skip_at_eof_returns_zero() -> None:
    s = _wrap()
    s.seek(0, io.SEEK_END)
    assert s.skip(10) == 0


# ---------------------------------------------------------------------------
# close() — non-propagating
# ---------------------------------------------------------------------------
def test_close_does_not_close_underlying_random_access_read() -> None:
    backing = RandomAccessReadBuffer(PAYLOAD)
    s = RandomAccessReadNonClosingInputStream(backing)
    s.close()
    assert s.closed is True
    # The underlying ``RandomAccessReadBuffer`` exposes ``is_closed``;
    # verify it is still open after the stream wrapper was closed.
    assert backing.is_closed() is False
    # And callers can still use the underlying read directly.
    backing.seek(0)
    assert backing.read() == ord("A")


# ---------------------------------------------------------------------------
# tell()
# ---------------------------------------------------------------------------
def test_tell_reflects_underlying_position() -> None:
    s = _wrap()
    assert s.tell() == 0
    s.read(4)
    assert s.tell() == 4
