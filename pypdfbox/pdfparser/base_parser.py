from __future__ import annotations

from typing import ClassVar

from pypdfbox.io import RandomAccessRead

from .parse_error import PDFParseError


class BaseParser:
    """
    Low-level PDF tokenizer over a ``RandomAccessRead`` source. Produces
    primitive tokens (integers, floats, names, literal strings, hex
    strings, keywords) per ISO 32000-1 §7.2-§7.3. Has **no knowledge of
    COS object construction** — that lives in ``COSParser``.

    Position management is delegated to the underlying source: every
    token-reading method advances the source's read position past the
    token; the ``position`` property exposes it.
    """

    # ISO 32000-1 §7.2.3 — character classes.
    WHITESPACE: ClassVar[bytes] = b"\x00\t\n\x0c\r "
    EOL_BYTES: ClassVar[bytes] = b"\r\n"
    DELIMITERS: ClassVar[bytes] = b"()<>[]{}/%"
    DIGITS: ClassVar[bytes] = b"0123456789"
    HEX_DIGITS: ClassVar[bytes] = b"0123456789ABCDEFabcdef"

    def __init__(self, source: RandomAccessRead) -> None:
        self._src = source

    # ---------- position / low-level byte access ----------

    @property
    def position(self) -> int:
        return self._src.get_position()

    def seek(self, position: int) -> None:
        self._src.seek(position)

    def is_eof(self) -> bool:
        return self._src.is_eof()

    def read_byte(self) -> int:
        """Return the next byte (0..255) or -1 at EOF."""
        return self._src.read()

    def peek_byte(self) -> int:
        """Look at the next byte without consuming it. Returns -1 at EOF."""
        return self._src.peek()

    def unread_byte(self) -> None:
        if self._src.get_position() > 0:
            self._src.rewind(1)

    def require_byte(self) -> int:
        """Read a byte; raise ``PDFParseError`` at EOF."""
        b = self._src.read()
        if b == RandomAccessRead.EOF:
            raise PDFParseError("unexpected EOF", position=self.position)
        return b

    # ---------- character classification ----------

    @classmethod
    def is_whitespace(cls, b: int) -> bool:
        return 0 <= b <= 0x20 and bytes((b,)) in cls.WHITESPACE

    @classmethod
    def is_eol(cls, b: int) -> bool:
        return b in (0x0A, 0x0D)

    @classmethod
    def is_delimiter(cls, b: int) -> bool:
        return 0 <= b <= 0x7F and bytes((b,)) in cls.DELIMITERS

    @classmethod
    def is_digit(cls, b: int) -> bool:
        return 0x30 <= b <= 0x39

    @classmethod
    def is_hex_digit(cls, b: int) -> bool:
        return cls.is_digit(b) or 0x41 <= b <= 0x46 or 0x61 <= b <= 0x66

    @classmethod
    def is_regular(cls, b: int) -> bool:
        """Regular character per §7.2.3 — not whitespace, not delimiter."""
        if b < 0:
            return False
        return not cls.is_whitespace(b) and not cls.is_delimiter(b)

    # ---------- whitespace / comments / EOL ----------

    def skip_whitespace(self) -> None:
        """Skip whitespace bytes and ``%``-comments. Comments run to EOL."""
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                return
            if b == 0x25:  # '%' — comment to EOL
                self._skip_to_eol()
                continue
            if not self.is_whitespace(b):
                self._src.rewind(1)
                return

    def _skip_to_eol(self) -> None:
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF or self.is_eol(b):
                # Consume CRLF as a unit — the LF after CR is part of the EOL.
                if b == 0x0D and self._src.peek() == 0x0A:
                    self._src.read()
                return

    def skip_eol(self) -> None:
        """Consume one EOL marker (CR, LF, or CRLF) if present."""
        b = self._src.peek()
        if b == 0x0D:
            self._src.read()
            if self._src.peek() == 0x0A:
                self._src.read()
        elif b == 0x0A:
            self._src.read()

    def read_until_eol(self) -> bytes:
        """Read bytes up to (but not including) the next EOL or EOF."""
        out = bytearray()
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                break
            if self.is_eol(b):
                self._src.rewind(1)
                break
            out.append(b)
        return bytes(out)

    # ---------- numbers ----------

    def read_int(self) -> int:
        """Parse an integer literal: optional ``+``/``-`` followed by digits."""
        start_pos = self.position
        sign = 1
        b = self._src.read()
        if b == 0x2B:  # '+'
            b = self._src.read()
        elif b == 0x2D:  # '-'
            sign = -1
            b = self._src.read()
        if b == RandomAccessRead.EOF or not self.is_digit(b):
            raise PDFParseError("expected integer", position=start_pos)
        digits = bytearray([b])
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                break
            if not self.is_digit(b):
                self._src.rewind(1)
                break
            digits.append(b)
        return sign * int(digits.decode("ascii"))

    def read_long(self) -> int:
        """Alias for ``read_int`` — Python ints are unbounded; the
        method exists for PDFBox API parity."""
        return self.read_int()

    def read_number(self) -> int | float:
        """Parse an integer or real number per ISO 32000-1 §7.3.3.

        Real numbers may use a leading or trailing decimal point. No
        scientific-notation branch — that's a malformed-recovery
        affordance reserved for ``PDFParser``."""
        start_pos = self.position
        sign_chr = b""
        b = self._src.read()
        if b in (0x2B, 0x2D):
            sign_chr = bytes((b,))
            b = self._src.read()
        body = bytearray()
        saw_dot = False
        while b != RandomAccessRead.EOF:
            if self.is_digit(b):
                body.append(b)
            elif b == 0x2E and not saw_dot:  # '.'
                saw_dot = True
                body.append(b)
            else:
                self._src.rewind(1)
                break
            b = self._src.read()
        if not body or body == b".":
            raise PDFParseError("expected number", position=start_pos)
        text = (sign_chr + bytes(body)).decode("ascii")
        return float(text) if saw_dot else int(text)

    # ---------- name objects ----------

    def read_name(self) -> str:
        """Parse a name object ``/Foo`` per §7.3.5. Caller must position
        the reader at the leading ``/``. Returns the **decoded** name
        (``#xx`` hex escapes resolved per PDF 1.2+)."""
        start_pos = self.position
        b = self._src.read()
        if b != 0x2F:  # '/'
            raise PDFParseError("expected name (leading '/')", position=start_pos)
        out = bytearray()
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF or not self.is_regular(b):
                if b != RandomAccessRead.EOF:
                    self._src.rewind(1)
                break
            if b == 0x23:  # '#' — hex escape
                hi = self._src.peek()
                if hi == RandomAccessRead.EOF or not self.is_hex_digit(hi):
                    # Malformed escape — keep '#' literally and continue.
                    out.append(b)
                    continue
                self._src.read()
                lo = self._src.peek()
                if lo == RandomAccessRead.EOF or not self.is_hex_digit(lo):
                    # Only one valid hex digit followed '#'; keep both raw.
                    out.append(b)
                    out.append(hi)
                    continue
                self._src.read()
                out.append(int(bytes((hi, lo)).decode("ascii"), 16))
            else:
                out.append(b)
        # Names are UTF-8 in PDF 1.2+; fall back to latin-1 for malformed input
        # rather than raise — PDF callers expect a string they can stash on a COSName.
        try:
            return out.decode("utf-8")
        except UnicodeDecodeError:
            return out.decode("latin-1")

    # ---------- literal string ( ... ) ----------

    _ESCAPE_MAP: ClassVar[dict[int, int]] = {
        0x6E: 0x0A,  # n  → LF
        0x72: 0x0D,  # r  → CR
        0x74: 0x09,  # t  → HT
        0x62: 0x08,  # b  → BS
        0x66: 0x0C,  # f  → FF
        0x28: 0x28,  # (  → (
        0x29: 0x29,  # )  → )
        0x5C: 0x5C,  # \  → \
    }

    def read_literal_string(self) -> bytes:
        """Parse a literal string ``( ... )`` per §7.3.4.2 with balanced
        parens, backslash escapes, octal sequences, and EOL continuation."""
        start_pos = self.position
        b = self._src.read()
        if b != 0x28:  # '('
            raise PDFParseError("expected literal string '('", position=start_pos)
        out = bytearray()
        depth = 1
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                raise PDFParseError("unterminated literal string", position=start_pos)
            if b == 0x28:  # '(' — nested
                depth += 1
                out.append(b)
            elif b == 0x29:  # ')'
                depth -= 1
                if depth == 0:
                    return bytes(out)
                out.append(b)
            elif b == 0x5C:  # '\'
                self._consume_escape(out)
            elif b == 0x0D:
                # CR or CRLF → LF (§7.3.4.2 EOL normalization).
                if self._src.peek() == 0x0A:
                    self._src.read()
                out.append(0x0A)
            else:
                out.append(b)

    def _consume_escape(self, out: bytearray) -> None:
        b = self._src.read()
        if b == RandomAccessRead.EOF:
            return
        mapped = self._ESCAPE_MAP.get(b)
        if mapped is not None:
            out.append(mapped)
            return
        if 0x30 <= b <= 0x37:  # octal: 1-3 digits
            digits = bytearray([b])
            for _ in range(2):
                nxt = self._src.peek()
                if nxt == RandomAccessRead.EOF or not (0x30 <= nxt <= 0x37):
                    break
                digits.append(self._src.read())
            value = int(digits.decode("ascii"), 8)
            out.append(value & 0xFF)
            return
        if b == 0x0D:  # CR or CRLF after backslash → line continuation
            if self._src.peek() == 0x0A:
                self._src.read()
            return
        if b == 0x0A:  # LF after backslash → line continuation
            return
        # Unknown escape: drop the backslash, keep the byte literally (§7.3.4.2).
        out.append(b)

    # ---------- hex string < ... > ----------

    def read_hex_string(self) -> bytes:
        """Parse a hex string ``< ... >`` per §7.3.4.3. Whitespace inside is
        ignored; an odd trailing digit is implicitly padded with ``0``."""
        start_pos = self.position
        b = self._src.read()
        if b != 0x3C:  # '<'
            raise PDFParseError("expected hex string '<'", position=start_pos)
        digits = bytearray()
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                raise PDFParseError("unterminated hex string", position=start_pos)
            if b == 0x3E:  # '>'
                break
            if self.is_whitespace(b):
                continue
            if not self.is_hex_digit(b):
                raise PDFParseError(
                    f"invalid hex digit {b:#04x} in hex string", position=self.position
                )
            digits.append(b)
        if len(digits) % 2:
            digits.append(0x30)  # pad with '0'
        return bytes.fromhex(digits.decode("ascii"))

    # ---------- keywords ----------

    def read_keyword(self) -> bytes:
        """Read a keyword token (alphabetic ASCII run). Used for
        ``true``/``false``/``null``/``obj``/``endobj``/``stream``/
        ``endstream``/``R``/``xref``/``trailer``/``startxref``."""
        out = bytearray()
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                break
            if (0x41 <= b <= 0x5A) or (0x61 <= b <= 0x7A):
                out.append(b)
            else:
                self._src.rewind(1)
                break
        if not out:
            raise PDFParseError("expected keyword", position=self.position)
        return bytes(out)

    def read_expected(self, expected: bytes) -> None:
        """Consume ``expected`` exactly; raise on mismatch."""
        start_pos = self.position
        for ch in expected:
            b = self._src.read()
            if b != ch:
                raise PDFParseError(
                    f"expected {expected!r} at byte {start_pos}", position=start_pos
                )
