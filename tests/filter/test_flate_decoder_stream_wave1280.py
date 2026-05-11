"""Tests for :class:`FlateFilterDecoderStream`."""

from __future__ import annotations

import io
import zlib

import pytest

from pypdfbox.filter import FlateFilterDecoderStream


def _compress(data: bytes) -> bytes:
    return zlib.compress(data)


class TestFlateFilterDecoderStream:
    def test_read_all_roundtrip(self) -> None:
        raw = b"the quick brown fox jumps over the lazy dog" * 25
        stream = FlateFilterDecoderStream(io.BytesIO(_compress(raw)))
        assert stream.read() == raw

    def test_read_sized_chunks(self) -> None:
        raw = b"abc" * 100
        stream = FlateFilterDecoderStream(io.BytesIO(_compress(raw)))
        out = bytearray()
        while True:
            chunk = stream.read(32)
            if not chunk:
                break
            out.extend(chunk)
        assert bytes(out) == raw

    def test_read_after_eof_returns_empty(self) -> None:
        raw = b"hello"
        stream = FlateFilterDecoderStream(io.BytesIO(_compress(raw)))
        assert stream.read() == raw
        assert stream.read() == b""

    def test_readinto(self) -> None:
        raw = b"0123456789" * 10
        stream = FlateFilterDecoderStream(io.BytesIO(_compress(raw)))
        buf = bytearray(50)
        n = stream.readinto(buf)
        assert n == 50
        assert bytes(buf) == raw[:50]

    def test_short_truncated_stream_does_not_raise(self) -> None:
        raw = b"hello world" * 10
        comp = _compress(raw)
        # Cut off the final adler32; with nowrap mode that data is already
        # stripped, but truncating mid-deflate stream should be tolerated
        # gracefully (warning, no exception).
        truncated = comp[:-5]
        stream = FlateFilterDecoderStream(io.BytesIO(truncated))
        # No exception; some prefix of the data should come back.
        got = stream.read()
        assert isinstance(got, (bytes, bytearray))

    def test_mark_supported_false(self) -> None:
        s = FlateFilterDecoderStream(io.BytesIO(_compress(b"x")))
        assert s.mark_supported() is False

    def test_reset_raises(self) -> None:
        s = FlateFilterDecoderStream(io.BytesIO(_compress(b"x")))
        with pytest.raises(OSError):
            s.reset()

    def test_skip_zero(self) -> None:
        s = FlateFilterDecoderStream(io.BytesIO(_compress(b"x")))
        assert s.skip(10) == 0

    def test_available_zero(self) -> None:
        s = FlateFilterDecoderStream(io.BytesIO(_compress(b"x")))
        assert s.available() == 0
