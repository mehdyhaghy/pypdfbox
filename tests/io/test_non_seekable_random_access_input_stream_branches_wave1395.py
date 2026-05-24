"""Wave 1395 — residual ``_available_on_underlying`` exception branch.

Targets lines 205-207 of
``pypdfbox/io/non_seekable_random_access_read_input_stream.py``:
the ``getbuffer/tell`` fallback's ``except Exception: return 0`` arm.

Mirrors the defensive Java ``try/catch`` upstream wraps around
``ByteArrayInputStream.available()`` style callables.
"""

from __future__ import annotations

from pypdfbox.io.non_seekable_random_access_read_input_stream import (
    NonSeekableRandomAccessReadInputStream,
)


class _BadGetBufferStream:
    """Stream-like object whose ``getbuffer()`` raises — the helper must
    swallow the exception and return 0."""

    def __init__(self) -> None:
        self._read_buf = b"abcdef"
        self._pos = 0

    def read(self, n: int) -> bytes:
        chunk = self._read_buf[self._pos : self._pos + n]
        self._pos += len(chunk)
        return chunk

    def readinto(self, buf: bytearray) -> int:
        chunk = self.read(len(buf))
        buf[: len(chunk)] = chunk
        return len(chunk)

    def tell(self) -> int:
        return self._pos

    def getbuffer(self) -> object:
        raise OSError("synthetic getbuffer failure")

    def close(self) -> None:  # noqa: D401 - shim
        """Compatibility no-op."""


def test_available_on_underlying_returns_zero_when_getbuffer_raises() -> None:
    """``_available_on_underlying`` must catch ``Exception`` and return 0
    when ``getbuffer()`` raises — guards against quirky in-memory streams."""
    stream = NonSeekableRandomAccessReadInputStream(_BadGetBufferStream())
    # Nothing buffered + getbuffer raises -> length() ends up at 0.
    assert stream._available_on_underlying() == 0  # noqa: SLF001
    # available() routes through the same helper and reports buffered only.
    assert stream.available() == 0
