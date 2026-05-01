from __future__ import annotations

from typing import ClassVar

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSObjectKey,
    COSStream,
    COSString,
)
from pypdfbox.io import RandomAccessRead, RandomAccessReadBuffer

from .base_parser import BaseParser
from .parse_error import PDFParseError


class COSParser(BaseParser):
    """
    Builds ``COSBase`` objects from the token stream produced by
    ``BaseParser``. Mirrors `org.apache.pdfbox.pdfparser.COSParser` for
    the direct-object / array / dictionary / indirect-reference subset.

    Stream bodies (the ``stream ... endstream`` payload following a
    stream dictionary) are NOT handled here — that requires resolved
    ``/Length`` and lives in ``PDFParser`` (cluster #3).

    Usage:
        parser = COSParser(source, document=doc)  # document is optional
        obj = parser.parse_direct_object()
    """

    # System-property name controlling how many trailing bytes of a PDF
    # source are scanned for the ``%%EOF`` / ``startxref`` markers.
    # Mirrors upstream ``COSParser.SYSPROP_EOFLOOKUPRANGE``. The pypdfbox
    # parser does not consult ``System.getProperty`` (Java-only); the
    # constant exists for downstream callers reading PDFBox-style config.
    SYSPROP_EOFLOOKUPRANGE: ClassVar[str] = (
        "org.apache.pdfbox.pdfparser.nonSequentialPDFParser.eofLookupRange"
    )

    # Default trailing byte count scanned for ``%%EOF`` and the ``startxref``
    # offset. Mirrors upstream ``COSParser.DEFAULT_TRAIL_BYTECOUNT`` (which
    # is private upstream but exposed here for parity-test access — same
    # 2048-byte default).
    DEFAULT_TRAIL_BYTECOUNT: ClassVar[int] = 2048

    # Marker character arrays used by upstream's brute-force scanners.
    # Mirrors ``COSParser.EOF_MARKER`` / ``COSParser.OBJ_MARKER`` — kept
    # as ``bytes`` since pypdfbox sources are byte streams.
    EOF_MARKER: ClassVar[bytes] = b"%%EOF"
    OBJ_MARKER: ClassVar[bytes] = b"obj"

    def __init__(
        self, source: RandomAccessRead, document: COSDocument | None = None
    ) -> None:
        super().__init__(source)
        self._document = document
        # Trailing /XRef byte offset for the source. Mirrors upstream
        # ``COSParser`` private state behind ``getXrefOffset`` /
        # ``setXrefOffset`` accessors. ``-1`` means "not yet recorded".
        self._xref_offset: int = -1
        # Lenient parsing toggle. Mirrors upstream
        # ``COSParser.setLenient`` / ``isLenient``. The pypdfbox tokenizer
        # is already permissive — the flag is exposed for API parity and
        # stored only; no behaviour branches off it yet.
        self._lenient: bool = True
        # Number of trailing bytes scanned for ``%%EOF``. Mirrors upstream
        # ``COSParser.readTrailBytes``. Configurable via
        # :meth:`set_eof_lookup_range`.
        self._read_trail_bytes: int = self.DEFAULT_TRAIL_BYTECOUNT
        # Length of the source at construction time. Mirrors upstream
        # ``COSParser.fileLen``.
        try:
            self._file_len: int = source.length()
        except Exception:  # noqa: BLE001 — length() is best-effort here
            self._file_len = -1
        # Latches set by upstream's xref-recovery path. We don't drive
        # them automatically (the recovery walker lives in ``PDFParser``)
        # but mirror the protected fields so callers reading state via
        # ``isInitialParseDone`` / ``isTrailerWasRebuild`` find them.
        self._initial_parse_done: bool = False
        self._trailer_was_rebuild: bool = False

    @property
    def document(self) -> COSDocument | None:
        return self._document

    # ---------- top-level dispatch ----------

    def parse_direct_object(self) -> COSBase:
        """Parse one direct object (or an indirect reference, returned as
        an unresolved ``COSObject``). Whitespace is consumed first."""
        self.skip_whitespace()
        b = self.peek_byte()
        if b == RandomAccessRead.EOF:
            raise PDFParseError("unexpected EOF in object stream", position=self.position)
        # Dispatch by the first byte of the object.
        if b == 0x3C:  # '<' — could be '<<' (dict) or '<' (hex string)
            second = self._peek_two_bytes()[1]
            if second == 0x3C:
                return self.parse_cos_dictionary()
            return self._read_cos_hex_string()
        if b == 0x28:  # '('
            return self._read_cos_literal_string()
        if b == 0x2F:  # '/'
            return COSName.get_pdf_name(self.read_name())
        if b == 0x5B:  # '['
            return self.parse_cos_array()
        if b in (0x2B, 0x2D, 0x2E) or self.is_digit(b):
            return self._parse_number_or_indirect_reference()
        if b in (0x74, 0x66, 0x6E):  # 't', 'f', 'n' — true / false / null
            return self._parse_keyword_value()
        raise PDFParseError(
            f"unexpected byte {b:#04x} ({chr(b)!r}) at start of object",
            position=self.position,
        )

    # ---------- arrays ----------

    def parse_cos_array(self) -> COSArray:
        """Parse a ``[ ... ]`` array."""
        start = self.position
        b = self.read_byte()
        if b != 0x5B:
            raise PDFParseError("expected array '['", position=start)
        items: list[COSBase] = []
        while True:
            self.skip_whitespace()
            nxt = self.peek_byte()
            if nxt == RandomAccessRead.EOF:
                raise PDFParseError("unterminated array", position=start)
            if nxt == 0x5D:  # ']'
                self.read_byte()
                return COSArray(items)
            items.append(self.parse_direct_object())

    # ---------- dictionaries ----------

    def parse_cos_dictionary(self) -> COSDictionary:
        """Parse a ``<< ... >>`` dictionary."""
        start = self.position
        self.read_expected(b"<<")
        d = COSDictionary()
        while True:
            self.skip_whitespace()
            nxt = self.peek_byte()
            if nxt == RandomAccessRead.EOF:
                raise PDFParseError("unterminated dictionary", position=start)
            if nxt == 0x3E:  # '>'
                self.read_expected(b">>")
                return d
            if nxt != 0x2F:  # '/'
                raise PDFParseError(
                    f"expected name in dictionary at byte {self.position}",
                    position=self.position,
                )
            key = self.read_name()
            value = self.parse_direct_object()
            d.set_item(key, value)

    # ---------- numbers and indirect references ----------

    def _parse_number_or_indirect_reference(self) -> COSBase:
        """Parse a number; if followed by a second number and the keyword
        ``R``, return an indirect-reference ``COSObject`` instead."""
        start = self.position
        first = self.read_number()
        # An indirect reference looks like ``<int> <int> R`` and the first
        # token must be a non-negative integer. Anything else is just a
        # number.
        if not isinstance(first, int) or first < 0:
            return self._wrap_number(first, start)
        # Save position to potentially rewind if this isn't an indirect ref.
        post_first = self.position
        # Lookahead: next token might be the second integer.
        self.skip_whitespace()
        if not self._next_byte_starts_unsigned_int():
            self.seek(post_first)
            return self._wrap_number(first, start)
        try:
            second = self.read_number()
        except PDFParseError:
            self.seek(post_first)
            return self._wrap_number(first, start)
        if not isinstance(second, int) or second < 0:
            self.seek(post_first)
            return self._wrap_number(first, start)
        # Lookahead: keyword ``R``?
        self.skip_whitespace()
        if self.peek_byte() != 0x52:  # 'R'
            self.seek(post_first)
            return self._wrap_number(first, start)
        try:
            kw = self.read_keyword()
        except PDFParseError:
            self.seek(post_first)
            return self._wrap_number(first, start)
        if kw != b"R":
            self.seek(post_first)
            return self._wrap_number(first, start)
        return self._make_indirect_reference(first, second)

    def _next_byte_starts_unsigned_int(self) -> bool:
        b = self.peek_byte()
        return b != RandomAccessRead.EOF and self.is_digit(b)

    def _wrap_number(self, value: int | float, start: int) -> COSBase:
        if isinstance(value, int):
            cos_int = COSInteger.get(value)
            return cos_int
        # Re-read original textual representation so COSFloat preserves it.
        end = self.position
        cur = self.position
        self.seek(start)
        text_bytes = bytearray()
        while self.position < end:
            text_bytes.append(self.read_byte())
        self.seek(cur)
        return COSFloat(text_bytes.decode("ascii"))

    def _make_indirect_reference(self, object_number: int, generation_number: int) -> COSObject:
        """Build (or fetch from the document pool) the ``COSObject``
        referenced by ``<n> <m> R``. Without a bound document the reference
        is fresh — the caller is responsible for resolving it later."""
        if self._document is None:
            return COSObject(object_number, generation_number)
        return self._document.get_object_from_pool(
            COSObjectKey(object_number, generation_number)
        )

    # ---------- keyword-valued primitives ----------

    def _parse_keyword_value(self) -> COSBase:
        """Parse ``true``, ``false``, or ``null``."""
        start = self.position
        kw = self.read_keyword()
        if kw == b"true":
            return COSBoolean.TRUE
        if kw == b"false":
            return COSBoolean.FALSE
        if kw == b"null":
            return COSNull.NULL
        raise PDFParseError(f"unexpected keyword {kw!r}", position=start)

    # ---------- string helpers (return COSString) ----------

    def _read_cos_literal_string(self) -> COSString:
        return COSString(self.read_literal_string())

    def _read_cos_hex_string(self) -> COSString:
        s = COSString(self.read_hex_string())
        s.set_force_hex_form(True)
        return s

    # ---------- indirect object definitions ----------

    def parse_indirect_object_definition(self) -> COSObject:
        """Parse ``n m obj <direct-object> endobj``. Returns a resolved
        ``COSObject`` whose target is the parsed direct object.

        Stream bodies (``... <<dict>> stream ... endstream endobj``) are
        NOT supported here — they require ``/Length`` resolution and live
        in ``PDFParser`` (cluster #3). If the next keyword after the
        object is ``stream`` rather than ``endobj``, this raises
        ``NotImplementedError``."""
        start = self.position
        self.skip_whitespace()
        object_number = self.read_int()
        self.skip_whitespace()
        generation_number = self.read_int()
        self.skip_whitespace()
        kw = self.read_keyword()
        if kw != b"obj":
            raise PDFParseError(
                f"expected 'obj' after object header, got {kw!r}", position=start
            )
        body = self.parse_direct_object()
        self.skip_whitespace()
        # Distinguish ``endobj`` from ``stream`` keyword.
        peeked = self.peek_byte()
        if peeked == 0x73:  # 's' — possibly 'stream'
            kw2 = self.read_keyword()
            if kw2 == b"stream":
                # Stream body parsing — supports the direct-/Length case
                # (``/Length n`` is an integer literal in the stream
                # dictionary). Indirect-/Length resolution requires the
                # full xref pool and lives in ``PDFParser``; if /Length
                # is an indirect reference we fall back to NotImplemented.
                if not isinstance(body, COSDictionary):
                    raise PDFParseError(
                        "stream object body is not a dictionary",
                        position=self.position,
                    )
                stream = self._build_stream_from_dict(body)
                self._read_stream_body_into(stream)
                self.skip_whitespace()
                end_kw = self.read_keyword()
                if end_kw != b"endobj":
                    raise PDFParseError(
                        f"expected 'endobj' after stream, got {end_kw!r}",
                        position=self.position,
                    )
                if self._document is not None:
                    cos_obj = self._document.get_object_from_pool(
                        COSObjectKey(object_number, generation_number)
                    )
                    cos_obj.set_object(stream)
                    return cos_obj
                return COSObject(object_number, generation_number, resolved=stream)
            raise PDFParseError(
                f"expected 'endobj' after object body, got {kw2!r}",
                position=self.position,
            )
        kw_end = self.read_keyword()
        if kw_end != b"endobj":
            raise PDFParseError(
                f"expected 'endobj' after object body, got {kw_end!r}",
                position=self.position,
            )
        if self._document is not None:
            cos_obj = self._document.get_object_from_pool(
                COSObjectKey(object_number, generation_number)
            )
            cos_obj.set_object(body)
            return cos_obj
        cos_obj = COSObject(object_number, generation_number, resolved=body)
        return cos_obj

    # ---------- stream-body helpers ----------
    #
    # Used by ``parse_indirect_object_definition`` and
    # ``parse_xref_object_stream``. Stream-body parsing requires
    # ``/Length`` resolution; we handle the direct-/Length case here
    # (the common one) and raise ``NotImplementedError`` for the
    # indirect-/Length case, which needs the full xref pool and lives
    # in ``PDFParser``.

    def _build_stream_from_dict(self, src: COSDictionary) -> COSStream:
        """Promote a parsed ``COSDictionary`` to a ``COSStream`` by
        copying every entry. The original dict is no longer
        referenced. Uses the bound document's scratch file when
        available so body bytes are spilled per the document's memory
        policy."""
        scratch = self._document.scratch_file if self._document is not None else None
        stream = COSStream(scratch_file=scratch)
        for k, v in src.entry_set():
            stream.set_item(k, v)
        return stream

    def _read_stream_body_into(self, stream: COSStream) -> None:
        """Per ISO 32000-1 §7.3.8.1: ``stream`` keyword is followed by
        EOL (CRLF or LF — bare CR is non-conformant). Then exactly
        ``/Length`` bytes. Then ``endstream`` (typically preceded by
        EOL).

        Only direct integer ``/Length`` values are resolved here. An
        indirect-reference ``/Length`` requires the full xref pool and
        is rejected with ``NotImplementedError`` so callers fall
        through to ``PDFParser._read_stream_body``."""
        self._consume_eol_after_stream_keyword()
        length_obj = stream.get_dictionary_object(COSName.get_pdf_name("Length"))
        if not isinstance(length_obj, COSInteger):
            # Either missing or indirect — defer to PDFParser.
            raise NotImplementedError(
                "indirect or missing /Length; stream body resolution "
                "lives in PDFParser (cluster #3)"
            )
        length = length_obj.value
        if length < 0:
            raise PDFParseError(
                f"stream /Length is negative: {length}", position=self.position
            )
        body = bytearray(length)
        n = self._src.read_into(body)
        if n != length:
            raise PDFParseError(
                f"stream body truncated: expected {length} bytes, got {n}",
                position=self.position,
            )
        stream.set_raw_data(bytes(body))
        # Trailing EOL is conventional but optional; skip it then verify
        # 'endstream' is next.
        self.skip_whitespace()
        kw = self.read_keyword()
        if kw != b"endstream":
            raise PDFParseError(
                f"expected 'endstream', got {kw!r}", position=self.position
            )

    def _consume_eol_after_stream_keyword(self) -> None:
        """Per spec: a single CRLF or LF after ``stream``. Tolerate a
        bare CR (PDFBox quirk — some producers emit just CR)."""
        b = self._src.read()
        if b == 0x0D:  # CR
            if self._src.peek() == 0x0A:
                self._src.read()  # consume LF too
            return
        if b == 0x0A:  # LF
            return
        # No EOL after 'stream' — extremely non-conformant; rewind so
        # the body read sees the byte.
        if b != RandomAccessRead.EOF:
            self._src.rewind(1)

    # ---------- internal byte-pair lookahead ----------

    def _peek_two_bytes(self) -> tuple[int, int]:
        """Return the next two bytes without consuming them. Returns
        ``(-1, -1)`` if both are at EOF; ``(b, -1)`` if only one byte
        remains."""
        first = self._src.read()
        if first == RandomAccessRead.EOF:
            return (-1, -1)
        second = self._src.read()
        if second == RandomAccessRead.EOF:
            self._src.rewind(1)
            return (first, -1)
        self._src.rewind(2)
        return (first, second)

    # ---------- upstream-name aliases (org.apache.pdfbox.pdfparser.COSParser) ----------
    #
    # The aliases below mirror the public surface of upstream
    # ``COSParser`` so PDFBox-style call sites (and the PDFParser
    # subclass) can reach the same primitives by their familiar names.
    # No semantics change — each alias either re-uses an existing
    # method on this class / its base, exposes parser state, or raises
    # ``NotImplementedError`` for surface that legitimately belongs in
    # ``PDFParser`` (cluster #3) and is deferred here.

    # Typed parse aliases — parse_cos_dictionary / parse_cos_array are
    # already defined above.

    def parse_cos_string(self) -> COSString:
        """Parse a literal ``( ... )`` or hex ``< ... >`` string at the
        current position and return a ``COSString``. Whitespace is consumed
        first. Mirrors upstream ``COSParser.parseCOSString``."""
        self.skip_whitespace()
        b = self.peek_byte()
        if b == 0x28:  # '('
            return self._read_cos_literal_string()
        if b == 0x3C:  # '<'
            second = self._peek_two_bytes()[1]
            if second == 0x3C:
                raise PDFParseError(
                    "expected string, found dictionary '<<'", position=self.position
                )
            return self._read_cos_hex_string()
        raise PDFParseError(
            f"expected COS string, got byte {b:#04x}", position=self.position
        )

    def parse_cos_name(self) -> COSName:
        """Parse a ``/Foo`` name at the current position and return a
        ``COSName``. Whitespace is consumed first. Mirrors upstream
        ``COSParser.parseCOSName``."""
        self.skip_whitespace()
        return COSName.get_pdf_name(self.read_name())

    def parse_cos_number(self) -> COSBase:
        """Parse a numeric literal at the current position and return
        either a ``COSInteger`` or a ``COSFloat``. Whitespace is consumed
        first. Mirrors upstream ``COSParser.parseCOSNumber``."""
        self.skip_whitespace()
        start = self.position
        value = self.read_number()
        return self._wrap_number(value, start)

    def parse_cos_object_reference(self) -> COSObject:
        """Parse a full ``n m R`` indirect reference at the current
        position and return the placeholder ``COSObject`` (resolved via
        the bound document's pool when one is available). Whitespace is
        consumed first. Mirrors upstream
        ``COSParser.parseCOSObjectReference``."""
        self.skip_whitespace()
        start = self.position
        obj = self._parse_number_or_indirect_reference()
        if not isinstance(obj, COSObject):
            raise PDFParseError(
                "expected indirect reference 'n m R'", position=start
            )
        return obj

    # Indirect-object resolution. Upstream ``parseObjectDynamically`` walks
    # the xref + object pool to materialise a referenced object; that
    # machinery lives in ``PDFParser``. With a bound document we can still
    # answer the common case by routing through the document pool's
    # already-installed loader.

    def parse_object_dynamically(
        self,
        obj_num: int,
        gen_num: int,
        requires_existing_not_compressed: bool = False,
    ) -> COSBase | None:
        """Resolve the object referenced by ``(obj_num, gen_num)``.

        When a document is bound and an existing pool entry has a loader
        attached (the normal post-``populate_document`` state), this
        triggers lazy resolution and returns the underlying ``COSBase``.
        Without a bound document — or when the placeholder has no loader
        and ``requires_existing_not_compressed`` is ``False`` — an empty
        placeholder is returned (matching upstream's "create on demand"
        affordance).

        ``requires_existing_not_compressed`` mirrors the upstream third
        argument: when ``True``, raises if the object isn't already known
        to the document. The compressed-vs-uncompressed distinction lives
        with the loader (``PDFParser``); this alias preserves the call
        signature so PDFBox-style call sites work unchanged.

        Mirrors upstream ``COSParser.parseObjectDynamically``."""
        if self._document is None:
            if requires_existing_not_compressed:
                raise PDFParseError(
                    f"parse_object_dynamically({obj_num}, {gen_num}): "
                    "no document bound to parser"
                )
            return COSObject(obj_num, gen_num)
        key = COSObjectKey(obj_num, gen_num)
        if requires_existing_not_compressed and not self._document.has_object(key):
            raise PDFParseError(
                f"parse_object_dynamically({obj_num}, {gen_num}): "
                "object not present in document pool"
            )
        cos_obj = self._document.get_object_from_pool(key)
        # Trigger lazy resolution if a loader is attached; otherwise return
        # whatever the placeholder currently wraps (may be ``None``).
        return cos_obj.get_object()

    def parse_object_stream(self, obj_num: int) -> list[COSBase]:
        """Load every direct object packed inside the object stream
        identified by ``obj_num``. Mirrors upstream
        ``COSParser.parseObjectStream``.

        The ObjStm body, after /Filter is applied, is a header of ``/N``
        ``(obj_num byte_offset)`` integer pairs followed by ``/N`` packed
        direct objects starting at byte ``/First``. This implementation
        materialises the ObjStm via the bound document's pool, decodes
        the body, parses every contained direct object in order, and
        registers each into the document pool with key ``(stored_obj_num,
        0)`` (PDF 32000-1 §7.5.7 fixes generation 0 for compressed
        objects). Returns the list of parsed objects in storage order.

        Requires a bound document — without one, the ObjStm cannot be
        looked up so the call raises ``PDFParseError``."""
        if self._document is None:
            raise PDFParseError(
                f"parse_object_stream({obj_num}): no document bound to parser"
            )
        objstm_holder = self._document.get_object_from_pool(
            COSObjectKey(obj_num, 0)
        )
        objstm_body = objstm_holder.get_object()
        if not isinstance(objstm_body, COSStream):
            raise PDFParseError(
                f"object stream {obj_num} is not a stream"
            )
        n_obj = objstm_body.get_dictionary_object(COSName.get_pdf_name("N"))
        first_obj = objstm_body.get_dictionary_object(
            COSName.get_pdf_name("First")
        )
        if not isinstance(n_obj, COSInteger) or not isinstance(first_obj, COSInteger):
            raise PDFParseError(
                f"object stream {obj_num} missing /N or /First"
            )
        n = n_obj.value
        first = first_obj.value
        with objstm_body.create_input_stream() as src:
            decoded = src.read()
        # Header: N pairs of "<obj_num> <byte_offset>", whitespace
        # separated. Parse them via a fresh BaseParser scoped to just
        # the header window.
        header_view = RandomAccessReadBuffer(decoded[:first])
        header_parser = BaseParser(header_view)
        pairs: list[tuple[int, int]] = []
        try:
            for _ in range(n):
                header_parser.skip_whitespace()
                stored_obj_num = header_parser.read_int()
                header_parser.skip_whitespace()
                byte_offset = header_parser.read_int()
                pairs.append((stored_obj_num, byte_offset))
        finally:
            header_view.close()
        results: list[COSBase] = []
        # Body: each entry starts at decoded[first + offset]. Parse all
        # of them; register into the pool so subsequent indirect
        # references resolve immediately.
        for stored_obj_num, byte_offset in pairs:
            body_view = RandomAccessReadBuffer(decoded[first + byte_offset:])
            body_parser = COSParser(body_view, document=self._document)
            try:
                parsed = body_parser.parse_direct_object()
            finally:
                body_view.close()
            results.append(parsed)
            holder = self._document.get_object_from_pool(
                COSObjectKey(stored_obj_num, 0)
            )
            holder.set_object(parsed)
        return results

    # ``is_eof``, ``peek``, ``unread`` are inherited from BaseParser.
    # Restated here as explicit pass-throughs so ``hasattr(COSParser, …)``
    # finds them at the COSParser level (matches upstream API surface
    # — these accessors are documented on COSParser, not just BaseParser).

    def is_eof(self) -> bool:
        """Upstream-name alias — ``True`` when the source has no more
        bytes. Inherited from ``BaseParser``; restated for parity."""
        return super().is_eof()

    def peek(self) -> int:
        """Upstream-name alias — return the next byte without consuming
        it; ``-1`` at EOF. Inherited from ``BaseParser``."""
        return super().peek()

    def unread(self, b: int = -1) -> None:
        """Upstream-name alias — push the most recently read byte back
        onto the source. The ``b`` argument matches upstream's signature
        and is ignored (PDFBox semantics assume the byte equals what was
        previously read). Inherited from ``BaseParser``."""
        super().unread(b)

    # /XRef byte offset accessors.

    def get_xref_offset(self) -> int:
        """Return the trailing ``/XRef`` byte offset most recently
        recorded by :meth:`set_xref_offset`, or ``-1`` if none. Mirrors
        upstream ``COSParser.getXrefOffset``."""
        return self._xref_offset

    def set_xref_offset(self, offset: int) -> None:
        """Record the trailing ``/XRef`` byte offset. Used by
        ``PDFParser`` to share the value with downstream consumers
        without re-scanning the source. Mirrors upstream
        ``COSParser.setXrefOffset``."""
        self._xref_offset = int(offset)

    # Bound-document accessor — companion to the read-only ``document``
    # property already exposed above.

    def get_document(self) -> COSDocument | None:
        """Return the bound ``COSDocument``, or ``None`` if the parser
        was constructed without one. Mirrors upstream
        ``COSParser.getDocument``."""
        return self._document

    # Lenient-mode toggle.

    def set_lenient(self, lenient: bool) -> None:
        """Toggle lenient parsing mode. The pypdfbox tokenizer is
        already permissive — the flag is stored for API parity. Mirrors
        upstream ``COSParser.setLenient``.

        Per upstream contract this method may only be called before the
        initial parse runs; once ``set_initial_parse_done(True)`` has
        been recorded, attempts to flip leniency raise ``ValueError`` —
        upstream throws ``IllegalArgumentException`` for the same case."""
        if self._initial_parse_done:
            raise ValueError("Cannot change leniency after parsing")
        self._lenient = bool(lenient)

    def is_lenient(self) -> bool:
        """Return the current lenient-mode flag. Mirrors upstream
        ``COSParser.isLenient``."""
        return self._lenient

    # Initial-parse latch. Upstream stores this as a protected boolean
    # (``initialParseDone``) and uses it to lock leniency changes once a
    # parse has begun. The accessors below mirror that state.

    def is_initial_parse_done(self) -> bool:
        """Return ``True`` once :meth:`set_initial_parse_done` has been
        called. Mirrors upstream ``COSParser.initialParseDone`` (no
        explicit getter upstream — the field is package-protected; we
        expose a getter for parity testability)."""
        return self._initial_parse_done

    def set_initial_parse_done(self, done: bool) -> None:
        """Latch the initial-parse-done flag. Once set to ``True`` the
        leniency toggle becomes read-only (see :meth:`set_lenient`).
        Mirrors the package-protected upstream assignment to
        ``initialParseDone``."""
        self._initial_parse_done = bool(done)

    # Trailer-rebuilt latch. Upstream sets ``trailerWasRebuild = true``
    # whenever ``retrieveTrailer`` falls through to the brute-force
    # rebuild path. We expose a getter so callers downstream can
    # distinguish a recovered trailer from a normally-parsed one.

    def is_trailer_was_rebuild(self) -> bool:
        """Return ``True`` if the trailer was rebuilt by the brute-force
        recovery path. Mirrors upstream ``COSParser.trailerWasRebuild``
        (no upstream accessor — exposed here for parity testability)."""
        return self._trailer_was_rebuild

    # File-length accessor. Upstream stores ``fileLen`` as a protected
    # ``long`` populated at construction; downstream subclasses
    # (``PDFParser``) read it. Mirroring the read/write surface keeps
    # those subclasses happy without touching the private field directly.

    def get_file_len(self) -> int:
        """Return the source length recorded at parser construction
        (or ``-1`` if the source could not be sized). Mirrors upstream
        ``COSParser.fileLen`` access (the field is protected upstream;
        we expose a getter for parity)."""
        return self._file_len

    def set_file_len(self, file_len: int) -> None:
        """Override the recorded source length. Used by downstream
        subclasses (``PDFParser``) when the source is wrapped or
        truncated post-construction. Mirrors upstream's protected
        assignment to ``COSParser.fileLen``."""
        self._file_len = int(file_len)

    # ``%%EOF`` / ``startxref`` lookup window.

    def set_eof_lookup_range(self, byte_count: int) -> None:
        """Override how many trailing bytes of the source are scanned
        for ``%%EOF`` / ``startxref``. Values of 15 or fewer are
        rejected silently (matching upstream — values that small can't
        cover the marker plus its preceding offset). Mirrors upstream
        ``COSParser.setEOFLookupRange``."""
        if byte_count > 15:
            self._read_trail_bytes = int(byte_count)

    def get_eof_lookup_range(self) -> int:
        """Return the configured ``%%EOF`` lookup-window size. No
        upstream getter exists — this companion is exposed for parity
        testability and to let subclasses read the active value without
        reaching into the private field."""
        return self._read_trail_bytes

    # ``isString`` — non-consuming match check.

    def is_string(self, expected: bytes | bytearray | str) -> bool:
        """Return ``True`` if ``expected`` is the next sequence of bytes
        at the current source position, *without* advancing the cursor.
        Mirrors upstream ``COSParser.isString(char[])``.

        ``expected`` may be ``bytes``/``bytearray`` (preferred) or a
        ``str`` (treated as ASCII for parity with the upstream
        ``char[]`` overload)."""
        if isinstance(expected, str):
            expected = expected.encode("ascii")
        origin = self.position
        try:
            for c in expected:
                b = self._src.read()
                if b == RandomAccessRead.EOF or b != c:
                    return False
            return True
        finally:
            self.seek(origin)

    # ``lastIndexOf`` — backward sub-byte search utility.

    def last_index_of(
        self, pattern: bytes | bytearray | str, buf: bytes | bytearray, end_off: int
    ) -> int:
        """Return the offset of the last occurrence of ``pattern`` in
        ``buf`` searching backward from ``end_off`` (exclusive), or
        ``-1`` if no match. Mirrors upstream
        ``COSParser.lastIndexOf(char[], byte[], int)``.

        The implementation mirrors the upstream Boyer-Moore-ish
        backwards walk (no library shortcut — semantics must include
        the ``end_off`` exclusive bound and accept any partial-match
        reset behaviour)."""
        if isinstance(pattern, str):
            pattern = pattern.encode("ascii")
        last_pat_off = len(pattern) - 1
        if last_pat_off < 0:
            return -1
        buf_off = end_off
        pat_off = last_pat_off
        lookup_ch = pattern[pat_off]
        while True:
            buf_off -= 1
            if buf_off < 0:
                return -1
            if buf[buf_off] == lookup_ch:
                pat_off -= 1
                if pat_off < 0:
                    return buf_off
                lookup_ch = pattern[pat_off]
            elif pat_off < last_pat_off:
                pat_off = last_pat_off
                lookup_ch = pattern[pat_off]

    # Xref entry points — full implementations live in PDFParser
    # (cluster #3). Aliases here are deferred placeholders so calls
    # routed through the upstream API surface fail loudly with a
    # discoverable message rather than ``AttributeError``.

    def parse_xref_object_stream(
        self, xref_table_offset: int, is_standalone: bool = True
    ) -> COSDictionary:
        """Parse a PDF 1.5+ xref stream at ``xref_table_offset`` and
        return its trailer dictionary. Mirrors upstream
        ``COSParser.parseXrefObjStream``.

        Reads the indirect-object header (``n g obj``), parses the
        stream dictionary, validates ``/Type /XRef``, then consumes the
        ``stream`` keyword + EOL and reads exactly ``/Length`` body
        bytes (when ``/Length`` is direct). The returned dictionary is
        the trailer fragment — body decoding lives at the
        cross-reference layer (``parse_xref_stream`` /
        ``PDFParser._decode_xref_stream_entries``).

        ``is_standalone`` mirrors upstream's flag: when ``True`` (the
        default — chain entry point), an absent or non-``/XRef`` typed
        dictionary is a hard error; when ``False`` (chained from a
        hybrid xref), a missing /Type /XRef is tolerated."""
        self.seek(xref_table_offset)
        self.skip_whitespace()
        # n g obj
        self.read_int()
        self.skip_whitespace()
        self.read_int()
        self.skip_whitespace()
        kw = self.read_keyword()
        if kw != b"obj":
            raise PDFParseError(
                f"expected 'obj' at xref-stream offset {xref_table_offset}, "
                f"got {kw!r}",
                position=self.position,
            )
        body = self.parse_direct_object()
        if not isinstance(body, COSDictionary):
            raise PDFParseError(
                "xref-stream object body is not a dictionary",
                position=self.position,
            )
        type_obj = body.get_dictionary_object(COSName.get_pdf_name("Type"))
        if is_standalone:
            if not (isinstance(type_obj, COSName) and type_obj.name == "XRef"):
                raise PDFParseError(
                    "xref-stream dict missing /Type /XRef",
                    position=self.position,
                )
        # Promote the dict to a COSStream + read its body so callers
        # that want the on-disk bytes can drive ``create_input_stream``.
        stream = self._build_stream_from_dict(body)
        self.skip_whitespace()
        if self.peek_byte() == 0x73:  # 's' — stream
            kw2 = self.read_keyword()
            if kw2 != b"stream":
                raise PDFParseError(
                    f"expected 'stream' in xref-stream object, got {kw2!r}",
                    position=self.position,
                )
            self._read_stream_body_into(stream)
            # Cross-reference streams are never encrypted (ISO 32000-2
            # §7.6.2) — flag so future decrypt walks skip this body.
            stream.set_skip_encryption(True)
        return stream

    def parse_xref_table(
        self,
        start_byte_offset: int,
        xref_table: dict[COSObjectKey, int] | None = None,
    ) -> bool:
        """Parse a traditional ``xref`` section starting at
        ``start_byte_offset`` and return ``True`` on success. The parsed
        entries are merged into ``xref_table`` (a fresh dict by default)
        as ``{COSObjectKey: byte_offset}``. ``-1`` is recorded for
        free entries so callers can distinguish them.

        Mirrors upstream ``COSParser.parseXrefTable(long, XrefTrailerResolver)``
        — the caller-provided table replaces the resolver argument so
        this call is usable without the full ``PDFParser`` plumbing."""
        if xref_table is None:
            xref_table = {}
        self.seek(start_byte_offset)
        self.skip_whitespace()
        try:
            kw = self.read_keyword()
        except PDFParseError:
            return False
        if kw != b"xref":
            return False
        self.skip_whitespace()
        # Subsections until 'trailer' (or EOF in a malformed file).
        while True:
            peek = self.peek_byte()
            if peek == RandomAccessRead.EOF:
                return False
            if peek == 0x74:  # 't' — start of 'trailer'
                break
            try:
                first_obj = self.read_int()
                self.skip_whitespace()
                count = self.read_int()
                self.skip_whitespace()
            except PDFParseError:
                return False
            for i in range(count):
                # 20-byte fixed entry: ``oooooooooo ggggg n\r\n``.
                raw = bytearray(20)
                n = self._src.read_into(raw)
                if n < 20:
                    return False
                line = bytes(raw)
                try:
                    offset = int(line[0:10].decode("ascii"))
                    generation = int(line[11:16].decode("ascii"))
                    flag = chr(line[17])
                except (ValueError, IndexError):
                    return False
                key = COSObjectKey(first_obj + i, generation)
                if flag == "n":
                    # First-write wins so chained /Prev sections (parsed
                    # newest-first by walkers above this layer) don't get
                    # overwritten by older entries when they happen to be
                    # parsed in the wrong order.
                    xref_table.setdefault(key, offset)
                elif flag == "f":
                    xref_table.setdefault(key, -1)
                else:
                    return False
        return True

    def parse_pdf_header(self) -> float:
        """Validate the ``%PDF-x.y`` magic and return the version as a
        float. Tolerates up to 1024 bytes of leading garbage (some
        producers prepend MIME envelopes / shebangs / etc.). Mirrors
        upstream ``COSParser.parsePDFHeader``."""
        scan_window = 1024
        self._src.seek(0)
        head = bytearray()
        while len(head) < scan_window:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                break
            head.append(b)
        idx = bytes(head).find(b"%PDF-")
        if idx < 0:
            raise PDFParseError("missing %PDF- header (not a PDF file)")
        # Position the cursor just past "%PDF-" for version parsing.
        self._src.seek(idx + len(b"%PDF-"))
        version_bytes = bytearray()
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF or b in (0x0A, 0x0D, 0x20):
                break
            version_bytes.append(b)
        try:
            return float(version_bytes.decode("ascii"))
        except ValueError as exc:
            raise PDFParseError(
                f"malformed %PDF version {version_bytes!r}"
            ) from exc

    # Brute-force scan helpers — used by upstream's malformed-recovery
    # path. Mirrors `org.apache.pdfbox.pdfparser.COSParser` recovery
    # surface (``bfSearchForObjects`` / ``bfSearchForXRef`` /
    # ``rebuildTrailer`` / ``parseXrefStream``). Lenient mode must be
    # enabled for these to be exercised by upstream callers, but the
    # methods themselves work in any mode.

    def _read_all_bytes(self) -> bytes:
        """Snapshot the entire source as a ``bytes`` blob. Position is
        preserved. Used by the brute-force scanners below — they are
        whole-file linear sweeps and a single ``bytes`` view is the
        simplest fast path."""
        saved = self.position
        try:
            length = self._src.length()
            self._src.seek(0)
            buf = bytearray(length)
            read = 0
            while read < length:
                n = self._src.read_into(buf, read, length - read)
                if n <= 0:
                    break
                read += n
            return bytes(buf[:read])
        finally:
            self._src.seek(saved)

    def bf_search_for_objects(self) -> dict[COSObjectKey, int]:
        """Brute-force scan the source for ``n g obj`` headers and return
        an ``{COSObjectKey: byte_offset}`` map. Mirrors upstream
        ``COSParser.bfSearchForObjects``.

        The scan walks the raw source byte-by-byte looking for the
        keyword ``obj`` preceded by two unsigned integers separated by
        whitespace. The recorded offset points at the start of the
        leading object number — the same offset format that an xref
        entry would carry."""
        data = self._read_all_bytes()
        offsets: dict[COSObjectKey, int] = {}
        n = len(data)
        i = 0
        ws = self.WHITESPACE
        # Search for the literal token ``obj`` separated from neighbours
        # by whitespace; then back-walk to recover the (n g) header.
        while i < n - 3:
            j = data.find(b"obj", i)
            if j < 0:
                break
            # ``obj`` must be preceded by whitespace and followed by a
            # whitespace / delimiter / EOF — otherwise it's a substring
            # of e.g. ``endobj`` or part of a name.
            if j == 0 or data[j - 1] not in ws:
                i = j + 1
                continue
            after = j + 3
            if after < n and data[after] not in ws and data[after] not in self.DELIMITERS:
                i = j + 1
                continue
            # Back-walk: skip whitespace, then digits (gen), whitespace,
            # then digits (obj number).
            k = j - 1
            while k >= 0 and data[k] in ws:
                k -= 1
            gen_end = k + 1
            while k >= 0 and 0x30 <= data[k] <= 0x39:
                k -= 1
            gen_start = k + 1
            if gen_start == gen_end:
                i = j + 1
                continue
            while k >= 0 and data[k] in ws:
                k -= 1
            num_end = k + 1
            while k >= 0 and 0x30 <= data[k] <= 0x39:
                k -= 1
            num_start = k + 1
            if num_start == num_end:
                i = j + 1
                continue
            # Make sure the byte before the object number isn't itself a
            # digit — otherwise we'd be picking up only the trailing
            # digits of a longer number (rare, but possible in malformed
            # streams where two int literals abut).
            if num_start > 0 and 0x30 <= data[num_start - 1] <= 0x39:
                i = j + 1
                continue
            try:
                obj_num = int(data[num_start:num_end])
                gen_num = int(data[gen_start:gen_end])
            except ValueError:
                i = j + 1
                continue
            if obj_num < 0 or gen_num < 0:
                i = j + 1
                continue
            key = COSObjectKey(obj_num, gen_num)
            # First occurrence wins for any given key — matches upstream
            # behaviour where the brute-force scan records the *earliest*
            # offset and leaves the resolver to disambiguate.
            offsets.setdefault(key, num_start)
            i = j + 3
        return offsets

    def bf_search_for_xref(self, start_xref_offset: int) -> int:
        """Brute-force scan the source for an ``xref`` keyword (or an
        xref-stream object header) near ``start_xref_offset`` and return
        the byte offset of the recovered xref. Mirrors upstream
        ``COSParser.bfSearchForXRef``.

        The scan first looks for a literal ``xref`` keyword (traditional
        cross-reference table); if none is found it falls back to the
        nearest ``n g obj`` header containing an ``/XRef`` typed stream
        dictionary. Returns ``-1`` if neither candidate can be located."""
        data = self._read_all_bytes()
        ws = self.WHITESPACE
        # 1) Traditional xref tables: scan for the literal ``xref`` token
        # (must be preceded and followed by whitespace / EOF — guards
        # against ``startxref`` and ``/XRef`` substrings).
        candidates: list[int] = []
        i = 0
        n = len(data)
        while i <= n - 4:
            j = data.find(b"xref", i)
            if j < 0:
                break
            before_ok = j == 0 or data[j - 1] in ws
            after_ok = j + 4 == n or data[j + 4] in ws
            # Reject the trailing ``xref`` of ``startxref`` — preceded
            # by ``start`` not whitespace.
            if before_ok and after_ok:
                # Reject ``/XRef`` (preceded by ``/``).
                if not (j > 0 and data[j - 1] == 0x2F):
                    candidates.append(j)
            i = j + 1
        if candidates:
            # Pick the candidate nearest to ``start_xref_offset``; ties
            # break to the earlier offset (matches upstream).
            target = max(0, int(start_xref_offset))
            return min(candidates, key=lambda c: (abs(c - target), c))
        # 2) Fall back to xref-stream objects: scan for ``n g obj`` and
        # check the dictionary for ``/Type /XRef``.
        objects = self.bf_search_for_objects()
        if not objects:
            return -1
        target = max(0, int(start_xref_offset))
        best_offset = -1
        best_distance = -1
        for offset in objects.values():
            self.seek(offset)
            try:
                # Parse just enough to get the dictionary.
                self.read_int()
                self.skip_whitespace()
                self.read_int()
                self.skip_whitespace()
                kw = self.read_keyword()
                if kw != b"obj":
                    continue
                self.skip_whitespace()
                if self.peek_byte() != 0x3C:
                    continue
                # Don't fully parse — just look for "/Type/XRef" /
                # "/Type /XRef" textual marker between ``<<`` and ``>>``.
            except (PDFParseError, ValueError):
                continue
            # Substring check on the raw bytes between the object header
            # and the next ``endobj``/``stream`` keyword.
            end = data.find(b"endobj", offset)
            stream_pos = data.find(b"stream", offset)
            if 0 <= stream_pos < end or end < 0:
                end = stream_pos if stream_pos >= 0 else min(offset + 4096, n)
            window = data[offset:end]
            if b"/XRef" not in window or b"/Type" not in window:
                continue
            distance = abs(offset - target)
            if best_offset < 0 or distance < best_distance:
                best_offset = offset
                best_distance = distance
        return best_offset

    def rebuild_trailer(self) -> COSDictionary:
        """Reconstruct a trailer dictionary by scanning every recovered
        object for ``/Root``, ``/Info``, ``/Encrypt``, and ``/ID``
        candidates. Mirrors upstream ``COSParser.rebuildTrailer``.

        The first object that owns a ``/Type /Catalog`` entry wins for
        ``/Root``; the first object containing standard document-info
        keys (``/CreationDate``, ``/Producer``, ``/Title``, ...) wins for
        ``/Info``. ``/Encrypt`` and ``/ID`` are copied from any object
        whose dictionary advertises them. The reconstructed trailer also
        receives a ``/Size`` equal to ``max(object_number) + 1``."""
        objects = self.bf_search_for_objects()
        trailer = COSDictionary()
        if not objects:
            return trailer
        max_obj = 0
        info_keys = {
            COSName.get_pdf_name("CreationDate"),
            COSName.get_pdf_name("ModDate"),
            COSName.get_pdf_name("Producer"),
            COSName.get_pdf_name("Creator"),
            COSName.get_pdf_name("Title"),
            COSName.get_pdf_name("Author"),
            COSName.get_pdf_name("Subject"),
            COSName.get_pdf_name("Keywords"),
        }
        catalog_name = COSName.get_pdf_name("Catalog")
        type_name = COSName.get_pdf_name("Type")
        encrypt_name = COSName.get_pdf_name("Encrypt")
        id_name = COSName.get_pdf_name("ID")
        root_name = COSName.get_pdf_name("Root")
        info_name = COSName.get_pdf_name("Info")
        size_name = COSName.get_pdf_name("Size")
        for key, offset in objects.items():
            if key.object_number > max_obj:
                max_obj = key.object_number
            self.seek(offset)
            try:
                self.read_int()
                self.skip_whitespace()
                self.read_int()
                self.skip_whitespace()
                kw = self.read_keyword()
                if kw != b"obj":
                    continue
                self.skip_whitespace()
                if self.peek_byte() != 0x3C:
                    continue
                second = self._peek_two_bytes()[1]
                if second != 0x3C:
                    continue
                d = self.parse_cos_dictionary()
            except (PDFParseError, NotImplementedError, ValueError):
                continue
            if not isinstance(d, COSDictionary):
                continue
            # /Root candidate: dictionary advertises /Type /Catalog.
            if (
                not trailer.contains_key(root_name)
                and d.get_item(type_name) is catalog_name
            ):
                trailer.set_item(
                    root_name,
                    self._make_indirect_reference(
                        key.object_number, key.generation_number
                    ),
                )
            # /Info candidate: dictionary contains a known info key.
            if (
                not trailer.contains_key(info_name)
                and any(d.get_item(k) is not None for k in info_keys)
                and d.get_item(type_name) is not catalog_name
            ):
                trailer.set_item(
                    info_name,
                    self._make_indirect_reference(
                        key.object_number, key.generation_number
                    ),
                )
            # /Encrypt: copy reference / direct value through verbatim.
            if not trailer.contains_key(encrypt_name):
                enc = d.get_item(encrypt_name)
                if enc is not None:
                    trailer.set_item(encrypt_name, enc)
            # /ID: same.
            if not trailer.contains_key(id_name):
                ids = d.get_item(id_name)
                if ids is not None:
                    trailer.set_item(id_name, ids)
        trailer.set_item(size_name, COSInteger.get(max_obj + 1))
        return trailer

    def parse_xref_stream(
        self, xref_stream_dict: COSDictionary, xref_table: dict | None = None
    ) -> dict[COSObjectKey, int]:
        """Tolerantly parse a PDF 1.5+ xref-stream trailer dictionary's
        ``/W`` and ``/Index`` arrays and return an
        ``{COSObjectKey: in-stream-byte-offset}`` map. Mirrors upstream
        ``COSParser.parseXrefStream`` (the dictionary-shape inspection
        half — the body decode lives in
        ``PDFParser._decode_xref_stream_entries``).

        ``/W`` may have any non-negative element widths (0 means "field
        absent"); ``/Index`` defaults to ``[0 /Size]`` when missing. The
        return value records the *byte position within the decoded
        stream body* at which each entry starts, so callers that need to
        reach into a partially-parsed body can do so without re-walking
        ``/Index`` themselves.

        ``xref_table`` is accepted for API parity (upstream merges into a
        shared map) but defaults to a fresh dict; the populated map is
        always returned to the caller."""
        if xref_table is None:
            xref_table = {}
        w_obj = xref_stream_dict.get_dictionary_object(COSName.get_pdf_name("W"))
        if not isinstance(w_obj, COSArray):
            raise PDFParseError("xref stream missing /W array")
        w = []
        for i in range(w_obj.size()):
            v = w_obj.get(i)
            if isinstance(v, COSInteger):
                w.append(v.int_value())
            elif isinstance(v, COSFloat):
                w.append(int(v.float_value()))
            else:
                w.append(0)
        # Pad /W out to at least three fields — older malformed encoders
        # sometimes ship a 2-element array (omitting the trailing
        # generation slot).
        while len(w) < 3:
            w.append(0)
        if any(v < 0 for v in w):
            raise PDFParseError("xref stream /W contains a negative width")
        entry_size = sum(w)
        if entry_size <= 0:
            raise PDFParseError("xref stream /W defines a zero-byte entry")
        # PDFBOX-6037: an entry wider than 20 bytes is nonsensical (the
        # spec caps practical widths well below this). Mirrors upstream
        # ``PDFXrefStreamParser.initParserValues``.
        if entry_size > 20:
            raise PDFParseError(
                f"xref stream /W defines an entry wider than 20 bytes: {w!r}"
            )
        # /Index defaults to [0 /Size] per ISO 32000-1 §7.5.8.2.
        index_obj = xref_stream_dict.get_dictionary_object(COSName.get_pdf_name("Index"))
        index_pairs: list[tuple[int, int]] = []
        if isinstance(index_obj, COSArray):
            # Upstream ``PDFXrefStreamParser.initParserValues`` rejects
            # an empty /Index or one whose length is odd — the array
            # must be a sequence of ``[first count]`` pairs.
            if index_obj.size() == 0 or index_obj.size() % 2 == 1:
                raise PDFParseError(
                    f"xref stream /Index has odd or empty length: {index_obj.size()}"
                )
            i = 0
            while i + 1 < index_obj.size():
                first = index_obj.get(i)
                count = index_obj.get(i + 1)
                # Upstream rejects non-integer entries with
                # "Xref stream must have integer in /Index array".
                if not isinstance(first, COSInteger) or not isinstance(
                    count, COSInteger
                ):
                    raise PDFParseError(
                        "xref stream /Index entries must be integers"
                    )
                index_pairs.append((first.int_value(), count.int_value()))
                i += 2
        if not index_pairs:
            size_obj = xref_stream_dict.get_dictionary_object(
                COSName.get_pdf_name("Size")
            )
            size = size_obj.int_value() if isinstance(size_obj, COSInteger) else 0
            index_pairs = [(0, size)]
        body_offset = 0
        for first_obj_num, count in index_pairs:
            if count <= 0:
                continue
            for k in range(count):
                xref_table[COSObjectKey(first_obj_num + k, 0)] = body_offset
                body_offset += entry_size
        return xref_table
