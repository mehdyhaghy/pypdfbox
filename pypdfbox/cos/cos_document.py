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
        when forward references are encountered."""
        existing = self._objects.get(key)
        if existing is None:
            existing = COSObject(key.object_number, key.generation_number)
            self._objects[key] = existing
        return existing

    def getObjectFromPool(self, key: COSObjectKey) -> COSObject:  # noqa: N802
        return self.get_object_from_pool(key)

    def get_object(self, key: COSObjectKey) -> COSObject | None:
        """Return the ``COSObject`` registered for ``key`` or ``None`` if no
        such object has been seen by the parser yet. Mirrors PDFBox's
        ``getObjectFromPool``-companion ``getObject(COSObjectKey)`` lookup —
        does NOT auto-create a placeholder."""
        return self._objects.get(key)

    def getObject(self, key: COSObjectKey) -> COSObject | None:  # noqa: N802
        return self.get_object(key)

    def has_object(self, key: COSObjectKey) -> bool:
        return key in self._objects

    def get_objects(self) -> list[COSObject]:
        """All known indirect objects in insertion order."""
        return list(self._objects.values())

    def getObjects(self) -> list[COSObject]:  # noqa: N802
        return self.get_objects()

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

    def getKey(self, base_object: COSBase) -> COSObjectKey | None:  # noqa: N802
        return self.get_key(base_object)

    def remove_object(self, key: COSObjectKey) -> COSObject | None:
        return self._objects.pop(key, None)

    def removeObject(self, key: COSObjectKey) -> COSObject | None:  # noqa: N802
        return self.remove_object(key)

    def add_xref_table(self, table: dict[COSObjectKey | None, int]) -> None:
        """Bulk-register xref entries — mirrors PDFBox's ``addXRefTable``.

        Entries with a ``None`` key (PDFBOX-6132 — corrupt xref entry) are
        ignored; offsets are stored in ``_xref_table`` for later retrieval via
        :meth:`get_xref_table`."""
        for key, offset in table.items():
            if key is None:
                continue
            self.get_object_from_pool(key)
            self._xref_table[key] = offset

    def addXRefTable(self, table: dict[COSObjectKey | None, int]) -> None:  # noqa: N802
        self.add_xref_table(table)

    def get_xref_table(self) -> dict[COSObjectKey, int]:
        """Sparse object-key → byte-offset map populated by the parser.
        Mirrors PDFBox's ``getXrefTable()``. Positive offsets are absolute
        file positions; negative values encode object-stream membership
        (``-objstm_object_number`` per PDFBox convention)."""
        return self._xref_table

    def getXrefTable(self) -> dict[COSObjectKey, int]:  # noqa: N802
        return self.get_xref_table()

    def get_objects_by_type(
        self,
        type_name: COSName | str,
        type_alt: COSName | str | None = None,
    ) -> list[COSObject]:
        """Return every resolved object whose dictionary's ``/Type`` equals
        ``type_name`` (or, when ``type_alt`` is given, either of the two
        names). Matches PDFBox semantics — both the single-arg and the
        two-arg overloads of ``getObjectsByType``. The two-arg form is used
        upstream where a /Type entry has both a long and an abbreviated
        spelling (e.g. ``/CIDFontType0`` vs ``/Font``)."""
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

        Linearized files place the parameter dictionary as the **first**
        indirect object after the header; we walk the object pool in
        insertion order and pick the first resolved dictionary carrying a
        truthy ``/Linearized`` entry. The result is cached — repeated calls
        do not re-scan."""
        if self._linearized_resolved:
            return self._linearized_dict
        for cos_obj in self._objects.values():
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

    def getTrailer(self) -> COSDictionary | None:  # noqa: N802
        return self.get_trailer()

    def set_trailer(self, trailer: COSDictionary) -> None:
        self._trailer = trailer

    def setTrailer(self, trailer: COSDictionary) -> None:  # noqa: N802
        self.set_trailer(trailer)

    def get_catalog(self) -> COSDictionary | None:
        """Resolve ``trailer/Root`` to its dictionary, or ``None``."""
        if self._trailer is None:
            return None
        catalog = self._trailer.get_dictionary_object(COSName.ROOT)  # type: ignore[attr-defined]
        return catalog if isinstance(catalog, COSDictionary) else None

    def getCatalog(self) -> COSDictionary | None:  # noqa: N802
        return self.get_catalog()

    def get_document_id(self) -> COSArray | None:
        """Return ``trailer/ID`` as a typed ``COSArray`` or ``None`` if the
        trailer is missing / has no ``/ID`` entry / the entry is not an
        array. Mirrors upstream ``getDocumentID()`` which calls
        ``getTrailer().getCOSArray(COSName.ID)``."""
        if self._trailer is None:
            return None
        return self._trailer.get_cos_array(COSName.ID)  # type: ignore[attr-defined]

    def set_document_id(self, ids: COSArray) -> None:
        """Write ``trailer/ID``. The trailer is auto-created when absent —
        mirrors PDFBox's ``setDocumentID`` while sparing callers from
        seeding a trailer first when building a document from scratch."""
        if self._trailer is None:
            self._trailer = COSDictionary()
        self._trailer.set_item(COSName.ID, ids)  # type: ignore[attr-defined]

    def is_encrypted(self) -> bool:
        if self._trailer is None:
            return False
        return self._trailer.contains_key(COSName.ENCRYPT)  # type: ignore[attr-defined]

    def isEncrypted(self) -> bool:  # noqa: N802
        return self.is_encrypted()

    def get_encryption_dictionary(self) -> COSDictionary | None:
        if self._trailer is None:
            return None
        enc = self._trailer.get_dictionary_object(COSName.ENCRYPT)  # type: ignore[attr-defined]
        return enc if isinstance(enc, COSDictionary) else None

    def getEncryptionDictionary(self) -> COSDictionary | None:  # noqa: N802
        return self.get_encryption_dictionary()

    def set_encryption_dictionary(self, enc_dictionary: COSDictionary) -> None:
        """Write ``trailer/Encrypt`` — used by the writer when a save
        operation needs to install (or replace) the encryption parameters.
        Mirrors upstream ``setEncryptionDictionary(COSDictionary)``. The
        trailer is auto-created when absent so callers building a document
        from scratch do not have to seed it first."""
        if self._trailer is None:
            self._trailer = COSDictionary()
        self._trailer.set_item(COSName.ENCRYPT, enc_dictionary)  # type: ignore[attr-defined]

    def is_decrypted(self) -> bool:
        """``True`` once the parser has run the security handler over every
        encrypted stream/string in this document's object pool. The writer
        checks this to know whether the in-memory graph is plaintext (and
        must be re-enciphered on save) or already-ciphertext. Mirrors
        upstream ``isDecrypted()``."""
        return self._is_decrypted

    def set_decrypted(self) -> None:
        """Mark the document as decrypted — called by the parser/security
        handler once the cipher has been undone over the entire object
        pool. One-way (matches upstream ``setDecrypted()`` which has no
        corresponding ``setDecrypted(false)``)."""
        self._is_decrypted = True

    # ---------- version ----------

    def get_version(self) -> float:
        return self._version

    def getVersion(self) -> float:  # noqa: N802
        return self.get_version()

    def set_version(self, version: float) -> None:
        if version <= 0:
            raise ValueError("version must be positive")
        self._version = version

    def setVersion(self, version: float) -> None:  # noqa: N802
        self.set_version(version)

    # ---------- xref-stream marker ----------

    def is_xref_stream(self) -> bool:
        return self._is_xref_stream

    def isXRefStream(self) -> bool:  # noqa: N802
        return self.is_xref_stream()

    def set_xref_stream(self, value: bool) -> None:
        self._is_xref_stream = value

    def setXRefStream(self, value: bool) -> None:  # noqa: N802
        self.set_xref_stream(value)

    def set_is_xref_stream(self, value: bool) -> None:
        """Mirror of upstream ``setIsXRefStream(boolean)``. Kept alongside
        :meth:`set_xref_stream` for naming parity with PDFBox 3.x."""
        self._is_xref_stream = value

    # ---------- hybrid-xref marker ----------

    def has_hybrid_xref(self) -> bool:
        """``True`` when the parser saw BOTH a plain cross-reference table
        and a cross-reference stream in this document. The hybrid trick
        (PDF 1.5+) is used to keep older readers working while the
        canonical xref information lives in a stream. Mirrors upstream
        ``hasHybridXRef()``."""
        return self._has_hybrid_xref

    def set_has_hybrid_xref(self) -> None:
        """Mark the document as hybrid-xref. One-way, matches upstream
        ``setHasHybridXRef()`` (no boolean parameter — the flag is set
        when the parser detects the second xref form, never cleared)."""
        self._has_hybrid_xref = True

    # ---------- COSStream factory ----------

    def create_cos_stream(
        self,
        dictionary: COSDictionary | None = None,
    ) -> Any:
        """Allocate a fresh ``COSStream`` bound to this document's scratch
        file. Mirrors upstream ``createCOSStream()``. When ``dictionary``
        is supplied, every entry is copied onto the new stream — matches
        the parser-helper overload ``createCOSStream(COSDictionary, long,
        long)`` minus the on-disk view (we don't carry a parser-level
        random-access read view through this surface yet).

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
        return stream

    # ---------- highest xref object number ----------

    def get_highest_xref_object_number(self) -> int:
        """Largest object number the parser has registered against this
        document — used by the writer when allocating new objects so it
        doesn't reuse an existing number."""
        return self._highest_xref_object_number

    def set_highest_xref_object_number(self, number: int) -> None:
        if number < 0:
            raise ValueError("highest xref object number must be non-negative")
        self._highest_xref_object_number = number

    # ---------- source / startxref (incremental save plumbing) ----------

    def get_source(self) -> RandomAccessRead | None:
        """Return the underlying ``RandomAccessRead`` the parser created for
        this document, or ``None`` if the caller built the document from
        scratch. Used by the incremental writer to copy original bytes
        verbatim before appending updates."""
        return self._source

    def get_start_xref(self) -> int:
        """Byte offset of the trailing ``startxref`` directive in the source
        file. ``0`` for newly-built (unsaved) documents."""
        return self._start_xref

    def set_start_xref(self, offset: int) -> None:
        """Record the trailing ``startxref`` value seen by the parser. The
        incremental writer reads this back as the ``/Prev`` chain pointer."""
        if offset < 0:
            raise ValueError("startxref offset must be non-negative")
        self._start_xref = offset

    # ---------- document state ----------

    def get_document_state(self) -> COSDocumentState:
        """Return the lifecycle marker for this document — initially
        ``parsing``, flipped by the parser to ``accepting updates`` once
        xref consumption completes. Mirrors upstream ``getDocumentState()``.
        """
        return self._document_state

    # ---------- visitor / lifecycle ----------

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_document(self)

    def is_closed(self) -> bool:
        return self._closed

    def set_warn_missing_close(self, warn: bool) -> None:
        """Mirror of PDFBox ``setWarnMissingClose``. When ``False`` the
        finalizer suppresses the "document was not closed" log warning. The
        parser flips this off when it is going to retain a reference itself."""
        self._warn_missing_close = warn

    def close(self) -> None:
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
