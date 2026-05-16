"""Coverage-boost for ``pypdfbox.filter.ascii85_input_stream`` (wave 1321).

Targets the previously-untested branches:

* ``_ensure_decoded`` — short-circuit when already decoded.
* ``_ensure_decoded`` — trailing-whitespace strip when the input is missing
  the ``~>`` marker (the ``while encoded[-1:] in ...`` loop).
* ``_ensure_decoded`` — ValueError -> OSError translation for bad data.
* ``read`` — EOF short-circuit after a full drain.
* ``read`` — size omitted / None.
* ``read`` — chunked reads (partial drain then completion).
* ``readinto`` — write into a caller-provided bytearray buffer.
* ``close`` — idempotency + underlying-stream close.
* Java-parity stubs: ``mark_supported``, ``skip``, ``available``, ``mark``,
  ``reset``.
"""

from __future__ import annotations

import base64
import io

import pytest

from pypdfbox.filter.ascii85_input_stream import ASCII85InputStream


def _encode(data: bytes) -> bytes:
    """Encode ``data`` to ASCII85 in the adobe variant (with markers)."""
    return base64.a85encode(data, adobe=True)


def test_read_all_with_negative_size() -> None:
    payload = b"Hello, World! " * 4
    encoded = _encode(payload)
    stream = ASCII85InputStream(io.BytesIO(encoded))
    assert stream.read(-1) == payload
    # EOF on subsequent read.
    assert stream.read(8) == b""


def test_read_with_size_none() -> None:
    payload = b"abc123"
    stream = ASCII85InputStream(io.BytesIO(_encode(payload)))
    assert stream.read(None) == payload


def test_read_chunked_then_eof() -> None:
    payload = b"0123456789" * 10
    stream = ASCII85InputStream(io.BytesIO(_encode(payload)))
    parts: list[bytes] = []
    while True:
        chunk = stream.read(7)
        if not chunk:
            break
        parts.append(chunk)
    assert b"".join(parts) == payload


def test_read_after_eof_short_circuits() -> None:
    stream = ASCII85InputStream(io.BytesIO(_encode(b"abc")))
    # Drain.
    assert stream.read(-1) == b"abc"
    # Hit the ``if self._eof: return b""`` branch.
    assert stream.read(4) == b""


def test_ensure_decoded_only_runs_once() -> None:
    """Re-reading must not re-decode."""
    payload = b"xyzzy"
    stream = ASCII85InputStream(io.BytesIO(_encode(payload)))
    # First read triggers decode.
    assert stream.read(3) == payload[:3]
    # Second read takes the ``if self._decoded: return`` branch on entry.
    assert stream.read(2) == payload[3:]


def test_missing_terminator_strips_trailing_whitespace() -> None:
    """Adobe variant requires ``~>``; input lacking it must be patched.

    Hits the ``while encoded[-1:] in (...)`` strip loop.
    """
    payload = b"hello"
    encoded = _encode(payload)
    # base64.a85encode adobe=True yields ``<~...~>`` — drop the trailing marker
    # and append whitespace.
    assert encoded.endswith(b"~>")
    body_no_terminator = encoded[:-2] + b"\n \t\r"
    stream = ASCII85InputStream(io.BytesIO(body_no_terminator))
    assert stream.read(-1) == payload


def test_invalid_data_raises_oserror() -> None:
    """Bad ASCII85 bytes must translate ValueError -> OSError."""
    stream = ASCII85InputStream(io.BytesIO(b"\x01\x02not-ascii85~>"))
    with pytest.raises(OSError, match="Invalid data in Ascii85 stream"):
        stream.read(-1)


def test_readinto_returns_byte_count() -> None:
    payload = b"abcdefgh"
    stream = ASCII85InputStream(io.BytesIO(_encode(payload)))
    buf = bytearray(4)
    n = stream.readinto(buf)
    assert n == 4
    assert bytes(buf) == payload[:4]


def test_close_is_idempotent_and_closes_underlying() -> None:
    inner = io.BytesIO(_encode(b"data"))
    stream = ASCII85InputStream(inner)
    stream.close()
    # Calling close twice must not raise.
    stream.close()
    assert inner.closed


def test_mark_supported_is_false() -> None:
    stream = ASCII85InputStream(io.BytesIO(_encode(b"")))
    assert stream.mark_supported() is False


def test_skip_and_available_and_mark_return_defaults() -> None:
    stream = ASCII85InputStream(io.BytesIO(_encode(b"abc")))
    assert stream.skip(5) == 0
    assert stream.available() == 0
    # mark() is a no-op (returns None).
    assert stream.mark(1024) is None


def test_reset_raises() -> None:
    stream = ASCII85InputStream(io.BytesIO(_encode(b"abc")))
    with pytest.raises(OSError, match="Reset is not supported"):
        stream.reset()


def test_readable_is_true() -> None:
    stream = ASCII85InputStream(io.BytesIO(_encode(b"x")))
    assert stream.readable() is True


def test_empty_stream_decodes_to_empty_bytes() -> None:
    """Encoder produces ``<~~>`` for empty input; decoder must handle it."""
    stream = ASCII85InputStream(io.BytesIO(_encode(b"")))
    assert stream.read(-1) == b""
