"""ASCII85 output stream wrapper.

Mirrors ``org.apache.pdfbox.filter.ASCII85OutputStream``. Buffers raw bytes
into 4-byte groups, transforms each group to its 5-character base-85
representation, and writes the framed encoded output (hard line breaks every
72 chars, ``~>`` EOD marker, trailing LF) on :meth:`flush`/:meth:`close`.

This is a faithful byte-for-byte port of upstream's stream encoder — verified
against the live PDFBox 3.0.7 oracle. Notably:

  * the line-break is a *running* counter spanning full groups (emitted by
    :meth:`write`) and the trailing partial group (emitted by :meth:`flush`),
    so a newline can fall immediately before the ``~>`` terminator when the
    body length is an exact multiple of the line length;
  * an output stream that never received a byte emits NOTHING on flush — not
    even the ``~>`` marker (``flushed`` starts ``True``). Empty input therefore
    encodes to zero bytes, matching upstream (and diverging from a bare
    ``base64.a85encode`` which would frame the empty body).
"""

from __future__ import annotations

import contextlib
import io
from typing import BinaryIO


class ASCII85OutputStream(io.RawIOBase):
    """ASCII85 stream-style encoder writing to ``out``.

    Buffers raw bytes into 4-byte groups; each full group is transformed and
    written immediately (with running line-break folding), and the trailing
    partial group plus the ``~>`` EOD marker are emitted on :meth:`flush`.
    """

    Z: int = ord("z")
    OFFSET: int = ord("!")
    NEWLINE: int = ord("\n")

    def __init__(self, out: BinaryIO) -> None:
        super().__init__()
        self._out: BinaryIO = out
        # Running line-break counter — decremented per output char; when it
        # reaches 0 a newline is emitted and it resets to ``_max_line``.
        self._line_break: int = 72
        self._max_line: int = 72
        self._count: int = 0  # bytes buffered in the current 4-byte group
        self._indata: bytearray = bytearray(4)
        self._outdata: bytearray = bytearray(5)
        # Upstream initialises ``flushed = true`` so a stream that never
        # received a byte emits nothing (not even ``~>``) on flush.
        self._flushed: bool = True
        self._terminator: int = ord("~")

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
        # Upstream only grows the running counter when the new length exceeds
        # the current remaining count; ``maxline`` always takes the new value.
        if self._line_break > line_length:
            self._line_break = line_length
        self._max_line = line_length

    def get_line_length(self) -> int:
        return self._max_line

    # ------------------------------------------------------------------
    # IOBase interface
    # ------------------------------------------------------------------

    def writable(self) -> bool:
        return True

    def _write_byte(self, b: int) -> None:
        self._flushed = False
        self._indata[self._count] = b & 0xFF
        self._count += 1
        if self._count < 4:
            return
        self.transform_into_out()
        for i in range(5):
            if self._outdata[i] == 0:
                break
            self._out.write(bytes([self._outdata[i]]))
            self._line_break -= 1
            if self._line_break == 0:
                self._out.write(bytes([self.NEWLINE]))
                self._line_break = self._max_line
        self._count = 0

    def write(self, b) -> int:  # type: ignore[override]
        if isinstance(b, int):
            self._write_byte(b)
            return 1
        view = bytes(b)
        for byte in view:
            self._write_byte(byte)
        return len(view)

    def flush(self) -> None:
        if self._flushed:
            return
        if self._count > 0:
            # Zero-pad the trailing partial group, transform, then emit
            # ``count + 1`` output bytes (a partial group of n bytes yields
            # n + 1 base-85 chars).
            for i in range(self._count, 4):
                self._indata[i] = 0
            self.transform_into_out()
            if self._outdata[0] == self.Z:
                # An all-zero trailing group is written out as literal '!'s,
                # not the 'z' shortcut (which only applies to full groups).
                for i in range(5):
                    self._outdata[i] = self.OFFSET
            for i in range(self._count + 1):
                self._out.write(bytes([self._outdata[i]]))
                self._line_break -= 1
                if self._line_break == 0:
                    self._out.write(bytes([self.NEWLINE]))
                    self._line_break = self._max_line
        # Terminator path: the running counter is decremented once more
        # before the terminator, so an exact-multiple body folds a newline
        # immediately before ``~>``.
        self._line_break -= 1
        if self._line_break == 0:
            self._out.write(bytes([self.NEWLINE]))
        self._out.write(bytes([self._terminator]))
        self._out.write(b">")
        self._out.write(bytes([self.NEWLINE]))
        self._count = 0
        self._line_break = self._max_line
        self._flushed = True
        with contextlib.suppress(Exception):
            self._out.flush()

    def detach(self) -> None:
        """Sever the underlying stream so :meth:`close` no longer closes it.

        Used by filter encode paths that wrap a *live* destination buffer
        (the encode chain reads ``getvalue()`` after the filter returns):
        after :meth:`flush` has emitted the framed output, detaching keeps
        the wrapper's finaliser (``RawIOBase.__del__`` → :meth:`close`) from
        closing a buffer the caller still needs to read.
        """
        self._out = io.BytesIO()

    def close(self) -> None:
        try:
            self.flush()
        finally:
            self._count = 0
            with contextlib.suppress(Exception):
                self._out.close()
            super().close()

    # ------------------------------------------------------------------
    # Codec primitive
    # ------------------------------------------------------------------

    def transform_into_out(self) -> None:
        """Transform the buffered 4-byte group in ``_indata`` into the
        5-byte base-85 group in ``_outdata`` (in place).

        Mirrors upstream's private ``transformASCII85()``. An all-zero group
        encodes to the single byte ``z`` (the trailing slot zeroed) so the
        caller's emit loop stops after one byte.
        """
        word = (
            ((self._indata[0] & 0xFF) << 24)
            | ((self._indata[1] & 0xFF) << 16)
            | ((self._indata[2] & 0xFF) << 8)
            | (self._indata[3] & 0xFF)
        ) & 0xFFFFFFFF
        if word == 0:
            self._outdata[0] = self.Z
            self._outdata[1] = 0
            return
        for i in range(4, -1, -1):
            self._outdata[i] = (word % 85) + self.OFFSET
            word //= 85

    def transform_ascii85(self, indata: bytes | bytearray | memoryview) -> bytes:
        """Encode one 4-byte group to ASCII85 (5 output bytes).

        Standalone variant of :meth:`transform_into_out` kept for API parity
        with the Java surface. As a special case, the all-zero group encodes
        to the single byte ``z`` (with the trailing slot zeroed).
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
