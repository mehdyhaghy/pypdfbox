"""Wave 1332 coverage boost for ``FlateFilterDecoderStream``.

Targets the remaining uncovered branches in
``pypdfbox/filter/flate_filter_decoder_stream.py``:

* ``fetch()`` flush-time ``zlib.error`` path (empty chunk → ``flush()``
  raises) and the chunk-time ``zlib.error`` path (raw garbage bytes);
* :meth:`readable` returns ``True``;
* :meth:`mark` is a no-op (does not raise).
"""

from __future__ import annotations

import io
import zlib

from pypdfbox.filter import FlateFilterDecoderStream


def _compress(data: bytes) -> bytes:
    return zlib.compress(data)


def test_readable_returns_true() -> None:
    s = FlateFilterDecoderStream(io.BytesIO(_compress(b"x")))
    assert s.readable() is True


def test_mark_is_noop() -> None:
    s = FlateFilterDecoderStream(io.BytesIO(_compress(b"x")))
    # mark() must return None and not raise for any readlimit.
    assert s.mark(0) is None
    assert s.mark(100) is None


def test_decompress_raises_zlib_error_is_swallowed() -> None:
    """A corrupt body byte triggers ``zlib.error`` inside ``decompress``
    — that branch must log + set EOF and not propagate."""
    # First two bytes are stripped by the constructor as the zlib header;
    # what follows is invalid raw-deflate which makes ``decompress`` raise.
    body = b"\x78\x9c" + b"\xff" * 32
    s = FlateFilterDecoderStream(io.BytesIO(body))
    got = s.read()
    # No exception; result is bytes (may be empty).
    assert isinstance(got, bytes)


def test_flush_raises_zlib_error_is_swallowed() -> None:
    """When the input ends mid-stream, the next ``fetch()`` call gets
    an empty chunk and calls ``flush()``. If the decompressor's internal
    state is incomplete enough that ``flush()`` raises, that branch must
    also be swallowed (yielding ``b""`` and EOF)."""
    # Construct a normally-initialised wrapper and then swap in a stub
    # decompressor whose ``flush()`` always raises ``zlib.error`` — this
    # exercises the flush-time exception branch deterministically.
    s = FlateFilterDecoderStream(io.BytesIO(_compress(b"abc")))

    class _BadFlushInflate:
        eof = False

        def decompress(self, data: bytes) -> bytes:  # pragma: no cover
            return b""

        def flush(self) -> bytes:
            raise zlib.error("synthetic flush failure")

    s._inflate = _BadFlushInflate()  # type: ignore[assignment]
    # Replace the underlying stream with one that yields no further bytes,
    # forcing fetch() to take the empty-chunk → flush() path.
    s._in = io.BytesIO(b"")  # type: ignore[assignment]
    assert s.fetch() is False
    assert s._eof is True
    assert s._buffer == b""


def test_close_underlying_exception_swallowed() -> None:
    """The constructor closes any wrapper exception via
    ``contextlib.suppress(Exception)`` so :meth:`close` must remain
    idempotent even if the underlying stream raises."""

    class _BadCloseStream(io.BytesIO):
        def close(self) -> None:
            raise RuntimeError("nope")

    raw = _compress(b"abc")
    s = FlateFilterDecoderStream(_BadCloseStream(raw))
    # close() must not raise — underlying exception is suppressed.
    s.close()
    assert s.closed is True
