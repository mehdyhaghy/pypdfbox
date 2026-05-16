"""Wave 1321: COSInputStream coverage-boost tests.

Exercises the IOBase proxy methods (``readinto``, ``readable``,
``seekable``, ``seek``, ``tell``) and the populated filter-chain path
(``create`` with one filter) so that the per-filter
:class:`DecodeResult` list is non-empty and ``get_decode_result``
returns the last entry rather than the synthetic default.
"""

from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary, COSInputStream
from pypdfbox.filter.identity_filter import IdentityFilter


def test_readinto_proxies_to_inner() -> None:
    raw = io.BytesIO(b"abcdef")
    stream = COSInputStream.create([], COSDictionary(), raw)
    buf = bytearray(3)
    n = stream.readinto(buf)
    assert n == 3
    assert bytes(buf) == b"abc"


def test_readable_returns_true() -> None:
    stream = COSInputStream.create([], COSDictionary(), io.BytesIO(b""))
    assert stream.readable() is True


def test_seekable_true_when_inner_seekable() -> None:
    stream = COSInputStream.create([], COSDictionary(), io.BytesIO(b"abc"))
    assert stream.seekable() is True


def test_seekable_false_when_inner_not_seekable() -> None:
    class _NoSeek:
        def read(self, _n: int = -1) -> bytes:
            return b""

        def close(self) -> None:
            pass

    stream = COSInputStream.create([], COSDictionary(), _NoSeek())  # type: ignore[arg-type]
    # No ``seekable`` attribute → fallback lambda returns False.
    assert stream.seekable() is False


def test_seek_and_tell_proxy_to_inner() -> None:
    raw = io.BytesIO(b"0123456789")
    stream = COSInputStream.create([], COSDictionary(), raw)
    pos = stream.seek(4)
    assert pos == 4
    assert stream.tell() == 4
    assert stream.read(2) == b"45"
    assert stream.tell() == 6


def test_create_with_filter_populates_decode_results() -> None:
    # ``IdentityFilter`` is a pass-through that produces one
    # ``DecodeResult`` in the per-filter results list.
    raw = io.BytesIO(b"payload")
    stream = COSInputStream.create(
        [IdentityFilter()], COSDictionary(), raw
    )
    # Decoded bytes match the input verbatim.
    assert stream.read() == b"payload"
    # The per-filter result list now has one entry, so
    # ``get_decode_result`` returns the last (only) entry rather than
    # the synthetic default.
    result = stream.get_decode_result()
    assert result is not None
    assert result.bytes_written == len(b"payload")


def test_get_decode_result_returns_last_when_multiple_filters() -> None:
    raw = io.BytesIO(b"abc")
    stream = COSInputStream.create(
        # Two distinct instances — dedup is by equality; default
        # ``Filter`` equality is identity, so both run.
        [IdentityFilter(), IdentityFilter()],
        COSDictionary(),
        raw,
    )
    assert stream.read() == b"abc"
    last = stream.get_decode_result()
    assert last.bytes_written == 3
