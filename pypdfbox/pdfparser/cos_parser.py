from __future__ import annotations

import contextlib
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

    Stream bodies with a direct ``/Length`` are handled here; indirect
    ``/Length`` resolution, full document xref walking, and lazy object
    loading live in ``PDFParser``.

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

    # Header markers + default versions. Mirrors upstream
    # ``COSParser.PDF_HEADER`` / ``FDF_HEADER`` / ``PDF_DEFAULT_VERSION`` /
    # ``FDF_DEFAULT_VERSION``. The defaults apply when a PDF document
    # advertises a header marker but no version digits — upstream falls
    # back to ``1.4`` for PDFs and ``1.0`` for FDFs.
    PDF_HEADER: ClassVar[str] = "%PDF-"
    FDF_HEADER: ClassVar[str] = "%FDF-"
    PDF_DEFAULT_VERSION: ClassVar[str] = "1.4"
    FDF_DEFAULT_VERSION: ClassVar[str] = "1.0"

    # Keyword markers used by xref-locator helpers. Mirrors upstream
    # ``COSParser.XREF_TABLE`` / ``COSParser.STARTXREF`` (which are
    # ``char[]`` upstream — bytes here for parity with our byte sources).
    XREF_TABLE_MARKER: ClassVar[bytes] = b"xref"
    STARTXREF_MARKER: ClassVar[bytes] = b"startxref"

    # End-of-object markers. Mirrors upstream
    # ``COSParser.ENDSTREAM`` / ``COSParser.ENDOBJ`` byte arrays used by
    # the stream-body terminator scan.
    ENDSTREAM_MARKER: ClassVar[bytes] = b"endstream"
    ENDOBJ_MARKER: ClassVar[bytes] = b"endobj"

    # Lower bound for the byte offset at which a brute-force xref scan
    # may legitimately find a match. Mirrors upstream
    # ``COSParser.MINIMUM_SEARCH_OFFSET`` (= 6 — i.e. shorter than
    # ``%PDF-x.y`` so the scan never drifts into the header).
    MINIMUM_SEARCH_OFFSET: ClassVar[int] = 6

    # Buffer length used by the stream-body / endstream-scan helpers.
    # Mirrors upstream ``COSParser.STRMBUFLEN`` (= 2048 bytes).
    STRMBUFLEN: ClassVar[int] = 2048

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
        self._recursion_depth: int = 0

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
            return COSName.get_pdf_name(self.read_name_bytes())
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
        self._enter_recursion("array", start)
        try:
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
        finally:
            self._leave_recursion()

    # ---------- dictionaries ----------

    def parse_cos_dictionary(self) -> COSDictionary:
        """Parse a ``<< ... >>`` dictionary."""
        start = self.position
        self.read_expected(b"<<")
        self._enter_recursion("dictionary", start)
        try:
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
                key = COSName.get_pdf_name(self.read_name_bytes())
                value = self.parse_direct_object()
                d.set_item(key, value)
        finally:
            self._leave_recursion()

    def _enter_recursion(self, object_type: str, position: int) -> None:
        if self._recursion_depth >= self.MAX_RECURSION_DEPTH:
            raise PDFParseError(
                f"maximum COS {object_type} nesting depth exceeded",
                position=position,
            )
        self._recursion_depth += 1

    def _leave_recursion(self) -> None:
        self._recursion_depth -= 1

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
        return COSName.get_pdf_name(self.read_name_bytes())

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
        decoded, pairs, first = _read_object_stream_offsets(objstm_body, obj_num)
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
        if is_standalone and not (
            isinstance(type_obj, COSName) and type_obj.name == "XRef"
        ):
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
                try:
                    line = self.read_until_eol()
                    self.skip_eol()
                    offset, generation, flag = _parse_xref_entry_line(line)
                except PDFParseError:
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
        return self.parse_header(
            self.PDF_HEADER.encode("ascii"), self.PDF_DEFAULT_VERSION
        )

    def parse_fdf_header(self) -> float:
        """Validate the ``%FDF-x.y`` magic and return the version as a
        float. FDF (Forms Data Format) shares the PDF header layout but
        uses a different magic and a default of ``1.0``. Tolerates up to
        1024 bytes of leading garbage (matches the PDF parser). Mirrors
        upstream ``COSParser.parseFDFHeader``."""
        return self.parse_header(
            self.FDF_HEADER.encode("ascii"), self.FDF_DEFAULT_VERSION
        )

    def parse_header(self, marker: bytes | str, default_version: str) -> float:
        """Shared implementation for :meth:`parse_pdf_header` and
        :meth:`parse_fdf_header`. Scans the leading 1024 bytes for
        ``marker``, then reads the version digits up to EOL/whitespace.
        Falls back to ``default_version`` when no digits follow the
        marker. Mirrors upstream ``COSParser.parseHeader(String, String)``
        (Java line 1617).

        ``marker`` may be ``bytes``/``bytearray`` (preferred) or a ``str``
        (treated as ASCII for parity with the upstream ``String``
        signature)."""
        if isinstance(marker, str):
            marker = marker.encode("ascii")
        scan_window = 1024
        self._src.seek(0)
        head = bytearray()
        while len(head) < scan_window:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                break
            head.append(b)
        idx = bytes(head).find(marker)
        if idx < 0:
            raise PDFParseError(f"missing {marker.decode('ascii')} header")
        # Position the cursor just past the marker for version parsing.
        self._src.seek(idx + len(marker))
        version_bytes = bytearray()
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF or b in (0x0A, 0x0D, 0x20):
                break
            version_bytes.append(b)
        if not version_bytes:
            return float(default_version)
        try:
            return float(version_bytes.decode("ascii"))
        except ValueError as exc:
            raise PDFParseError(
                f"malformed {marker.decode('ascii')} version {version_bytes!r}"
            ) from exc

    def has_pdf_header(self) -> bool:
        """``True`` when :meth:`parse_pdf_header` would succeed. Useful
        for callers wanting a non-throwing predicate before dispatching
        between PDF / FDF entry points. Mirrors the boolean return shape
        of upstream ``COSParser.parsePDFHeader`` (which returns ``true``
        when a header is found)."""
        saved = self._src.get_position()
        try:
            self.parse_pdf_header()
            return True
        except PDFParseError:
            return False
        finally:
            self._src.seek(saved)

    def has_fdf_header(self) -> bool:
        """``True`` when :meth:`parse_fdf_header` would succeed. Mirrors
        the boolean return shape of upstream ``COSParser.parseFDFHeader``."""
        saved = self._src.get_position()
        try:
            self.parse_fdf_header()
            return True
        except PDFParseError:
            return False
        finally:
            self._src.seek(saved)

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
            if before_ok and after_ok and not (j > 0 and data[j - 1] == 0x2F):
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
        self,
        xref_stream_dict: COSDictionary,
        xref_table: dict[COSObjectKey, int] | None = None,
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
                first_obj = index_obj.get(i)
                count_obj = index_obj.get(i + 1)
                # Upstream rejects non-integer entries with
                # "Xref stream must have integer in /Index array".
                if not isinstance(first_obj, COSInteger) or not isinstance(
                    count_obj, COSInteger
                ):
                    raise PDFParseError(
                        "xref stream /Index entries must be integers"
                    )
                first = first_obj.int_value()
                count = count_obj.int_value()
                _validate_xref_index_pair(first, count)
                index_pairs.append((first, count))
                i += 2
        if not index_pairs:
            size_obj = xref_stream_dict.get_dictionary_object(
                COSName.get_pdf_name("Size")
            )
            size = size_obj.int_value() if isinstance(size_obj, COSInteger) else 0
            _validate_xref_index_pair(0, size)
            index_pairs = [(0, size)]
        body_offset = 0
        for first_obj_num, count in index_pairs:
            if count <= 0:
                continue
            for object_index in range(count):
                xref_table[COSObjectKey(first_obj_num + object_index, 0)] = body_offset
                body_offset += entry_size
        return xref_table

    # ---------- trailer-resolver hook (org.apache.pdfbox.pdfparser.COSParser:322) ----------

    def reset_trailer_resolver(self) -> bool:
        """Indicate whether the xref-trailer-resolver should be reset
        once :meth:`retrieve_trailer` finishes. Subclasses that need the
        resolver state preserved (typically because they perform their
        own additional walks afterwards) override this to return
        ``False``. Mirrors upstream
        ``COSParser.resetTrailerResolver()`` (Java line 322)."""
        return True

    # ---------- trailer retrieval (org.apache.pdfbox.pdfparser.COSParser:252) ----------

    def retrieve_trailer(self) -> COSDictionary | None:
        """Read the trailer dictionary from the source. The default
        pypdfbox flow drives the full xref chain through ``PDFParser``;
        this method is the upstream-named entry point. Mirrors upstream
        ``COSParser.retrieveTrailer()`` (Java line 252).

        When a bound document already carries a trailer (because
        ``PDFParser.parse`` ran), that trailer is returned directly.
        Otherwise this falls back to :meth:`rebuild_trailer` in lenient
        mode and raises ``PDFParseError`` in strict mode — matching the
        upstream branch where ``isLenient`` toggles the brute-force
        recovery path."""
        if self._document is not None:
            existing = self._document.get_trailer()
            if existing is not None:
                return existing
        if not self._lenient:
            raise PDFParseError(
                "retrieve_trailer requires PDFParser-driven xref walk in "
                "strict mode; bind a document or run PDFParser.parse() first"
            )
        rebuilt = self.rebuild_trailer()
        self._trailer_was_rebuild = True
        return rebuilt

    # ---------- COSObject dereference (org.apache.pdfbox.pdfparser.COSParser:621) ----------

    def dereference_cos_object(self, obj: COSObject) -> COSBase | None:
        """Resolve ``obj`` (a ``COSObject`` placeholder) to its underlying
        ``COSBase`` value. The source position is preserved across the
        call. Mirrors upstream ``COSParser.dereferenceCOSObject(COSObject)``
        (Java line 621) — the protected override of
        ``ICOSParser.dereferenceCOSObject``.

        With a bound document the resolution routes through the pool's
        installed loader; without one the call returns the placeholder's
        currently-attached payload (or ``None``)."""
        current_pos = self.position
        try:
            key = COSObjectKey(obj.object_number, obj.generation_number)
            parsed = self.parse_object_dynamically(
                key.object_number, key.generation_number, False
            )
            if parsed is not None:
                # Match upstream's setDirect(false) + setKey(key) on the
                # resolved payload — only `set_direct` exists today.
                if hasattr(parsed, "set_direct"):
                    with contextlib.suppress(Exception):
                        parsed.set_direct(False)
                if hasattr(parsed, "set_key"):
                    with contextlib.suppress(Exception):
                        parsed.set_key(key)
            return parsed
        finally:
            if current_pos > 0:
                with contextlib.suppress(Exception):
                    self.seek(current_pos)

    # ---------- random-access view (org.apache.pdfbox.pdfparser.COSParser:639) ----------

    def create_random_access_read_view(
        self, start_position: int, stream_length: int
    ) -> RandomAccessRead:
        """Return a ``RandomAccessReadView`` over ``[start_position,
        start_position + stream_length)`` of this parser's source. Mirrors
        upstream ``COSParser.createRandomAccessReadView(long, long)``
        (Java line 639) — used by stream-body code that wants a sliced
        view without loading bytes into memory."""
        return self._src.create_view(int(start_position), int(stream_length))

    # ---------- compressed-object loader (org.apache.pdfbox.pdfparser.COSParser:812) ----------

    def parse_object_stream_object(
        self, objstm_obj_nr: int, key: COSObjectKey
    ) -> COSBase | None:
        """Parse one specific compressed object identified by ``key`` from
        the object stream whose container has number ``objstm_obj_nr``.
        Mirrors upstream ``COSParser.parseObjectStreamObject(long,
        COSObjectKey)`` (Java line 812).

        Implementation walks the same code path as :meth:`parse_object_stream`
        but returns only the requested object (and registers all its
        siblings in the document pool as a side-effect). Returns ``None``
        when the object is not present in the stream."""
        if self._document is None:
            raise PDFParseError(
                f"parse_object_stream_object({objstm_obj_nr}, {key}): "
                "no document bound to parser"
            )
        # parse_object_stream populates the pool and returns a list in
        # storage order; the resolved object is then read out of the pool.
        self.parse_object_stream(int(objstm_obj_nr))
        if not self._document.has_object(key):
            return None
        return self._document.get_object_from_pool(key).get_object()

    # ---------- COSStream parsing (org.apache.pdfbox.pdfparser.COSParser:904) ----------

    def parse_cos_stream(self, dic: COSDictionary) -> COSStream:
        """Read a stream body (``stream ... endstream``) immediately
        following the dictionary ``dic`` and return the resulting
        ``COSStream`` (with ``dic``'s entries copied onto it). The
        ``stream`` keyword must already be the next token. Mirrors
        upstream ``COSParser.parseCOSStream(COSDictionary)`` (Java line
        904).

        Direct integer ``/Length`` is required by this implementation —
        an indirect-reference ``/Length`` raises ``NotImplementedError``
        and the resolution lives in ``PDFParser`` (which has full xref
        access). Trailing whitespace before ``endstream`` is tolerated."""
        # Consume the 'stream' keyword (mirrors upstream's leading
        # readString() — already validated by the caller in upstream).
        self.skip_whitespace()
        kw = self.read_keyword()
        if kw != b"stream":
            raise PDFParseError(
                f"expected 'stream' keyword, got {kw!r}", position=self.position
            )
        stream = self._build_stream_from_dict(dic)
        self._read_stream_body_into(stream)
        return stream

    # ---------- page-tree validation (org.apache.pdfbox.pdfparser.COSParser:1403) ----------

    def check_pages(self, root: COSDictionary) -> None:
        """Validate that the document's page tree (``root[/Pages]``) is
        a dictionary. When the trailer was rebuilt by the brute-force
        recovery path, also walk every ``/Kids`` entry and prune those
        whose targets are missing or invalid. Mirrors upstream
        ``COSParser.checkPages(COSDictionary)`` (Java line 1403).

        Raises ``PDFParseError`` (upstream's ``IOException``) when the
        page-tree root is not a dictionary."""
        pages_name = COSName.get_pdf_name("Pages")
        if self._trailer_was_rebuild:
            pages = root.get_dictionary_object(pages_name)
            if isinstance(pages, COSDictionary):
                self.check_pages_dictionary(pages, set())
        if not isinstance(root.get_dictionary_object(pages_name), COSDictionary):
            raise PDFParseError("Page tree root must be a dictionary")

    def check_pages_dictionary(
        self, pages_dict: COSDictionary, seen: set
    ) -> int:
        """Recursive worker for :meth:`check_pages`. Mirrors private
        upstream ``checkPagesDictionary`` (Java line 1420) — exposed
        publicly here so the parity audit recognises the 1:1 port.

        Walks ``pages_dict[/Kids]`` removing entries whose targets are
        missing or invalid, recurses through nested ``/Pages`` nodes,
        counts ``/Page`` leaves, and writes the resulting tally back to
        ``pages_dict[/Count]``."""
        kids_name = COSName.get_pdf_name("Kids")
        type_name = COSName.get_pdf_name("Type")
        count_name = COSName.get_pdf_name("Count")
        kids = pages_dict.get_dictionary_object(kids_name)
        number_of_pages = 0
        if isinstance(kids, COSArray):
            removals: list[COSBase] = []
            for kid in list(kids):
                if not isinstance(kid, COSObject) or kid in seen:
                    removals.append(kid)
                    continue
                kid_obj = kid.get_object()
                if kid_obj is None or kid_obj is COSNull.NULL:
                    removals.append(kid)
                    continue
                if isinstance(kid_obj, COSDictionary):
                    type_obj = kid_obj.get_dictionary_object(type_name)
                    if isinstance(type_obj, COSName) and type_obj.name == "Pages":
                        seen.add(kid)
                        number_of_pages += self.check_pages_dictionary(
                            kid_obj, seen
                        )
                    elif isinstance(type_obj, COSName) and type_obj.name == "Page":
                        number_of_pages += 1
            for victim in removals:
                with contextlib.suppress(Exception):
                    kids.remove(victim)
        pages_dict.set_item(count_name, COSInteger.get(number_of_pages))
        return number_of_pages

    # ---------- encryption surface (org.apache.pdfbox.pdfparser.COSParser:1829) ----------

    def get_encryption(self):  # type: ignore[no-untyped-def]
        """Return the ``PDEncryption`` instance bound to this parser, or
        ``None`` when the document is not encrypted. The document must
        have been parsed first. Mirrors upstream
        ``COSParser.getEncryption()`` (Java line 1829).

        pypdfbox stores the encryption metadata at the ``PDFParser``
        layer — when the parser is unbound this returns ``None``; when a
        document is bound, the trailer's ``/Encrypt`` dictionary is wrapped
        as a ``PDEncryption`` if available (matches the upstream
        accessor's read-only contract)."""
        if self._document is None:
            raise PDFParseError(
                "You must parse the document first before calling get_encryption()"
            )
        enc_dict = self._document.get_encryption_dictionary()
        if enc_dict is None:
            return None
        # Local import to avoid a cos_parser → pdmodel.encryption cycle at
        # module load.
        try:
            from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption  # noqa: PLC0415
        except ImportError:  # pragma: no cover - module always importable here
            return enc_dict
        return PDEncryption(enc_dict)

    def get_access_permission(self):  # type: ignore[no-untyped-def]
        """Return the ``AccessPermission`` derived from the security
        handler attached during decryption preparation, or ``None`` when
        the document is unencrypted / not yet decrypted. Mirrors upstream
        ``COSParser.getAccessPermission()`` (Java line 1846).

        Requires a bound document — without one this raises
        ``PDFParseError`` (upstream throws ``IOException``)."""
        if self._document is None:
            raise PDFParseError(
                "You must parse the document first before calling "
                "get_access_permission()"
            )
        # pypdfbox surfaces AccessPermission off the security handler at
        # the PDFParser layer. Without a handler bound to the parser we
        # return None (the document is either unencrypted, or decryption
        # hasn't been prepared yet).
        handler = getattr(self, "_security_handler", None)
        if handler is None:
            return None
        if hasattr(handler, "get_current_access_permission"):
            return handler.get_current_access_permission()
        return None

    def prepare_decryption(self) -> None:
        """Stage the security handler for the bound document so subsequent
        object reads go through decryption. Mirrors upstream
        ``COSParser.prepareDecryption()`` (Java line 1862).

        pypdfbox does the heavy lifting in
        ``PDFParser._prepare_security_handler_if_needed`` — this entry
        point exists to make the upstream call surface available on
        ``COSParser`` itself for downstream callers driving an
        already-loaded document."""
        if self._document is None:
            return
        enc_dict = self._document.get_encryption_dictionary()
        if enc_dict is None:
            return
        # Idempotent: do nothing if a handler is already attached.
        if getattr(self, "_security_handler", None) is not None:
            return
        # We don't pull in the standard security handler here — that
        # binding lives in ``PDFParser._prepare_security_handler_if_needed``
        # (which has access to the password). Subclasses (PDFParser) call
        # super().prepare_decryption() then perform the heavy work.

    def get_security_handler(self):
        """Return the security handler bound to this parser.

        Mirrors upstream ``COSParser.getSecurityHandler()`` (Java line
        1820). Returns the handler the document was decrypted with, or
        ``None`` for unencrypted PDFs / parsers that never staged
        decryption. The document must already be parsed."""
        return getattr(self, "_security_handler", None)

    def read_object_marker(self) -> None:
        """Consume the literal ``obj`` keyword. Mirrors upstream
        ``COSParser.readObjectMarker()`` (Java line 1543) — a thin
        wrapper around :meth:`read_expected_string` used by subclasses
        that hand-walk the indirect-object preamble."""
        self.read_expected_string(self.OBJ_MARKER, True)

    def parse_cos_literal_string(self) -> COSString:
        """Parse a ``(...)`` literal PDF string.

        Mirrors upstream ``COSParser.parseCOSLiteralString()`` (Java
        line 1903) — wraps :meth:`read_literal_string` into a
        :class:`COSString`. Used by subclasses that need to dispatch
        on the leading ``(`` token themselves."""
        return COSString(self.read_literal_string())

    # ---------- xref-recovery / startxref / trailer parsing ----------
    #
    # Upstream's ``COSParser`` private xref-recovery helpers, surfaced
    # here under upstream's snake_cased names. Most are 1:1 ports of the
    # Java logic; a handful diverge minimally to fit pypdfbox's
    # call-graph (notably ``get_brute_force_parser`` returns ``self``
    # because we inline brute-force scans on this class instead of
    # delegating to a separate ``BruteForceParser``).

    def init(self) -> None:
        """Apply the ``SYSPROP_EOFLOOKUPRANGE`` system property override
        (when set) to the ``%%EOF`` lookup range. Mirrors upstream
        ``COSParser.init(StreamCacheCreateFunction)`` (Java line 205).

        pypdfbox does not consult the JVM's system-property table — the
        upstream init also constructs a ``COSDocument`` from the
        provided stream-cache factory, but pypdfbox passes the document
        in via ``__init__``. The method exists for parity callers and is
        a no-op when no environment override is present (matches
        upstream when the property is unset)."""
        import os  # noqa: PLC0415 — local import keeps cos_parser import-cheap
        override = os.environ.get(self.SYSPROP_EOFLOOKUPRANGE)
        if override is None:
            return
        try:
            self.set_eof_lookup_range(int(override))
        except ValueError:
            # Upstream LOG.warn — silent here (CLAUDE.md: stdlib logging
            # is acceptable; we don't want chatty parser output).
            return

    def get_startxref_offset(self) -> int:
        """Locate the ``startxref`` marker by scanning the trailing
        ``read_trail_bytes`` window of the source for ``%%EOF`` and
        walking backwards to ``startxref``. Returns the absolute byte
        offset of ``startxref`` within the source. Mirrors upstream
        ``COSParser.getStartxrefOffset()`` (Java line 497).

        Raises ``PDFParseError`` (upstream ``IOException``) when the
        ``startxref`` marker is missing. Strict mode also rejects a
        missing ``%%EOF`` marker; lenient mode treats it as if it
        appeared at the end of the buffer."""
        if self._file_len < 0:
            raise PDFParseError("source length unknown; cannot locate startxref")
        trail_byte_count = (
            self._file_len if self._file_len < self._read_trail_bytes
            else self._read_trail_bytes
        )
        skip_bytes = self._file_len - trail_byte_count
        saved = self.position
        try:
            self._src.seek(skip_bytes)
            buf = bytearray(trail_byte_count)
            off = 0
            while off < trail_byte_count:
                read = self._src.read_into(buf, off, trail_byte_count - off)
                if read < 1:
                    raise PDFParseError(
                        "No more bytes to read for trailing buffer, "
                        f"but expected: {trail_byte_count - off}"
                    )
                off += read
        finally:
            self._src.seek(saved if saved >= 0 else 0)
        buf_off = self.last_index_of(self.EOF_MARKER, buf, len(buf))
        if buf_off < 0:
            if self._lenient:
                buf_off = len(buf)
            else:
                raise PDFParseError(
                    f"Missing end of file marker {self.EOF_MARKER!r}"
                )
        buf_off = self.last_index_of(self.STARTXREF_MARKER, buf, buf_off)
        if buf_off < 0:
            raise PDFParseError("Missing 'startxref' marker.")
        return skip_bytes + buf_off

    def parse_start_xref(self) -> int:
        """Read the ``startxref`` keyword + integer offset at the current
        position and return the offset (or ``-1`` when the keyword does
        not appear). Mirrors upstream ``COSParser.parseStartXref()``
        (Java line 1472)."""
        start_xref = -1
        if self.is_string(self.STARTXREF_MARKER):
            self.read_keyword()  # consume 'startxref'
            self.skip_spaces()
            start_xref = self.read_long()
        return start_xref

    def parse_trailer(self) -> bool:
        """Parse the ``trailer << ... >>`` block at the current source
        position and return ``True`` on success. The parsed dictionary
        is returned via :meth:`get_document` -> trailer when a document
        is bound; without one this method only validates the structure.
        Mirrors upstream ``COSParser.parseTrailer()`` (Java line 1537).

        Lenient mode tolerates extra leading digit lines (PDFBOX-1739
        — RegisSTAR documents) and a trailer that runs onto the same
        line as the keyword (no EOL after ``trailer``)."""
        trailer_offset = self.position
        if self._lenient:
            next_character = self.peek()
            while (
                next_character != 0x74  # 't'
                and next_character != RandomAccessRead.EOF
                and self.is_digit(next_character)
            ):
                # Skip a leading digit line; keep retrying.
                self.read_line()
                next_character = self.peek()
        if self.peek() != 0x74:
            return False
        current_offset = self.position
        next_line = self.read_line().strip()
        if next_line != "trailer":
            if next_line.startswith("trailer"):
                # EOL missing after 'trailer'; jump just past the keyword.
                self._src.seek(current_offset + len("trailer"))
            else:
                return False
        self.skip_spaces()
        parsed_trailer = self.parse_cos_dictionary()
        if self._document is not None:
            existing = self._document.get_trailer()
            if existing is None:
                self._document.set_trailer(parsed_trailer)
        self._last_parsed_trailer = parsed_trailer
        self.skip_spaces()
        # silence "trailer_offset unused" — kept to mirror upstream's
        # local but not strictly needed for the return contract.
        _ = trailer_offset
        return True

    def parse_xref(self, start_xref_offset: int) -> COSDictionary | None:
        """Parse the cross-reference chain starting at
        ``start_xref_offset`` and return the resolved trailer dictionary.
        Mirrors upstream ``COSParser.parseXref(long)`` (Java line 334).

        Walks ``/Prev`` references through every linked xref section
        (traditional ``xref`` table or PDF 1.5+ xref-stream object).
        ``/Prev`` loops are detected via a visited-offset set and raise
        ``PDFParseError``. The full implementation (with hybrid
        ``/XRefStm`` handling and document-pool population) lives in
        ``PDFParser`` — this entry point provides the upstream call
        surface and delegates to :meth:`parse_xref_table` /
        :meth:`parse_xref_obj_stream` for the per-section work."""
        self._src.seek(start_xref_offset)
        start = max(0, self.parse_start_xref())
        fixed = self.check_x_ref_offset(start)
        if fixed > -1:
            start = fixed
        if self._document is not None:
            with contextlib.suppress(Exception):
                self._document.set_start_xref(start)
        prev = start
        prev_set: set[int] = set()
        trailer: COSDictionary | None = None
        while prev > 0:
            if prev in prev_set:
                raise PDFParseError(f"/Prev loop at offset {prev}")
            prev_set.add(prev)
            self._src.seek(prev)
            self.skip_spaces()
            prev_set.add(self.position)
            if self.peek() == 0x78:  # 'x'
                if not self.parse_xref_table(prev) or not self.parse_trailer():
                    raise PDFParseError(
                        f"Expected trailer object at offset {self.position}"
                    )
                trailer = getattr(self, "_last_parsed_trailer", None)
                if trailer is None:  # pragma: no cover - parse_trailer sets this
                    return None
                prev_obj = trailer.get_dictionary_object(
                    COSName.get_pdf_name("Prev")
                )
                prev = prev_obj.int_value() if isinstance(prev_obj, COSInteger) else 0
            else:
                # xref-stream object: parse and read /Prev from its dict.
                prev = self.parse_xref_obj_stream(prev, True)
        return trailer

    def parse_xref_obj_stream(
        self, obj_byte_offset: int, is_standalone: bool = True
    ) -> int:
        """Parse the xref-stream object header at ``obj_byte_offset``
        (consuming the ``n g obj`` prefix and the trailing stream body)
        and return the value of the ``/Prev`` entry, or ``-1`` when the
        dictionary lacks one. Mirrors upstream
        ``COSParser.parseXrefObjStream(long, boolean)`` (Java line
        465).

        ``is_standalone`` mirrors upstream's flag — when ``True`` the
        parsed dictionary is registered as the active trailer; when
        ``False`` (hybrid xref) the dictionary is parsed only for its
        ``/Prev`` link."""
        self._src.seek(obj_byte_offset)
        self.read_object_number()
        self.read_generation_number()
        self.read_expected_string(b"obj", True)
        body = self.parse_direct_object()
        if not isinstance(body, COSDictionary):
            raise PDFParseError(
                "xref-stream object body is not a dictionary",
                position=self.position,
            )
        if is_standalone and self._document is not None:
            with contextlib.suppress(Exception):
                self._document.set_trailer(body)
        # Promote + read body so the parser advances past 'endstream'
        # (matches upstream's parseCOSStream call).
        self.skip_spaces()
        if self.peek() == 0x73:  # 's' — stream
            kw = self.read_keyword()
            if kw == b"stream":
                stream = self._build_stream_from_dict(body)
                with contextlib.suppress(NotImplementedError, PDFParseError):
                    self._read_stream_body_into(stream)
        prev_obj = body.get_dictionary_object(COSName.get_pdf_name("Prev"))
        return prev_obj.int_value() if isinstance(prev_obj, COSInteger) else -1

    def get_object_offset(
        self, obj_key: COSObjectKey, require_existing_not_compressed: bool
    ) -> int | None:
        """Look up ``obj_key`` in the document's xref table and return
        the byte offset (positive) or compressed-objstm reference
        (negative — magnitude is the ObjStm container number). Returns
        ``None`` when the key is unknown. Mirrors upstream
        ``COSParser.getObjectOffset(COSObjectKey, boolean)`` (Java line
        690).

        In lenient mode an unknown key triggers a brute-force scan; the
        recovered offset is recorded back into the xref table. Strict
        mode (``require_existing_not_compressed`` true) raises when the
        key is missing or points at a compressed object."""
        if self._document is None:
            if require_existing_not_compressed:
                raise PDFParseError(
                    f"Object must be defined and must not be compressed object: "
                    f"{obj_key.object_number}:{obj_key.generation_number}"
                )
            return None
        xref_table = self._document.get_xref_table()
        offset = xref_table.get(obj_key)
        if offset is None and self._lenient:
            scanned = self.get_brute_force_parser().bf_search_for_objects()
            offset = scanned.get(obj_key)
            if offset is not None:
                xref_table[obj_key] = offset
        if require_existing_not_compressed and (offset is None or offset <= 0):
            raise PDFParseError(
                f"Object must be defined and must not be compressed object: "
                f"{obj_key.object_number}:{obj_key.generation_number}"
            )
        return offset

    def parse_file_object(
        self, obj_offset: int, obj_key: COSObjectKey
    ) -> COSBase | None:
        """Parse the indirect-object definition stored at
        ``obj_offset`` and return its body. Mirrors upstream
        ``COSParser.parseFileObject(Long, COSObjectKey)`` (Java line
        717).

        The header ``n g obj`` is validated against ``obj_key`` (an
        upstream ``IOException`` is raised on mismatch — pypdfbox uses
        ``PDFParseError``). Stream objects are promoted via
        :meth:`parse_cos_stream`. Encryption is not applied here —
        decryption happens at the ``PDFParser`` layer where the
        security handler lives."""
        self._src.seek(obj_offset)
        read_obj_nr = self.read_object_number()
        read_obj_gen = self.read_generation_number()
        self.read_expected_string(b"obj", True)
        if (
            read_obj_nr != obj_key.object_number
            or read_obj_gen != obj_key.generation_number
        ):
            raise PDFParseError(
                f"XREF for {obj_key.object_number}:{obj_key.generation_number} "
                f"points to wrong object: {read_obj_nr}:{read_obj_gen} at "
                f"offset {obj_offset}"
            )
        self.skip_spaces()
        parsed = self.parse_direct_object()
        self.skip_spaces()
        end_kw = self.read_keyword()
        if end_kw == b"stream":
            self._src.rewind(len(b"stream"))
            if isinstance(parsed, COSDictionary):
                parsed = self.parse_cos_stream(parsed)
            else:
                raise PDFParseError(
                    f"Stream not preceded by dictionary (offset: {obj_offset})."
                )
            self.skip_spaces()
            with contextlib.suppress(PDFParseError):
                self.read_keyword()  # consume trailing 'endobj'
        return parsed

    def get_length(self, length_base_obj: COSBase | None) -> COSBase | None:
        """Resolve a stream's ``/Length`` entry to a ``COSNumber``
        (``COSInteger`` / ``COSFloat``). Mirrors upstream
        ``COSParser.getLength(COSBase)`` (Java line 854).

        Returns ``None`` when the input is ``None`` or resolves to
        ``COSNull``. Raises ``PDFParseError`` when an indirect-reference
        ``/Length`` cannot be resolved or when the resolved type is
        wrong (upstream throws ``IOException``)."""
        if length_base_obj is None:
            return None
        if isinstance(length_base_obj, (COSInteger, COSFloat)):
            return length_base_obj
        if isinstance(length_base_obj, COSObject):
            length = length_base_obj.get_object()
            if length is None:
                raise PDFParseError("Length object content was not read.")
            if length is COSNull.NULL:
                return None
            if isinstance(length, (COSInteger, COSFloat)):
                return length
            raise PDFParseError(
                f"Wrong type of referenced length object {length_base_obj}: "
                f"{type(length).__name__}"
            )
        raise PDFParseError(
            f"Wrong type of length object: {type(length_base_obj).__name__}"
        )

    def read_until_end_stream(self, out: bytearray | None = None) -> int:
        """Scan forward from the current source position until
        ``endstream`` (or ``endobj`` — some malformed producers omit
        ``endstream``) and return the number of body bytes consumed.
        Mirrors upstream
        ``COSParser.readUntilEndStream(EndstreamFilterStream)`` (Java
        line 983).

        ``out`` is an optional ``bytearray`` that receives the body
        bytes as they're consumed; pass ``None`` to skip without
        recording. The returned length excludes the terminator
        keyword."""
        endstream = self.ENDSTREAM_MARKER
        endobj = self.ENDOBJ_MARKER
        consumed = 0
        match: bytes = b""
        match_target = endstream
        match_off = 0
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                break
            if b == match_target[match_off]:
                match_off += 1
                if match_off == len(match_target):
                    # Found the terminator — rewind so the keyword stays
                    # readable to callers (matches upstream which leaves
                    # the source positioned just past the keyword's
                    # final byte; we mirror that by NOT rewinding).
                    return consumed
            else:
                # Reset / re-evaluate. If we'd matched 'endst' but the
                # next byte is 'r' (endobj), upstream switches keywords
                # at offset 3 ('endo' vs 'ends').
                if match_off == 3 and b == endobj[3]:
                    match_target = endobj
                    match_off += 1
                    consumed += match_off
                    match_off = 0
                    continue
                # Append the consumed-but-unmatched prefix to the body.
                if match_off > 0:
                    if out is not None:
                        out.extend(match_target[:match_off])
                    consumed += match_off
                    match_off = 0
                    match_target = endstream
                # Now record this byte.
                if out is not None:
                    out.append(b)
                consumed += 1
                _ = match  # placeholder; upstream uses a quick-test
                # buffer that we don't need for parity correctness.
        return consumed

    def validate_stream_length(self, stream_length: int) -> bool:
        """Return ``True`` when seeking ``stream_length`` bytes forward
        from the current source position lands on an ``endstream``
        keyword. Mirrors upstream
        ``COSParser.validateStreamLength(long)`` (Java line 1077).

        Used by stream-body parsing as a fast path: if ``/Length`` looks
        sane the body bytes can be skipped wholesale; otherwise the
        parser falls back to :meth:`read_until_end_stream`."""
        origin_offset = self.position
        if stream_length == 0:
            return False
        if stream_length < 0:
            return False
        expected_end = origin_offset + stream_length
        if self._file_len > 0 and expected_end > self._file_len:
            return False
        try:
            self._src.seek(expected_end)
            self.skip_spaces()
            end_stream_found = self.is_string(self.ENDSTREAM_MARKER)
        finally:
            self._src.seek(origin_offset)
        return end_stream_found

    def check_x_ref_offset(self, start_x_ref_offset: int) -> int:
        """Validate the byte offset claimed for the cross-reference
        table/stream and return either the original offset, a
        brute-force-recovered offset, or ``-1`` when no valid offset
        exists. Mirrors upstream
        ``COSParser.checkXRefOffset(long)`` (Java line 1121).

        Strict mode short-circuits and returns ``start_x_ref_offset``
        unchanged. Lenient mode probes for the literal ``xref`` keyword,
        falls back to xref-stream-object detection, and finally invokes
        the brute-force scanner."""
        if not self._lenient:
            return start_x_ref_offset
        self._src.seek(start_x_ref_offset)
        self.skip_spaces()
        if self.is_string(self.XREF_TABLE_MARKER):
            return start_x_ref_offset
        if start_x_ref_offset > 0:
            if self.check_x_ref_stream_offset(start_x_ref_offset):
                return start_x_ref_offset
            return self.calculate_x_ref_fixed_offset(start_x_ref_offset)
        return -1

    def check_x_ref_stream_offset(self, start_x_ref_offset: int) -> bool:
        """Return ``True`` when the byte at ``start_x_ref_offset``
        opens a valid xref-stream object header (``n g obj << /Type
        /XRef ... >>``). Mirrors upstream
        ``COSParser.checkXRefStreamOffset(long)`` (Java line 1156)."""
        if not self._lenient or start_x_ref_offset == 0:
            return True
        self._src.seek(start_x_ref_offset - 1)
        next_value = self._src.read()
        if next_value not in self.WHITESPACE:
            return False
        self.skip_spaces()
        peek = self.peek()
        if peek == RandomAccessRead.EOF or not self.is_digit(peek):
            return False
        try:
            self.read_object_number()
            self.read_generation_number()
            self.read_expected_string(b"obj", True)
            d = self.parse_direct_object()
        except (PDFParseError, ValueError):
            self._src.seek(start_x_ref_offset)
            return False
        self._src.seek(start_x_ref_offset)
        if not isinstance(d, COSDictionary):
            return False
        type_obj = d.get_dictionary_object(COSName.get_pdf_name("Type"))
        return isinstance(type_obj, COSName) and type_obj.name == "XRef"

    def calculate_x_ref_fixed_offset(self, object_offset: int) -> int:
        """Return a brute-force-recovered xref offset near
        ``object_offset``, or ``0`` when no candidate could be found.
        Mirrors upstream ``COSParser.calculateXRefFixedOffset(long)``
        (Java line 1205)."""
        if object_offset < 0:
            return 0
        new_offset = self.get_brute_force_parser().bf_search_for_xref(object_offset)
        if new_offset > -1:
            return new_offset
        return 0

    def validate_xref_offsets(
        self, xref_offset: dict[COSObjectKey, int] | None
    ) -> bool:
        """Walk every entry of ``xref_offset`` confirming each key
        actually appears at its claimed byte offset. Mirrors upstream
        ``COSParser.validateXrefOffsets(Map)`` (Java line 1223).

        Generation-number mismatches are corrected in place. Returns
        ``False`` when even one key cannot be dereferenced — the caller
        should fall back to a brute-force scan."""
        if xref_offset is None:
            return True
        corrected: dict[COSObjectKey, COSObjectKey] = {}
        valid: set[COSObjectKey] = set()
        for object_key, object_offset in list(xref_offset.items()):
            if object_offset is not None and object_offset >= 0:
                found = self.find_object_key(object_key, object_offset, xref_offset)
                if found is None:
                    return False
                if found != object_key:
                    corrected[object_key] = found
                else:
                    valid.add(object_key)
        corrected_pointers: dict[COSObjectKey, int] = {}
        for original, replacement in corrected.items():
            if replacement not in valid:
                corrected_pointers[replacement] = xref_offset[original]
        for original in corrected:
            xref_offset.pop(original, None)
        xref_offset.update(corrected_pointers)
        return True

    def check_xref_offsets(self) -> None:
        """Drive the xref-table dereferencing walk; if even one entry
        fails to resolve, replace the table with a brute-force scan.
        Mirrors upstream ``COSParser.checkXrefOffsets()`` (Java line
        1278)."""
        if self._document is None:
            return
        xref_table = self._document.get_xref_table()
        if not self.validate_xref_offsets(xref_table):
            recovered = self.get_brute_force_parser().bf_search_for_objects()
            if recovered:
                xref_table.clear()
                xref_table.update(recovered)

    def find_object_key(
        self,
        object_key: COSObjectKey,
        offset: int,
        xref_offset: dict[COSObjectKey, int],
    ) -> COSObjectKey | None:
        """Verify that ``object_key`` actually starts at byte
        ``offset``; return the (possibly generation-corrected) key on
        success or ``None`` on mismatch. Mirrors upstream
        ``COSParser.findObjectKey(COSObjectKey, long, Map)`` (Java line
        1305)."""
        if offset < self.MINIMUM_SEARCH_OFFSET:
            return None
        try:
            self._src.seek(offset)
            self.skip_spaces()
            if self.position == offset:
                self._src.seek(offset - 1)
                if self.position < offset:
                    peek = self.peek()
                    if peek == RandomAccessRead.EOF or not self.is_digit(peek):
                        self._src.read()
            try:
                found_object_number = self.read_object_number()
            except PDFParseError:
                return None
            if object_key.object_number != found_object_number:
                if not self._lenient:
                    return None
                object_key = COSObjectKey(
                    found_object_number, object_key.generation_number
                )
            gen_number = self.read_generation_number()
            self.read_expected_string(b"obj", True)
            if gen_number == object_key.generation_number:
                return object_key
            if self._lenient and gen_number > object_key.generation_number:
                return COSObjectKey(object_key.object_number, gen_number)
        except PDFParseError:
            return None
        return None

    def get_brute_force_parser(self) -> COSParser:
        """Return the brute-force parser. Mirrors upstream
        ``COSParser.getBruteForceParser()`` (Java line 1388).

        Upstream wraps a separate ``BruteForceParser`` class around the
        source; pypdfbox inlines the brute-force scans
        (:meth:`bf_search_for_objects`, :meth:`bf_search_for_xref`,
        :meth:`rebuild_trailer`) on ``COSParser`` itself, so this
        accessor returns ``self``. The return type matches the ``self``
        instance so callers can chain the brute-force methods directly."""
        return self


def _validate_xref_index_pair(first_obj_num: int, count: int) -> None:
    """Reject negative xref-stream /Index values before key construction."""
    if first_obj_num < 0:
        raise PDFParseError(
            f"xref stream /Index first object number is negative: {first_obj_num}"
        )
    if count < 0:
        raise PDFParseError(f"xref stream /Index count is negative: {count}")


def _parse_xref_entry_line(line: bytes) -> tuple[int, int, str]:
    """Parse one traditional xref entry line.

    The PDF grammar defines fixed-width 20-byte records, but real files
    often use compact LF-only lines without the optional trailing space.
    Splitting keeps both forms aligned without consuming bytes from the
    following entry.
    """
    parts = line.split()
    if len(parts) != 3:
        raise PDFParseError(f"malformed xref entry {line!r}")
    offset_bytes, generation_bytes, flag_bytes = parts
    if len(flag_bytes) != 1:
        raise PDFParseError(f"malformed xref entry flag {flag_bytes!r}")
    try:
        offset = int(offset_bytes.decode("ascii"))
        generation = int(generation_bytes.decode("ascii"))
        flag = flag_bytes.decode("ascii")
    except ValueError as exc:
        raise PDFParseError(f"malformed xref entry {line!r}") from exc
    return offset, generation, flag


def _read_object_stream_offsets(
    objstm_body: COSStream, objstm_obj_num: int
) -> tuple[bytes, list[tuple[int, int]], int]:
    """Return decoded ObjStm bytes, header pairs, and the payload start.

    Object streams encode a header of ``/N`` ``(object_number, byte_offset)``
    pairs before the packed object bodies. This helper centralizes the
    malformed-metadata checks shared by eager ``COSParser.parse_object_stream``
    and lazy ``PDFParser`` compressed-object loading.
    """
    type_obj = objstm_body.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
    if not (isinstance(type_obj, COSName) and type_obj.name == "ObjStm"):
        raise PDFParseError(f"object stream {objstm_obj_num} missing /Type /ObjStm")

    n_obj = objstm_body.get_dictionary_object(COSName.get_pdf_name("N"))
    first_obj = objstm_body.get_dictionary_object(COSName.get_pdf_name("First"))
    if not isinstance(n_obj, COSInteger) or not isinstance(first_obj, COSInteger):
        raise PDFParseError(f"object stream {objstm_obj_num} missing /N or /First")

    object_count = n_obj.value
    first = first_obj.value
    if object_count < 0:
        raise PDFParseError(f"object stream {objstm_obj_num} has negative /N")
    if first < 0:
        raise PDFParseError(f"object stream {objstm_obj_num} has negative /First")

    with objstm_body.create_input_stream() as src:
        decoded = src.read()
    if first > len(decoded):
        raise PDFParseError(
            f"object stream {objstm_obj_num} /First {first} exceeds decoded length "
            f"{len(decoded)}"
        )

    payload_length = len(decoded) - first
    header_view = RandomAccessReadBuffer(decoded[:first])
    header_parser = BaseParser(header_view)
    pairs: list[tuple[int, int]] = []
    try:
        for pair_index in range(object_count):
            try:
                header_parser.skip_whitespace()
                stored_obj_num = header_parser.read_int()
                header_parser.skip_whitespace()
                byte_offset = header_parser.read_int()
            except PDFParseError as exc:
                raise PDFParseError(
                    f"object stream {objstm_obj_num} header truncated at pair "
                    f"{pair_index}"
                ) from exc
            if stored_obj_num < 0:
                raise PDFParseError(
                    f"object stream {objstm_obj_num} has negative object number "
                    f"{stored_obj_num}"
                )
            if byte_offset < 0 or byte_offset >= payload_length:
                raise PDFParseError(
                    f"object stream {objstm_obj_num} object {stored_obj_num} "
                    f"offset {byte_offset} outside payload length {payload_length}"
                )
            pairs.append((stored_obj_num, byte_offset))
    finally:
        header_view.close()
    return decoded, pairs, first
