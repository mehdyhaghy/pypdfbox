"""Wave 1365 — coverage round-out for :class:`CMSProcessableInputStream`.

The base tests cover the ``content_type`` default/override and the happy
``write`` path. This module covers: multi-chunk loops (data larger than
the 8 KiB read buffer), source close-on-exception via the ``try/finally``
pair, custom content type for failure paths, and EOF handling when the
source already returns no bytes.
"""

from __future__ import annotations

from io import BytesIO
from typing import IO

import pytest

from pypdfbox.examples.signature.cms_processable_input_stream import (
    CMSProcessableInputStream,
)


def test_write_handles_multi_chunk_payload() -> None:
    """Drive the ``while True / chunk`` loop with a >8 KiB payload so it
    iterates more than once (lines 33-39)."""
    payload = b"abcdefgh" * 2048  # 16 KiB — at least two read() calls.
    wrapper = CMSProcessableInputStream(BytesIO(payload))
    out = BytesIO()
    wrapper.write(out)
    assert out.getvalue() == payload


def test_write_with_empty_payload_closes_source() -> None:
    """When the source is already at EOF the ``while`` loop exits on the
    first ``chunk`` check; the source is still closed (line 41)."""
    source = BytesIO(b"")
    wrapper = CMSProcessableInputStream(source)
    out = BytesIO()
    wrapper.write(out)
    assert out.getvalue() == b""
    assert source.closed is True


def test_write_closes_source_on_destination_exception() -> None:
    """The ``try/finally`` must close the source even if the destination
    raises on write (lines 33-41)."""

    class _ExplodingSink:
        def write(self, _: bytes) -> int:
            raise OSError("destination is full")

    source = BytesIO(b"some data")
    wrapper = CMSProcessableInputStream(source)
    with pytest.raises(OSError, match="destination is full"):
        wrapper.write(_ExplodingSink())  # type: ignore[arg-type]
    assert source.closed is True


def test_content_type_default_constant_matches_id_data() -> None:
    """The class constant must match RFC 5652 ``id-data``."""
    assert CMSProcessableInputStream.CONTENT_TYPE_DATA == "1.2.840.113549.1.7.1"


def test_custom_content_type_used_when_provided() -> None:
    """An explicit ``content_type`` overrides the default constant (line
    26)."""
    wrapper = CMSProcessableInputStream(BytesIO(b""), content_type="1.9.9.9")
    assert wrapper.get_content_type() == "1.9.9.9"


def test_explicit_empty_content_type_falls_back_to_default() -> None:
    """Empty-string ``content_type`` is falsy, so the ``or`` fallback to
    ``CONTENT_TYPE_DATA`` engages (line 26 — ``content_type or ...``)."""
    wrapper = CMSProcessableInputStream(BytesIO(b""), content_type="")
    assert wrapper.get_content_type() == CMSProcessableInputStream.CONTENT_TYPE_DATA


def test_get_content_after_write_returns_closed_source() -> None:
    """``get_content`` keeps returning the wrapped stream even after it
    has been closed by ``write`` (line 31)."""
    source = BytesIO(b"hello")
    wrapper = CMSProcessableInputStream(source)
    wrapper.write(BytesIO())
    same = wrapper.get_content()
    assert same is source
    assert same.closed is True


def test_write_accepts_arbitrary_writable_sink() -> None:
    """The destination only needs a ``write`` method — feed a bytearray
    via a tiny shim to confirm no isinstance check leaks in."""
    captured = bytearray()

    class _Shim:
        def write(self, b: bytes) -> int:
            captured.extend(b)
            return len(b)

    wrapper = CMSProcessableInputStream(BytesIO(b"abc"))
    wrapper.write(_Shim())  # type: ignore[arg-type]
    assert bytes(captured) == b"abc"


def test_get_content_returns_underlying_stream_typed() -> None:
    """``get_content`` exposes ``IO[bytes]``-compatible content."""
    source: IO[bytes] = BytesIO(b"abc")
    wrapper = CMSProcessableInputStream(source)
    assert wrapper.get_content() is source
