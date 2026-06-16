from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from pypdfbox.io import RandomAccessRead

from .parse_error import PDFParseError

if TYPE_CHECKING:
    from pypdfbox.cos.cos_array import COSArray
    from pypdfbox.cos.cos_base import COSBase
    from pypdfbox.cos.cos_dictionary import COSDictionary
    from pypdfbox.cos.cos_document import COSDocument
    from pypdfbox.cos.cos_name import COSName
    from pypdfbox.cos.cos_number import COSNumber
    from pypdfbox.cos.cos_object import COSObject
    from pypdfbox.cos.cos_object_key import COSObjectKey
    from pypdfbox.cos.cos_string import COSString

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

    # Mirrors upstream's ``this instanceof PDFStreamParser`` discriminator in
    # ``BaseParser.parseDirObject``: a content-stream parser returns ``None``
    # (not ``COSNull.NULL``) for a skipped unexpected dir-object so the
    # enclosing ``parseCOSArray`` corrupt-element recovery fires instead of
    # silently inserting a null element. Overridden to ``True`` on
    # ``PDFStreamParser`` only. Implemented as a class attribute rather than
    # an ``isinstance`` check to avoid a circular import of the subclass.
    _is_pdf_stream_parser: ClassVar[bool] = False

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

    def get_object_from_pool(self, key: COSObjectKey) -> COSObject:
        """Return the (lazy) ``COSObject`` placeholder for ``key`` from the
        bound document's object pool. Mirrors upstream
        ``BaseParser.getObjectFromPool(COSObjectKey)`` (line 257) — without
        a bound document the upstream method raises ``IOException`` because
        a content-stream reference can't be resolved; we mirror that with a
        :class:`PDFParseError`."""
        if self._document is None:
            raise PDFParseError(
                f"object reference {key} at offset {self.position} "
                "in content stream",
                position=self.position,
            )
        return self._document.get_object_from_pool(key)

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
    def is_lf(cls, b: int) -> bool:
        """Mirrors upstream ``BaseParser.isLF(int)`` (line 1274) — true iff
        ``b`` is the ASCII LF byte (0x0A)."""
        return b == cls.ASCII_LF

    @classmethod
    def is_cr(cls, b: int) -> bool:
        """Mirrors upstream ``BaseParser.isCR(int)`` (line 1279) — true iff
        ``b`` is the ASCII CR byte (0x0D)."""
        return b == cls.ASCII_CR

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
        """Parse an integer literal: optional ``+``/``-`` followed by digits.

        Mirrors upstream ``BaseParser.readInt`` (Java line 600): leading
        PDF whitespace (including ``%`` comments) is consumed before the
        digit run so callers may rely on the same behaviour as Java.
        """
        self.skip_whitespace()
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
        """Read a long integer; mirrors upstream ``BaseParser.readLong``
        (Java line 628). Python ints are unbounded so this delegates to
        :meth:`read_int`.
        """
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

        Real numbers may use a leading or trailing decimal point. PDF spec
        does NOT allow scientific notation, but PDFBox's lenient
        ``BaseParser.parseCOSNumber`` accepts ``e``/``E`` followed by an
        optional sign and exponent digits — real-world PDFs sometimes
        carry ``1.5e-2``-shaped reals. A trailing ``e``/``E`` with no
        following exponent digit is stripped and rewound, matching
        upstream parseCOSNumber (Java bytecode offsets 95-149)."""
        start_pos = self.position
        sign_chr = b""
        b = self._src.read()
        if b in (0x2B, 0x2D):
            sign_chr = bytes((b,))
            b = self._src.read()
        body = bytearray()
        saw_dot = False
        saw_exp = False
        while b != RandomAccessRead.EOF:
            if self.is_digit(b):
                body.append(b)
            elif b == 0x2E and not saw_dot and not saw_exp:  # '.'
                saw_dot = True
                body.append(b)
            elif b in (0x65, 0x45) and not saw_exp:  # 'e' / 'E'
                saw_exp = True
                body.append(b)
                # Accept an optional sign immediately after the exponent
                # marker (``1.5e-2``).
                nxt = self._src.read()
                if nxt in (0x2B, 0x2D):
                    body.append(nxt)
                    b = self._src.read()
                else:
                    b = nxt
                continue
            else:
                self._src.rewind(1)
                break
            b = self._src.read()
        # Strip a trailing ``e``/``E`` (no exponent digits followed) and
        # rewind the source so the next read sees that ``e``/``E`` again —
        # upstream parseCOSNumber strips it before invoking COSNumber.get.
        if body and body[-1] in (0x65, 0x45):
            body.pop()
            self._src.rewind(1)
            saw_exp = False
        if not body or body == b".":
            raise PDFParseError("expected number", position=start_pos)
        text = (sign_chr + bytes(body)).decode("ascii")
        try:
            return float(text) if (saw_dot or saw_exp) else int(text)
        except ValueError as exc:
            # Pathological number tokens (e.g. ``1.5e+`` with no exponent
            # digit) reach here from the lenient accept set above; surface
            # them as a parse error rather than a raw ``ValueError`` so
            # callers can treat number-read failures uniformly.
            raise PDFParseError(
                f"invalid number {text!r}", position=start_pos
            ) from exc

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
        """Parse a name object and return the raw decoded byte sequence.

        Mirrors upstream ``BaseParser.parseCOSName()`` (line 1412) byte for
        byte. The ``#XX`` hex escape reads BOTH following bytes via ``read()``
        (not ``peek``):

        * both hex digits → write the decoded byte and continue;
        * one byte is EOF → log "Premature EOF" and stop WITHOUT writing the
          ``#`` (so ``/AB#`` decodes to ``AB``, matching PDFBox 3.0.7);
        * otherwise (both present, at least one non-hex) → push the second
          byte back, write a literal ``#``, and re-process the first byte in
          the loop (so ``/A#GB`` decodes to ``A#GB``).
        """
        start_pos = self.position
        b = self._src.read()
        if b != 0x2F:  # '/'
            raise PDFParseError("expected name (leading '/')", position=start_pos)
        out = bytearray()
        b = self._src.read()
        while not self.is_end_of_name(b):
            if b == 0x23:  # '#' — hex escape
                ch1 = self._src.read()
                ch2 = self._src.read()
                if (
                    ch1 != RandomAccessRead.EOF
                    and self.is_hex_digit(ch1)
                    and ch2 != RandomAccessRead.EOF
                    and self.is_hex_digit(ch2)
                ):
                    out.append(int(bytes((ch1, ch2)).decode("ascii"), 16))
                    b = self._src.read()
                elif ch1 == RandomAccessRead.EOF or ch2 == RandomAccessRead.EOF:
                    # Premature EOF: upstream logs and stops, discarding the
                    # dangling '#'. Match by breaking without writing it.
                    b = RandomAccessRead.EOF
                    break
                else:
                    # Neither EOF but not a valid hex pair: rewind the second
                    # byte, keep '#' literally, and re-process the first byte.
                    self._src.rewind(1)
                    b = ch1
                    out.append(0x23)
            else:
                out.append(b)
                b = self._src.read()
        if b != RandomAccessRead.EOF:
            self._src.rewind(1)
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
                # PDFBox's lenient literal-string loop returns the bytes
                # accumulated so far when EOF arrives before a closing ')'.
                return bytes(out)
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
            else:
                # Upstream ``BaseParser.parseCOSString`` writes every other
                # byte verbatim — including bare CR / LF. It does NOT perform
                # the ISO 32000-1 §7.3.4.2 EOL→LF normalization on
                # unescaped end-of-line bytes (only the backslash + EOL line
                # continuation is special, handled in ``_consume_escape``).
                # Storing the raw byte keeps the decoded payload byte-identical
                # to PDFBox 3.0.7 (verified by the live oracle).
                out.append(b)

    def check_for_end_of_string(self, braces_parameter: int) -> int:
        """Patch for malformed literal strings — see PDFBOX-276 / 1217.
        Mirrors upstream ``BaseParser.checkForEndOfString(int)`` (line 494).

        Looks ahead up to three bytes; if they form one of the documented
        end-of-string sequences (``CR/LF/CRLF`` followed by ``/`` or ``>``)
        the brace count is forced to 0 so the caller stops accumulating
        bytes into the literal string. Otherwise ``braces_parameter`` is
        returned unchanged."""
        if braces_parameter == 0:
            return 0
        next_three = bytearray(3)
        amount_read = self._src.read_into(next_three)
        if amount_read > 0:
            self._src.rewind(amount_read)
        if amount_read < 3:
            return braces_parameter
        if self.is_eol(next_three[0]) and next_three[1] in (0x2F, 0x3E):  # '/', '>'
            return 0
        if (
            next_three[0] == 0x0D
            and next_three[1] == 0x0A
            and next_three[2] in (0x2F, 0x3E)  # '/', '>'
        ):
            return 0
        return braces_parameter

    def _check_for_end_of_string(self, depth: int) -> int:
        """Back-compat alias for :meth:`check_for_end_of_string` — kept for
        any internal callers that still reference the leading-underscore
        spelling. Prefer the upstream-name method in new code."""
        return self.check_for_end_of_string(depth)

    def _consume_escape(self, out: bytearray, depth: int) -> int:
        b = self._src.read()
        if b == RandomAccessRead.EOF:
            # Java writes the EOF sentinel through its byte-oriented output
            # stream on a trailing backslash, yielding 0xFF, then exits the
            # outer loop at EOF.
            out.append(0xFF)
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
        """Parse a hex string ``< ... >`` per §7.3.4.3.

        Mirrors the leniency of upstream ``BaseParser.parseCOSHexString()``:
        embedded whitespace (space, LF, CR, HT, BS, FF) is ignored; an odd
        trailing digit is implicitly padded with ``0``; and a stray non-hex,
        non-whitespace character triggers recovery — any dangling half-pair is
        discarded and the parser skips to the closing ``>`` (decoding only the
        clean leading pairs). EOF before ``>`` is the only hard error.
        """
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
            # Upstream skips space/LF/HT/CR/BS/FF between hex digits.
            if b in (0x20, 0x0A, 0x09, 0x0D, 0x08, 0x0C):
                continue
            if self.is_hex_digit(b):
                digits.append(b)
                continue
            # Non-hex, non-whitespace: discard a dangling half-pair, then read
            # to the closing '>' (matching upstream's skip-to-close recovery).
            if len(digits) % 2:
                digits.pop()
            while b != 0x3E and b != RandomAccessRead.EOF:
                b = self._src.read()
            if b == RandomAccessRead.EOF:
                raise PDFParseError("unterminated hex string", position=start_pos)
            break
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

    # ---------- COS-object parse helpers (upstream BaseParser parity) ----------
    #
    # The upstream Java BaseParser is concrete and includes the parse_cos_*
    # / parse_dir_object methods directly. Our pypdfbox layout splits the
    # higher-level ``COSParser`` overrides off into ``cos_parser.py`` for
    # readability, but the upstream surface is mirrored here so:
    #
    #   * BaseParser-only callers (and parity tooling) see the same
    #     methods on the same class as upstream;
    #   * COSParser's overrides — kept for tighter integration with its
    #     recursion-guard and stream-body machinery — replace these at the
    #     subclass boundary without breaking any caller.

    def parse_dir_object(self) -> COSBase | None:
        """Parse one direct object per upstream
        ``BaseParser.parseDirObject()`` (line 969). Returns ``None`` at EOF
        or for unknown content the parser cannot recover from."""
        # Late imports — cos types are not safe to import at module level
        # for the subclass chain, but the cos package itself does not import
        # from pypdfbox.pdfparser so a runtime import here is safe.
        from pypdfbox.cos.cos_boolean import COSBoolean
        from pypdfbox.cos.cos_null import COSNull
        from pypdfbox.cos.cos_object import COSObject

        self.skip_whitespace()
        c = self._src.peek()
        if c == RandomAccessRead.EOF:
            return None
        # The container branches below recurse (array/dict elements are
        # themselves parsed via ``parse_dir_object``). Deeply nested direct
        # ``[...]`` / ``<<...>>`` structures in a malformed PDF can exhaust
        # Python's recursion limit; convert that into the parser's own error
        # type so callers catching ``PDFParseError`` aren't surprised by a
        # raw ``RecursionError``. Legitimate PDFs nest only a few levels
        # (direct nesting, not indirect references), so this never fires on
        # real documents — it is a hostile-input guard. (Upstream PDFBox is
        # likewise recursive here; it tolerates more only because the JVM
        # stack is deeper.)
        try:
            if c == 0x3C:  # '<'
                self._src.read()
                second = self._src.peek()
                self._src.rewind(1)
                if second == 0x3C:
                    return self.parse_cos_dictionary(is_direct=True)
                return self.parse_cos_string()
            if c == 0x5B:  # '['
                return self.parse_cos_array()
        except RecursionError as exc:
            raise PDFParseError(
                "PDF object nesting too deep to parse", position=self.position
            ) from exc
        if c == 0x28:  # '('
            return self.parse_cos_string()
        if c == 0x2F:  # '/'
            return self.parse_cos_name()
        if c == 0x6E:  # 'n' — null
            self.read_expected_string(b"null", skip_spaces=False)
            return COSNull.NULL
        if c == 0x74:  # 't' — true
            self.read_expected_string(b"true", skip_spaces=False)
            return COSBoolean.TRUE
        if c == 0x66:  # 'f' — false
            self.read_expected_string(b"false", skip_spaces=False)
            return COSBoolean.FALSE
        if c == 0x52:  # 'R' — bare-reference recovery placeholder
            self._src.read()
            # Upstream returns ``new COSObject(null)`` as a sentinel; the
            # caller (``parse_cos_array``) only checks ``isinstance``,
            # never reads object_number. ``(0, 0)`` keeps the construction
            # valid under our non-negative-number invariant.
            return COSObject(0, 0)
        if self.is_digit(c) or c in (0x2B, 0x2D, 0x2E):  # '+', '-', '.'
            return self.parse_cos_number()
        # Recovery branch: read the unknown token and decide whether to
        # rewind it (for endobj/endstream) or warn-and-skip (PDFNull).
        start_offset = self.position
        bad_string = self.read_string()
        if not bad_string:  # pragma: no cover - corrupt-stream recovery edge
            peek = self._src.peek()
            raise PDFParseError(
                f"Unknown dir object c={chr(c)!r} cInt={c} peek="
                f"{chr(peek) if peek != -1 else '-1'!r} peekInt={peek} at offset "
                f"{self.position} (start offset: {start_offset})",
                position=start_offset,
            )
        if bad_string in (self.ENDOBJ_STRING, self.ENDSTREAM_STRING):
            # Put it back so the outer caller sees the terminator.
            self._src.rewind(len(bad_string.encode("latin-1")))
            return None
        _LOG.warning(
            "Skipped unexpected dir object = %r at offset %d (start offset: %d)",
            bad_string,
            self.position,
            start_offset,
        )
        # Upstream: ``return this instanceof PDFStreamParser ? null :
        # COSNull.NULL;`` — a content-stream parser returns ``None`` so the
        # enclosing ``parse_cos_array`` treats the skipped token as a corrupt
        # element (recover + continue) rather than appending a null element.
        return None if self._is_pdf_stream_parser else COSNull.NULL

    def parse_cos_array(self) -> COSArray:
        """Parse a PDF ``[ ... ]`` array per upstream
        ``BaseParser.parseCOSArray()`` (line 764). Permissive on bad
        elements: a corrupt entry is logged and the array continues until
        the closing ``]`` or an ``endobj`` / ``endstream`` keyword is
        encountered."""
        from pypdfbox.cos.cos_array import COSArray
        from pypdfbox.cos.cos_integer import COSInteger
        from pypdfbox.cos.cos_object import COSObject

        start_position = self.position
        self.read_expected_char("[")
        po = COSArray()
        self.skip_whitespace()
        while True:
            i = self._src.peek()
            if i <= 0 or i == 0x5D:  # ']' or EOF
                break
            pbo = self.parse_dir_object()
            if isinstance(pbo, COSObject):
                # Replace the placeholder with a resolved indirect reference
                # using the two preceding integers as ``num gen R`` (PDFBOX-385).
                pbo = None
                if len(po) > 1 and isinstance(po.get(len(po) - 1), COSInteger):
                    gen_number = po.remove_at(len(po) - 1)
                    if len(po) > 0 and isinstance(po.get(len(po) - 1), COSInteger):
                        number = po.remove_at(len(po) - 1)
                        num_value = number.value
                        gen_value = gen_number.value
                        if num_value >= 0 and gen_value >= 0:
                            key = self.get_object_key(num_value, gen_value)
                            pbo = self.get_object_from_pool(key)
                        else:
                            _LOG.warning(
                                "Invalid value(s) for an object key %d %d",
                                num_value,
                                gen_value,
                            )
            if pbo is None:
                _LOG.warning(
                    "Corrupt array element at offset %d, start offset: %d",
                    self.position,
                    start_position,
                )
                is_this_the_end = self.read_string()
                # pragma: no cover - nested-array corruption recovery
                if not is_this_the_end and self._src.peek() == 0x5B:  # '['  # pragma: no cover
                    return po
                self._src.rewind(len(is_this_the_end.encode("latin-1")))
                if is_this_the_end in (self.ENDOBJ_STRING, self.ENDSTREAM_STRING):
                    return po
            else:
                po.add(pbo)
            self.skip_whitespace()
        # consume ']'
        self._src.read()
        self.skip_whitespace()
        return po

    def parse_cos_dictionary(self, is_direct: bool = False) -> COSDictionary:
        """Parse a PDF ``<< ... >>`` dictionary per upstream
        ``BaseParser.parseCOSDictionary(boolean)`` (line 276). Permissive on
        malformed input: a stray non-``/`` byte triggers
        :meth:`read_until_end_of_cos_dictionary` for recovery."""
        from pypdfbox.cos.cos_dictionary import COSDictionary

        self.read_expected_char("<")
        self.read_expected_char("<")
        self.skip_whitespace()
        obj = COSDictionary()
        obj.set_direct(is_direct)
        while True:
            self.skip_whitespace()
            c = self._src.peek()
            if c == 0x3E:  # '>'
                break
            if c == 0x2F:  # '/'
                if not self.parse_cos_dictionary_name_value_pair(obj):
                    return obj
            else:
                _LOG.warning(
                    "Invalid dictionary, found: %r but expected: '/' at offset %d",
                    chr(c) if c >= 0 else "",
                    self.position,
                )
                if self.read_until_end_of_cos_dictionary():
                    return obj
        try:
            self.read_expected_char(">")
            self.read_expected_char(">")
        except PDFParseError:
            _LOG.warning(
                "Invalid dictionary, can't find end of dictionary at offset %d",
                self.position,
            )
        return obj

    def parse_cos_dictionary_name_value_pair(self, obj: COSDictionary) -> bool:
        """Parse one ``/Name value`` entry into ``obj``. Returns ``False``
        if the dictionary is corrupt (caller bails). Mirrors upstream
        ``BaseParser.parseCOSDictionaryNameValuePair`` (line 384)."""
        from pypdfbox.cos.cos_integer import COSInteger

        key = self.parse_cos_name()
        if key is None or not key.get_name():
            _LOG.warning("Empty COSName at offset %d", self.position)
        value = self.parse_cos_dictionary_value()
        self.skip_whitespace()
        if value is None:
            _LOG.warning("Bad dictionary declaration at offset %d", self.position)
            return False
        if isinstance(value, COSInteger) and not value.is_valid():
            _LOG.warning(
                "Skipped out of range number value at offset %d", self.position
            )
        else:
            value.set_direct(True)
            obj.set_item(key, value)
        return True

    def parse_cos_dictionary_value(self) -> COSBase | None:
        """Parse a dictionary value, including the special ``num gen R``
        indirect-reference recovery. Mirrors upstream
        ``BaseParser.parseCOSDictionaryValue`` (line 216)."""
        from pypdfbox.cos.cos_integer import COSInteger
        from pypdfbox.cos.cos_null import COSNull
        from pypdfbox.cos.cos_number import COSNumber

        num_offset = self.position
        value = self.parse_dir_object()
        self.skip_whitespace()
        if not isinstance(value, COSNumber) or not self.is_digit_at():
            return value
        gen_offset = self.position
        generation_number = self.parse_dir_object()
        self.skip_whitespace()
        self.read_expected_char("R")
        if not isinstance(value, COSInteger):
            _LOG.error(
                "expected number, actual=%r at offset %d", value, num_offset
            )
            return COSNull.NULL
        if not isinstance(generation_number, COSInteger):
            _LOG.error(
                "expected number, actual=%r at offset %d",
                generation_number,
                gen_offset,
            )
            return COSNull.NULL
        obj_number = value.value
        if obj_number <= 0:
            _LOG.warning(
                "invalid object number value =%d at offset %d",
                obj_number,
                num_offset,
            )
            return COSNull.NULL
        gen_number = generation_number.value
        if gen_number < 0:  # pragma: no cover - lexer rejects negative ints
            _LOG.error(
                "invalid generation number value =%d at offset %d",
                gen_number,
                num_offset,
            )
            return COSNull.NULL
        return self.get_object_from_pool(self.get_object_key(obj_number, gen_number))

    def read_until_end_of_cos_dictionary(self) -> bool:
        """Skip bytes until a ``/``, ``>``, ``endstream``, ``endobj``, or
        EOF is reached — recovery for malformed dictionaries. Returns
        ``True`` if the object/file ended (caller stops parsing); returns
        ``False`` if a ``/`` was found and parsing can continue. Mirrors
        upstream ``BaseParser.readUntilEndOfCOSDictionary`` (line 346)."""
        # Match upstream byte-by-byte: peek 'e n d' then 's t r e a m' or
        # 'o b j' to detect early end-of-object markers.
        c = self._src.read()
        EOF = RandomAccessRead.EOF
        while c != EOF and c != 0x2F and c != 0x3E:
            if c == 0x65:  # 'e'
                c = self._src.read()
                if c == 0x6E:  # 'n'
                    c = self._src.read()
                    if c == 0x64:  # 'd'
                        c = self._src.read()
                        is_stream = (
                            c == 0x73  # 's'
                            and self._src.read() == 0x74  # 't'
                            and self._src.read() == 0x72  # 'r'
                            and self._src.read() == 0x65  # 'e'
                            and self._src.read() == 0x61  # 'a'
                            and self._src.read() == 0x6D  # 'm'
                        )
                        is_obj = (
                            not is_stream
                            and c == 0x6F  # 'o'
                            and self._src.read() == 0x62  # 'b'
                            and self._src.read() == 0x6A  # 'j'
                        )
                        if is_stream or is_obj:
                            return True
            c = self._src.read()
        if c == EOF:
            return True
        self._src.rewind(1)
        return False

    def parse_cos_name(self) -> COSName:
        """Parse a name object ``/Foo`` and return a :class:`COSName`.
        Mirrors upstream ``BaseParser.parseCOSName()`` (line 882)."""
        from pypdfbox.cos.cos_name import COSName

        return COSName.get_pdf_name(self.read_name_bytes())

    def parse_cos_number(self) -> COSNumber:
        """Parse a numeric token and return a :class:`COSNumber` (either
        :class:`COSInteger` or :class:`COSFloat`). Mirrors upstream
        ``BaseParser.parseCOSNumber()`` (line 1051) — including the
        ``74191endobj`` recovery where a trailing ``e``/``E`` is rewound."""
        from pypdfbox.cos.cos_float import COSFloat
        from pypdfbox.cos.cos_integer import COSInteger

        buf = bytearray()
        ic = self._src.read()
        while ic != RandomAccessRead.EOF:
            c = ic
            if (
                self.is_digit(c)
                or c in (0x2B, 0x2D, 0x2E, 0x45, 0x65)  # '+ - . E e'
            ):
                buf.append(c)
                ic = self._src.read()
            else:
                break
        if ic != RandomAccessRead.EOF:
            self._src.rewind(1)
        if not buf:
            raise PDFParseError("expected number", position=self.position)
        # Upstream PDFBOX-5025: drop a stray trailing 'e'/'E' and rewind so
        # 'endobj' / 'endstream' tokens are not consumed as part of a real.
        last = buf[-1]
        if last in (0x65, 0x45):  # 'e' or 'E'
            buf.pop()
            self._src.rewind(1)
        text = bytes(buf).decode("ascii")
        if any(ch in text for ch in (".", "e", "E")):
            return COSFloat(text)
        try:
            return COSInteger.get(int(text))
        except ValueError as exc:
            # CPython caps int() string parsing at sys.get_int_max_str_digits()
            # (4300 digits by default) as a CPU-DoS guard. A pathologically long
            # integer literal in a malformed PDF would otherwise leak a bare
            # ValueError to the caller instead of the parser's own error type.
            raise PDFParseError(
                "integer literal too long to parse", position=self.position
            ) from exc

    def parse_cos_string(self) -> COSString:
        """Parse a literal ``( ... )`` or hex ``< ... >`` string per upstream
        ``BaseParser.parseCOSString()`` (line 537). Includes balanced-paren
        handling, octal escapes, and EOL-continuation escape support — all
        delegated to :meth:`read_literal_string` / :meth:`parse_cos_hex_string`."""
        from pypdfbox.cos.cos_string import COSString

        next_char = self._src.read()
        if next_char == 0x3C:  # '<'
            return self.parse_cos_hex_string()
        if next_char != 0x28:  # '('
            raise PDFParseError(
                "parseCOSString string should start with '(' or '<' and not "
                f"{chr(next_char) if next_char >= 0 else ''!r} at offset "
                f"{self.position}",
                position=self.position,
            )
        # Reuse the byte-level literal-string reader; it expects to be
        # positioned at '(' so rewind first.
        self._src.rewind(1)
        return COSString(self.read_literal_string())

    def parse_cos_hex_string(self) -> COSString:
        """Parse a hex string ``< ... >`` with the upstream fail-fast /
        skip-to-close recovery semantic. Assumes the leading ``<`` was
        already consumed by the caller (matching upstream contract).
        Mirrors ``BaseParser.parseCOSHexString()`` (line 702)."""
        from pypdfbox.cos.cos_string import COSString

        s_buf = bytearray()
        while True:
            c = self._src.read()
            if c >= 0 and self.is_hex_digit(c):
                s_buf.append(c)
            elif c == 0x3E:  # '>'
                break
            elif c < 0:
                raise PDFParseError(
                    "Missing closing bracket for hex string. Reached EOS.",
                    position=self.position,
                )
            elif c in (0x20, 0x0A, 0x09, 0x0D, 0x08, 0x0C):
                continue
            else:
                # Skip past invalid input until ``>`` — drop a dangling
                # half-pair first so the resulting hex decodes cleanly.
                if len(s_buf) % 2:
                    s_buf.pop()
                while c != 0x3E and c >= 0:
                    c = self._src.read()
                if c < 0:
                    raise PDFParseError(
                        "Missing closing bracket for hex string. Reached EOS.",
                        position=self.position,
                    )
                break
        return COSString.parse_hex(s_buf.decode("ascii"))
