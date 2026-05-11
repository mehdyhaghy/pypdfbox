"""Port of ``ConnectedInputStream`` (upstream
``ConnectedInputStream.java`` lines 28-93).

Delegating ``InputStream`` that disconnects its backing
``HttpURLConnection`` on close.

Python's standard library handles HTTP connection lifecycle through
``urllib.request`` / ``http.client`` directly, so the upstream's
``HttpURLConnection`` doesn't map cleanly. The port keeps the upstream
class shape — a wrapper around a file-like object plus a "connection"
handle — so consumers familiar with the Java sample see the same API.
"""

from __future__ import annotations

from typing import Any, BinaryIO


class ConnectedInputStream:
    """Mirrors ``ConnectedInputStream`` (public class, line 28).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/util/
    ConnectedInputStream.java`` (lines 28-93).
    """

    def __init__(self, con: Any, is_: BinaryIO) -> None:
        # ``con`` mirrors upstream's ``HttpURLConnection con`` — any object
        # exposing a ``disconnect`` (or ``close``) method works here.
        # ``is_`` mirrors ``InputStream is`` — any binary file-like.
        self.con = con
        self.is_ = is_
        # ``is`` is a Python reserved word; the attribute matches the
        # upstream Java field name when accessed via ``getattr``.

    def read(
        self,
        b: bytes | bytearray | None = None,
        off: int = 0,
        len_: int | None = None,
    ) -> Any:
        """Read bytes from the underlying stream.

        Mirrors the upstream three-overload pattern (lines 39-55):

        - ``read()`` -> single byte (returns ``int`` or ``-1`` at EOF)
        - ``read(b)`` -> fills ``b`` and returns count
        - ``read(b, off, len_)`` -> partial fill"""
        if b is None:
            data = self.is_.read(1)
            if not data:
                return -1
            return data[0]
        if len_ is None:
            data = self.is_.read(len(b))
            if not data:
                return -1
            b[: len(data)] = data
            return len(data)
        data = self.is_.read(len_)
        if not data:
            return -1
        b[off : off + len(data)] = data
        return len(data)

    def skip(self, n: int) -> int:
        """Skip ``n`` bytes — mirrors upstream's ``skip(long)`` (line 58)."""
        skip_fn = getattr(self.is_, "seek", None)
        if skip_fn is not None:
            current = self.is_.tell()
            self.is_.seek(current + n)
            return n
        self.is_.read(n)
        return n

    def available(self) -> int:
        """Return bytes available without blocking — mirrors upstream's
        ``available()`` (line 64). Python streams rarely expose this so
        the port returns ``0`` when the backing stream lacks support."""
        avail = getattr(self.is_, "available", None)
        if callable(avail):
            return int(avail())
        return 0

    def mark(self, readlimit: int) -> None:
        """Mark the current position — mirrors upstream's
        ``mark(int)`` (line 70)."""
        # ``io.IOBase`` doesn't expose mark/reset directly; tell+seek
        # provides equivalent semantics for seekable streams.
        self._mark_position = self.is_.tell() if hasattr(self.is_, "tell") else None
        self._mark_readlimit = readlimit

    def reset(self) -> None:
        """Reset to the previously marked position — mirrors upstream's
        ``reset()`` (line 76)."""
        pos = getattr(self, "_mark_position", None)
        if pos is None:
            raise OSError("mark not set")
        self.is_.seek(pos)

    def mark_supported(self) -> bool:
        """``True`` when the underlying stream is seekable — mirrors
        upstream's ``markSupported()`` (line 82)."""
        return hasattr(self.is_, "seek") and hasattr(self.is_, "tell")

    def close(self) -> None:
        """Close the stream and disconnect the connection — mirrors
        upstream's ``close()`` (line 88)."""
        try:
            self.is_.close()
        finally:
            disconnect = getattr(self.con, "disconnect", None)
            if callable(disconnect):
                disconnect()
            else:
                close = getattr(self.con, "close", None)
                if callable(close):
                    close()

    def __enter__(self) -> ConnectedInputStream:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
