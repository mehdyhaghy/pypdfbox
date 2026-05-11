"""Wave 1281: NonSeekableRandomAccessReadInputStream port."""

from __future__ import annotations

import io

import pytest

from pypdfbox.io import NonSeekableRandomAccessReadInputStream


def test_sequential_read() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"hello"))
    out = bytearray(5)
    n = raw.read_into(out)
    assert n == 5
    assert bytes(out) == b"hello"


def test_eof_returns_minus_one_single_byte() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b""))
    assert raw.read() == raw.EOF


def test_seek_unsupported() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"a"))
    with pytest.raises(OSError):
        raw.seek(0)


def test_skip_advances_position() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"abcdef"))
    raw.skip(3)
    assert raw.read() == ord("d")


def test_rewind_within_current_buffer() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"abcdef"))
    out = bytearray(4)
    raw.read_into(out)
    raw.rewind(2)
    out2 = bytearray(2)
    raw.read_into(out2)
    assert bytes(out2) == b"cd"


def test_create_view_unsupported() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"abc"))
    with pytest.raises(OSError):
        raw.create_view(0, 1)


def test_position_advances_with_read() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"abc"))
    raw.read()
    raw.read()
    assert raw.get_position() == 2
