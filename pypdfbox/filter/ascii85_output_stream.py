"""ASCII85 output stream wrapper.

Mirrors ``org.apache.pdfbox.filter.ASCII85OutputStream``. Buffers raw bytes
written by the caller and emits ASCII85-encoded output on
:meth:`flush`/:meth:`close`. Library-first: delegates the codec to the
stdlib :func:`base64.a85encode` with the Adobe variant.
"""

from __future__ import annotations

import base64
import contextlib
import io
from typing import BinaryIO


class ASCII85OutputStream(io.RawIOBase):
    """ASCII85 stream-style encoder writing to ``out``.

    Holds buffered raw bytes until flushed; on flush the buffered bytes
    are encoded via :func:`base64.a85encode` (adobe variant), broken into
    lines of length :attr:`max_line` (default 72), and written to the
    underlying stream followed by the ``~>`` terminator.
    """

    Z: int = ord("z")
    OFFSET: int = ord("!")
    NEWLINE: int = ord("\n")

    def __init__(self, out: BinaryIO) -> None:
        super().__init__()
        self._out: BinaryIO = out
        self._raw: bytearray = bytearray()
        self._flushed: bool = True
        self._terminator: int = ord("~")
        self._max_line: int = 72  # upstream default = 36 * 2

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_terminator(self, term: str | int) -> None:
        """Set the single-character terminator preceding ``>``.

        Java accepts any of ``118..126`` excluding ``z`` (122). The PDF
        spec uses ``~``; callers should rarely override this.
        """
        if isinstance(term, str):
            term = ord(term)
        if term < 118 or term > 126 or term == self.Z:
            raise ValueError("Terminator must be 118-126 excluding z")
        self._terminator = term

    def get_terminator(self) -> str:
        return chr(self._terminator)

    def set_line_length(self, line_length: int) -> None:
        self._max_line = line_length

    def get_line_length(self) -> int:
        return self._max_line

    # ------------------------------------------------------------------
    # IOBase interface
    # ------------------------------------------------------------------

    def writable(self) -> bool:
        return True

    def write(self, b) -> int:  # type: ignore[override]
        if isinstance(b, int):
            self._raw.append(b)
            n = 1
        else:
            view = bytes(b)
            self._raw.extend(view)
            n = len(view)
        self._flushed = False
        return n

    def flush(self) -> None:
        if self._flushed:
            return
        # Adobe variant encodes ``\0\0\0\0`` as ``z``, pads short final
        # groups, and (when adobe=True) brackets the body with ``<~`` /
        # ``~>``. We strip the leading ``<~`` to match upstream's
        # marker-less body and inject our own configured terminator.
        encoded = base64.a85encode(bytes(self._raw), adobe=True)
        # adobe=True wraps with ``<~ ... ~>``. Strip both sentinels.
        if encoded.startswith(b"<~"):
            encoded = encoded[2:]
        if encoded.endswith(b"~>"):
            encoded = encoded[:-2]

        # Insert hard line breaks every ``_max_line`` chars to mirror the
        # Java line-folding behaviour.
        if self._max_line > 0 and self._max_line < len(encoded):
            parts: list[bytes] = []
            for i in range(0, len(encoded), self._max_line):
                parts.append(encoded[i : i + self._max_line])
            encoded = b"\n".join(parts)

        self._out.write(encoded)
        # Trailing terminator + newline, matching ``out.write(terminator);
        # out.write('>'); out.write(NEWLINE);``.
        self._out.write(bytes([self._terminator, ord(">"), self.NEWLINE]))
        with contextlib.suppress(Exception):
            self._out.flush()
        self._raw = bytearray()
        self._flushed = True

    def close(self) -> None:
        try:
            self.flush()
        finally:
            self._raw = bytearray()
            with contextlib.suppress(Exception):
                self._out.close()
            super().close()

    # ------------------------------------------------------------------
    # Codec primitive
    # ------------------------------------------------------------------

    def transform_ascii85(self, indata: bytes | bytearray | memoryview) -> bytes:
        """Encode one 4-byte group to ASCII85 (5 output bytes).

        Mirrors upstream's private ``transformASCII85()`` which converts
        ``indata[0..3]`` into ``outdata[0..4]``. As a special case, the
        all-zero group encodes to the single byte ``z`` (with the trailing
        slot zeroed). The actual stream encoding goes through
        :func:`base64.a85encode` in :meth:`flush`; this method exists for
        API parity with the Java surface.
        """
        if len(indata) < 4:
            raise ValueError("transform_ascii85 requires a 4-byte input group")
        word = (
            ((indata[0] & 0xFF) << 24)
            | ((indata[1] & 0xFF) << 16)
            | ((indata[2] & 0xFF) << 8)
            | (indata[3] & 0xFF)
        ) & 0xFFFFFFFF
        if word == 0:
            return bytes([self.Z, 0, 0, 0, 0])
        out = bytearray(5)
        for i in range(4, -1, -1):
            out[i] = (word % 85) + self.OFFSET
            word //= 85
        return bytes(out)
