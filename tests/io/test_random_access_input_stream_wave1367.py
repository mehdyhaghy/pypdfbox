"""Wave 1367 — :class:`RandomAccessInputStream` adapter edge cases.

Targets read-to-EOF semantics, ``read(-1)`` slurp, ``available()``
clamping behaviour, ``skip`` past EOF, ``readinto(memoryview)`` round-trip,
and the EOF logging path.
"""

from __future__ import annotations

import io
import logging

import pytest

from pypdfbox.io.random_access_input_stream import RandomAccessInputStream
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer


def test_read_negative_size_returns_all_remaining() -> None:
    rar = RandomAccessReadBuffer(b"hello world")
    stream = RandomAccessInputStream(rar)
    assert stream.read(-1) == b"hello world"
    assert stream.tell() == 11


def test_read_none_size_returns_all_remaining() -> None:
    rar = RandomAccessReadBuffer(b"x" * 10_000)
    stream = RandomAccessInputStream(rar)
    out = stream.read(None)  # type: ignore[arg-type]
    assert out == b"x" * 10_000


def test_read_zero_returns_empty_bytes() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    stream = RandomAccessInputStream(rar)
    assert stream.read(0) == b""
    assert stream.tell() == 0


def test_read_at_eof_returns_empty_bytes() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    stream = RandomAccessInputStream(rar)
    stream.read(-1)  # drain
    assert stream.read(8) == b""


def test_available_reports_remaining_bytes() -> None:
    rar = RandomAccessReadBuffer(b"abcdef")
    stream = RandomAccessInputStream(rar)
    assert stream.available() == 6
    stream.read(2)
    assert stream.available() == 4
    stream.read(-1)
    assert stream.available() == 0


def test_available_on_closed_parent_returns_zero() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    stream = RandomAccessInputStream(rar)
    rar.close()
    assert stream.available() == 0


def test_skip_advances_position() -> None:
    rar = RandomAccessReadBuffer(b"0123456789")
    stream = RandomAccessInputStream(rar)
    assert stream.skip(3) == 3
    assert stream.tell() == 3
    assert stream.read(2) == b"34"


def test_skip_zero_or_negative_returns_zero() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    stream = RandomAccessInputStream(rar)
    assert stream.skip(0) == 0
    assert stream.skip(-5) == 0
    assert stream.tell() == 0


def test_readinto_bytearray() -> None:
    rar = RandomAccessReadBuffer(b"abcdef")
    stream = RandomAccessInputStream(rar)
    out = bytearray(4)
    assert stream.readinto(out) == 4
    assert bytes(out) == b"abcd"


def test_readinto_memoryview_roundtrips() -> None:
    rar = RandomAccessReadBuffer(b"abcdef")
    stream = RandomAccessInputStream(rar)
    out = bytearray(4)
    mv = memoryview(out)
    n = stream.readinto(mv)
    assert n == 4
    assert bytes(out) == b"abcd"


def test_readinto_at_eof_returns_zero_not_eof() -> None:
    rar = RandomAccessReadBuffer(b"ab")
    stream = RandomAccessInputStream(rar)
    stream.read(-1)
    # Python RawIOBase contract: readinto returns 0 at EOF, never -1.
    assert stream.readinto(bytearray(4)) == 0


def test_seekable_returns_false() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    stream = RandomAccessInputStream(rar)
    assert stream.seekable() is False


def test_readable_returns_true() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    stream = RandomAccessInputStream(rar)
    assert stream.readable() is True


def test_read_then_read_to_eof_concatenates() -> None:
    rar = RandomAccessReadBuffer(b"abcdefghij")
    stream = RandomAccessInputStream(rar)
    head = stream.read(3)
    tail = stream.read(-1)
    assert head + tail == b"abcdefghij"


def test_restore_position_seeks_parent() -> None:
    rar = RandomAccessReadBuffer(b"abcdef")
    stream = RandomAccessInputStream(rar)
    stream.read(2)
    # Move the parent away to simulate shared use.
    rar.seek(5)
    stream.restore_position()
    assert rar.get_position() == 2


def test_two_streams_share_parent_with_independent_positions() -> None:
    rar = RandomAccessReadBuffer(b"abcdef")
    a = RandomAccessInputStream(rar)
    b = RandomAccessInputStream(rar)
    assert a.read(2) == b"ab"
    assert b.read(3) == b"abc"
    assert a.read(2) == b"cd"


def test_eof_path_logs_error(caplog: pytest.LogCaptureFixture) -> None:
    """When the parent returns ``EOF`` mid-call, the stream logs the assumed/actual mismatch."""

    class StuckReader(RandomAccessReadBuffer):
        """Override ``read_into`` to always return ``EOF`` regardless of position."""

        def read_into(  # type: ignore[override]
            self, buf: bytearray, offset: int = 0, length: int | None = None
        ) -> int:
            return self.EOF

    parent = StuckReader(b"abcdef")
    stream = RandomAccessInputStream(parent)
    # is_eof() must report False for the log path to fire.
    assert parent.is_eof() is False
    with caplog.at_level(
        logging.ERROR, logger="pypdfbox.io.random_access_input_stream"
    ):
        stream.read(4)
    msgs = [r.getMessage() for r in caplog.records]
    assert any("read() returns -1" in m for m in msgs)


def test_underlying_bytesio_compat() -> None:
    """Plumb the adapter into an ``io.BufferedReader`` and read through it."""
    rar = RandomAccessReadBuffer(b"abcdef" * 100)
    stream = RandomAccessInputStream(rar)
    reader = io.BufferedReader(stream)  # type: ignore[arg-type]
    payload = reader.read()
    assert payload == b"abcdef" * 100
