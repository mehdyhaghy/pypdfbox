"""Wave 1367 — :class:`RandomAccessReadBuffer` boundary coverage.

Covers branches in :mod:`pypdfbox.io.random_access_read_buffer` that the
existing test files (waves 292/329) leave untouched:

* ``seek`` clamping to length when given a value past EOF (PDFBox parity).
* ``read_into`` zero-length probe at EOF returning 0 (not ``EOF``).
* ``read_remaining_bytes`` honouring offset+length validation.
* ``next_buffer`` raising on EOF / no-op mid-stream.
* ``expand_buffer`` / ``reset_buffers`` round-trip.
* ``create_buffer_from_stream`` closes the source even when copying raises.
* Stream-source ctor with ``read()`` returning non-bytes / non-callable
  ``read`` attribute.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer


def test_seek_past_eof_clamps_to_length() -> None:
    rar = RandomAccessReadBuffer(b"abcdef")
    rar.seek(10_000)
    assert rar.get_position() == 6
    assert rar.is_eof() is True
    assert rar.read() == rar.EOF


def test_seek_negative_raises_oserror() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    with pytest.raises(OSError):
        rar.seek(-1)


def test_read_into_zero_length_returns_zero_even_at_eof() -> None:
    rar = RandomAccessReadBuffer(b"x")
    rar.seek(1)  # EOF
    buf = bytearray(4)
    # length=0 must return 0, not -1 — matches Java read(b, off, 0) semantics
    # via our explicit short-circuit.
    assert rar.read_into(buf, 0, 0) == 0


def test_read_into_bad_offset_raises() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    buf = bytearray(2)
    with pytest.raises(ValueError):
        rar.read_into(buf, 0, 3)  # length > buf size
    with pytest.raises(ValueError):
        rar.read_into(buf, -1, 1)
    with pytest.raises(ValueError):
        rar.read_into(buf, 0, -1)


def test_read_remaining_bytes_at_eof_returns_eof() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    rar.seek(3)
    out = bytearray(4)
    assert rar.read_remaining_bytes(out, 0, 4) == rar.EOF


def test_read_remaining_bytes_validates_offset_length() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    out = bytearray(2)
    with pytest.raises(ValueError):
        rar.read_remaining_bytes(out, 0, 5)
    with pytest.raises(ValueError):
        rar.read_remaining_bytes(out, -1, 1)


def test_next_buffer_raises_at_eof() -> None:
    rar = RandomAccessReadBuffer(b"xy")
    rar.seek(2)
    with pytest.raises(OSError):
        rar.next_buffer()


def test_next_buffer_noop_mid_stream() -> None:
    rar = RandomAccessReadBuffer(b"abcdef")
    rar.seek(2)
    rar.next_buffer()  # no exception, no-op
    # Position untouched, still readable.
    assert rar.read() == ord("c")


def test_expand_buffer_after_close_raises() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    rar.close()
    with pytest.raises(OSError):
        rar.expand_buffer()


def test_reset_buffers_clears_and_makes_empty() -> None:
    rar = RandomAccessReadBuffer(b"abcdef")
    rar.seek(3)
    rar.reset_buffers()
    assert rar.length() == 0
    assert rar.get_position() == 0
    assert rar.is_eof() is True


def test_check_closed_raises_oserror_when_closed() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    rar.close()
    with pytest.raises(OSError):
        rar.check_closed()


def test_create_buffer_from_stream_closes_source_on_success() -> None:
    closed: list[bool] = []

    class TrackingStream(io.BytesIO):
        def close(self) -> None:
            closed.append(True)
            super().close()

    src = TrackingStream(b"hello")
    buf = RandomAccessReadBuffer.create_buffer_from_stream(src)
    try:
        assert closed == [True]
        assert buf.length() == 5
    finally:
        buf.close()


def test_create_buffer_from_stream_closes_source_on_failure() -> None:
    closed: list[bool] = []

    class BadStream:
        def read(self, n: int | None = None) -> bytes:  # noqa: ARG002
            raise OSError("simulated")

        def close(self) -> None:
            closed.append(True)

    src = BadStream()
    with pytest.raises(OSError):
        RandomAccessReadBuffer.create_buffer_from_stream(src)
    assert closed == [True]


def test_ctor_non_callable_read_attr_raises() -> None:
    class Bogus:
        read = "not callable"

    with pytest.raises(TypeError):
        RandomAccessReadBuffer(Bogus())


def test_ctor_missing_read_method_raises() -> None:
    class Bogus:
        pass

    with pytest.raises(TypeError):
        RandomAccessReadBuffer(Bogus())


def test_ctor_stream_yielding_non_bytes_raises() -> None:
    class NonBytesStream:
        def __init__(self) -> None:
            self._calls = 0

        def read(self, n: int | None = None) -> object:  # noqa: ARG002
            self._calls += 1
            return "not bytes"

    with pytest.raises(TypeError):
        RandomAccessReadBuffer(NonBytesStream())


def test_chunk_size_records_buffer_length_for_bytes_source() -> None:
    data = b"x" * 9999
    rar = RandomAccessReadBuffer(data)
    assert rar.chunk_size == len(data)


def test_chunk_size_defaults_for_empty_bytes_source() -> None:
    rar = RandomAccessReadBuffer(b"")
    assert rar.chunk_size == RandomAccessReadBuffer.DEFAULT_CHUNK_SIZE_4KB


def test_create_view_after_close_raises() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    rar.close()
    # Upstream checkClosed throws IOException -> OSError (project convention).
    with pytest.raises(OSError, match="RandomAccessBuffer already closed"):
        rar.create_view(0, 3)


def test_create_view_returns_independent_cursor() -> None:
    rar = RandomAccessReadBuffer(b"abcdefghij")
    view = rar.create_view(2, 4)  # "cdef"
    rar.seek(8)
    # View not affected by parent seek.
    out = bytearray(4)
    n = view.read_into(out)
    assert n == 4
    assert bytes(out) == b"cdef"


def test_create_view_recycles_closed_per_thread_copy() -> None:
    rar = RandomAccessReadBuffer(b"abcdefghij")
    v1 = rar.create_view(0, 5)
    # Close the per-thread copy to force regeneration on next create_view call.
    import threading

    tid = threading.get_ident()
    rar._rarb_copies[tid].close()
    v2 = rar.create_view(0, 5)
    # v2 must be usable.
    out = bytearray(5)
    assert v2.read_into(out) == 5
    assert bytes(out) == b"abcde"
    v1.close()
    v2.close()


def test_read_returns_unsigned_byte_values() -> None:
    rar = RandomAccessReadBuffer(b"\x00\x7f\x80\xff")
    assert rar.read() == 0x00
    assert rar.read() == 0x7F
    assert rar.read() == 0x80
    assert rar.read() == 0xFF
    assert rar.read() == rar.EOF
