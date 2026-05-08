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


def _require_plain_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    return value


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
        self._position = _require_plain_int(position, "position")
        self._on_new_line = False
        self._closed = False

    # ---------- byte writers ----------

    def write_bytes(self, data: bytes | bytearray | memoryview) -> None:
        """Write the entire buffer. Mirrors upstream ``write(byte[] b)``
        which delegates to ``write(b, 0, b.length)``. Provided as a named
        alias so call sites that read like the Java original keep their
        meaning."""
        if data is None:
            raise TypeError("write_bytes requires a bytes-like argument, not None")
        self.write(data)

    def write(
        self,
        data: bytes | bytearray | memoryview,
        offset: int = 0,
        length: int | None = None,
    ) -> None:
        """Write a slice of ``data`` to the underlying sink and update
        ``position`` / ``onNewLine`` based on the **last** byte written."""
        if data is None:
            raise TypeError("write requires a bytes-like argument, not None")
        offset = _require_plain_int(offset, "offset")
        length = len(data) - offset if length is None else _require_plain_int(length, "length")
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

    def write_text(self, text: str, encoding: str = "iso-8859-1") -> None:
        """Encode ``text`` and emit the resulting bytes.

        Convenience wrapper around the upstream pattern
        ``output.write("...".getBytes(StandardCharsets.US_ASCII))`` which
        appears throughout ``COSWriter`` for headers, ``startxref``, ``%%EOF``,
        and similar fixed tokens. Defaults to ``iso-8859-1`` because that is
        the encoding upstream uses when serialising parsed-form numeric
        literals (see ``COSWriter.doWriteObject`` and
        ``COSWriter.writeReference``)."""
        if text is None:
            raise TypeError("write_text requires a str argument, not None")
        if not isinstance(text, str):
            raise TypeError(
                f"write_text expects a str; got {type(text).__name__}"
            )
        self.write(text.encode(encoding))

    def write_byte(self, value: int) -> None:
        """Write a single byte. ``value`` must be in 0..255."""
        value = _require_plain_int(value, "byte value")
        if not 0 <= value <= 0xFF:
            raise ValueError("byte value must be in 0..255")
        self._out.write(bytes((value,)))
        self._position += 1
        self._on_new_line = False

    def write_int(self, value: int) -> None:
        """Write the ASCII decimal form of ``value``. Used for object numbers,
        offsets, and similar non-negotiable integer fields."""
        value = _require_plain_int(value, "integer value")
        self.write(str(value).encode("ascii"))

    def write_crlf(self) -> None:
        """Emit a literal CR LF pair — required for the xref-entry trailer
        (ISO 32000-1 §7.5.4: each entry must be exactly 20 bytes including
        the trailing two-byte EOL)."""
        self.write(CRLF)

    def writeCRLF(self) -> None:
        """PDFBox-name alias for :meth:`write_crlf`."""
        self.write_crlf()

    def write_lf(self) -> None:
        """Emit a single LF."""
        self.write(LF)

    def writeLF(self) -> None:
        """PDFBox-name alias for :meth:`write_lf`."""
        self.write_lf()

    def write_eol(self) -> None:
        """Emit an EOL only if the previous byte wasn't already one — matches
        upstream's ``writeEOL`` so we don't generate stacked blank lines."""
        if not self._on_new_line:
            self.write(EOL)
            self._on_new_line = True

    def writeEOL(self) -> None:
        """PDFBox-name alias for :meth:`write_eol`."""
        self.write_eol()

    # ---------- introspection ----------

    def get_position(self) -> int:
        return self._position

    # PDFBox-style alias kept verbatim (``getPos`` in upstream).
    def get_pos(self) -> int:
        return self._position

    def getPos(self) -> int:
        """PDFBox-name alias for :meth:`get_pos`."""
        return self.get_pos()

    def is_on_newline(self) -> bool:
        return self._on_new_line

    def isOnNewLine(self) -> bool:
        """PDFBox-name alias for :meth:`is_on_newline`."""
        return self.is_on_newline()

    def set_on_newline(self, value: bool) -> None:
        self._on_new_line = value

    def setOnNewLine(self, value: bool) -> None:
        """PDFBox-name alias for :meth:`set_on_newline`."""
        self.set_on_newline(value)

    def get_out(self) -> _Writable:
        """Return the underlying byte sink. Mirrors access to
        ``FilterOutputStream.out`` — the upstream class exposes the
        wrapped stream via that protected field."""
        return self._out

    @property
    def closed(self) -> bool:
        """Whether :meth:`close` has been invoked. Mirrors the standard
        Python ``io.IOBase.closed`` predicate so ``COSStandardOutputStream``
        behaves like a regular Python output stream when introspected."""
        return self._closed

    # ---------- lifecycle ----------

    def flush(self) -> None:
        flush = getattr(self._out, "flush", None)
        if callable(flush):
            flush()

    def close(self) -> None:
        # Idempotent: existing call sites (``COSWriter.close``,
        # ``COSWriter.release``) invoke ``close()`` more than once on the
        # same instance, so we must not propagate a second close to the
        # underlying sink (which on ``BytesIO`` is harmless but on a real
        # file would raise ``ValueError: I/O operation on closed file``).
        if self._closed:
            return
        self._closed = True
        close = getattr(self._out, "close", None)
        if callable(close):
            close()

    # ---------- diagnostics ----------

    def __repr__(self) -> str:
        # Useful when logging signing offsets / xref byte ranges. Includes
        # position + on-newline state but deliberately omits the underlying
        # sink (could be a large buffer) to keep log lines bounded.
        return (
            f"COSStandardOutputStream(position={self._position}, "
            f"on_newline={self._on_new_line}, closed={self._closed})"
        )

    # ---------- context manager ----------

    def __enter__(self) -> COSStandardOutputStream:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        # Mirrors ``FilterOutputStream.close()`` semantics on try-with-resources:
        # flush first to commit any buffered bytes, then close.
        try:
            self.flush()
        finally:
            self.close()
