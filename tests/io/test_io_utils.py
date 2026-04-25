from __future__ import annotations

import io

import pytest

from pypdfbox.io import close_quietly, copy, populate_buffer, to_byte_array


def test_copy_returns_total_bytes_and_writes_all() -> None:
    src = io.BytesIO(b"the quick brown fox")
    dst = io.BytesIO()
    n = copy(src, dst)
    assert n == 19
    assert dst.getvalue() == b"the quick brown fox"


def test_copy_with_small_buffer_handles_multiple_reads() -> None:
    src = io.BytesIO(b"abcdefghij")
    dst = io.BytesIO()
    n = copy(src, dst, buffer_size=3)
    assert n == 10
    assert dst.getvalue() == b"abcdefghij"


def test_copy_invalid_buffer_size_raises() -> None:
    with pytest.raises(ValueError):
        copy(io.BytesIO(b""), io.BytesIO(), buffer_size=0)


def test_to_byte_array_reads_all() -> None:
    src = io.BytesIO(b"\x00\x01\x02\xff")
    assert to_byte_array(src) == b"\x00\x01\x02\xff"


def test_to_byte_array_empty() -> None:
    assert to_byte_array(io.BytesIO(b"")) == b""


def test_close_quietly_closes() -> None:
    src = io.BytesIO(b"abc")
    close_quietly(src)
    assert src.closed


def test_close_quietly_none_is_noop() -> None:
    close_quietly(None)


def test_close_quietly_swallows_exceptions() -> None:
    class Bad:
        def close(self) -> None:
            raise RuntimeError("boom")

    close_quietly(Bad())  # must not raise


def test_populate_buffer_fills_completely() -> None:
    src = io.BytesIO(b"abcdef")
    buf = bytearray(6)
    n = populate_buffer(src, buf)
    assert n == 6
    assert bytes(buf) == b"abcdef"


def test_populate_buffer_partial_at_eof() -> None:
    src = io.BytesIO(b"abc")
    buf = bytearray(10)
    n = populate_buffer(src, buf)
    assert n == 3
    assert bytes(buf[:3]) == b"abc"


def test_populate_buffer_handles_short_reads() -> None:
    """A stream that returns small chunks should still completely fill the buffer."""

    class Drip(io.BytesIO):
        def read(self, size: int = -1) -> bytes:  # type: ignore[override]
            return super().read(min(size, 1) if size > 0 else size)

    src = Drip(b"abcdef")
    buf = bytearray(6)
    n = populate_buffer(src, buf)
    assert n == 6
    assert bytes(buf) == b"abcdef"
