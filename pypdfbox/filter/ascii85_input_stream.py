"""ASCII85 input stream wrapper.

Mirrors ``org.apache.pdfbox.filter.ASCII85InputStream``. Wraps a binary
stream and decodes ASCII85-encoded bytes on the fly, returning the
original binary data. Buffers the encoded body up to the first ``~``
(or EOF) and decodes it with the same upstream-exact accumulator as
:class:`pypdfbox.filter.ascii85_decode.ASCII85Decode`.
"""

import contextlib
import io
from typing import BinaryIO

from .ascii85_decode import ASCII85Decode


class ASCII85InputStream(io.RawIOBase):
    """ASCII85 stream-style decoder over a binary input stream.

    The encoded stream may contain PDF white-space (NUL, TAB, LF, FF, CR,
    SP; silently skipped), the ``z`` shorthand (expands to four zero bytes
    at a group boundary), and an optional ``~>`` end-of-data marker.
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
        # Read until the first ``~`` (upstream ends the stream at that byte;
        # the ``>`` that follows is incidental) or EOF. A missing ``~>``
        # ends the last group at EOF exactly like ``~>`` (PDFBOX-6317).
        encoded = bytearray()
        while True:
            chunk = self._in.read(4096)
            if not chunk:
                break
            term_idx = chunk.find(b"~")
            if term_idx >= 0:
                encoded.extend(chunk[: term_idx + 1])
                break
            encoded.extend(chunk)
        # Share the filter's decoder: it reproduces upstream's accumulator
        # byte-for-byte (PDF whitespace set per PDFBOX-6330, ``z`` only at a
        # group boundary, 32-bit wrap, padded partial last group).
        self._buf = ASCII85Decode._decode_bytes(bytes(encoded))
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
