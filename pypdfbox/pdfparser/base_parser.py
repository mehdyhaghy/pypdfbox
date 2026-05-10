from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from pypdfbox.io import RandomAccessRead

from .parse_error import PDFParseError

if TYPE_CHECKING:
    from pypdfbox.cos.cos_document import COSDocument
    from pypdfbox.cos.cos_object_key import COSObjectKey

_LOG = logging.getLogger(__name__)


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

    # Upstream (org.apache.pdfbox.pdfparser.BaseParser) string constants.
    DEF: ClassVar[str] = "def"
    ENDOBJ_STRING: ClassVar[str] = "endobj"
    ENDSTREAM_STRING: ClassVar[str] = "endstream"
    STREAM_STRING: ClassVar[str] = "stream"

    # Upstream ASCII byte constants.
    ASCII_LF: ClassVar[int] = 0x0A
    ASCII_CR: ClassVar[int] = 0x0D
    ASCII_SPACE: ClassVar[int] = 0x20

    # Upstream object/generation number thresholds (PDF spec).
    OBJECT_NUMBER_THRESHOLD: ClassVar[int] = 10_000_000_000
    GENERATION_NUMBER_THRESHOLD: ClassVar[int] = 65535

    # Maximum recursion depth allowed when nesting parsed objects (arrays /
    # dictionaries) per upstream ``BaseParser.MAX_RECURSION_DEPTH``. The
    # pypdfbox tokenizer does not enforce this guard yet (see
    # ``PROVENANCE.md`` — recursive-depth tracking lives at the structural
    # layer in ``COSParser.parse_direct_object``); the constant is exposed
    # here for parity-test access and future enforcement work.
    MAX_RECURSION_DEPTH: ClassVar[int] = 500

    # Maximum number of digits accepted by ``read_string_number`` before
    # the parser bails out — mirrors upstream
    # ``BaseParser.MAX_LENGTH_LONG`` (length of ``Long.MAX_VALUE`` decimal,
    # i.e. 19). Python ints are unbounded so the runtime never trips on
    # this in practice — exposed for API parity.
    MAX_LENGTH_LONG: ClassVar[int] = 19

    def __init__(self, source: RandomAccessRead) -> None:
        self._src = source
        # Mirrors upstream ``BaseParser.document`` (protected COSDocument).
        # Subclasses (``COSParser``) may set this via their own constructor;
        # held here so :meth:`get_object_key` and any future BaseParser-level
        # helpers can consult the xref table the way upstream does.
        self._document: COSDocument | None = None
        # Backing store for :meth:`get_object_key` — mirrors upstream's
        # ``private final Map<Long, COSObjectKey> keyCache``. Keyed on the
        # ``(object_number, generation_number)`` tuple (Python's stand-in
        # for upstream's ``computeInternalHash``) so lookups stay O(1) for
        # big PDFs.
        self._key_cache: dict[tuple[int, int], COSObjectKey] = {}

    # ---------- document handle (upstream protected COSDocument) ----------

    @property
    def document(self) -> COSDocument | None:
        """Mirrors upstream ``BaseParser.document`` (protected field).
        ``COSParser``/``PDFParser`` set the backing attribute via the
        subclass constructor; consumers can read it through this property
        the same way Java callers read the ``document`` field."""
        return self._document

    # ---------- object key cache ----------

    def get_object_key(self, num: int, gen: int) -> COSObjectKey:
        """Return the :class:`COSObjectKey` for ``(num, gen)``.

        Mirrors upstream ``BaseParser.getObjectKey(long, int)`` (line 188):
        if a document is attached and its xref table already contains a key
        with the same ``(num, gen)``, that exact key instance is reused so
        identity comparisons match. Otherwise a fresh key is constructed.
        The key cache is populated lazily — only when the xref table grows
        past what we've already mirrored — to avoid per-call iteration on
        large PDFs."""
        # Late import to avoid circulars with cos.cos_object_key.
        from pypdfbox.cos.cos_object_key import COSObjectKey as _Key

        document = self._document
        if document is None or not document.get_xref_table():
            return _Key(num, gen)
        xref_table = document.get_xref_table()
        if len(xref_table) > len(self._key_cache):
            for key in xref_table:
                # ``setdefault`` mirrors upstream's ``putIfAbsent``.
                self._key_cache.setdefault(
                    (key.object_number, key.generation_number), key
                )
        cached = self._key_cache.get((num, gen))
        return cached if cached is not None else _Key(num, gen)

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

    # ---------- upstream-name aliases (org.apache.pdfbox.pdfparser.BaseParser) ----------

    def peek(self) -> int:
        """Upstream-name alias for ``peek_byte``. Returns the next byte
        without consuming it, or -1 at EOF."""
        return self._src.peek()

    def read(self) -> int:
        """Upstream-name alias for ``read_byte``. Reads one byte and
        advances; returns -1 at EOF."""
        return self._src.read()

    def unread(self, b: int) -> None:
        """Upstream-name alias for ``unread_byte``. Pushes a byte back into
        the stream (rewinds one position; ``b`` is ignored — PDFBox semantics
        assume the byte matches what was previously read)."""
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

    @classmethod
    def is_space(cls, b: int) -> bool:
        """Upstream-name alias: matches ASCII space (0x20) only — distinct
        from ``is_whitespace`` which covers the full PDF whitespace set."""
        return b == cls.ASCII_SPACE

    @classmethod
    def is_end_of_name(cls, b: int) -> bool:
        """Mirrors upstream ``BaseParser.isEndOfName(int)``. A PDF name
        terminates on whitespace, EOL, ``> < [ ] / ) ( % \\f`` or EOF."""
        if b < 0:
            return True
        # whitespace bytes (incl. NUL, HT, LF, FF, CR, SPACE) terminate the name
        if cls.is_whitespace(b):
            return True
        return b in (0x3E, 0x3C, 0x5B, 0x5D, 0x29, 0x28, 0x2F, 0x25, 0x0C)

    # ---------- one-arg/no-arg classifier overloads (upstream parity) ----------

    def is_whitespace_at(self) -> bool:
        """No-arg upstream alias: peeks the next byte and reports whether
        it is a PDF whitespace character. Mirrors upstream
        ``BaseParser.isWhitespace()``."""
        return self.is_whitespace(self._src.peek())

    def is_space_at(self) -> bool:
        """No-arg upstream alias: peeks the next byte and reports whether
        it is an ASCII space. Mirrors upstream ``BaseParser.isSpace()``."""
        return self.is_space(self._src.peek())

    def is_digit_at(self) -> bool:
        """No-arg upstream alias: peeks the next byte and reports whether
        it is a digit. Mirrors upstream ``BaseParser.isDigit()``."""
        return self.is_digit(self._src.peek())

    def is_eol_at(self) -> bool:
        """No-arg upstream alias: peeks the next byte and reports whether
        it is an EOL byte (CR or LF). Mirrors upstream
        ``BaseParser.isEOL()``."""
        return self.is_eol(self._src.peek())

    def is_closing(self, b: int | None = None) -> bool:
        """Reports whether the byte (or the peek byte, if ``b`` is None)
        closes a PDF array. Mirrors upstream ``BaseParser.isClosing()`` /
        ``isClosing(int)``."""
        if b is None:
            b = self._src.peek()
        return b == 0x5D  # ']'

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

    def skip_spaces(self) -> None:
        """Upstream-name alias for ``skip_whitespace`` — mirrors upstream
        ``BaseParser.skipSpaces()`` (which skips PDF whitespace and
        ``%``-comments to EOL)."""
        self.skip_whitespace()

    def skip_linebreak(self) -> bool:
        """Skip one line break (CR, LF, or CRLF). Returns ``True`` if a
        line break was consumed. Mirrors upstream
        ``BaseParser.skipLinebreak()``."""
        b = self._src.read()
        if b == RandomAccessRead.EOF:
            return False
        if b == 0x0D:  # CR — may be followed by LF
            nxt = self._src.read()
            if nxt != 0x0A and nxt != RandomAccessRead.EOF:
                self._src.rewind(1)
            return True
        if b == 0x0A:
            return True
        self._src.rewind(1)
        return False

    def skip_white_spaces(self) -> None:
        """Skip the upcoming CR / LF / CRLF that follows a stream keyword,
        plus any leading ASCII spaces. Mirrors upstream
        ``BaseParser.skipWhiteSpaces()`` — note this is *not* the general
        whitespace skipper (that's ``skip_spaces`` / ``skip_whitespace``)."""
        # Per ISO 32000-1 §7.3.8.1: a stream keyword is followed by either
        # CRLF or LF — but real-world PDFs add leading spaces (see
        # brother_scan_cover.pdf). Eat spaces, then a single line break.
        b = self._src.read()
        while b == self.ASCII_SPACE:
            b = self._src.read()
        if b == RandomAccessRead.EOF:
            return
        if b == 0x0D:
            nxt = self._src.read()
            if nxt != 0x0A and nxt != RandomAccessRead.EOF:
                self._src.rewind(1)
        elif b != 0x0A:
            self._src.rewind(1)

    def read_line(self) -> str:
        """Read bytes until (and consuming) the next EOL marker (CR, LF,
        or CRLF) and return them as a string. Mirrors upstream
        ``BaseParser.readLine()`` — raises ``PDFParseError`` if already at
        EOF when called."""
        if self._src.is_eof():
            raise PDFParseError(
                "expected line, hit EOF", position=self.position
            )
        out = bytearray()
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                break
            if self.is_eol(b):
                # CRLF is a single EOL marker — consume the LF after CR.
                if b == 0x0D and self._src.peek() == 0x0A:
                    self._src.read()
                break
            out.append(b)
        try:
            return out.decode("ascii")
        except UnicodeDecodeError:
            return out.decode("latin-1")

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

    def read_string_number(self) -> str:
        """Read an unsigned digit-only token and return it as a string.
        Mirrors upstream ``BaseParser.readStringNumber()`` — the protected
        helper used by ``readInt`` / ``readLong`` to gather the textual
        representation before parsing.

        Stops at the first non-digit byte (which is left unread) or EOF.
        Raises ``PDFParseError`` if the token would exceed
        :data:`MAX_LENGTH_LONG` characters."""
        out = bytearray()
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                break
            if not (0x30 <= b <= 0x39):
                self._src.rewind(1)
                break
            out.append(b)
            if len(out) > self.MAX_LENGTH_LONG:
                raise PDFParseError(
                    f"Number {bytes(out)!r} is getting too long, "
                    f"stop reading at offset {self.position}",
                    position=self.position,
                )
        return out.decode("ascii")

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
        out = self.read_name_bytes()
        # Names are UTF-8 in PDF 1.2+; fall back to latin-1 for malformed input
        # rather than raise — PDF callers expect a string they can stash on a COSName.
        try:
            return out.decode("utf-8")
        except UnicodeDecodeError:
            return out.decode("latin-1")

    def read_name_bytes(self) -> bytes:
        """Parse a name object and return the raw decoded byte sequence."""
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
        return bytes(out)

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
                depth = self._check_for_end_of_string(depth)
                if depth == 0:
                    return bytes(out)
                out.append(b)
            elif b == 0x5C:  # '\'
                depth = self._consume_escape(out, depth)
                if depth == 0:
                    return bytes(out)
            elif b == 0x0D:
                # CR or CRLF → LF (§7.3.4.2 EOL normalization).
                if self._src.peek() == 0x0A:
                    self._src.read()
                out.append(0x0A)
            else:
                out.append(b)

    def _check_for_end_of_string(self, depth: int) -> int:
        if depth == 0:
            return 0
        next_three = bytearray(3)
        amount_read = self._src.read_into(next_three)
        if amount_read > 0:
            self._src.rewind(amount_read)
        if amount_read < 3:
            return depth
        if self.is_eol(next_three[0]) and next_three[1] in (0x2F, 0x3E):  # '/', '>'
            return 0
        if (
            next_three[0] == 0x0D
            and next_three[1] == 0x0A
            and next_three[2] in (0x2F, 0x3E)  # '/', '>'
        ):
            return 0
        return depth

    def _consume_escape(self, out: bytearray, depth: int) -> int:
        b = self._src.read()
        if b == RandomAccessRead.EOF:
            return depth
        if b == 0x29:  # ')' — PDFBox-276 malformed string recovery.
            depth = self._check_for_end_of_string(depth)
            if depth == 0:
                out.append(0x5C)
                return 0
            out.append(b)
            return depth
        mapped = self._ESCAPE_MAP.get(b)
        if mapped is not None:
            out.append(mapped)
            return depth
        if 0x30 <= b <= 0x37:  # octal: 1-3 digits
            digits = bytearray([b])
            for _ in range(2):
                nxt = self._src.peek()
                if nxt == RandomAccessRead.EOF or not (0x30 <= nxt <= 0x37):
                    break
                digits.append(self._src.read())
            value = int(digits.decode("ascii"), 8)
            out.append(value & 0xFF)
            return depth
        if b == 0x0D:  # CR or CRLF after backslash → line continuation
            if self._src.peek() == 0x0A:
                self._src.read()
            return depth
        if b == 0x0A:  # LF after backslash → line continuation
            return depth
        # Unknown escape: drop the backslash, keep the byte literally (§7.3.4.2).
        out.append(b)
        return depth

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
        """Read a keyword-like regular token with an alphabetic start. Used for
        ``true``/``false``/``null``/``obj``/``endobj``/``stream``/
        ``endstream``/``R``/``xref``/``trailer``/``startxref``."""
        start_pos = self.position
        out = bytearray()
        b = self._src.read()
        if b == RandomAccessRead.EOF:
            raise PDFParseError("expected keyword", position=start_pos)
        if not ((0x41 <= b <= 0x5A) or (0x61 <= b <= 0x7A)):
            self._src.rewind(1)
            raise PDFParseError("expected keyword", position=start_pos)
        out.append(b)
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                break
            if self.is_regular(b):
                out.append(b)
            else:
                self._src.rewind(1)
                break
        return bytes(out)

    def read_string(self) -> str:
        """Read a token: bytes up to (but not including) the next whitespace
        or EOF. Mirrors upstream ``BaseParser.readString()``. Returns the
        decoded ASCII/latin-1 string. The terminating whitespace byte (if
        any) is left unread.

        Behavioural divergence from upstream: PDFBox calls ``skipSpaces``
        first and stops on ``isEndOfName``; we deliberately omit the
        leading skip so callers that already positioned the reader (e.g.
        the wave497 callers in ``tests/pdfparser/``) keep working. The
        function still terminates on the full PDF whitespace set, so
        downstream behaviour after a leading skip is upstream-equivalent."""
        out = bytearray()
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                break
            if self.is_whitespace(b):
                self._src.rewind(1)
                break
            out.append(b)
        try:
            return out.decode("ascii")
        except UnicodeDecodeError:
            return out.decode("latin-1")

    def read_string_with_length(self, length: int) -> str:
        """Read up to ``length`` characters of a token. Mirrors upstream's
        deprecated ``BaseParser.readString(int length)`` overload (line
        1153) — preserved for API parity even though upstream marks it
        ``@Deprecated`` for removal in 4.0. Stops at whitespace, EOF, any
        of ``[ < ( /``, or once ``length`` characters have been read."""
        self.skip_whitespace()
        out = bytearray()
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                break
            if self.is_whitespace(b) or b in (0x5B, 0x3C, 0x28, 0x2F):
                self._src.rewind(1)
                break
            if len(out) >= length:
                self._src.rewind(1)
                break
            out.append(b)
        try:
            return out.decode("ascii")
        except UnicodeDecodeError:
            return out.decode("latin-1")

    @staticmethod
    def decode_buffer(data: bytes | bytearray) -> str:
        """Decode ``data`` as UTF-8 with a Windows-1252 fallback. Mirrors
        upstream ``BaseParser.decodeBuffer(ByteArrayOutputStream)`` (line
        947): UTF-8 is tried first; on a malformed-input error the bytes
        are decoded with Windows-1252 (PDFBOX-3347) — Latin-1 acts as the
        secondary safety net. Used by name / keyword decoders that need a
        decoded string but must not raise on legacy 1-byte encodings."""
        buf = bytes(data)
        try:
            return buf.decode("utf-8")
        except UnicodeDecodeError:
            _LOG.debug(
                "Buffer could not be decoded using UTF-8 — falling back to Windows-1252"
            )
            try:
                return buf.decode("windows-1252")
            except UnicodeDecodeError:
                return buf.decode("latin-1")

    def read_expected(self, expected: bytes) -> None:
        """Consume ``expected`` exactly; raise on mismatch."""
        start_pos = self.position
        for ch in expected:
            b = self._src.read()
            if b != ch:
                raise PDFParseError(
                    f"expected {expected!r} at byte {start_pos}", position=start_pos
                )

    def read_expected_string(
        self, expected: bytes | bytearray | str, skip_spaces: bool = False
    ) -> None:
        """Read ``expected`` from the source, optionally skipping whitespace
        before and after. Mirrors upstream
        ``BaseParser.readExpectedString(char[], boolean)`` (line 1109) — the
        protected helper used to consume keyword sequences like ``true`` /
        ``null`` while permissively eating surrounding whitespace.

        ``expected`` may be a ``bytes``/``bytearray`` or a ``str`` (which
        is interpreted as a sequence of ASCII byte values, matching the
        Java ``char[]`` signature). Raises :class:`PDFParseError` if any
        byte fails to match — the position-on-error mirrors upstream where
        the byte just-read is reported as the mismatch site."""
        expected_bytes = (
            expected.encode("ascii") if isinstance(expected, str) else bytes(expected)
        )
        if skip_spaces:
            self.skip_whitespace()
        for ch in expected_bytes:
            b = self._src.read()
            if b != ch:
                raise PDFParseError(
                    f"Expected string {expected_bytes!r} but missed at "
                    f"character {chr(ch)!r} at offset {self.position}",
                    position=self.position,
                )
        if skip_spaces:
            self.skip_whitespace()

    def read_expected_char(self, ec: int | str) -> None:
        """Read one byte and raise unless it matches ``ec``. Mirrors
        upstream ``BaseParser.readExpectedChar(char)``. Accepts an int
        (byte value) or a single-character ``str`` for ergonomics."""
        if isinstance(ec, str):
            if len(ec) != 1:
                raise ValueError("read_expected_char expects a single character")
            ec_int = ord(ec)
        else:
            ec_int = ec
        start_pos = self.position
        b = self._src.read()
        if b != ec_int:
            raise PDFParseError(
                f"expected {chr(ec_int)!r} at byte {start_pos}, got {b}",
                position=start_pos,
            )

    # ---------- object / generation number readers ----------

    def read_object_number(self) -> int:
        """Read an object number, validating against the upstream
        ``OBJECT_NUMBER_THRESHOLD`` (10**10) and rejecting negative
        values. Mirrors upstream ``BaseParser.readObjectNumber()``."""
        self.skip_whitespace()
        value = self.read_int()
        if value < 0 or value >= self.OBJECT_NUMBER_THRESHOLD:
            raise PDFParseError(
                f"object number {value!r} has more than 10 digits or is negative",
                position=self.position,
            )
        return value

    def read_generation_number(self) -> int:
        """Read a generation number, validating against the upstream
        ``GENERATION_NUMBER_THRESHOLD`` (65535) and rejecting negative
        values. Mirrors upstream ``BaseParser.readGenerationNumber()``."""
        self.skip_whitespace()
        value = self.read_int()
        if value < 0 or value > self.GENERATION_NUMBER_THRESHOLD:
            raise PDFParseError(
                f"generation number {value!r} has more than 5 digits",
                position=self.position,
            )
        return value
