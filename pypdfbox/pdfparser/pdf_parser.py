from __future__ import annotations

from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
    COSStream,
    COSString,
)
from pypdfbox.io import RandomAccessRead, RandomAccessReadBuffer

from .base_parser import BaseParser
from .cos_parser import (
    COSParser,
    _parse_xref_entry_line,
    _read_object_stream_offsets,
    _validate_xref_index_pair,
)
from .endstream_filter_stream import EndstreamFilterStream
from .parse_error import PDFParseError
from .xref_trailer_resolver import XrefEntry, XrefTrailerResolver, XrefType

# How many trailing bytes to scan for ``startxref`` / ``%%EOF``. Mirrors the
# upstream ``COSParser.DEFAULT_TRAIL_BYTECOUNT`` knob (default 2048 in PDFBox;
# pypdfbox bumps the floor to 4096 to absorb noisier tails). Per-instance
# overrides go through :meth:`PDFParser.set_eof_lookup_range`.
_TAIL_SCAN_BYTES: int = 4096

# Upstream system-property name that lets callers override the EOF lookup
# range without code changes (``-Dorg.apache.pdfbox.pdfparser…``). Exposed
# verbatim for source-level parity with PDFBox; pypdfbox does not consult
# environment variables on its own — callers wire up the override
# explicitly via :meth:`PDFParser.set_eof_lookup_range` when desired.
SYSPROP_EOFLOOKUPRANGE: str = (
    "org.apache.pdfbox.pdfparser.nonSequentialPDFParser.eofLookupRange"
)


class PDFParser:
    """
    Top-level PDF document parser.

    Pipeline:
      1. ``parse_header()`` validates the ``%PDF-x.y`` magic and records
         the version.
      2. ``find_startxref_offset()`` scans the trailing bytes for
         ``startxref <int> %%EOF``.
      3. ``parse_xref_chain()`` walks the xref → trailer → ``/Prev`` chain
         via ``XrefTrailerResolver``, populating one entry per indirect
         object from traditional xref tables and PDF 1.5+ xref streams.
      4. ``populate_document()`` registers every xref entry as a
         ``COSObject`` in the document's pool with a lazy loader that
         seeks to the entry's offset on demand and parses the body.

    The convenience method ``parse()`` runs all four steps and returns
    the populated ``COSDocument``.
    """

    def __init__(self, source: RandomAccessRead) -> None:
        self._src = source
        self._base = BaseParser(source)
        self._resolver = XrefTrailerResolver()
        self._document: COSDocument | None = None
        self._version: float | None = None
        self._cos_parser: COSParser | None = None
        # Optional decryption material — when set via ``set_password`` the
        # parser instantiates a security handler eagerly (as soon as the
        # trailer's ``/Encrypt`` + ``/ID`` are available) so encrypted
        # xref-stream bodies can be deciphered before their entries are
        # decoded. Mirrors the upstream ``PDFParser(source, password, …)``
        # ctor overload. ``None`` (the default) preserves the lazy
        # post-load decryption flow driven by ``PDDocument.decrypt``.
        self._password: str | bytes | None = None
        # Populated by ``_prepare_security_handler_if_needed`` once the
        # trailer's ``/Encrypt`` is in scope. Reused for every subsequent
        # xref-stream object in the chain.
        self._security_handler: Any | None = None
        # Set to ``True`` whenever the parser observes an indirect object
        # whose dictionary advertises ``/Type /XRef`` while the document
        # carries an ``/Encrypt`` entry. Diagnostic surface for callers
        # that want to know whether the early-handler path was exercised.
        self._has_encrypted_xref_streams: bool = False
        # Lenient parsing toggle. Mirrors upstream
        # ``PDFParser.setLenient(boolean)``. The pypdfbox parser already
        # operates in a permissive (lenient) mode — this flag is exposed
        # for API parity so callers staging documents through PDFBox-style
        # entry points can round-trip the value. Stored only; no behaviour
        # branches off it yet.
        self._lenient: bool = True
        # Lazy ``PDDocument`` wrapper around the parsed ``COSDocument``.
        # Built on first call to :meth:`get_pd_document`; mirrors upstream
        # ``PDFParser.getPDDocument()``.
        self._pd_document: Any | None = None
        # How many trailing bytes :meth:`find_startxref_offset` reads when
        # hunting for the ``startxref`` directive. Mirrors upstream
        # ``COSParser.readTrailBytes`` and the ``setEOFLookupRange`` knob.
        self._eof_lookup_range: int = _TAIL_SCAN_BYTES
        # Optional linearization parameter dictionary (PDF 32000-1 Annex F).
        # Populated by :meth:`_detect_linearization` when the **first**
        # indirect object after the header carries a truthy ``/Linearized``
        # entry. Advisory metadata only — the regular xref-walk path is
        # unaffected by linearization (the trailing xref still wins).
        self.linearization_dict: COSDictionary | None = None
        # Raw bytes of the primary hint stream, slurped via the offset+
        # length pair in the linearization dict's ``/H`` entry. Hint
        # streams encode the page-offset / shared-object / thumbnail
        # tables that web-streaming viewers consult to fetch only the
        # bytes they need; pypdfbox does not interpret the hint table
        # body — exposed as raw bytes for downstream tooling.
        self.hint_table_bytes: bytes | None = None

    # ---------- public entry point ----------

    def parse(self) -> COSDocument:
        """Parse the document end-to-end. Returns a populated COSDocument
        whose object pool is ready for lazy resolution."""
        self._document = COSDocument()
        self._cos_parser = COSParser(self._src, document=self._document)
        self._version = self.parse_header()
        self._document.set_version(self._version)
        # Detect linearization (PDF 32000-1 Annex F): the **first**
        # indirect object after the header is the linearization
        # parameter dictionary. Advisory only — the regular xref-walk
        # path below is unaffected (trailing xref still wins).
        self._detect_linearization()
        startxref = self.find_startxref_offset(validate_bounds=not self._lenient)
        startxref = self._recover_xref_offset_if_needed(startxref)
        if not self._xref_section_starts_at(startxref):
            raise PDFParseError(f"startxref offset {startxref} does not point to xref")
        self._cos_parser.set_xref_offset(startxref)
        # Record so the incremental writer can chain its appended xref
        # via /Prev (PRD §6.5 cluster #2).
        self._document.set_start_xref(startxref)
        self.parse_xref_chain(startxref)
        trailer = self._resolver.get_trailer()
        if trailer is not None:
            self._document.set_trailer(trailer)
        self.populate_document()
        self._document.get_document_state().set_parsing(False)
        return self._document

    # ---------- document accessors ----------

    def get_document(self) -> COSDocument | None:
        """Return the parsed ``COSDocument`` or ``None`` if :meth:`parse`
        has not been called yet. Mirrors upstream
        ``PDFParser.getDocument()``."""
        return self._document

    def get_xref_offset(self) -> int:
        """Return the ``startxref`` byte offset recorded during
        :meth:`parse`, or ``-1`` before parsing. Mirrors the
        upstream ``COSParser.getXrefOffset`` surface inherited by
        ``PDFParser`` in PDFBox."""
        if self._cos_parser is None:
            return -1
        return self._cos_parser.get_xref_offset()

    def get_pd_document(self) -> Any:
        """Return a ``PDDocument`` wrapper around the parsed
        ``COSDocument``. Lazily constructed and cached on the parser
        instance so repeated calls return the same wrapper. Mirrors
        upstream ``PDFParser.getPDDocument()``.

        Must be called after :meth:`parse`."""
        if self._pd_document is not None:
            return self._pd_document
        if self._document is None:
            raise PDFParseError(
                "get_pd_document() called before parse(); no document yet"
            )
        # Local import — pdfparser must not depend on pdmodel at import
        # time (PDDocument lives one layer up).
        from pypdfbox.pdmodel.pd_document import PDDocument  # noqa: PLC0415

        self._pd_document = PDDocument(self._document)
        return self._pd_document

    # ---------- trailer / root accessors ----------

    def get_trailer(self) -> COSDictionary | None:
        """Return the consolidated trailer dictionary (the merged view of
        every parsed xref section's trailer fragment) or ``None`` before
        :meth:`parse` has run. Mirrors upstream
        ``COSParser.retrieveTrailer()``'s return surface — pypdfbox keeps
        the trailer permanently on :class:`COSDocument`, this accessor just
        forwards through the ``XrefTrailerResolver`` for parity with code
        that talks to the parser directly."""
        return self._resolver.get_trailer()

    def get_root(self) -> COSDictionary | None:
        """Resolve the trailer's ``/Root`` entry to its dictionary.

        Returns ``None`` when the trailer is absent or ``/Root`` is missing
        / not a dictionary. Mirrors the ``trailer.getCOSDictionary(ROOT)``
        access pattern in upstream ``PDFParser.initialParse``."""
        trailer = self._resolver.get_trailer()
        if trailer is None:
            return None
        root = trailer.get_dictionary_object(COSName.ROOT)  # type: ignore[attr-defined]
        return root if isinstance(root, COSDictionary) else None

    def get_xref_trailer_resolver(self) -> XrefTrailerResolver:
        """Return the parser's ``XrefTrailerResolver``. Diagnostic surface
        — upstream PDFBox exposes the resolver via a protected field
        (``COSParser.xrefTrailerResolver``); pypdfbox surfaces it through
        an explicit accessor so tests / callers can introspect the merged
        xref table after :meth:`parse`."""
        return self._resolver

    # ---------- EOF lookup range (PDFBox-style knob) ----------

    def set_eof_lookup_range(self, byte_count: int) -> None:
        """Adjust how many trailing bytes :meth:`find_startxref_offset`
        scans. Mirrors upstream ``COSParser.setEOFLookupRange(int)``;
        values ``<= 15`` are ignored (matches the upstream guard)."""
        if byte_count > 15:
            self._eof_lookup_range = int(byte_count)

    def get_eof_lookup_range(self) -> int:
        """Return the current EOF-lookup byte count (the window
        :meth:`find_startxref_offset` uses to locate ``startxref``)."""
        return self._eof_lookup_range

    # ---------- lenient mode ----------

    def set_lenient(self, lenient: bool) -> None:
        """Toggle lenient parsing mode. Mirrors upstream
        ``PDFParser.setLenient(boolean)``. The pypdfbox parser is already
        permissive by default — the flag is stored for API parity."""
        self._lenient = bool(lenient)

    def is_lenient(self) -> bool:
        """Return whether lenient parsing is enabled. Mirrors upstream
        ``PDFParser.isLenient()``."""
        return self._lenient

    # ---------- linearization (PDF 32000-1 Annex F) ----------

    def is_linearized(self) -> bool:
        """``True`` when a linearization parameter dictionary was detected
        as the first indirect object after the header. Mirrors the
        conceptual surface PDFBox exposes through
        ``COSDocument.getLinearizedDictionary()`` returning non-null.

        Set during :meth:`parse` (more precisely, by
        :meth:`_detect_linearization`)."""
        return self.linearization_dict is not None

    def get_linearization_dictionary(self) -> COSDictionary | None:
        """Return the parsed linearization parameter dictionary, or
        ``None`` when the document is not linearized."""
        return self.linearization_dict

    def get_hint_table_bytes(self) -> bytes | None:
        """Return the raw bytes of the primary hint stream (offset +
        length taken from the linearization dict's ``/H`` array), or
        ``None`` when the document is not linearized or the hint table
        could not be located. The body is **not** interpreted — hint
        stream parsing (page-offset, shared-object, thumbnail tables)
        is left to higher-level callers."""
        return self.hint_table_bytes

    def _detect_linearization(self) -> None:
        """Parse the first indirect object after the header. If it is a
        dictionary carrying a truthy ``/Linearized`` entry, record it on
        :attr:`linearization_dict` and slurp the primary hint stream's
        bytes into :attr:`hint_table_bytes`. Quiet on every failure path
        — linearization is advisory metadata, never load-blocking.

        Cursor is restored to its post-header position before returning
        so :meth:`find_startxref_offset` (which scans from EOF anyway)
        and the rest of :meth:`parse` are unaffected."""
        saved = self._src.get_position()
        try:
            self._base.skip_whitespace()
            # An indirect-object header reads ``<num> <gen> obj``. Bail
            # out quietly if the first non-whitespace byte isn't a
            # decimal digit (some producers prepend comments — we
            # could call ``skip_comment`` here but per spec the
            # linearization dict, if present, is the very first object).
            peek = self._base.peek_byte()
            if peek == RandomAccessRead.EOF or not (0x30 <= peek <= 0x39):
                return
            try:
                obj_num = self._base.read_int()
                self._base.skip_whitespace()
                gen_num = self._base.read_int()
            except PDFParseError:
                return
            self._base.skip_whitespace()
            try:
                kw = self._base.read_keyword()
            except PDFParseError:
                return
            if kw != b"obj":
                return
            assert self._cos_parser is not None
            try:
                body = self._cos_parser.parse_direct_object()
            except PDFParseError:
                return
            if not isinstance(body, COSDictionary):
                return
            lin = body.get_dictionary_object(COSName.get_pdf_name("Linearized"))
            if not isinstance(lin, (COSInteger, COSFloat)):
                return
            if lin.value == 0:
                return
            # Genuine linearization dict — record it.
            self.linearization_dict = body
            # Slurp the primary hint stream's raw bytes (don't decode the
            # hint-table body; that's a deeper task). /H is an array of
            # 2 ints (primary only) or 4 ints (primary + overflow).
            h_arr = body.get_dictionary_object(COSName.get_pdf_name("H"))
            if isinstance(h_arr, COSArray) and h_arr.size() >= 2:
                h_off = h_arr.get(0)
                h_len = h_arr.get(1)
                if isinstance(h_off, (COSInteger, COSFloat)) and isinstance(
                    h_len, (COSInteger, COSFloat)
                ):
                    offset = int(h_off.value)
                    length = int(h_len.value)
                    file_len = self._src.length()
                    if 0 <= offset < file_len and 0 <= length <= file_len - offset:
                        # Snapshot cursor again — read_into moves it.
                        cursor_snap = self._src.get_position()
                        try:
                            self._src.seek(offset)
                            buf = bytearray(length)
                            n = self._src.read_into(buf)
                            self.hint_table_bytes = bytes(buf[: max(n, 0)])
                        finally:
                            self._src.seek(cursor_snap)
            # Discard the obj_num / gen_num to silence "unused" linters
            # without losing the parse-side validation above.
            del obj_num, gen_num
        finally:
            # Always restore the cursor to where the caller left it.
            self._src.seek(saved)

    # ---------- encryption / id introspection ----------

    def get_encryption_dictionary(self) -> COSDictionary | None:
        """Return the trailer's ``/Encrypt`` dictionary (resolved through
        an indirect reference if necessary) or ``None`` when the document
        is not encrypted. Mirrors PDFBox ``PDFParser.getEncryption()``.

        Must be called after :meth:`parse` so the trailer is populated."""
        trailer = self._resolver.get_trailer()
        if trailer is None:
            return None
        enc = trailer.get_dictionary_object(COSName.ENCRYPT)  # type: ignore[attr-defined]
        return enc if isinstance(enc, COSDictionary) else None

    def get_document_id(self) -> bytes | None:
        """Return the first element of the trailer's ``/ID`` array (the
        permanent file identifier per PDF 32000-1 §14.4) as bytes, or
        ``None`` when no ``/ID`` is present. The standard security handler
        keys file-encryption-key derivation off of this value."""
        trailer = self._resolver.get_trailer()
        if trailer is None:
            return None
        ids = trailer.get_dictionary_object(COSName.get_pdf_name("ID"))
        if not isinstance(ids, COSArray) or ids.size() == 0:
            return None
        first = ids.get(0)
        if isinstance(first, COSString):
            return first.get_bytes()
        return None

    # ---------- early-decryption surface (PDF 1.5+ encrypted xref streams) ----------

    def set_password(self, password: str | bytes | None) -> None:
        """Stage a password so the parser can instantiate a security
        handler the moment the trailer's ``/Encrypt`` becomes available.
        Required for documents whose xref *itself* is an encrypted stream
        — the handler must decipher the body before entries can be parsed.

        Pass ``None`` (the default) to keep the legacy flow where loading
        finishes first and ``PDDocument.decrypt`` walks the pool to attach
        a handler retroactively. Mirrors the ``password`` argument of
        upstream's ``PDFParser`` constructor overloads."""
        self._password = password

    def get_password(self) -> str | bytes | None:
        return self._password

    def get_security_handler(self) -> Any | None:
        """Return the security handler instantiated by the eager-decrypt
        path (see :meth:`set_password`), or ``None`` when no password was
        supplied or the document is not encrypted."""
        return self._security_handler

    def has_encrypted_xref_streams(self) -> bool:
        """``True`` when the parser saw at least one xref-stream object in
        a document that carries an ``/Encrypt`` entry. Set during
        :meth:`parse_xref_chain`; useful for tests and diagnostics."""
        return self._has_encrypted_xref_streams

    def _prepare_security_handler_if_needed(self) -> Any | None:
        """If the trailer carries ``/Encrypt`` and a password has been
        staged via :meth:`set_password`, build (and cache) a
        ``StandardSecurityHandler`` ready to decipher subsequent xref-stream
        bodies / objects. Returns the cached handler on subsequent calls."""
        if self._security_handler is not None:
            return self._security_handler
        if self._password is None:
            return None
        trailer = self._resolver.get_trailer()
        if trailer is None:
            return None
        # The trailer's /Encrypt entry is almost always an indirect ref
        # (``/Encrypt 4 0 R``) that hasn't been loader-attached yet —
        # ``populate_document`` runs after the xref chain is fully walked.
        # Resolve it manually here so the handler can stand up before any
        # downstream xref-stream body is touched.
        enc_dict = self._resolve_dict_entry(trailer, COSName.ENCRYPT)  # type: ignore[attr-defined]
        if not isinstance(enc_dict, COSDictionary):
            return None
        # Local imports — pdfparser must not depend on pdmodel at import
        # time (encryption lives one layer up).
        from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption  # noqa: PLC0415
        from pypdfbox.pdmodel.encryption.standard_security_handler import (  # noqa: PLC0415
            StandardDecryptionMaterial,
            StandardSecurityHandler,
        )

        encryption = PDEncryption(enc_dict)
        document_id = self._resolve_document_id(trailer) or b""
        password_bytes: bytes
        if isinstance(self._password, str):
            password_bytes = self._password.encode("utf-8")
        else:
            password_bytes = bytes(self._password)
        handler = StandardSecurityHandler(encryption)
        handler.prepare_for_decryption(
            encryption,
            document_id,
            StandardDecryptionMaterial(password_bytes),
        )
        self._security_handler = handler
        return handler

    def _resolve_dict_entry(
        self, container: COSDictionary, key: COSName
    ) -> COSBase | None:
        """Return ``container[key]`` resolved through the parser's
        already-known xref entries, even when ``populate_document`` has
        not yet attached loaders. Direct values pass through unchanged.
        Used during the eager-decrypt bootstrap where the trailer is
        available but the object pool is still being assembled."""
        item = container.get_item(key)
        if item is None:
            return None
        if not isinstance(item, COSObject):
            return item
        if item.is_object_loaded():
            return item.get_object()
        # Look up the entry in the resolver and parse it inline. We do
        # NOT register a loader on the COSObject here — populate_document
        # will do that for the whole pool when the chain is complete.
        target_key = COSObjectKey(
            item.get_object_number(), item.get_generation_number()
        )
        xref = self._resolver.get_xref_table()
        entry = xref.get(target_key)
        if entry is None or entry.compressed_index == -1:
            return None
        if entry.type is XrefType.COMPRESSED:
            # Object lives inside an object stream — that decoder runs
            # later; leave the eager bootstrap dormant in that case.
            # ``XrefType.STREAM`` (uncompressed entry from an xref stream)
            # still carries a real byte offset and can be loaded inline,
            # which is exactly the path encrypted PDF 1.5+ documents need:
            # /Encrypt object is referenced by an xref-STREAM entry, and
            # we have to materialise it here so the security handler can
            # be built before any other xref-stream body is decoded.
            return None
        # Snapshot cursor, parse the indirect, restore cursor so the
        # outer xref walker isn't disturbed.
        saved = self._src.get_position()
        try:
            return self._load_indirect_object_at(entry.offset, item)
        finally:
            self._src.seek(saved)

    def _resolve_document_id(self, trailer: COSDictionary) -> bytes | None:
        """``/ID`` companion to :meth:`_resolve_dict_entry`. Returns the
        first element of the ID array as bytes, or ``None``."""
        ids = trailer.get_dictionary_object(COSName.get_pdf_name("ID"))
        if not isinstance(ids, COSArray) or ids.size() == 0:
            return None
        first = ids.get(0)
        if isinstance(first, COSString):
            return first.get_bytes()
        return None

    # ---------- step 1: header ----------

    def parse_header(self) -> float:
        """Validate the ``%PDF-x.y`` magic and return the version as a
        float. Tolerates up to 1024 bytes of leading garbage (some
        producers prepend MIME envelopes / shebangs / etc.)."""
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
            raise PDFParseError(f"malformed %PDF version {version_bytes!r}") from exc

    def parse_pdf_header(self) -> bool:
        """Validate the ``%PDF-x.y`` magic and record the version on the
        underlying :class:`COSDocument` (when one has been instantiated).
        Returns ``True`` on success, ``False`` when no header is found.

        Java-style boolean alias for :meth:`parse_header` — mirrors
        upstream ``COSParser.parsePDFHeader()`` whose contract is "did we
        find a PDF header?"."""
        try:
            version = self.parse_header()
        except PDFParseError:
            return False
        if self._document is not None:
            self._document.set_version(version)
        self._version = version
        return True

    # ---------- step 2: locate startxref ----------

    def find_startxref_offset(self, *, validate_bounds: bool = True) -> int:
        """Return the byte offset given by the ``startxref`` directive
        near the end of the file. Raises ``PDFParseError`` if not found.

        The trailing-byte scan window honours :meth:`get_eof_lookup_range`
        (default :data:`_TAIL_SCAN_BYTES`), matching upstream's
        ``readTrailBytes`` knob. ``validate_bounds=False`` is used by the
        lenient parse path so an invalid declared offset can still be
        corrected by the brute-force xref search."""
        length = self._src.length()
        scan_from = max(0, length - self._eof_lookup_range)
        self._src.seek(scan_from)
        tail = bytearray(length - scan_from)
        n = self._src.read_into(tail)
        tail_bytes = bytes(tail[: n if n > 0 else 0])
        marker = b"startxref"
        idx = tail_bytes.rfind(marker)
        if idx < 0:
            raise PDFParseError("missing 'startxref' directive near EOF")
        # Re-position absolute and skip past the keyword.
        self._src.seek(scan_from + idx + len(marker))
        self._base.skip_whitespace()
        offset = self._base.read_int()
        # Defensive: ensure the offset is plausible.
        if validate_bounds and not 0 <= offset < length:
            raise PDFParseError(f"startxref offset {offset} out of file bounds")
        return offset

    # ---------- step 3: xref chain ----------

    def parse_xref_chain(self, start_offset: int) -> None:
        """Walk xref → trailer → ``/Prev`` until the chain terminates or a
        cycle is detected."""
        offset = start_offset
        while offset >= 0:
            offset = self._recover_xref_offset_if_needed(offset)
            if self._resolver.has_visited(offset):
                # Cycle in /Prev — stop instead of looping.
                break
            self._resolver.begin_section(offset)
            self.parse_xref_section_at(offset)
            trailer = self._resolver.get_current_trailer()
            # The /Prev pointer for the *current* iteration must come from
            # the section we just parsed, not the merged trailer (which is
            # built up over all sections).
            current_prev = -1
            if trailer is not None and trailer.contains_key(COSName.get_pdf_name("Prev")):
                prev_obj = trailer.get_dictionary_object(COSName.get_pdf_name("Prev"))
                if isinstance(prev_obj, COSInteger):
                    current_prev = prev_obj.value
            offset = current_prev

    def _recover_xref_offset_if_needed(self, offset: int) -> int:
        """Return a usable xref offset, recovering in lenient mode when
        ``startxref`` or ``/Prev`` points near but not at the section.

        PDFBox's lenient parser falls back to ``bfSearchForXRef`` when a
        declared xref position is malformed. Keep the correction before
        ``XrefTrailerResolver.begin_section`` so visited-offset tracking
        records the real section start."""
        if self._xref_section_starts_at(offset):
            return offset
        if not self._lenient or self._cos_parser is None:
            return offset
        recovered = self._cos_parser.bf_search_for_xref(offset)
        if recovered >= 0 and self._xref_section_starts_at(recovered):
            return recovered
        return offset

    def _xref_section_starts_at(self, offset: int) -> bool:
        """Lightweight shape check for a traditional xref table or xref
        stream object at ``offset``. Cursor position is preserved."""
        if offset < 0 or offset >= self._src.length():
            return False
        saved = self._src.get_position()
        try:
            self._src.seek(offset)
            self._base.skip_whitespace()
            peek = self._base.peek_byte()
            if peek == 0x78:  # 'x'
                return self._base.read_keyword() == b"xref"
            if not (0x30 <= peek <= 0x39) or self._cos_parser is None:
                return False
            # Xref streams start as indirect-object definitions whose
            # dictionary advertises /Type /XRef.
            self._base.read_int()
            self._base.skip_whitespace()
            self._base.read_int()
            self._base.skip_whitespace()
            if self._base.read_keyword() != b"obj":
                return False
            self._base.skip_whitespace()
            if self._base.peek_byte() != 0x3C:  # '<'
                return False
            body = self._cos_parser.parse_cos_dictionary()
            type_obj = body.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
            return isinstance(type_obj, COSName) and type_obj.name == "XRef"
        except PDFParseError:
            return False
        finally:
            self._src.seek(saved)

    def parse_xref_section_at(self, offset: int) -> None:
        """Parse one xref section + trailer starting at ``offset``."""
        self._src.seek(offset)
        self._base.skip_whitespace()
        # Distinguish traditional ``xref`` keyword from an xref stream
        # (PDF 1.5+: an indirect object whose dict has /Type /XRef).
        peek = self._base.peek_byte()
        if peek == 0x78:  # 'x' — likely the "xref" keyword
            self._parse_traditional_xref_section()
            # Once the trailer has been merged, eagerly stand up the
            # security handler if the caller staged a password — the next
            # iteration of /Prev may land on an xref STREAM, and that
            # body has to be deciphered before its entries decode.
            self._prepare_security_handler_if_needed()
        else:
            # PDF 1.5+ xref-stream (an indirect object whose dict carries
            # /Type /XRef and whose body holds packed xref entries).
            # The handler also wires the early-decryption bootstrap needed
            # before encrypted object bodies are parsed later.
            self._handle_xref_stream_at(offset)

    def _handle_xref_stream_at(self, offset: int) -> None:
        """Parse one xref-stream object (PDF 32000-1 §7.5.8): read its
        dictionary, decode the body via ``COSStream.create_input_stream``
        (so /Filter chains — typically ``/FlateDecode`` with a PNG
        predictor — are unwound), and register one xref entry per packed
        record.

        Also doubles as the early-decryption surface: when the stream
        dictionary carries ``/Encrypt`` (which can only happen in a
        hybrid layout, since the stream itself can't reference the
        document's own /Encrypt), or when the trailer of a previous
        section already had it, the staged password (see
        :meth:`set_password`) is used to attach a security handler to
        the stream before the body is decoded."""
        # Reset cursor to the indirect-object header and parse the
        # ``n g obj`` line + dictionary + ``stream`` body.
        self._src.seek(offset)
        self._base.skip_whitespace()
        self._base.read_int()
        self._base.skip_whitespace()
        self._base.read_int()
        self._base.skip_whitespace()
        kw = self._base.read_keyword()
        if kw != b"obj":
            raise PDFParseError(
                f"expected 'obj' at offset {offset}, got {kw!r}",
                position=self._base.position,
            )
        assert self._cos_parser is not None
        body = self._cos_parser.parse_direct_object()
        if not isinstance(body, COSDictionary):
            raise PDFParseError(
                "xref-stream object body is not a dictionary",
                position=self._base.position,
            )
        type_obj = body.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
        if not (isinstance(type_obj, COSName) and type_obj.name == "XRef"):
            raise PDFParseError(
                "xref-stream dict missing /Type /XRef",
                position=self._base.position,
            )
        # Convert the parsed dict to a stream and read its body using the
        # same machinery the regular indirect-object loader uses.
        stream = self._convert_dict_to_stream(body)
        # The dictionary may reference /Length indirectly; the body-read
        # path through ``_read_stream_body`` already handles that.
        self._base.skip_whitespace()
        peek = self._base.peek_byte()
        if peek != 0x73:
            raise PDFParseError(
                "xref-stream object missing 'stream' keyword",
                position=self._base.position,
            )
        kw2 = self._base.read_keyword()
        if kw2 != b"stream":
            raise PDFParseError(
                f"expected 'stream' in xref-stream object, got {kw2!r}",
                position=self._base.position,
            )
        self._read_stream_body(stream)
        # Per ISO 32000-2 §7.6.2 cross-reference streams "shall not be
        # encrypted". Mark this stream so the COSStream decode path skips
        # the security-handler pass even after the document-level handler
        # walk in ``PDDocument.decrypt`` retroactively wires one onto
        # every other stream — otherwise the same body would be deciphered
        # twice (once now during xref load, once later) and the second
        # pass would garble the entries.
        stream.set_skip_encryption(True)
        # Treat the xref-stream dict as a trailer fragment so /Encrypt /ID
        # /Root /Size are visible to /Prev walking and the early-handler
        # bootstrap. Existing trailer keys from previously-parsed sections
        # still win — the resolver merges newest-first.
        self._resolver.set_trailer(stream)
        # Diagnostic flag for callers / tests.
        if stream.contains_key(COSName.ENCRYPT):  # type: ignore[attr-defined]
            self._has_encrypted_xref_streams = True
        # Decode the body and walk the packed entries — this populates
        # the resolver with byte offsets for every object, including the
        # /Encrypt object itself. Has to run BEFORE the handler bootstrap
        # because ``_prepare_security_handler_if_needed`` resolves
        # ``/Encrypt`` through the resolver to grab its dict.
        self._decode_xref_stream_entries(stream)
        # Now that entries are registered, eagerly stand up the security
        # handler if /Encrypt is in scope and a password was staged. The
        # handler isn't used to decrypt THIS stream (xref streams are
        # exempt — see set_skip_encryption above), but it must exist
        # before subsequent /Prev-chained sections or downstream pool
        # objects are touched.
        if stream.contains_key(COSName.ENCRYPT):  # type: ignore[attr-defined]
            self._prepare_security_handler_if_needed()

    def _decode_xref_stream_entries(self, stream: COSStream) -> None:
        """Decode an xref stream's body and register one xref entry per
        record. PDF 32000-1 §7.5.8.3."""
        # /W [w1 w2 w3] — field widths in bytes. w1=0 means "type defaults
        # to 1 (uncompressed in-use)"; w3=0 means "generation defaults to 0".
        w_obj = stream.get_dictionary_object(COSName.get_pdf_name("W"))
        if not isinstance(w_obj, COSArray) or w_obj.size() < 3:
            raise PDFParseError("xref stream missing or malformed /W")
        widths: list[int] = []
        for i in range(3):
            wi = w_obj.get(i)
            if not isinstance(wi, COSInteger):
                raise PDFParseError(f"xref stream /W[{i}] is not an integer")
            widths.append(wi.value)
        w1, w2, w3 = widths
        if any(width < 0 for width in widths):
            raise PDFParseError("xref stream /W contains a negative width")
        # /Index [first1 count1 first2 count2 ...]; default = [0 /Size].
        index_pairs: list[tuple[int, int]] = []
        idx_obj = stream.get_dictionary_object(COSName.get_pdf_name("Index"))
        if isinstance(idx_obj, COSArray):
            if idx_obj.size() % 2 != 0:
                raise PDFParseError("xref stream /Index has odd length")
            for i in range(0, idx_obj.size(), 2):
                first_obj = idx_obj.get(i)
                count_obj = idx_obj.get(i + 1)
                if not isinstance(first_obj, COSInteger) or not isinstance(
                    count_obj, COSInteger
                ):
                    raise PDFParseError("xref stream /Index entries must be integers")
                first = first_obj.value
                count = count_obj.value
                _validate_xref_index_pair(first, count)
                index_pairs.append((first, count))
        else:
            size_obj = stream.get_dictionary_object(COSName.SIZE)  # type: ignore[attr-defined]
            if not isinstance(size_obj, COSInteger):
                raise PDFParseError("xref stream missing /Size and /Index")
            _validate_xref_index_pair(0, size_obj.value)
            index_pairs.append((0, size_obj.value))
        # Decode the body through any /Filter chain (and the security
        # handler, when one is attached).
        with stream.create_input_stream() as src:
            body = src.read()
        record_size = w1 + w2 + w3
        if record_size <= 0:
            raise PDFParseError("xref stream /W field widths sum to zero")
        # PDFBOX-6037: cap the entry width at 20 bytes — anything wider
        # is malformed and would tend to mask attacker-supplied size
        # explosions. Mirrors upstream
        # ``PDFXrefStreamParser.initParserValues``.
        if record_size > 20:
            raise PDFParseError(
                f"xref stream /W defines an entry wider than 20 bytes: {widths!r}"
            )
        cursor = 0
        for first_obj_num, object_count in index_pairs:
            for object_index in range(object_count):
                if cursor + record_size > len(body):
                    raise PDFParseError(
                        "xref stream body truncated relative to /Index"
                    )
                record = body[cursor : cursor + record_size]
                cursor += record_size
                # Slice each field; honour the spec's defaults when w_i==0.
                field1 = (
                    1 if w1 == 0 else int.from_bytes(record[0:w1], "big")
                )
                field2 = int.from_bytes(record[w1 : w1 + w2], "big")
                field3 = (
                    0
                    if w3 == 0
                    else int.from_bytes(record[w1 + w2 : w1 + w2 + w3], "big")
                )
                obj_num = first_obj_num + object_index
                if field1 == 0:
                    # Free entry — record it but flag with compressed_index=-1
                    # so populate_document() skips it (matches the traditional
                    # 'f' flag path).
                    self._resolver.set_entry(
                        COSObjectKey(obj_num, field3),
                        XrefEntry(
                            type=XrefType.STREAM,
                            offset=field2,
                            compressed_index=-1,
                        ),
                    )
                elif field1 == 1:
                    # Uncompressed: field2 = byte offset, field3 = generation.
                    self._resolver.set_entry(
                        COSObjectKey(obj_num, field3),
                        XrefEntry(type=XrefType.STREAM, offset=field2),
                    )
                elif field1 == 2:
                    # Compressed: field2 = ObjStm obj number, field3 = index
                    # within stream. Generation is always 0 per spec.
                    self._resolver.set_entry(
                        COSObjectKey(obj_num, 0),
                        XrefEntry(
                            type=XrefType.COMPRESSED,
                            offset=field2,
                            compressed_index=field3,
                        ),
                    )
                else:
                    # PDF 32000-1 §7.5.8.3: "any other value of the type
                    # field shall be interpreted as a reference to the null
                    # object." Treat as a free slot.
                    self._resolver.set_entry(
                        COSObjectKey(obj_num, 0),
                        XrefEntry(
                            type=XrefType.STREAM,
                            offset=0,
                            compressed_index=-1,
                        ),
                    )

    def _parse_traditional_xref_section(self) -> None:
        """Parse ``xref <subsections> trailer << ... >>``."""
        kw = self._base.read_keyword()
        if kw != b"xref":
            raise PDFParseError(f"expected 'xref', got {kw!r}", position=self._base.position)
        # Some producers omit the EOL after 'xref' but the spec requires it
        # and PDFBox tolerates either way; skip whitespace defensively.
        self._base.skip_whitespace()
        # Loop subsections until we hit the 'trailer' keyword.
        while True:
            peek = self._base.peek_byte()
            if peek == 0x74:  # 't' — start of 'trailer'
                break
            if peek == RandomAccessRead.EOF:
                raise PDFParseError("unexpected EOF inside xref section")
            first_obj = self._base.read_int()
            self._base.skip_whitespace()
            count = self._base.read_int()
            self._base.skip_whitespace()
            for i in range(count):
                self._read_xref_entry(first_obj + i)
        kw = self._base.read_keyword()
        if kw != b"trailer":
            raise PDFParseError(
                f"expected 'trailer', got {kw!r}", position=self._base.position
            )
        self._base.skip_whitespace()
        assert self._cos_parser is not None  # established by parse()
        trailer = self._cos_parser.parse_cos_dictionary()
        self._resolver.set_trailer(trailer)

    def _read_xref_entry(self, object_number: int) -> None:
        """Read one traditional xref entry line."""
        line = self._base.read_until_eol()
        self._base.skip_eol()
        offset, generation, flag = _parse_xref_entry_line(line)
        if flag == "n":
            self._resolver.set_entry(
                COSObjectKey(object_number, generation),
                XrefEntry(type=XrefType.TABLE, offset=offset),
            )
        elif flag == "f":
            # Free entry — record it so a later /Prev section's "n" can be
            # detected as superseding it. Storing the offset (which is
            # actually "next free object number") is mostly informational
            # at this stage; the writer will care later.
            self._resolver.set_entry(
                COSObjectKey(object_number, generation),
                XrefEntry(type=XrefType.TABLE, offset=offset, compressed_index=-1),
            )
        else:
            raise PDFParseError(f"unknown xref entry flag {flag!r}")

    # ---------- step 4: populate document ----------

    def populate_document(self) -> None:
        """Walk the consolidated xref and attach a loader to every
        in-use COSObject in the document pool."""
        assert self._document is not None
        xref = self._resolver.get_xref_table()
        for key, entry in xref.items():
            if entry.compressed_index == -1:
                # Free entry — skip; PDFBox does not register a placeholder
                # for free slots in the regular object pool.
                continue
            cos_obj = self._document.get_object_from_pool(key)
            cos_obj.set_loader(self._make_loader(entry))

    def _make_loader(self, entry: XrefEntry):  # type: ignore[no-untyped-def]
        """Build a lazy loader callback for a single xref entry."""
        if entry.type is XrefType.COMPRESSED:
            objstm_obj_num = entry.offset
            inner_index = entry.compressed_index

            def _compressed_loader(obj: COSObject) -> COSBase | None:
                return self._load_compressed_object(
                    objstm_obj_num, inner_index, obj
                )
            return _compressed_loader

        offset = entry.offset

        def _loader(obj: COSObject) -> COSBase | None:
            return self._load_indirect_object_at(offset, obj)

        return _loader

    def _load_compressed_object(
        self, objstm_obj_num: int, inner_index: int, obj: COSObject
    ) -> COSBase | None:
        """Resolve an object stored inside an object stream (PDF 32000-1
        §7.5.7). The owning ``ObjStm`` is itself an indirect object whose
        body, after /Filter is applied, is a header of ``/N`` ``(obj_num
        byte_offset)`` pairs followed by ``/N`` packed direct objects
        starting at ``/First``.

        ``inner_index`` is the position of the requested object inside the
        ObjStm — *not* the requested object's own number. ``obj`` is the
        ``COSObject`` placeholder whose ``_resolved`` field the caller
        will populate from our return value."""
        assert self._document is not None
        objstm = self._document.get_object_from_pool(
            COSObjectKey(objstm_obj_num, 0)
        )
        objstm_body = objstm.get_object()
        if not isinstance(objstm_body, COSStream):
            raise PDFParseError(
                f"object stream {objstm_obj_num} is not a stream"
            )
        decoded, pairs, first = _read_object_stream_offsets(
            objstm_body, objstm_obj_num
        )
        object_count = len(pairs)
        if not 0 <= inner_index < object_count:
            raise PDFParseError(
                f"compressed-object index {inner_index} out of range "
                f"[0, {object_count}) for ObjStm {objstm_obj_num}"
            )
        target_obj_num, target_byte_offset = pairs[inner_index]
        # Optional sanity check: the obj_num stored in the header should
        # match the placeholder's own number (PDFBox warns when they
        # disagree but trusts the xref entry; we follow).
        if target_obj_num != obj.object_number:
            # Tolerate the discrepancy — match upstream's permissive
            # behaviour for malformed object streams.
            pass
        # Parse the requested direct object from the decoded payload.
        body_view = RandomAccessReadBuffer(decoded[first + target_byte_offset:])
        body_parser = COSParser(body_view, document=self._document)
        try:
            return body_parser.parse_direct_object()
        finally:
            body_view.close()

    def _load_indirect_object_at(self, offset: int, obj: COSObject) -> COSBase | None:
        """Seek to ``offset`` and parse the indirect-object definition.
        For a stream object, also reads the body."""
        self._src.seek(offset)
        self._base.skip_whitespace()
        # n m obj
        on = self._base.read_int()
        self._base.skip_whitespace()
        gn = self._base.read_int()
        self._base.skip_whitespace()
        kw = self._base.read_keyword()
        if kw != b"obj":
            raise PDFParseError(
                f"expected 'obj' at offset {offset}, got {kw!r}",
                position=self._base.position,
            )
        if on != obj.object_number or gn != obj.generation_number:
            # Tolerable: PDFBox warns and uses what it found. We follow.
            pass
        assert self._cos_parser is not None
        body = self._cos_parser.parse_direct_object()
        self._base.skip_whitespace()
        # Distinguish 'endobj' from 'stream'.
        peek = self._base.peek_byte()
        if peek == 0x73:  # 's' — possibly 'stream'
            kw2 = self._base.read_keyword()
            if kw2 == b"stream":
                if not isinstance(body, COSDictionary):
                    raise PDFParseError(
                        "stream object body is not a dictionary",
                        position=self._base.position,
                    )
                stream = self._convert_dict_to_stream(body)
                self._read_stream_body(stream)
                # After endstream comes endobj.
                self._base.skip_whitespace()
                end_kw = self._base.read_keyword()
                if end_kw != b"endobj":
                    raise PDFParseError(
                        f"expected 'endobj' after stream, got {end_kw!r}"
                    )
                return stream
            raise PDFParseError(
                f"expected 'endobj' after object body, got {kw2!r}",
                position=self._base.position,
            )
        end_kw = self._base.read_keyword()
        if end_kw != b"endobj":
            raise PDFParseError(
                f"expected 'endobj' after object body, got {end_kw!r}",
                position=self._base.position,
            )
        return body

    def _convert_dict_to_stream(self, src: COSDictionary) -> COSStream:
        """Build a fresh ``COSStream`` from a parsed dictionary, copying
        every entry. The original dict is no longer referenced."""
        assert self._document is not None
        stream = COSStream(scratch_file=self._document.scratch_file)
        for k, v in src.entry_set():
            stream.set_item(k, v)
        return stream

    def _read_stream_body(self, stream: COSStream) -> None:
        """Per ISO 32000-1 §7.3.8.1: ``stream`` keyword is followed by EOL
        (CRLF or LF — bare CR is non-conformant). Then exactly /Length
        bytes. Then ``endstream`` (typically preceded by EOL)."""
        self._consume_eol_after_stream_keyword()
        # /Length may be an indirect reference whose resolution recurses
        # into ``_load_indirect_object_at`` and moves the shared cursor.
        # Snapshot here, resolve, then re-seek before reading the body.
        body_start = self._src.get_position()
        try:
            length = self._resolve_stream_length(stream)
        except PDFParseError as exc:
            if not self._lenient or "missing or malformed /Length" not in str(exc):
                raise
            self._src.seek(body_start)
            stream.set_raw_data(self._read_until_endstream())
            return
        self._src.seek(body_start)
        body = bytearray(length)
        n = self._src.read_into(body)
        if n != length:
            raise PDFParseError(
                f"stream body truncated: expected {length} bytes, got {n}",
                position=self._src.get_position(),
            )
        stream.set_raw_data(bytes(body))
        # Trailing EOL is conventional but optional; skip it then verify
        # 'endstream' is next.
        self._base.skip_whitespace()
        kw = self._base.read_keyword()
        if kw != b"endstream":
            raise PDFParseError(
                f"expected 'endstream', got {kw!r}", position=self._base.position
            )

    def _read_until_endstream(self) -> bytes:
        """Lenient stream recovery for missing or malformed ``/Length``.

        Reads from the current source position until the next ``endstream``
        marker, strips the final stream line break using
        :class:`EndstreamFilterStream`, and leaves the cursor immediately
        after the consumed marker.
        """
        start = self._src.get_position()
        remaining = max(0, self._src.length() - start)
        buf = bytearray(remaining)
        n = self._src.read_into(buf)
        if n == RandomAccessRead.EOF:
            raise PDFParseError("expected 'endstream'", position=start)
        if n < remaining:
            del buf[n:]

        marker = b"endstream"
        marker_at = bytes(buf).find(marker)
        if marker_at < 0:
            raise PDFParseError("expected 'endstream'", position=self._src.get_position())

        body = bytes(buf[:marker_at])
        filtered = EndstreamFilterStream()
        filtered.filter(body, 0, len(body))
        length = filtered.calculate_length()
        self._src.seek(start + marker_at + len(marker))
        return body[:length]

    def _consume_eol_after_stream_keyword(self) -> None:
        """Per spec: a single CRLF or LF after ``stream``. Tolerate a CR
        immediately followed by something other than LF (PDFBox quirk —
        some producers emit just CR)."""
        b = self._src.read()
        if b == 0x0D:  # CR
            if self._src.peek() == 0x0A:
                self._src.read()  # consume LF too
            return
        if b == 0x0A:  # LF
            return
        # No EOL after 'stream' — extremely non-conformant; rewind so the
        # body read sees the byte.
        if b != RandomAccessRead.EOF:
            self._src.rewind(1)

    def _resolve_stream_length(self, stream: COSStream) -> int:
        """Read /Length from the stream dictionary. May be an indirect ref;
        we resolve it through the COSObject loader."""
        length_obj = stream.get_dictionary_object(COSName.LENGTH)  # type: ignore[attr-defined]
        if isinstance(length_obj, COSInteger):
            length = length_obj.value
            if length < 0:
                raise PDFParseError(f"stream /Length is negative: {length}")
            return length
        raise PDFParseError("stream missing or malformed /Length")
