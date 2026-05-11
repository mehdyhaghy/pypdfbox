"""Wave 1281: COSInputStream port."""

from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary, COSInputStream


def test_empty_filter_chain_passes_through() -> None:
    raw = io.BytesIO(b"abc")
    stream = COSInputStream.create([], COSDictionary(), raw)
    assert stream.read() == b"abc"


def test_get_decode_result_default_when_no_filters() -> None:
    raw = io.BytesIO(b"")
    stream = COSInputStream.create([], COSDictionary(), raw)
    result = stream.get_decode_result()
    # The default result has no parameters / no caveats — exact type
    # may vary; we only assert that the object is truthy.
    assert result is not None


def test_close_is_idempotent() -> None:
    raw = io.BytesIO(b"x")
    stream = COSInputStream.create([], COSDictionary(), raw)
    stream.close()
    stream.close()  # second close must be a no-op


def test_read_after_close_raises_or_returns_empty() -> None:
    raw = io.BytesIO(b"x")
    stream = COSInputStream.create([], COSDictionary(), raw)
    stream.close()
    try:
        result = stream.read()
    except ValueError:
        # CPython's BytesIO raises ValueError after close.
        return
    assert result == b""
