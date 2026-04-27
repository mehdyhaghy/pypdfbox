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
        ignored; the offset value itself is currently unused by ``COSDocument``
        but kept in the signature for parity."""
        for key in table:
            if key is None:
                continue
            self.get_object_from_pool(key)

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

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._objects.clear()
        if self._owns_scratch:
            self._scratch_file.close()
        if self._source is not None and not self._source.is_closed():
            self._source.close()

    def __enter__(self) -> COSDocument:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"COSDocument(version={self._version}, "
            f"objects={len(self._objects)}, "
            f"encrypted={self.is_encrypted()})"
        )
