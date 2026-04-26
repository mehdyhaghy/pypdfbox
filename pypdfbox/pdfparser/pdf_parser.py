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
from pypdfbox.io import RandomAccessRead, RandomAccessReadBuffer

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
        # /Index [first1 count1 first2 count2 ...]; default = [0 /Size].
        index_pairs: list[tuple[int, int]] = []
        idx_obj = stream.get_dictionary_object(COSName.get_pdf_name("Index"))
        if isinstance(idx_obj, COSArray):
            if idx_obj.size() % 2 != 0:
                raise PDFParseError("xref stream /Index has odd length")
            for i in range(0, idx_obj.size(), 2):
                first = idx_obj.get(i)
                count = idx_obj.get(i + 1)
                if not isinstance(first, COSInteger) or not isinstance(count, COSInteger):
                    raise PDFParseError("xref stream /Index entries must be integers")
                index_pairs.append((first.value, count.value))
        else:
            size_obj = stream.get_dictionary_object(COSName.SIZE)  # type: ignore[attr-defined]
            if not isinstance(size_obj, COSInteger):
                raise PDFParseError("xref stream missing /Size and /Index")
            index_pairs.append((0, size_obj.value))
        # Decode the body through any /Filter chain (and the security
        # handler, when one is attached).
        with stream.create_input_stream() as src:
            body = src.read()
        record_size = w1 + w2 + w3
        if record_size <= 0:
            raise PDFParseError("xref stream /W field widths sum to zero")
        cursor = 0
        for first, count in index_pairs:
            for i in range(count):
                if cursor + record_size > len(body):
                    raise PDFParseError(
                        "xref stream body truncated relative to /Index"
                    )
                record = body[cursor : cursor + record_size]
                cursor += record_size
                # Slice each field; honour the spec's defaults when w_i==0.
                if w1 == 0:
                    field1 = 1  # default = uncompressed in-use
                else:
                    field1 = int.from_bytes(record[0:w1], "big")
                field2 = int.from_bytes(record[w1 : w1 + w2], "big")
                if w3 == 0:
                    field3 = 0  # default generation
                else:
                    field3 = int.from_bytes(record[w1 + w2 : w1 + w2 + w3], "big")
                obj_num = first + i
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
        n_obj = objstm_body.get_dictionary_object(COSName.get_pdf_name("N"))
        first_obj = objstm_body.get_dictionary_object(
            COSName.get_pdf_name("First")
        )
        if not isinstance(n_obj, COSInteger) or not isinstance(first_obj, COSInteger):
            raise PDFParseError(
                f"object stream {objstm_obj_num} missing /N or /First"
            )
        n = n_obj.value
        first = first_obj.value
        if not 0 <= inner_index < n:
            raise PDFParseError(
                f"compressed-object index {inner_index} out of range "
                f"[0, {n}) for ObjStm {objstm_obj_num}"
            )
        with objstm_body.create_input_stream() as src:
            decoded = src.read()
        # The header is N pairs of "<obj_num> <byte_offset>", whitespace-
        # separated. Parse all of them so we can locate the requested entry
        # at ``inner_index``.
        header_view = RandomAccessReadBuffer(decoded[:first])
        header_parser = BaseParser(header_view)
        pairs: list[tuple[int, int]] = []
        for _ in range(n):
            header_parser.skip_whitespace()
            stored_obj_num = header_parser.read_int()
            header_parser.skip_whitespace()
            byte_offset = header_parser.read_int()
            pairs.append((stored_obj_num, byte_offset))
        header_view.close()
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
