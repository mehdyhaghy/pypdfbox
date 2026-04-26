from __future__ import annotations

from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
    COSStream,
    COSString,
)
from pypdfbox.io import RandomAccessRead

from .base_parser import BaseParser
from .cos_parser import COSParser
from .parse_error import PDFParseError
from .xref_trailer_resolver import XrefEntry, XrefTrailerResolver, XrefType

# How many trailing bytes to scan for ``startxref`` / ``%%EOF``.
_TAIL_SCAN_BYTES: int = 4096


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
         object (traditional ``xref`` tables only — xref streams and
         object streams land in cluster #4).
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

    # ---------- public entry point ----------

    def parse(self) -> COSDocument:
        """Parse the document end-to-end. Returns a populated COSDocument
        whose object pool is ready for lazy resolution."""
        self._document = COSDocument()
        self._cos_parser = COSParser(self._src, document=self._document)
        self._version = self.parse_header()
        self._document.set_version(self._version)
        startxref = self.find_startxref_offset()
        # Record so the incremental writer can chain its appended xref
        # via /Prev (PRD §6.5 cluster #2).
        self._document.set_start_xref(startxref)
        self.parse_xref_chain(startxref)
        trailer = self._resolver.get_trailer()
        if trailer is not None:
            self._document.set_trailer(trailer)
        self.populate_document()
        return self._document

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
        if entry.type is not XrefType.TABLE:
            # Compressed / xref-stream-derived entries need cluster #4 to
            # decode — leave the eager bootstrap dormant in that case.
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

    # ---------- step 2: locate startxref ----------

    def find_startxref_offset(self) -> int:
        """Return the byte offset given by the ``startxref`` directive
        near the end of the file. Raises ``PDFParseError`` if not found."""
        length = self._src.length()
        scan_from = max(0, length - _TAIL_SCAN_BYTES)
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
        if not 0 <= offset < length:
            raise PDFParseError(f"startxref offset {offset} out of file bounds")
        return offset

    # ---------- step 3: xref chain ----------

    def parse_xref_chain(self, start_offset: int) -> None:
        """Walk xref → trailer → ``/Prev`` until the chain terminates or a
        cycle is detected."""
        offset = start_offset
        while offset >= 0:
            if self._resolver.has_visited(offset):
                # Cycle in /Prev — stop instead of looping.
                break
            self._resolver.begin_section(offset)
            self.parse_xref_section_at(offset)
            trailer = self._resolver.get_trailer()
            # The /Prev pointer for the *current* iteration must come from
            # the section we just parsed, not the merged trailer (which is
            # built up over all sections).
            current_prev = -1
            if trailer is not None and trailer.contains_key(COSName.get_pdf_name("Prev")):
                prev_obj = trailer.get_dictionary_object(COSName.get_pdf_name("Prev"))
                if isinstance(prev_obj, COSInteger):
                    current_prev = prev_obj.value
            offset = current_prev

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
            #
            # The full xref-stream entry decoder still belongs to parser
            # cluster #4. What lives here is the *encryption integration*:
            # we peek at the dictionary to detect ``/Type /XRef`` and, if
            # the document is encrypted and a password has been staged,
            # build the security handler so the xref-stream body can be
            # deciphered before entries are parsed.
            self._handle_xref_stream_at(offset)
            raise NotImplementedError(
                "xref-stream parsing lives in parser cluster #4"
            )

    def _handle_xref_stream_at(self, offset: int) -> None:
        """Pre-flight an xref-stream object: surface diagnostic state and,
        when a password has been staged, attach the security handler so a
        future cluster-#4 entry decoder can decipher the body.

        Does NOT decode entries — that work is parser cluster #4. Always
        returns; never raises (the outer caller raises NotImplementedError
        until the entry decoder lands)."""
        # Reset cursor to the indirect-object header so a partial dict
        # parse can cheaply read the stream's dictionary without disturbing
        # the eventual entry decoder's view.
        self._src.seek(offset)
        self._base.skip_whitespace()
        try:
            on = self._base.read_int()
            self._base.skip_whitespace()
            gn = self._base.read_int()
            self._base.skip_whitespace()
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
        type_obj = body.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
        if not (isinstance(type_obj, COSName) and type_obj.name == "XRef"):
            return
        # Treat the xref-stream dict as a trailer fragment so /Encrypt /ID
        # /Root /Size are visible to the early-handler bootstrap. Existing
        # trailer keys from previously-parsed sections still win — the
        # resolver merges newest-first, and we install this fragment into
        # the *current* section.
        self._resolver.set_trailer(body)
        # Track that we crossed at least one encrypted xref-stream so
        # ``has_encrypted_xref_streams`` reflects reality.
        if body.contains_key(COSName.ENCRYPT):  # type: ignore[attr-defined]
            self._has_encrypted_xref_streams = True
            self._prepare_security_handler_if_needed()

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
        """Read one 20-byte xref entry: ``oooooooooo ggggg n\\r\\n`` (or ``f``)."""
        raw = bytearray(20)
        n = self._src.read_into(raw)
        if n < 20:
            raise PDFParseError("truncated xref entry", position=self._src.get_position())
        line = bytes(raw)
        try:
            offset = int(line[0:10].decode("ascii"))
            generation = int(line[11:16].decode("ascii"))
            flag = chr(line[17])
        except (ValueError, IndexError) as exc:
            raise PDFParseError(f"malformed xref entry {line!r}") from exc
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
            def _compressed_loader(_obj: COSObject) -> COSBase | None:
                raise NotImplementedError(
                    "compressed-object-stream loading lives in parser cluster #4"
                )
            return _compressed_loader

        offset = entry.offset

        def _loader(obj: COSObject) -> COSBase | None:
            return self._load_indirect_object_at(offset, obj)

        return _loader

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
        length = self._resolve_stream_length(stream)
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
            return length_obj.value
        raise PDFParseError("stream missing or malformed /Length")
