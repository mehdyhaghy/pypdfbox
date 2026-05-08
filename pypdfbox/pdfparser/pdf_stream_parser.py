from __future__ import annotations

from collections.abc import Iterator
from threading import Lock
from typing import TYPE_CHECKING, ClassVar

from pypdfbox.cos import (
    COSBase,
    COSBoolean,
    COSDictionary,
    COSName,
    COSNull,
    COSNumber,
)
from pypdfbox.io import RandomAccessRead, RandomAccessReadBuffer

from .cos_parser import COSParser
from .parse_error import PDFParseError

if TYPE_CHECKING:
    from pypdfbox.contentstream.pd_content_stream import PDContentStream


# Operator name constants (subset).
_OP_BEGIN_INLINE_IMAGE = "BI"
_OP_BEGIN_INLINE_IMAGE_DATA = "ID"
_OP_END_INLINE_IMAGE = "EI"


class Operator:
    """Content-stream operator token.

    Mirrors ``org.apache.pdfbox.contentstream.operator.Operator`` for the
    subset needed by the tokenizer. The contentstream module (§6.7) will
    augment this with operator-name constants and a singleton pool; for
    now it's a small value type holding the keyword and, for the inline-
    image data operator (``ID``), the raw image bytes captured between
    ``ID`` and ``EI``.

    Two operators carry parameters out of band:
    - ``ID`` — ``image_data`` is the raw byte payload between ``ID`` and ``EI``.
    - ``BI`` — ``image_parameters`` is the inline-image parameter dictionary.
    """

    __slots__ = ("_name", "image_data", "image_parameters")

    # Singleton cache mirroring upstream's ``ConcurrentHashMap`` of
    # cached operator instances. Inline-image operators bypass this
    # cache because they carry per-occurrence ``image_data`` /
    # ``image_parameters`` payloads.
    _operators: ClassVar[dict[str, Operator]] = {}
    _operators_lock: ClassVar[Lock] = Lock()

    def __init__(
        self,
        name: str,
        image_data: bytes | None = None,
        image_parameters: COSDictionary | None = None,
    ) -> None:
        # Upstream's private constructor rejects operator names that
        # start with ``/`` (those are name-object operands, not
        # operators).
        if name.startswith("/"):
            raise ValueError(
                f"Operators are not allowed to start with / '{name}'"
            )
        self._name = name
        self.image_data = image_data
        self.image_parameters = image_parameters

    @classmethod
    def get_operator(cls, name: str) -> Operator:
        """Return a (possibly cached) ``Operator`` for ``name``. Mirrors
        upstream's ``Operator.getOperator(String)`` static factory.

        Inline-image operators (``BI`` / ``ID``) bypass the cache
        because each occurrence carries distinct ``image_parameters`` /
        ``image_data`` payloads — caching would alias state across
        unrelated parses.
        """
        if cls.is_inline_image_operator_name(name):
            return cls(name)
        cached = cls._operators.get(name)
        if cached is not None:
            return cached
        with cls._operators_lock:
            cached = cls._operators.get(name)
            if cached is None:
                cached = cls(name)
                cls._operators[name] = cached
            return cached

    @staticmethod
    def is_inline_image_operator_name(name: str) -> bool:
        """Return ``True`` if ``name`` is one of the two inline-image
        operator keywords (``BI`` or ``ID``) that upstream's
        ``getOperator`` deliberately bypasses the singleton cache for —
        each occurrence carries a distinct payload (``image_parameters``
        / ``image_data``). Useful for callers that need to special-case
        inline-image dispatch without re-stating the byte literals.
        """
        return name in (_OP_BEGIN_INLINE_IMAGE, _OP_BEGIN_INLINE_IMAGE_DATA)

    def is_inline_image(self) -> bool:
        """Return ``True`` if this operator's name is the inline-image
        begin (``BI``) or inline-image-data (``ID``) keyword. Convenience
        predicate paired with :meth:`is_inline_image_operator_name`."""
        return self.is_inline_image_operator_name(self._name)

    def has_image_data(self) -> bool:
        """Return ``True`` if this operator carries inline-image bytes.
        Upstream callers gate ``ID``/``BI`` post-processing on
        ``getImageData() != null`` — this predicate keeps the same
        check from leaking the optional-typed accessor."""
        return self.image_data is not None

    def has_image_parameters(self) -> bool:
        """Return ``True`` if this operator carries an inline-image
        parameter dictionary. Companion to :meth:`has_image_data` that
        mirrors the ``getImageParameters() != null`` pattern in upstream
        callers."""
        return self.image_parameters is not None

    @property
    def name(self) -> str:
        return self._name

    def get_name(self) -> str:
        return self._name

    def get_image_data(self) -> bytes | None:
        return self.image_data

    def set_image_data(self, data: bytes) -> None:
        self.image_data = data

    def get_image_parameters(self) -> COSDictionary | None:
        return self.image_parameters

    def set_image_parameters(self, params: COSDictionary) -> None:
        self.image_parameters = params

    def __repr__(self) -> str:
        # Mirror upstream's ``toString()`` — ``"PDFOperator{<name>}"`` —
        # so ``str(op)`` and ``repr(op)`` round-trip with PDFBox output.
        return f"PDFOperator{{{self._name}}}"

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Operator):
            return NotImplemented
        return (
            self._name == other._name
            and self.image_data == other.image_data
        )

    def __hash__(self) -> int:
        return hash(("Operator", self._name))

    def __len__(self) -> int:
        # Convenience parity with ``op.getName().length()`` in upstream
        # callers — saves a hop through the name accessor when sizing
        # operator buffers / pretty-printers.
        return len(self._name)


class PDFStreamParser(COSParser):
    """
    Tokenize a content stream into a sequence of operands and operators
    per ISO 32000-1 §7.8 / §9 / §10. Mirrors
    ``org.apache.pdfbox.pdfparser.PDFStreamParser``.

    A content stream is conceptually a series of ``<operands...> <operator>``
    tuples. Operands are direct COS objects (numbers, names, strings,
    arrays, dicts, booleans, nulls); operators are alphabetic keywords
    like ``q``, ``Q``, ``BT``, ``Tf``, ``Tj``, ``re``, ``cm``, etc., not
    prefixed with ``/``. A few operators include the apostrophe (``'``)
    and quotation mark (``"``) — text-show variants from §9.4.3.

    Inline images (§8.9.7) are handled inline: ``BI`` opens the parameter
    dictionary, ``ID`` introduces the raw image bytes, ``EI`` closes the
    segment. The raw bytes between ``ID`` and ``EI`` are NOT parsed as
    PDF tokens — they're captured wholesale and attached as
    ``image_data`` on the ``ID`` operator (matching upstream PDFBox,
    which returns the begin-image-data operator carrying the bytes).
    """

    # Maximum scan window used to disambiguate a real ``EI`` from an
    # ``EI`` byte pair embedded in image data — mirrors PDFBox's
    # ``MAX_BIN_CHAR_TEST_LENGTH = 10``.
    MAX_BIN_CHAR_TEST_LENGTH: ClassVar[int] = 10

    # Whitespace bytes recognised as a separator immediately following a
    # candidate ``EI`` — matches PDFBox's ``isSpaceOrReturn`` (LF, CR, SP).
    _EI_SEP: ClassVar[frozenset[int]] = frozenset({0x0A, 0x0D, 0x20})

    def __init__(self, source: RandomAccessRead) -> None:
        super().__init__(source, document=None)
        self._inline_image_depth = 0
        self._inline_offset = 0

    # ---------- alternate constructors ----------

    @classmethod
    def from_bytes(cls, data: bytes) -> PDFStreamParser:
        """Construct a parser over an in-memory byte buffer. Mirrors
        the upstream ``PDFStreamParser(byte[] bytes)`` convenience
        constructor that wraps the bytes in a ``RandomAccessReadBuffer``
        before delegating to the primary constructor."""
        return cls(RandomAccessReadBuffer(data))

    @classmethod
    def from_content_stream(
        cls, pd_content_stream: PDContentStream
    ) -> PDFStreamParser:
        """Construct a parser over the bytes of a ``PDContentStream``.
        Mirrors the upstream
        ``PDFStreamParser(PDContentStream pdContentstream)`` constructor,
        which calls ``pdContentstream.getContentsForStreamParsing()`` to
        get the underlying ``RandomAccessRead``."""
        return cls(pd_content_stream.get_contents_for_stream_parsing())

    # ---------- public API ----------

    def parse_next_token(self) -> COSBase | Operator | None:
        """Return the next operand or operator. ``None`` at EOF."""
        # Upstream guards every call with a ``source.isClosed()`` check;
        # if the parser has already been closed (e.g. mid-parse on an
        # unrecoverable malformed dictionary) further token requests
        # return ``None`` rather than raising.
        if self.is_closed():
            return None
        self.skip_whitespace()
        if self.is_eof():
            return None
        b = self.peek_byte()
        if b == RandomAccessRead.EOF:
            return None

        # Dispatch on the first byte. Operands are handled via COSParser;
        # operators are picked up by the default branch.
        if b == 0x3C:  # '<' — '<<' (dict) or '<...>' (hex string)
            second = self._peek_two_bytes()[1]
            if second == 0x3C:
                try:
                    return self.parse_cos_dictionary()
                except PDFParseError:
                    self.close()
                    return None
            return self._read_cos_hex_string()
        if b == 0x5B:  # '[' — array
            try:
                return self.parse_cos_array()
            except PDFParseError:
                self.close()
                return None
        if b == 0x28:  # '(' — literal string
            return self._read_cos_literal_string()
        if b == 0x2F:  # '/' — name
            return COSName.get_pdf_name(self.read_name())
        if b == 0x6E:  # 'n' — possibly 'null' or an operator starting with 'n'
            return self._parse_n_keyword()
        if b in (0x74, 0x66):  # 't' / 'f' — true / false / operator
            return self._parse_tf_keyword()
        if b in (0x2B, 0x2D, 0x2E) or self.is_digit(b):
            return self._parse_number_token()
        if b == 0x42:  # 'B' — possibly BI (begin inline image) or other op
            return self._parse_b_keyword()
        if b == 0x49:  # 'I' — special-cased ID operator
            return self._parse_id_operator()
        if b == 0x5D:  # ']' — stray close-bracket. Upstream returns COSNull.
            self.read_byte()
            return COSNull.NULL
        # Default: an operator keyword (alphabetic + ' " * etc.).
        return self._read_operator_token()

    def parse(self) -> list[COSBase | Operator]:
        """Drain the stream — mirrors PDFBox's ``parse()``."""
        return list(self.tokens())

    def tokens(self) -> Iterator[COSBase | Operator]:
        while True:
            tok = self.parse_next_token()
            if tok is None:
                return
            yield tok

    # ---------- upstream-named aliases ----------

    def get_tokens(self) -> list[COSBase | Operator]:
        """Eager list form — drains the parser. Mirrors PDFBox's
        ``getTokens()`` (which returns ``List<Object>`` of operands and
        operators)."""
        return list(self.tokens())

    def parse_stream(self) -> list[COSBase | Operator]:
        """Alias for :meth:`parse` — the public PDFBox entry point on
        ``PDFStreamParser`` is named ``parse``; some upstream callers
        spelled the action as ``parseStream`` for clarity."""
        return self.parse()

    def is_in_inline_image(self) -> bool:
        """``True`` while the parser is inside a ``BI``/``ID``/``EI``
        inline-image segment. Tracks the same flag PDFBox surfaces via
        its inline-image bookkeeping."""
        return self._inline_image_depth > 0

    def get_inline_image_depth(self) -> int:
        """Return the current inline-image nesting depth. Mirrors
        upstream's private ``inlineImageDepth`` counter — exposed here
        for diagnostics and tests that need to assert the parser
        recovered cleanly after a malformed nested ``BI`` (PDFBOX-6038).
        Always ``0`` outside a ``BI``...``EI`` segment; ``1`` while one
        is open. A value greater than ``1`` is transient — the parser
        immediately raises ``PDFParseError`` and resets the counter."""
        return self._inline_image_depth

    def get_inline_offset(self) -> int:
        """Return the source byte offset where the most recent ``BI``
        opened (``0`` before any inline image has been seen). Mirrors
        upstream's private ``inlineOffset`` field — surfaced here for
        diagnostics and error reporting that needs to point back at the
        opening ``BI`` location after a nested-``BI`` failure."""
        return self._inline_offset

    def seek_to(self, offset: int) -> None:
        """Reposition the underlying source. Wraps :meth:`seek` from
        ``BaseParser``; named to match upstream convenience helpers."""
        self.seek(offset)

    def get_position(self) -> int:
        """Return the current source read position. Mirrors PDFBox's
        ``getPosition()`` accessor."""
        return self.position

    def close(self) -> None:
        """Close the underlying random-access source if it is still
        open. Mirrors PDFBox's public ``close()`` on PDFStreamParser
        which releases the source after parsing finishes. Idempotent —
        repeat calls are no-ops."""
        src = self._src
        if src is not None and not src.is_closed():
            src.close()

    def is_closed(self) -> bool:
        """Return ``True`` once the underlying source has been closed.
        Convenience accessor matching upstream's ``source.isClosed()``
        idiom used throughout PDFBox parsers."""
        return self._src is None or self._src.is_closed()

    # ---------- numbers ----------

    def _parse_number_token(self) -> COSBase:
        """Parse a numeric operand. Content-stream numbers do NOT take
        the ``<n> <m> R`` indirect-reference shape — so we route through
        ``COSNumber.get`` directly rather than ``COSParser._parse_number_or_indirect_reference``.

        Lenient like upstream: an isolated ``+`` becomes ``COSNull.NULL``;
        ``-`` immediately followed by another ``-`` discards the second
        sign (PDFBOX double-negative quirk); ``-`` mid-number is dropped
        (PDFBOX-4064)."""
        buf = bytearray()
        first = self.read_byte()
        buf.append(first)

        # Double-negative quirk: skip a second '-' right after the first.
        if first == 0x2D and self.peek_byte() == 0x2D:
            self.read_byte()

        dot_seen = first == 0x2E
        while True:
            nxt = self.peek_byte()
            if nxt == RandomAccessRead.EOF:
                break
            if self.is_digit(nxt):
                buf.append(self.read_byte())
                continue
            if nxt == 0x2E and not dot_seen:
                buf.append(self.read_byte())
                dot_seen = True
                continue
            if nxt == 0x2D:
                # Drop a stray '-' inside the number (PDFBOX-4064).
                self.read_byte()
                continue
            break

        text = buf.decode("ascii")
        if text == "+":
            # PDFBOX-5906 — isolated '+' is ignored; upstream returns null.
            return COSNull.NULL
        return COSNumber.get(text)

    # ---------- keyword dispatch ----------

    def _parse_n_keyword(self) -> COSBase | Operator:
        kw = self._read_operator_string()
        if kw == "null":
            return COSNull.NULL
        return Operator.get_operator(kw)

    def _parse_tf_keyword(self) -> COSBase | Operator:
        kw = self._read_operator_string()
        if kw == "true":
            return COSBoolean.TRUE
        if kw == "false":
            return COSBoolean.FALSE
        return Operator.get_operator(kw)

    def _parse_b_keyword(self) -> Operator:
        """Handle keywords starting with ``B``. ``BI`` triggers inline-
        image dictionary collection (the actual byte payload is captured
        when the subsequent ``ID`` is parsed)."""
        kw = self._read_operator_string()
        if kw != _OP_BEGIN_INLINE_IMAGE:
            return Operator.get_operator(kw)
        op = Operator(kw)
        # Inline-image: collect /Key value pairs into a dict until we hit
        # the ``ID`` operator (returned as an Operator carrying image_data).
        self._inline_image_depth += 1
        if self._inline_image_depth > 1:
            # Reset and surface the error like upstream (PDFBOX-6038).
            depth = self._inline_image_depth
            offset = self._inline_offset
            self._inline_image_depth = 0
            raise PDFParseError(
                f"Nested '{_OP_BEGIN_INLINE_IMAGE}' operator not allowed at offset "
                f"{self.position}, first: {offset}, depth: {depth}",
                position=self.position,
            )
        self._inline_offset = self.position
        params = COSDictionary()
        op.set_image_parameters(params)
        while True:
            tok = self.parse_next_token()
            if not isinstance(tok, COSName):
                break
            value = self.parse_next_token()
            if not isinstance(value, COSBase):
                # Malformed: bail out, mirror upstream's silent break.
                break
            params.set_item(tok.get_name(), value)
        # ``tok`` is the trailing operator — should be the ``ID`` operator
        # carrying the image bytes. Hand them to the BI op for convenience.
        if isinstance(tok, Operator) and tok.image_data is not None:
            op.set_image_data(tok.image_data)
        self._inline_image_depth -= 1
        return op

    def _parse_id_operator(self) -> Operator:
        """Handle ``ID`` exactly as the inline-image data operator.

        Other uppercase-I operators are legal content-stream operator names,
        so they must flow through the regular operator path.
        """
        kw = self._read_operator_string()
        if kw != _OP_BEGIN_INLINE_IMAGE_DATA:
            return Operator.get_operator(kw)
        # Consume one line break (CR / LF / CRLF) or any single whitespace
        # byte, mirroring upstream's ``skipLinebreak() || isWhitespace()``.
        if not self._skip_linebreak():
            nxt = self.peek_byte()
            if nxt != RandomAccessRead.EOF and self.is_whitespace(nxt):
                self.read_byte()
        # Walk forward looking for ``EI`` followed by whitespace AND not
        # immediately followed by binary data — same heuristic as upstream
        # so embedded ``EI`` byte pairs inside image bytes don't terminate
        # the segment prematurely. Mirrors upstream's loop condition:
        # ``!(EI && sep && !bin) && !isEOF()`` — note that ``isEOF()``
        # becomes true the moment the read cursor is past the last byte,
        # so a real ``EI`` at the very end of the stream terminates the
        # loop via the EOF guard rather than the ``hasNextSpaceOrReturn``
        # check (which sees -1 and returns false).
        out = bytearray()
        last_byte = self.read_byte()
        cur_byte = self.read_byte()
        while True:
            ei_terminates = (
                last_byte == 0x45  # 'E'
                and cur_byte == 0x49  # 'I'
                and self._next_is_ei_separator()
                and self._has_no_following_bin_data()
            )
            if ei_terminates or self.is_eof():
                break
            # last_byte is guaranteed non-EOF here: cur_byte fell behind it
            # but could only be EOF on the next iteration, which we catch
            # via ``is_eof()`` above.
            if last_byte == RandomAccessRead.EOF:
                break
            out.append(last_byte)
            last_byte = cur_byte
            cur_byte = self.read_byte()
        # The ``EI`` operator itself is intentionally NOT unread — upstream
        # discards it because nothing downstream consumes a separate EI op.
        op = Operator(_OP_BEGIN_INLINE_IMAGE_DATA)
        op.set_image_data(bytes(out))
        return op

    def _skip_linebreak(self) -> bool:
        """Consume one EOL marker (CR, LF, or CRLF). Returns True if any
        bytes were consumed."""
        b = self.peek_byte()
        if b == 0x0D:
            self.read_byte()
            if self.peek_byte() == 0x0A:
                self.read_byte()
            return True
        if b == 0x0A:
            self.read_byte()
            return True
        return False

    def _next_is_ei_separator(self) -> bool:
        b = self.peek_byte()
        return b in self._EI_SEP

    @classmethod
    def is_space_or_return(cls, b: int) -> bool:
        """Return ``True`` if ``b`` is the LF (10), CR (13), or SP (32)
        byte. Mirrors upstream's private ``isSpaceOrReturn(int c)``
        helper used to gate inline-image ``EI`` recognition; exposed
        here for parser introspection in ports of upstream callers."""
        return b in cls._EI_SEP

    def has_next_space_or_return(self) -> bool:
        """``True`` if the next byte at the read cursor is one of the
        three ``EI``-separator bytes (LF, CR, SP). Mirrors upstream's
        ``hasNextSpaceOrReturn()``."""
        return self.is_space_or_return(self.peek_byte())

    def _has_no_following_bin_data(self) -> bool:
        """Probe up to ``MAX_BIN_CHAR_TEST_LENGTH`` bytes ahead for binary
        garbage. If what follows looks like control bytes (other than the
        recognised whitespace), we're inside the image data and the ``EI``
        we matched isn't the real terminator. Mirrors PDFBox's
        ``hasNoFollowingBinData`` heuristic."""
        start_pos = self.position
        probe = bytearray()
        for _ in range(self.MAX_BIN_CHAR_TEST_LENGTH):
            b = self.read_byte()
            if b == RandomAccessRead.EOF:
                break
            probe.append(b)
        # Restore position regardless of what we found.
        self.seek(start_pos)
        if not probe:
            return True

        no_bin = True
        start_op = -1
        end_op = -1
        for i, byte_val in enumerate(probe):
            if (byte_val != 0 and byte_val < 0x09) or (
                0x0A < byte_val < 0x20 and byte_val != 0x0D
            ) or byte_val > 0x7F:
                no_bin = False
                break
            is_ws = byte_val in (0x00, 0x09, 0x20, 0x0A, 0x0D)
            if start_op == -1 and not is_ws:
                start_op = i
            elif start_op != -1 and end_op == -1 and is_ws:
                end_op = i

        if no_bin and end_op != -1 and start_op != -1:
            tok = probe[start_op:end_op].decode("ascii", errors="replace")
            if tok not in ("Q", "EMC", "S") and not _looks_like_number(tok):
                no_bin = False

        if no_bin and start_op != -1 and len(probe) == self.MAX_BIN_CHAR_TEST_LENGTH:
            slice_end = end_op if end_op != -1 else self.MAX_BIN_CHAR_TEST_LENGTH
            tok_bytes = probe[start_op:slice_end]
            tok_str = tok_bytes.decode("ascii", errors="replace")
            if slice_end - start_op > 3 and not _looks_like_number(tok_str):
                no_bin = False

        return no_bin

    # ---------- generic operator reader ----------

    def _read_operator_token(self) -> Operator:
        return Operator.get_operator(self._read_operator_string())

    def _read_operator_string(self) -> str:
        """Read an operator keyword. PDF operators are short alphabetic
        runs, optionally containing ``*`` (e.g. ``B*``, ``f*``, ``n*``)
        or being one of the apostrophe/quote text-show variants. Numbers
        are NOT consumed, except for the Type 3 glyph operators ``d0`` /
        ``d1`` (PDFBox carries this special case)."""
        self.skip_whitespace()
        out = bytearray()
        # Special case the apostrophe and quotation mark text-show
        # operators (§9.4.3): they're complete operators by themselves.
        first = self.peek_byte()
        if first == 0x27 or first == 0x22:  # ' or "
            out.append(self.read_byte())
            return out.decode("ascii")
        while True:
            b = self.peek_byte()
            if b == RandomAccessRead.EOF:
                break
            if (
                self.is_whitespace(b)
                or b in (0x5B, 0x3C, 0x28, 0x2F, 0x25)  # [ < ( / %
                or self.is_digit(b)
            ):
                break
            cur = self.read_byte()
            out.append(cur)
            # Type 3 glyph quirk: ``d0`` / ``d1`` operators include the digit.
            nxt = self.peek_byte()
            if cur == 0x64 and nxt in (0x30, 0x31):  # 'd' followed by '0' or '1'
                out.append(self.read_byte())
        return out.decode("ascii", errors="replace")


def _looks_like_number(s: str) -> bool:
    """Match ``^\\d*(\\.\\d*)?$`` — PDFBox's ``NUMBER_PATTERN``."""
    if not s:
        return True
    saw_dot = False
    for ch in s:
        if ch.isdigit():
            continue
        if ch == "." and not saw_dot:
            saw_dot = True
            continue
        return False
    return True
