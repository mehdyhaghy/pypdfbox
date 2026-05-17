"""Smoke + coverage tests for :class:`ConnectedInputStream`."""

from __future__ import annotations

import io

import pytest

from pypdfbox.examples.util.connected_input_stream import ConnectedInputStream


class _FakeConnection:
    """Mimics ``HttpURLConnection`` — exposes ``disconnect``."""

    def __init__(self) -> None:
        self.disconnected = False

    def disconnect(self) -> None:
        self.disconnected = True


class _CloseOnlyConnection:
    """Connection-like object that exposes ``close`` rather than ``disconnect``.

    Exercises the ``close()`` fallback branch in :meth:`ConnectedInputStream.close`.
    """

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _InertConnection:
    """Connection-like object with neither ``disconnect`` nor ``close``."""


class _AvailableStream(io.BytesIO):
    """``BytesIO`` extended with a Java-style ``available()`` method."""

    def available(self) -> int:
        return len(self.getvalue()) - self.tell()


# ---------------------------------------------------------------------------
# Construction / context manager
# ---------------------------------------------------------------------------


def test_close_disconnects_connection() -> None:
    payload = io.BytesIO(b"hello world")
    con = _FakeConnection()
    with ConnectedInputStream(con, payload):
        pass
    assert con.disconnected is True


def test_close_falls_back_to_close_method() -> None:
    payload = io.BytesIO(b"x")
    con = _CloseOnlyConnection()
    with ConnectedInputStream(con, payload):
        pass
    assert con.closed is True


def test_close_tolerates_inert_connection() -> None:
    # Should not raise even when neither disconnect nor close is callable.
    cis = ConnectedInputStream(_InertConnection(), io.BytesIO(b"x"))
    cis.close()


# ---------------------------------------------------------------------------
# read() — three overloads
# ---------------------------------------------------------------------------


def test_read_single_byte_returns_int() -> None:
    payload = io.BytesIO(b"AB")
    cis = ConnectedInputStream(_FakeConnection(), payload)
    assert cis.read() == ord("A")
    assert cis.read() == ord("B")
    # EOF: third read returns -1.
    assert cis.read() == -1


def test_read_into_buffer_returns_count() -> None:
    payload = io.BytesIO(b"abc")
    cis = ConnectedInputStream(_FakeConnection(), payload)
    buf = bytearray(3)
    n = cis.read(buf)
    assert n == 3
    assert buf == b"abc"


def test_read_into_empty_stream_returns_minus_one() -> None:
    payload = io.BytesIO(b"")
    cis = ConnectedInputStream(_FakeConnection(), payload)
    buf = bytearray(4)
    assert cis.read(buf) == -1


def test_read_with_offset_and_length() -> None:
    payload = io.BytesIO(b"abcdef")
    cis = ConnectedInputStream(_FakeConnection(), payload)
    buf = bytearray(6)
    n = cis.read(buf, 2, 3)
    assert n == 3
    assert buf[:2] == b"\x00\x00"
    assert buf[2:5] == b"abc"
    assert buf[5:] == b"\x00"


def test_read_with_len_at_eof_returns_minus_one() -> None:
    payload = io.BytesIO(b"")
    cis = ConnectedInputStream(_FakeConnection(), payload)
    buf = bytearray(3)
    assert cis.read(buf, 0, 3) == -1


# ---------------------------------------------------------------------------
# skip
# ---------------------------------------------------------------------------


def test_skip_seekable_advances_position() -> None:
    payload = io.BytesIO(b"0123456789")
    cis = ConnectedInputStream(_FakeConnection(), payload)
    assert cis.skip(4) == 4
    assert payload.tell() == 4


def test_skip_non_seekable_consumes_via_read() -> None:
    class _NonSeekable:
        """Stream-like object without ``seek`` — falls back to ``read``."""

        def __init__(self, data: bytes) -> None:
            self._data = data
            self._pos = 0
            self.consumed = 0

        def read(self, n: int = -1) -> bytes:
            chunk = self._data[self._pos : self._pos + n]
            self._pos += len(chunk)
            self.consumed += len(chunk)
            return chunk

        def close(self) -> None:
            pass

    stream = _NonSeekable(b"0123456789")
    cis = ConnectedInputStream(_FakeConnection(), stream)  # type: ignore[arg-type]
    assert cis.skip(5) == 5
    assert stream.consumed == 5


# ---------------------------------------------------------------------------
# available
# ---------------------------------------------------------------------------


def test_available_zero_when_unsupported() -> None:
    cis = ConnectedInputStream(_FakeConnection(), io.BytesIO(b"abc"))
    assert cis.available() == 0


def test_available_delegates_when_supported() -> None:
    cis = ConnectedInputStream(_FakeConnection(), _AvailableStream(b"abcdef"))
    assert cis.available() == 6


# ---------------------------------------------------------------------------
# mark / reset / mark_supported
# ---------------------------------------------------------------------------


def test_mark_and_reset_round_trip() -> None:
    payload = io.BytesIO(b"abcdef")
    cis = ConnectedInputStream(_FakeConnection(), payload)
    payload.read(2)  # advance to position 2
    cis.mark(10)
    payload.read(2)  # advance to 4
    cis.reset()
    assert payload.tell() == 2


def test_reset_without_mark_raises() -> None:
    cis = ConnectedInputStream(_FakeConnection(), io.BytesIO(b"abc"))
    with pytest.raises(OSError, match="mark not set"):
        cis.reset()


def test_mark_supported_for_seekable() -> None:
    cis = ConnectedInputStream(_FakeConnection(), io.BytesIO(b"x"))
    assert cis.mark_supported() is True


def test_mark_supported_false_for_non_seekable() -> None:
    class _NoSeek:
        def read(self, n: int = -1) -> bytes:
            return b""

        def close(self) -> None:
            pass

    cis = ConnectedInputStream(_FakeConnection(), _NoSeek())  # type: ignore[arg-type]
    assert cis.mark_supported() is False


def test_mark_with_non_tell_stream_records_none_position() -> None:
    class _NoTell:
        def read(self, n: int = -1) -> bytes:
            return b""

        def close(self) -> None:
            pass

    cis = ConnectedInputStream(_FakeConnection(), _NoTell())  # type: ignore[arg-type]
    cis.mark(5)
    # ``_mark_position`` is None → reset() should raise.
    with pytest.raises(OSError, match="mark not set"):
        cis.reset()
