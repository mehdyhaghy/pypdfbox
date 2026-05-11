"""Flate decoder stream wrapper.

Mirrors ``org.apache.pdfbox.filter.FlateFilterDecoderStream``. Wraps a
binary input stream of zlib-compressed bytes (PDF /FlateDecode body
including the 2-byte zlib header) and yields decoded bytes on demand.

Library-first: delegates to the stdlib :mod:`zlib` module
(``zlib.decompressobj``), which is the same backend ``Inflater`` uses on
the JVM side. Matches upstream's PDFBOX-1232 tolerance of streams missing
``Z_STREAM_END`` by simply yielding whatever the decompressor produces
before raising ``error``.
"""

from __future__ import annotations

import contextlib
import io
import logging
import zlib
from typing import BinaryIO

_LOG = logging.getLogger(__name__)


class FlateFilterDecoderStream(io.RawIOBase):
    """Streaming zlib decoder.

    The wrapper consumes the 2-byte zlib header on construction (matching
    upstream's ``in.read(); in.read();``) and then drives
    :class:`zlib.decompressobj` in raw-deflate (no-wrap) mode.
    """

    _CHUNK = 2048

    def __init__(self, input_stream: BinaryIO) -> None:
        super().__init__()
        self._in: BinaryIO = input_stream
        # Skip zlib header (CMF + FLG bytes). Mirrors Java's two
        # ``in.read()`` calls in the constructor.
        self._in.read(1)
        self._in.read(1)
        # nowrap mode matches Java's ``new Inflater(true)``.
        self._inflate = zlib.decompressobj(-zlib.MAX_WBITS)
        self._buffer: bytes = b""
        self._buffer_pos: int = 0
        self._eof: bool = False

    # ------------------------------------------------------------------
    # Refill helper
    # ------------------------------------------------------------------

    def fetch(self) -> bool:
        self._buffer_pos = 0
        if self._eof or self._inflate.eof:
            self._eof = True
            self._buffer = b""
            return False

        chunk = self._in.read(self._CHUNK)
        if not chunk:
            # Flush any tail bytes the decompressor is still holding.
            try:
                tail = self._inflate.flush()
            except zlib.error as exc:
                _LOG.warning(
                    "FlateFilter: premature end of stream due to a "
                    "DataFormatException = %s",
                    exc,
                )
                tail = b""
            self._buffer = tail
            self._eof = True
            return bool(tail)

        try:
            self._buffer = self._inflate.decompress(chunk)
        except zlib.error as exc:
            self._eof = True
            _LOG.warning(
                "FlateFilter: premature end of stream due to a "
                "DataFormatException = %s",
                exc,
            )
            return False
        return True

    # ------------------------------------------------------------------
    # RawIOBase interface
    # ------------------------------------------------------------------

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:  # type: ignore[override]
        if self._eof and self._buffer_pos >= len(self._buffer):
            return b""

        if size is None or size < 0:
            out = bytearray(self._buffer[self._buffer_pos :])
            self._buffer_pos = len(self._buffer)
            while not self._eof:
                if not self.fetch():
                    break
                out.extend(self._buffer)
                self._buffer_pos = len(self._buffer)
            return bytes(out)

        result = bytearray()
        while len(result) < size:
            available = len(self._buffer) - self._buffer_pos
            if available > 0:
                take = min(size - len(result), available)
                result.extend(
                    self._buffer[self._buffer_pos : self._buffer_pos + take]
                )
                self._buffer_pos += take
            elif not self.fetch():
                break
        return bytes(result)

    def readinto(self, b: bytearray | memoryview) -> int:  # type: ignore[override]
        chunk = self.read(len(b))
        n = len(chunk)
        b[:n] = chunk
        return n

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._in.close()
        super().close()

    # Java-API parity ---------------------------------------------------

    def mark_supported(self) -> bool:
        return False

    def skip(self, n: int) -> int:
        return 0

    def available(self) -> int:
        return 0

    def mark(self, readlimit: int) -> None:
        return

    def reset(self) -> None:
        raise OSError("reset is not supported")
