from __future__ import annotations

from typing import Any

from pypdfbox.io import RandomAccessRead, ScratchFile

from .cos_array import COSArray
from .cos_base import COSBase
from .cos_dictionary import COSDictionary
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

    def get_object(self, key: COSObjectKey) -> COSObject | None:
        """Return the ``COSObject`` registered for ``key`` or ``None`` if no
        such object has been seen by the parser yet. Mirrors PDFBox's
        ``getObjectFromPool``-companion ``getObject(COSObjectKey)`` lookup —
        does NOT auto-create a placeholder."""
        return self._objects.get(key)

    def has_object(self, key: COSObjectKey) -> bool:
        return key in self._objects

    def get_objects(self) -> list[COSObject]:
        """All known indirect objects in insertion order."""
        return list(self._objects.values())

    def get_object_keys(self) -> list[COSObjectKey]:
        return list(self._objects.keys())

    def remove_object(self, key: COSObjectKey) -> COSObject | None:
        return self._objects.pop(key, None)

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

    def get_xref_table(self) -> dict[COSObjectKey, int]:
        """Sparse object-key → byte-offset map populated by the parser.
        Mirrors PDFBox's ``getXrefTable()``. Positive offsets are absolute
        file positions; negative values encode object-stream membership
        (``-objstm_object_number`` per PDFBox convention)."""
        return self._xref_table

    def get_objects_by_type(self, type_name: COSName | str) -> list[COSObject]:
        """Return every resolved object whose dictionary's ``/Type`` equals
        ``type_name``. Matches PDFBox semantics (returns an empty list when
        no objects match)."""
        target = type_name if isinstance(type_name, COSName) else COSName.get_pdf_name(type_name)
        out: list[COSObject] = []
        for cos_obj in self._objects.values():
            resolved = cos_obj.get_object()
            if isinstance(resolved, COSDictionary):
                t = resolved.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
                if isinstance(t, COSName) and t == target:
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

    def set_trailer(self, trailer: COSDictionary) -> None:
        self._trailer = trailer

    def get_catalog(self) -> COSDictionary | None:
        """Resolve ``trailer/Root`` to its dictionary, or ``None``."""
        if self._trailer is None:
            return None
        catalog = self._trailer.get_dictionary_object(COSName.ROOT)  # type: ignore[attr-defined]
        return catalog if isinstance(catalog, COSDictionary) else None

    def get_document_id(self) -> COSArray | None:
        if self._trailer is None:
            return None
        ids = self._trailer.get_dictionary_object(COSName.get_pdf_name("ID"))
        return ids if isinstance(ids, COSArray) else None

    def set_document_id(self, ids: COSArray) -> None:
        if self._trailer is None:
            self._trailer = COSDictionary()
        self._trailer.set_item(COSName.get_pdf_name("ID"), ids)

    def is_encrypted(self) -> bool:
        if self._trailer is None:
            return False
        return self._trailer.contains_key(COSName.ENCRYPT)  # type: ignore[attr-defined]

    def get_encryption_dictionary(self) -> COSDictionary | None:
        if self._trailer is None:
            return None
        enc = self._trailer.get_dictionary_object(COSName.ENCRYPT)  # type: ignore[attr-defined]
        return enc if isinstance(enc, COSDictionary) else None

    # ---------- version ----------

    def get_version(self) -> float:
        return self._version

    def set_version(self, version: float) -> None:
        if version <= 0:
            raise ValueError("version must be positive")
        self._version = version

    # ---------- xref-stream marker ----------

    def is_xref_stream(self) -> bool:
        return self._is_xref_stream

    def set_xref_stream(self, value: bool) -> None:
        self._is_xref_stream = value

    def set_is_xref_stream(self, value: bool) -> None:
        """Mirror of upstream ``setIsXRefStream(boolean)``. Kept alongside
        :meth:`set_xref_stream` for naming parity with PDFBox 3.x."""
        self._is_xref_stream = value

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
