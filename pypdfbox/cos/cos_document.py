from __future__ import annotations

from typing import Any

from pypdfbox.io import RandomAccessRead, ScratchFile

from .cos_array import COSArray
from .cos_base import COSBase
from .cos_dictionary import COSDictionary
from .cos_document_state import COSDocumentState
from .cos_name import COSName
from .cos_object import COSObject
from .cos_object_key import COSObjectKey
from .i_cos_visitor import ICOSVisitor
from .pd_linearization_dictionary import PDLinearizationDictionary

DEFAULT_VERSION: float = 1.4


class COSDocument(COSBase):
    """
    Root container for a parsed (or about-to-be-written) PDF.

    Owns:
      - the object pool (``COSObjectKey → COSObject``) populated by
        the parser as it walks the xref;
      - the document trailer dictionary (with ``/Root``, ``/Info``,
        ``/Encrypt``, ``/ID``, ``/Size``);
      - the scratch file used by every ``COSStream`` in the graph
        (single shared instance — closing the document closes it).

    Versioning, the catalog accessor, and the document-ID helpers
    mirror PDFBox.
    """

    def __init__(
        self,
        scratch_file: ScratchFile | None = None,
        source: RandomAccessRead | None = None,
    ) -> None:
        super().__init__()
        if scratch_file is None:
            self._scratch_file = ScratchFile()
            self._owns_scratch = True
        else:
            self._scratch_file = scratch_file
            self._owns_scratch = False
        # Optional owned input source. The Loader sets this when it created
        # the RandomAccessRead on the caller's behalf so close() can release
        # it; callers that hand in their own source leave this None.
        self._source = source
        self._objects: dict[COSObjectKey, COSObject] = {}
        self._trailer: COSDictionary | None = None
        self._version: float = DEFAULT_VERSION
        self._is_xref_stream: bool = False
        # Byte offset of the most recent xref section the parser found at the
        # tail of the source — used by the incremental writer to set /Prev on
        # the appended xref. ``0`` means "unknown / new document".
        self._start_xref: int = 0
        self._linearized_dict: PDLinearizationDictionary | None = None
        self._linearized_resolved: bool = False
        self._closed: bool = False
        # Encryption-state flag: ``True`` once the parser has applied the
        # security handler to every encrypted stream/string in the pool.
        # Mirrors PDFBox's ``isDecrypted`` boolean. The writer consults this
        # to avoid double-encrypting on save (it must produce ciphertext
        # again from the now-plaintext object graph).
        self._is_decrypted: bool = False
        # Hybrid-xref marker: ``True`` for documents that ship BOTH a plain
        # cross-reference table AND a cross-reference stream (PDF 1.5+
        # backward-compat trick). Mirrors PDFBox's ``hasHybridXRef`` flag.
        self._has_hybrid_xref: bool = False
        # Highest object number seen by the parser — used by the writer when
        # allocating new indirect objects so it doesn't collide with existing
        # ones. ``0`` means "no objects seen yet".
        self._highest_xref_object_number: int = 0
        # When True (the default), ``__del__`` logs a warning if the document
        # was never explicitly closed; mirrors PDFBox's ``warnMissingClose``.
        self._warn_missing_close: bool = True
        # Sparse byte-offset map populated by the parser as it walks the xref.
        # Mirrors PDFBox's ``Map<COSObjectKey, Long> xrefTable``. ``None`` for
        # free entries; positive integers are absolute file offsets; negative
        # integers encode object-stream membership (``-objstm_object_number``)
        # following the PDFBox convention.
        self._xref_table: dict[COSObjectKey, int] = {}
        # Lifecycle state object — initial state is "parsing". The parser
        # flips it to "accepting updates" once xref consumption is complete.
        # Mirrors upstream ``COSDocumentState documentState``.
        self._document_state: COSDocumentState = COSDocumentState()

    # ---------- object pool ----------

    @property
    def scratch_file(self) -> ScratchFile:
        return self._scratch_file

    def get_object_from_pool(self, key: COSObjectKey) -> COSObject:
        """Return the existing ``COSObject`` for ``key``, creating an
        unresolved placeholder if none exists yet. Used by the parser
        when forward references are encountered. Mirrors upstream
        ``getObjectFromPool(COSObjectKey)`` (Java line 511)."""
        existing = self._objects.get(key)
        if existing is None:
            existing = COSObject(key.object_number, key.generation_number)
            self._objects[key] = existing
            existing.get_update_state().set_origin_document_state(
                self._document_state,
                dereferencing=True,
            )
        return existing

    def get_object(self, key: COSObjectKey) -> COSObject | None:
        """Return the ``COSObject`` registered for ``key`` or ``None`` if no
        such object has been seen by the parser yet. Companion to
        :meth:`get_object_from_pool` — does NOT auto-create a placeholder."""
        return self._objects.get(key)

    def has_object(self, key: COSObjectKey) -> bool:
        return key in self._objects

    def get_objects(self) -> list[COSObject]:
        """All known indirect objects in insertion order."""
        return list(self._objects.values())

    def get_object_keys(self) -> list[COSObjectKey]:
        return list(self._objects.keys())

    def get_key(self, base_object: COSBase) -> COSObjectKey | None:
        """Return the object-pool key for ``base_object``, or ``None``.

        Mirrors PDFBox ``getKey(COSBase)``: this is a linear scan over the
        pool and compares object identity, not value equality. Callers use
        it when they already hold a resolved COS object and need its
        indirect-reference key for lifecycle/update bookkeeping.
        """
        for key, cos_obj in self._objects.items():
            if cos_obj is base_object or cos_obj.get_object() is base_object:
                return key
        return None

    def remove_object(self, key: COSObjectKey) -> COSObject | None:
        return self._objects.pop(key, None)

    def add_xref_table(self, table: dict[COSObjectKey | None, int]) -> None:
        """Bulk-register xref entries — mirrors PDFBox's ``addXRefTable``
        (Java line 527).

        Entries with a ``None`` key (PDFBOX-6132 — corrupt xref entry) are
        ignored; offsets are stored in ``_xref_table`` for later retrieval via
        :meth:`get_xref_table`."""
        for key, offset in table.items():
            if key is None:
                continue
            self.get_object_from_pool(key)
            self._xref_table[key] = offset

    def add_x_ref_table(self, table: dict[COSObjectKey | None, int]) -> None:
        """Alias for :meth:`add_xref_table` matching the parity-audit's
        token-split spelling of ``XRef``."""
        self.add_xref_table(table)

    def get_xref_table(self) -> dict[COSObjectKey, int]:
        """Sparse object-key → byte-offset map populated by the parser.
        Mirrors PDFBox's ``getXrefTable()`` (Java line 537). Positive offsets
        are absolute file positions; negative values encode object-stream
        membership (``-objstm_object_number`` per PDFBox convention)."""
        return self._xref_table

    def get_objects_by_type(
        self,
        type_name: COSName | str,
        type_alt: COSName | str | None = None,
    ) -> list[COSObject]:
        """Return every resolved object whose dictionary's ``/Type`` equals
        ``type_name`` (or, when ``type_alt`` is given, either of the two
        names). Matches PDFBox semantics — both the single-arg and the
        two-arg overloads of ``getObjectsByType`` (Java lines 242, 255).
        The two-arg form is used upstream where a /Type entry has both a
        long and an abbreviated spelling (e.g. ``/CIDFontType0`` vs
        ``/Font``)."""
        target = type_name if isinstance(type_name, COSName) else COSName.get_pdf_name(type_name)
        target_alt: COSName | None
        if type_alt is None:
            target_alt = None
        else:
            target_alt = (
                type_alt if isinstance(type_alt, COSName) else COSName.get_pdf_name(type_alt)
            )
        out: list[COSObject] = []
        for cos_obj in self._objects.values():
            resolved = cos_obj.get_object()
            if isinstance(resolved, COSDictionary):
                t = resolved.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
                if isinstance(t, COSName) and (
                    t == target or (target_alt is not None and t == target_alt)
                ):
                    out.append(cos_obj)
        return out

    def get_linearized_dictionary(self) -> PDLinearizationDictionary | None:
        """Return the linearization parameter dictionary (PDF 32000-1 Annex F)
        as a typed wrapper, or ``None`` if the document is not linearized.

        Mirrors upstream ``getLinearizedDictionary()`` (Java line 207): walks
        the xref-table entries with a positive offset in ascending order and
        returns the first resolved dictionary tagged with a ``/Linearized``
        marker. Falls back to insertion order over the object pool when the
        xref table is empty (e.g. for in-memory-built documents).

        **Divergence from upstream:** upstream's check is bare key presence
        (``getItem(COSName.LINEARIZED) != null``); we require a non-zero
        numeric value because real-world linearization params always carry
        ``/Linearized 1`` and a key with a zero value would shadow legitimate
        linearization params on the same object.

        The result is cached — repeated calls do not re-scan."""
        if self._linearized_resolved:
            return self._linearized_dict
        # Match upstream: ascending file-offset order over xref entries with
        # positive offset (negative offsets encode objstm membership, zero is
        # a free entry).
        ordered_keys = sorted(
            (k for k, off in self._xref_table.items() if off > 0),
            key=lambda k: self._xref_table[k],
        )
        if not ordered_keys:
            # Fallback for documents built in memory with no xref table —
            # walk the pool in insertion order.
            ordered_keys = list(self._objects.keys())
        for key in ordered_keys:
            cos_obj = self._objects.get(key)
            if cos_obj is None:
                continue
            resolved = cos_obj.get_object()
            if not isinstance(resolved, COSDictionary):
                continue
            wrapper = PDLinearizationDictionary(resolved)
            if wrapper.is_linearized():
                self._linearized_dict = wrapper
                break
        self._linearized_resolved = True
        return self._linearized_dict

    # ---------- trailer / catalog / id ----------

    def get_trailer(self) -> COSDictionary | None:
        return self._trailer

    def set_trailer(self, trailer: COSDictionary | None) -> None:
        self._trailer = trailer
        if trailer is None:
            return
        trailer.get_update_state().set_origin_document_state(self._document_state)

    def get_catalog(self) -> COSDictionary | None:
        """Resolve ``trailer/Root`` to its dictionary, or ``None``.

        Convenience accessor — upstream callers fetch ``/Root`` off the
        trailer manually; we expose it here to keep the most common
        document-graph traversal one method away."""
        if self._trailer is None:
            return None
        catalog = self._trailer.get_dictionary_object(COSName.ROOT)  # type: ignore[attr-defined]
        return catalog if isinstance(catalog, COSDictionary) else None

    def get_document_id(self) -> COSArray | None:
        """Return ``trailer/ID`` as a typed ``COSArray`` or ``None`` if the
        trailer is missing / has no ``/ID`` entry / the entry is not an
        array. Mirrors upstream ``getDocumentID()`` (Java line 367)."""
        if self._trailer is None:
            return None
        return self._trailer.get_cos_array(COSName.ID)  # type: ignore[attr-defined]

    def set_document_id(self, ids: COSArray) -> None:
        """Write ``trailer/ID``. The trailer is auto-created when absent —
        mirrors PDFBox's ``setDocumentID`` (Java line 380) while sparing
        callers from seeding a trailer first when building a document from
        scratch."""
        if self._trailer is None:
            self.set_trailer(COSDictionary())
        self._trailer.set_item(COSName.ID, ids)  # type: ignore[attr-defined]

    def is_encrypted(self) -> bool:
        """Mirrors upstream ``isEncrypted()`` (Java line 335)."""
        if self._trailer is None:
            return False
        return self._trailer.contains_key(COSName.ENCRYPT)  # type: ignore[attr-defined]

    def get_encryption_dictionary(self) -> COSDictionary | None:
        """Mirrors upstream ``getEncryptionDictionary()`` (Java line 346)."""
        if self._trailer is None:
            return None
        enc = self._trailer.get_dictionary_object(COSName.ENCRYPT)  # type: ignore[attr-defined]
        return enc if isinstance(enc, COSDictionary) else None

    def set_encryption_dictionary(self, enc_dictionary: COSDictionary) -> None:
        """Write ``trailer/Encrypt`` — used by the writer when a save
        operation needs to install (or replace) the encryption parameters.
        Mirrors upstream ``setEncryptionDictionary(COSDictionary)`` (Java
        line 357). The trailer is auto-created when absent so callers
        building a document from scratch do not have to seed it first."""
        if self._trailer is None:
            self.set_trailer(COSDictionary())
        self._trailer.set_item(COSName.ENCRYPT, enc_dictionary)  # type: ignore[attr-defined]

    def is_decrypted(self) -> bool:
        """``True`` once the parser has run the security handler over every
        encrypted stream/string in this document's object pool. The writer
        checks this to know whether the in-memory graph is plaintext (and
        must be re-enciphered on save) or already-ciphertext. Mirrors
        upstream ``isDecrypted()`` (Java line 325)."""
        return self._is_decrypted

    def set_decrypted(self) -> None:
        """Mark the document as decrypted — called by the parser/security
        handler once the cipher has been undone over the entire object
        pool. One-way (matches upstream ``setDecrypted()`` Java line 315
        which has no corresponding ``setDecrypted(false)``)."""
        self._is_decrypted = True

    # ---------- version ----------

    def get_version(self) -> float:
        """Mirrors upstream ``getVersion()`` (Java line 307)."""
        return self._version

    def set_version(self, version: float) -> None:
        """Mirrors upstream ``setVersion(float)`` (Java line 297)."""
        if version <= 0:
            raise ValueError("version must be positive")
        self._version = version

    # ---------- xref-stream marker ----------

    def is_xref_stream(self) -> bool:
        """Mirrors upstream ``isXRefStream()`` (Java line 568)."""
        return self._is_xref_stream

    def set_is_xref_stream(self, value: bool) -> None:
        """Mirrors upstream ``setIsXRefStream(boolean)`` (Java line 579).
        Caller is expected to ensure the PDF version is 1.5 or higher when
        enabling cross-reference streams."""
        self._is_xref_stream = value

    def set_xref_stream(self, value: bool) -> None:
        """Older convenience name retained alongside :meth:`set_is_xref_stream`
        for callers predating the upstream-shaped getter/setter pair."""
        self._is_xref_stream = value

    def is_x_ref_stream(self) -> bool:
        """Alias for :meth:`is_xref_stream` matching the parity-audit's
        token-split spelling of ``XRef``."""
        return self._is_xref_stream

    def set_is_x_ref_stream(self, value: bool) -> None:
        """Alias for :meth:`set_is_xref_stream` matching the parity-audit's
        token-split spelling of ``XRef``."""
        self._is_xref_stream = value

    # ---------- hybrid-xref marker ----------

    def has_hybrid_xref(self) -> bool:
        """``True`` when the parser saw BOTH a plain cross-reference table
        and a cross-reference stream in this document. The hybrid trick
        (PDF 1.5+) is used to keep older readers working while the
        canonical xref information lives in a stream. Mirrors upstream
        ``hasHybridXRef()`` (Java line 589)."""
        return self._has_hybrid_xref

    def set_has_hybrid_xref(self) -> None:
        """Mark the document as hybrid-xref. One-way, matches upstream
        ``setHasHybridXRef()`` (Java line 597) — no boolean parameter, the
        flag is set when the parser detects the second xref form, never
        cleared."""
        self._has_hybrid_xref = True

    def has_hybrid_x_ref(self) -> bool:
        """Alias for :meth:`has_hybrid_xref` matching the parity-audit's
        token-split spelling of ``XRef``."""
        return self._has_hybrid_xref

    def set_has_hybrid_x_ref(self) -> None:
        """Alias for :meth:`set_has_hybrid_xref` matching the parity-audit's
        token-split spelling of ``XRef``."""
        self._has_hybrid_xref = True

    # ---------- COSStream factory ----------

    def create_cos_stream(
        self,
        dictionary: COSDictionary | None = None,
    ) -> Any:
        """Allocate a fresh ``COSStream`` bound to this document's scratch
        file. Mirrors upstream ``createCOSStream()`` (Java line 172). When
        ``dictionary`` is supplied, every entry is copied onto the new
        stream — matches the parser-helper overload ``createCOSStream(
        COSDictionary, long, long)`` (Java line 192) minus the on-disk
        view (we don't carry a parser-level random-access read view through
        this surface yet — see CHANGES.md).

        The returned ``COSStream`` does NOT own the scratch file (the
        document does), so closing the stream releases its buffer but
        leaves the document scratch intact."""
        # Local import to avoid a hard cos_document → cos_stream cycle at
        # module load time.
        from .cos_stream import COSStream  # noqa: PLC0415

        stream = COSStream(self._scratch_file)
        if dictionary is not None:
            for key, value in dictionary.entry_set():
                stream.set_item(key, value)
        stream.get_update_state().set_origin_document_state(self._document_state)
        return stream

    # ---------- highest xref object number ----------

    def get_highest_xref_object_number(self) -> int:
        """Largest object number the parser has registered against this
        document — used by the writer when allocating new objects so it
        doesn't reuse an existing number. Mirrors upstream
        ``getHighestXRefObjectNumber()`` (Java line 413)."""
        return self._highest_xref_object_number

    def set_highest_xref_object_number(self, number: int) -> None:
        """Mirrors upstream ``setHighestXRefObjectNumber(long)`` (Java
        line 424)."""
        if number < 0:
            raise ValueError("highest xref object number must be non-negative")
        self._highest_xref_object_number = number

    def get_highest_x_ref_object_number(self) -> int:
        """Alias for :meth:`get_highest_xref_object_number` matching the
        parity-audit's token-split spelling of ``XRef``."""
        return self._highest_xref_object_number

    def set_highest_x_ref_object_number(self, number: int) -> None:
        """Alias for :meth:`set_highest_xref_object_number` matching the
        parity-audit's token-split spelling of ``XRef``."""
        self.set_highest_xref_object_number(number)

    # ---------- source / startxref (incremental save plumbing) ----------

    def get_source(self) -> RandomAccessRead | None:
        """Return the underlying ``RandomAccessRead`` the parser created for
        this document, or ``None`` if the caller built the document from
        scratch. Used by the incremental writer to copy original bytes
        verbatim before appending updates."""
        return self._source

    def get_start_xref(self) -> int:
        """Byte offset of the trailing ``startxref`` directive in the source
        file. ``0`` for newly-built (unsaved) documents. Mirrors upstream
        ``getStartXref()`` (Java line 558)."""
        return self._start_xref

    def set_start_xref(self, offset: int) -> None:
        """Record the trailing ``startxref`` value seen by the parser. The
        incremental writer reads this back as the ``/Prev`` chain pointer.
        Mirrors upstream ``setStartXref(long)`` (Java line 548)."""
        if offset < 0:
            raise ValueError("startxref offset must be non-negative")
        self._start_xref = offset

    # ---------- document state ----------

    def get_document_state(self) -> COSDocumentState:
        """Return the lifecycle marker for this document — initially
        ``parsing``, flipped by the parser to ``accepting updates`` once
        xref consumption completes. Mirrors upstream ``getDocumentState()``
        (Java line 608)."""
        return self._document_state

    # ---------- visitor / lifecycle ----------

    def accept(self, visitor: ICOSVisitor) -> Any:
        """Visitor double-dispatch — mirrors upstream ``accept(ICOSVisitor)``
        (Java line 436) which routes to ``visitFromDocument(this)``."""
        return visitor.visit_from_document(self)

    def is_closed(self) -> bool:
        """Mirrors upstream ``isClosed()`` (Java line 499)."""
        return self._closed

    def set_warn_missing_close(self, warn: bool) -> None:
        """Mirror of PDFBox ``setWarnMissingClose``. When ``False`` the
        finalizer suppresses the "document was not closed" log warning. The
        parser flips this off when it is going to retain a reference itself."""
        self._warn_missing_close = warn

    def close(self) -> None:
        """Release the scratch file (when owned), the source (when owned)
        and clear the object pool. Mirrors upstream ``close()`` (Java line
        447); idempotent — repeated calls are safe."""
        if self._closed:
            return
        self._closed = True
        self._objects.clear()
        self._xref_table.clear()
        if self._owns_scratch:
            self._scratch_file.close()
        if self._source is not None and not self._source.is_closed():
            self._source.close()

    def __enter__(self) -> COSDocument:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def __del__(self) -> None:  # pragma: no cover - finalizer
        # Mirror PDFBox's "warnMissingClose": if the user forgot to close
        # the document and warnings are enabled, log it and best-effort
        # release the scratch / source so resources are not leaked. We
        # swallow any exceptions because finalizers run during interpreter
        # shutdown when modules may already be torn down.
        try:
            if not getattr(self, "_closed", True):
                if getattr(self, "_warn_missing_close", False):
                    import logging

                    logging.getLogger(__name__).warning(
                        "COSDocument was not closed — call close() explicitly",
                    )
                self.close()
        except Exception:
            pass

    def __repr__(self) -> str:
        return (
            f"COSDocument(version={self._version}, "
            f"objects={len(self._objects)}, "
            f"encrypted={self.is_encrypted()})"
        )
