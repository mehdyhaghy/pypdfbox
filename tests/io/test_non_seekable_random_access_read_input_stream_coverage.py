"""Coverage-boost tests for ``NonSeekableRandomAccessReadInputStream``
(wave 1318).

Pre-wave the module sat at 61%. Uncovered surface was:
  * ``close`` / ``is_closed`` / ``check_closed`` lifecycle,
  * ``read_fully`` with both a pre-sized bytearray and an integer length,
  * ``length`` + ``available`` against a stream that exposes ``available``,
  * the salvage-fetch branch in ``_fetch`` (preserves last+current bytes
    when the underlying stream is about to EOF mid-buffer),
  * the multi-buffer rewind path (rewind into the previous buffer),
  * ``skip`` with a length larger than the buffer size,
  * the read EOF fall-through (read returns -1 after exhaustion),
  * the public ``switch_buffers`` / ``fetch`` aliases,
  * ``read_fully_int`` length-overload wrapper.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.io.non_seekable_random_access_read_input_stream import (
    _BUFFER_SIZE,
    NonSeekableRandomAccessReadInputStream,
)


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------
def test_close_marks_stream_closed_and_closes_underlying() -> None:
    underlying = io.BytesIO(b"abc")
    raw = NonSeekableRandomAccessReadInputStream(underlying)
    assert raw.is_closed() is False
    raw.close()
    assert raw.is_closed() is True
    assert underlying.closed is True


def test_operations_after_close_raise_oserror() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"abc"))
    raw.close()
    with pytest.raises(OSError, match="already closed"):
        raw.check_closed()
    with pytest.raises(OSError, match="already closed"):
        raw.get_position()
    with pytest.raises(OSError, match="already closed"):
        raw.read()


# ---------------------------------------------------------------------------
# read_fully overloads
# ---------------------------------------------------------------------------
def test_read_fully_into_bytearray_reads_all_bytes() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"hello world"))
    buf = bytearray(5)
    result = raw.read_fully(buf)
    assert result is None
    assert bytes(buf) == b"hello"


def test_read_fully_with_int_length_returns_bytes() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"abcdef"))
    out = raw.read_fully(4)
    assert out == b"abcd"


def test_read_fully_int_alias_returns_bytes() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"abcdef"))
    out = raw.read_fully_int(3)
    assert out == b"abc"


def test_read_fully_short_read_raises_eof_error() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"abc"))
    buf = bytearray(10)
    with pytest.raises(EOFError):
        raw.read_fully(buf)


# ---------------------------------------------------------------------------
# length / available
# ---------------------------------------------------------------------------
class _AvailableStream:
    """File-like stream that exposes Java-style ``available()`` for length()."""

    def __init__(self, data: bytes) -> None:
        self._buf = io.BytesIO(data)
        self._total = len(data)

    def readinto(self, target: bytearray) -> int:
        return self._buf.readinto(target)

    def read(self, *a: object, **kw: object) -> bytes:
        return self._buf.read(*a, **kw)

    def close(self) -> None:
        self._buf.close()

    def available(self) -> int:
        return self._total - self._buf.tell()


def test_length_uses_underlying_available_when_present() -> None:
    raw = NonSeekableRandomAccessReadInputStream(_AvailableStream(b"abc" * 10))
    # Nothing buffered yet: full length should equal available() result.
    assert raw.length() == 30


def test_available_reports_buffered_plus_underlying() -> None:
    raw = NonSeekableRandomAccessReadInputStream(_AvailableStream(b"xy" * 50))
    # Force a fetch so buffered bytes show up alongside the still-available.
    raw.read()
    assert raw.available() >= 1


def test_length_swallows_underlying_available_errors() -> None:
    class _Boom:
        def readinto(self, target: bytearray) -> int:
            return io.BytesIO(b"").readinto(target)

        def close(self) -> None:
            return None

        def available(self) -> int:
            raise RuntimeError("nope")

    raw = NonSeekableRandomAccessReadInputStream(_Boom())
    # The ``available`` lookup swallows arbitrary errors and falls back to 0.
    assert raw.length() == 0


# ---------------------------------------------------------------------------
# rewind / multi-buffer
# ---------------------------------------------------------------------------
def test_rewind_into_previous_buffer_when_sufficient_capacity() -> None:
    payload = bytes(range(256)) * 50  # 12800 bytes — spans 3+ buffers
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(payload))
    # Advance well past the first buffer to populate "last".
    out = bytearray(_BUFFER_SIZE + 100)
    raw.read_into(out)
    assert raw.get_position() == _BUFFER_SIZE + 100
    # Rewind 200 bytes — crosses into the previous buffer.
    raw.rewind(200)
    assert raw.get_position() == _BUFFER_SIZE + 100 - 200
    out2 = bytearray(10)
    n = raw.read_into(out2)
    assert n == 10
    # Verify the data matches the original slice.
    start = _BUFFER_SIZE + 100 - 200
    assert bytes(out2) == payload[start : start + 10]


def test_rewind_beyond_buffered_history_raises() -> None:
    payload = bytes(range(256)) * 50
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(payload))
    out = bytearray(_BUFFER_SIZE + 100)
    raw.read_into(out)
    with pytest.raises(OSError, match="rewind"):
        raw.rewind(_BUFFER_SIZE * 10)


# ---------------------------------------------------------------------------
# skip / read EOF
# ---------------------------------------------------------------------------
def test_skip_handles_lengths_larger_than_buffer_size() -> None:
    payload = bytes(range(256)) * 50
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(payload))
    raw.skip(_BUFFER_SIZE + 500)
    assert raw.get_position() == _BUFFER_SIZE + 500


def test_skip_short_stream_stops_at_eof() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"abc"))
    raw.skip(1000)
    assert raw.is_eof() is True


def test_read_after_exhaustion_returns_minus_one() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"ab"))
    assert raw.read() == ord("a")
    assert raw.read() == ord("b")
    assert raw.read() == raw.EOF
    # Subsequent reads keep returning -1.
    assert raw.read() == raw.EOF


def test_read_into_after_eof_returns_minus_one() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"x"))
    raw.read_into(bytearray(1))
    out = bytearray(4)
    n = raw.read_into(out)
    assert n == raw.EOF


def test_read_into_with_zero_length_returns_zero() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"abc"))
    assert raw.read_into(bytearray(4), 0, 0) == 0


def test_read_into_rejects_invalid_offset_and_length() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"abc"))
    with pytest.raises(IndexError):
        raw.read_into(bytearray(4), -1, 1)
    with pytest.raises(IndexError):
        raw.read_into(bytearray(4), 0, 99)


# ---------------------------------------------------------------------------
# salvage-fetch branch + public buffer-rotation helpers
# ---------------------------------------------------------------------------
def test_fetch_salvage_path_preserves_history_at_eof() -> None:
    """When the underlying stream EOFs mid-buffer after a full first buffer,
    ``_fetch`` enters the salvage branch to preserve the tail of LAST and
    head of CURRENT so future rewinds can still consult historical bytes.
    """
    # Total = BUFFER_SIZE + (BUFFER_SIZE // 2). Read past the first buffer
    # then trigger one more fetch — the salvage branch kicks in.
    payload = b"A" * _BUFFER_SIZE + b"B" * (_BUFFER_SIZE // 2)
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(payload))
    out = bytearray(_BUFFER_SIZE + 10)
    n = raw.read_into(out)
    assert n == _BUFFER_SIZE + 10
    # We can still rewind 50 bytes (well within preserved last buffer).
    raw.rewind(50)
    out2 = bytearray(50)
    raw.read_into(out2)
    assert bytes(out2) == payload[_BUFFER_SIZE - 40 : _BUFFER_SIZE + 10]


def test_public_switch_buffers_swaps_in_place() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"abc"))
    raw.read()  # populate CURRENT
    raw._buffer_bytes[2] = 7  # type: ignore[attr-defined]
    raw.switch_buffers(0, 2)
    assert raw._buffer_bytes[0] == 7  # type: ignore[attr-defined]


def test_public_fetch_alias_loads_next_chunk() -> None:
    payload = b"x" * (_BUFFER_SIZE * 2 + 5)
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(payload))
    raw.read_into(bytearray(_BUFFER_SIZE))
    # Drained CURRENT; the public ``fetch`` alias should pull the next chunk.
    assert raw.fetch() is True


# ---------------------------------------------------------------------------
# unsupported operations
# ---------------------------------------------------------------------------
def test_is_eof_starts_false_then_flips_after_exhaustion() -> None:
    raw = NonSeekableRandomAccessReadInputStream(io.BytesIO(b"a"))
    assert raw.is_eof() is False
    raw.read()
    raw.read()  # forces EOF
    assert raw.is_eof() is True
