from __future__ import annotations

from typing import Protocol


class _Writable(Protocol):
    """Minimal duck-typed sink interface — anything with ``write(bytes) -> int``
    (``io.BytesIO``, file objects, ``RandomAccessWriteBuffer``-like wrappers)."""

    def write(self, data: bytes, /) -> int | None: ...


# Standard byte sequences the writer emits. Mirrors the upstream
# ``COSStandardOutputStream`` constants so call sites that read like the
# Java original keep their meaning.
CRLF: bytes = b"\r\n"
LF: bytes = b"\n"
EOL: bytes = b"\n"


class COSStandardOutputStream:
    """
    Line-aware byte sink wrapped around any writable binary stream.

    Tracks two pieces of state:

    * ``position`` — current absolute byte offset (the writer needs this for
      xref offsets and ``startxref``).
    * ``onNewLine`` — whether the previous byte was an EOL, so back-to-back
      ``write_eol()`` calls do not double up.

    Mirrors ``org.apache.pdfbox.pdfwriter.COSStandardOutputStream``.
    """

    CRLF: bytes = CRLF
    LF: bytes = LF
    EOL: bytes = EOL

    def __init__(self, out: _Writable, position: int = 0) -> None:
        self._out = out
        self._position = position
        self._on_new_line = False

    # ---------- byte writers ----------

    def write(
        self,
        data: bytes | bytearray | memoryview,
        offset: int = 0,
        length: int | None = None,
    ) -> None:
        """Write a slice of ``data`` to the underlying sink and update
        ``position`` / ``onNewLine`` based on the **last** byte written."""
        if length is None:
            length = len(data) - offset
        if length < 0:
            raise ValueError("length must be non-negative")
        if offset < 0 or offset + length > len(data):
            raise ValueError("offset/length out of range for data")
        if length == 0:
            return
        chunk = bytes(memoryview(data)[offset : offset + length])
        self._out.write(chunk)
        self._position += length
        # Match upstream behavior: any explicit ``write`` resets onNewLine
        # to False, then ``write_eol`` flips it back to True.
        self._on_new_line = False

    def write_byte(self, value: int) -> None:
        """Write a single byte. ``value`` must be in 0..255."""
        if not 0 <= value <= 0xFF:
            raise ValueError("byte value must be in 0..255")
        self._out.write(bytes((value,)))
        self._position += 1
        self._on_new_line = False

    def write_int(self, value: int) -> None:
        """Write the ASCII decimal form of ``value``. Used for object numbers,
        offsets, and similar non-negotiable integer fields."""
        self.write(str(value).encode("ascii"))

    def write_crlf(self) -> None:
        """Emit a literal CR LF pair — required for the xref-entry trailer
        (ISO 32000-1 §7.5.4: each entry must be exactly 20 bytes including
        the trailing two-byte EOL)."""
        self.write(CRLF)

    def write_lf(self) -> None:
        """Emit a single LF."""
        self.write(LF)

    def write_eol(self) -> None:
        """Emit an EOL only if the previous byte wasn't already one — matches
        upstream's ``writeEOL`` so we don't generate stacked blank lines."""
        if not self._on_new_line:
            self.write(EOL)
            self._on_new_line = True

    # ---------- introspection ----------

    def get_position(self) -> int:
        return self._position

    # PDFBox-style alias kept verbatim (``getPos`` in upstream).
    def get_pos(self) -> int:
        return self._position

    def is_on_newline(self) -> bool:
        return self._on_new_line

    def set_on_newline(self, value: bool) -> None:
        self._on_new_line = value

    # ---------- lifecycle ----------

    def flush(self) -> None:
        flush = getattr(self._out, "flush", None)
        if callable(flush):
            flush()

    def close(self) -> None:
        close = getattr(self._out, "close", None)
        if callable(close):
            close()
