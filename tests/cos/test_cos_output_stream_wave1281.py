"""Wave 1281: COSOutputStream port."""

from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary, COSOutputStream
from pypdfbox.io import RandomAccessStreamCacheImpl


def test_empty_filter_chain_writes_through() -> None:
    sink = io.BytesIO()
    stream = COSOutputStream(
        filters=[],
        parameters=COSDictionary(),
        output=sink,
        stream_cache=RandomAccessStreamCacheImpl(),
    )
    stream.write(b"hello")
    stream.flush()
    # ``close`` encodes and flushes everything, but here with no filters
    # the bytes are already written.
    value = sink.getvalue()
    stream.close()
    assert value == b"hello"


def test_int_argument_is_treated_as_byte() -> None:
    sink = io.BytesIO()
    stream = COSOutputStream(
        filters=[],
        parameters=COSDictionary(),
        output=sink,
        stream_cache=RandomAccessStreamCacheImpl(),
    )
    stream.write(0x41)
    # Take the value before close — closing the wrapper also closes
    # ``sink`` (it owns the lifetime).
    value = sink.getvalue()
    stream.close()
    assert value == b"A"


def test_close_is_idempotent() -> None:
    sink = io.BytesIO()
    stream = COSOutputStream(
        filters=[],
        parameters=COSDictionary(),
        output=sink,
        stream_cache=RandomAccessStreamCacheImpl(),
    )
    stream.close()
    stream.close()
