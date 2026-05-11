"""ASCII85 input stream wrapper.

Mirrors ``org.apache.pdfbox.filter.ASCII85InputStream``. Wraps a binary
stream and decodes ASCII85-encoded bytes on the fly, returning the
original binary data. Library-first: delegates the codec to the stdlib
:func:`base64.a85decode` after buffering the encoded body up to the ``~>``
terminator.
"""

from __future__ import annotations

import base64
import contextlib
import io
from typing import BinaryIO


class ASCII85InputStream(io.RawIOBase):
    """ASCII85 stream-style decoder over a binary input stream.

    The encoded stream may contain newlines, carriage returns, and spaces
    (silently skipped), the ``z`` shorthand (expands to four zero bytes),
    and an optional ``~>`` end-of-data marker. The PDF profile uses the
    Adobe variant (``adobe=True`` for :func:`base64.a85decode`).
    """

    def __init__(self, stream: BinaryIO) -> None:
        super().__init__()
        self._in: BinaryIO = stream
        self._buf: bytes = b""
        self._pos: int = 0
        self._eof: bool = False
        self._decoded: bool = False

    # ------------------------------------------------------------------
    # Decoding
    # ------------------------------------------------------------------

    def _ensure_decoded(self) -> None:
        if self._decoded:
            return
        # Read until ``~>`` or EOF. ASCII85 streams are bounded by the
        # ``~>`` end-of-data marker per PDF §7.4.3; tolerate streams that
        # omit it (some encoders do) by treating EOF as the boundary.
        encoded = bytearray()
        while True:
            chunk = self._in.read(4096)
            if not chunk:
                break
            encoded.extend(chunk)
            term_idx = encoded.find(b"~>")
            if term_idx >= 0:
                encoded = encoded[: term_idx + 2]
                break

        # ``base64.a85decode`` requires the ``~>`` marker when
        # ``adobe=True``; if it's missing, append one so the codec accepts
        # the bytes. We don't strip whitespace ourselves — ``ignorechars``
        # handles that.
        if not encoded.endswith(b"~>") and encoded:
            # Strip trailing whitespace before appending the marker so
            # we don't produce ``\n~>`` mid-pad.
            while encoded and encoded[-1:] in (b"\n", b"\r", b" ", b"\t"):
                encoded = encoded[:-1]
            encoded.extend(b"~>")
        try:
            self._buf = base64.a85decode(
                bytes(encoded),
                adobe=True,
                ignorechars=b" \t\n\r\v",
            )
        except ValueError as exc:
            raise OSError(f"Invalid data in Ascii85 stream: {exc}") from exc
        self._decoded = True

    # ------------------------------------------------------------------
    # RawIOBase interface
    # ------------------------------------------------------------------

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        self._ensure_decoded()
        if self._eof:
            return b""
        if size is None or size < 0:
            out = self._buf[self._pos :]
            self._pos = len(self._buf)
            self._eof = True
            return out
        end = min(self._pos + size, len(self._buf))
        out = self._buf[self._pos : end]
        self._pos = end
        if self._pos >= len(self._buf):
            self._eof = True
        return out

    def readinto(self, b: bytearray | memoryview) -> int:  # type: ignore[override]
        chunk = self.read(len(b))
        n = len(chunk)
        b[:n] = chunk
        return n

    def close(self) -> None:
        self._buf = b""
        self._eof = True
        with contextlib.suppress(Exception):
            self._in.close()
        super().close()

    # Java-API parity ---------------------------------------------------

    def mark_supported(self) -> bool:
        return False

    def skip(self, n_value: int) -> int:
        return 0

    def available(self) -> int:
        return 0

    def mark(self, readlimit: int) -> None:
        return

    def reset(self) -> None:
        raise OSError("Reset is not supported")
