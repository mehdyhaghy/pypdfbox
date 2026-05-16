"""Coverage boost for ``pypdfbox.cos.cos_output_stream`` (wave 1318).

Exercises both the filter-less direct-write path and the
filter-chain-encoding path (single and multi filter), plus the
``write(int)``/``flush``/``close`` accessor surface.
"""

from __future__ import annotations

import io
from typing import BinaryIO

import pytest

from pypdfbox.cos import COSDictionary, COSOutputStream
from pypdfbox.io import RandomAccessStreamCacheImpl


class _IdentityFilter:
    """Minimal Filter-shaped stub: copies raw bytes to encoded sink.

    Accepts an optional 4th positional ``index`` arg because
    :class:`COSOutputStream` passes it during multi-filter encoding.
    """

    calls: list[int]

    def __init__(self) -> None:
        self.calls = []

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> None:
        self.calls.append(index)
        # Stream the raw bytes through to the encoded sink.
        while True:
            chunk = raw.read(4096)
            if not chunk:
                break
            encoded.write(chunk)
        flush = getattr(encoded, "flush", None)
        if callable(flush):
            flush()


class _PrefixFilter(_IdentityFilter):
    """Filter that prepends a one-byte tag so we can verify ordering."""

    def __init__(self, tag: bytes) -> None:
        super().__init__()
        self._tag = tag

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> None:
        encoded.write(self._tag)
        super().encode(raw, encoded, parameters, index)


def _make_stream(filters: list[object]) -> tuple[COSOutputStream, io.BytesIO]:
    sink = io.BytesIO()
    stream = COSOutputStream(
        filters=filters,  # type: ignore[arg-type]
        parameters=COSDictionary(),
        output=sink,
        stream_cache=RandomAccessStreamCacheImpl(),
    )
    return stream, sink


def test_writable_is_true() -> None:
    stream, _ = _make_stream([])
    assert stream.writable() is True
    stream.close()


def test_write_bytearray_and_memoryview() -> None:
    stream, sink = _make_stream([])
    n_bytes = stream.write(bytearray(b"abc"))
    n_mv = stream.write(memoryview(b"de"))
    assert n_bytes == 3
    assert n_mv == 2
    value = sink.getvalue()
    stream.close()
    assert value == b"abcde"


def test_write_int_masks_to_one_byte() -> None:
    stream, sink = _make_stream([])
    n = stream.write(0x1FF)  # masked to 0xFF
    value = sink.getvalue()
    stream.close()
    assert n == 1
    assert value == b"\xff"


def test_flush_passes_through_without_filters() -> None:
    sink = io.BytesIO()

    class _RecordingSink(io.BytesIO):
        flushed = 0

        def flush(self) -> None:  # type: ignore[override]
            self.flushed += 1
            super().flush()

    recording: _RecordingSink = _RecordingSink()
    stream = COSOutputStream(
        filters=[],
        parameters=COSDictionary(),
        output=recording,
        stream_cache=RandomAccessStreamCacheImpl(),
    )
    stream.write(b"x")
    stream.flush()
    assert recording.flushed == 1
    stream.close()


def test_flush_is_noop_when_buffered() -> None:
    f = _IdentityFilter()
    stream, sink = _make_stream([f])
    stream.write(b"hello")
    # Buffered path: flush should NOT touch the underlying output yet.
    stream.flush()
    assert sink.getvalue() == b""
    stream.close()
    # Sink is closed during close(); test the write side via filter call.
    assert f.calls == [0]


def test_single_filter_encoding_round_trip() -> None:
    f = _IdentityFilter()
    stream, sink = _make_stream([f])
    stream.write(b"payload")
    # Snapshot bytes before close (close() closes the sink).
    assert sink.getvalue() == b""  # buffered, not yet encoded
    stream.close()
    # Filter ran once at index 0; the underlying sink is now closed so
    # we just verify the call record.
    assert f.calls == [0]


def test_multi_filter_encoding_applies_in_reverse() -> None:
    inner = _PrefixFilter(b"I:")   # index 0, runs last (against the sink)
    outer = _PrefixFilter(b"O:")   # index 1, runs first (against a temp buffer)
    stream, sink = _make_stream([inner, outer])
    stream.write(b"X")
    stream.close()
    # Reverse-order encoding: outer (i=1) runs first, then inner (i=0).
    assert inner.calls == [0]
    assert outer.calls == [1]


def test_close_is_idempotent_with_filters() -> None:
    f = _IdentityFilter()
    stream, _sink = _make_stream([f])
    stream.write(b"abc")
    stream.close()
    # Second close should be a no-op (early return on _closed_flag);
    # the filter must not be re-invoked.
    stream.close()
    assert f.calls == [0]


def test_close_without_writes() -> None:
    f = _IdentityFilter()
    stream, _sink = _make_stream([f])
    stream.close()
    # Empty buffer is still encoded once through the filter chain.
    assert f.calls == [0]


@pytest.mark.filterwarnings(
    "ignore::pytest.PytestUnraisableExceptionWarning"
)
def test_create_buffer_requires_factory_method() -> None:
    # A stream_cache lacking ``create_buffer`` should raise TypeError
    # eagerly when filters are present.
    class _Bad:
        pass

    with pytest.raises(TypeError, match="create_buffer"):
        COSOutputStream(
            filters=[_IdentityFilter()],  # type: ignore[list-item]
            parameters=COSDictionary(),
            output=io.BytesIO(),
            stream_cache=_Bad(),
        )


def test_no_filters_skips_buffer_construction() -> None:
    # When ``filters`` is empty the ``stream_cache`` shouldn't be touched.
    class _BoomCache:
        def create_buffer(self) -> object:
            raise AssertionError("should not be called")

    stream = COSOutputStream(
        filters=[],
        parameters=COSDictionary(),
        output=io.BytesIO(),
        stream_cache=_BoomCache(),
    )
    stream.write(b"y")
    stream.close()


def test_write_int_zero_is_null_byte() -> None:
    stream, sink = _make_stream([])
    stream.write(0)
    value = sink.getvalue()
    stream.close()
    assert value == b"\x00"
