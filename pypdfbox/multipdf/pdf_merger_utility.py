from __future__ import annotations

import enum
import logging
import os
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, BinaryIO, Union

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.io import RandomAccessRead

from .pdf_clone_utility import PDFCloneUtility

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


_LOG = logging.getLogger(__name__)


# ---------- COSName cache ----------

_FIELDS: COSName = COSName.get_pdf_name("Fields")
_T: COSName = COSName.get_pdf_name("T")
_ACRO_FORM: COSName = COSName.get_pdf_name("AcroForm")
_NAMES: COSName = COSName.get_pdf_name("Names")
_DESTS: COSName = COSName.get_pdf_name("Dests")
_THREADS: COSName = COSName.get_pdf_name("Threads")
_ID_TREE: COSName = COSName.get_pdf_name("IDTree")
_OUTLINES: COSName = COSName.get_pdf_name("Outlines")
_PAGE_MODE: COSName = COSName.get_pdf_name("PageMode")
_PAGE_LAYOUT: COSName = COSName.get_pdf_name("PageLayout")
_PAGE_LABELS: COSName = COSName.get_pdf_name("PageLabels")
_NUMS: COSName = COSName.get_pdf_name("Nums")
_METADATA: COSName = COSName.get_pdf_name("Metadata")
_OC_PROPERTIES: COSName = COSName.get_pdf_name("OCProperties")
_LANG: COSName = COSName.get_pdf_name("Lang")
_VIEWER_PREFS: COSName = COSName.get_pdf_name("ViewerPreferences")
_FILTER: COSName = COSName.get_pdf_name("Filter")
_LENGTH: COSName = COSName.get_pdf_name("Length")
_PARENT: COSName = COSName.get_pdf_name("Parent")
_STRUCT_PARENTS: COSName = COSName.get_pdf_name("StructParents")
_STRUCT_PARENT: COSName = COSName.get_pdf_name("StructParent")
_PREV: COSName = COSName.get_pdf_name("Prev")
_NEXT: COSName = COSName.get_pdf_name("Next")
_FIRST: COSName = COSName.get_pdf_name("First")
_LAST: COSName = COSName.get_pdf_name("Last")
_RESOURCES: COSName = COSName.get_pdf_name("Resources")
_TYPE: COSName = COSName.get_pdf_name("Type")
_PAGE: COSName = COSName.get_pdf_name("Page")
_OPEN_ACTION: COSName = COSName.get_pdf_name("OpenAction")
_OUTPUT_INTENTS: COSName = COSName.get_pdf_name("OutputIntents")
_STRUCT_TREE_ROOT: COSName = COSName.get_pdf_name("StructTreeRoot")
_PARENT_TREE: COSName = COSName.get_pdf_name("ParentTree")
_PARENT_TREE_NEXT_KEY: COSName = COSName.get_pdf_name("ParentTreeNextKey")
_ROLE_MAP: COSName = COSName.get_pdf_name("RoleMap")
_K: COSName = COSName.get_pdf_name("K")
_S: COSName = COSName.get_pdf_name("S")
_P: COSName = COSName.get_pdf_name("P")
_PG: COSName = COSName.get_pdf_name("Pg")
_OBJ: COSName = COSName.get_pdf_name("Obj")
_NUMS: COSName = COSName.get_pdf_name("Nums")
_KIDS: COSName = COSName.get_pdf_name("Kids")
_NAMES_TREE: COSName = COSName.get_pdf_name("Names")
_DOCUMENT: COSName = COSName.get_pdf_name("Document")
_PART: COSName = COSName.get_pdf_name("Part")
_ANNOTS: COSName = COSName.get_pdf_name("Annots")


# ---------- enums ----------


class DocumentMergeMode(enum.Enum):
    """Mirrors ``PDFMergerUtility.DocumentMergeMode``.

    ``OPTIMIZE_RESOURCES_MODE`` is recognised but currently delegates to the
    legacy path — true cross-document resource deduplication is deferred
    (see ``CHANGES.md``).
    """

    OPTIMIZE_RESOURCES_MODE = "OPTIMIZE_RESOURCES_MODE"
    PDFBOX_LEGACY_MODE = "PDFBOX_LEGACY_MODE"


class AcroFormMergeMode(enum.Enum):
    """Mirrors ``PDFMergerUtility.AcroFormMergeMode``."""

    JOIN_FORM_FIELDS_MODE = "JOIN_FORM_FIELDS_MODE"
    PDFBOX_LEGACY_MODE = "PDFBOX_LEGACY_MODE"


# Convenience aliases mirroring upstream's nested "static final" naming so
# ``PDFMergerUtility.DocumentMergeMode.PDFBOX_LEGACY_MODE`` etc. line up.
SourceLike = Union[
    str, "os.PathLike[str]", BinaryIO, "PDDocument", RandomAccessRead, bytes
]


# ---------- the utility ----------


class PDFMergerUtility:
    """Append the contents of one PDF to another. Mirrors
    ``org.apache.pdfbox.multipdf.PDFMergerUtility``.

    Source documents may be added as file paths, already-opened
    :class:`PDDocument` instances, or file-like binary streams. The
    destination is configured with :meth:`set_destination_file_name` or
    :meth:`set_destination_stream` (one or the other — :meth:`merge_documents`
    raises if neither is set). Page-tree concatenation is performed by
    deep-cloning each source into the destination via :class:`PDFCloneUtility`,
    so the resulting object graph is fully self-contained.

    **Scope notes** (see ``CHANGES.md`` for upstream divergences):

    - Page tree, ``/AcroForm`` fields (with name-uniquification), document
      outlines, ``/Names`` / legacy ``/Dests``, ``/PageLabels`` (with index
      shift), ``/Threads``, ``/Metadata``, ``/OCProperties``, ``/PageMode``,
      ``/Lang``, ``/ViewerPreferences``, document information, and the PDF
      version are merged.
    - Structure-tree merging is supported. ``/StructTreeRoot`` is cloned
      into the destination, ``/ParentTree`` keys are re-keyed by the
      destination's ``/ParentTreeNextKey`` so source/dest never collide,
      ``/StructParents`` on imported pages and ``/StructParent`` on
      imported annotations are bumped by the same offset, ``/IDTree``
      entries are folded in (a duplicated id logs a warning and the
      source entry is dropped, mirroring upstream), and ``/RoleMap`` is
      overlaid (dest wins on conflict). When the destination has no
      tree but a source does, a fresh empty ``/StructTreeRoot`` is
      created on the destination so the source tree can be cloned in.
    - ``OPTIMIZE_RESOURCES_MODE`` recognised but routes to the legacy path.
    - Dynamic XFA documents are rejected.
    """

    # Upstream-named nested type aliases — pypdfbox callers typically import
    # these from the module directly, but mirroring the nested form keeps
    # ports of upstream code lexically intact.
    DocumentMergeMode = DocumentMergeMode
    AcroFormMergeMode = AcroFormMergeMode

    def __init__(self) -> None:
        self._sources: list[Any] = []
        self._destination_file_name: str | os.PathLike[str] | None = None
        self._destination_stream: BinaryIO | None = None
        self._destination_document_information: Any = None
        self._destination_metadata: Any = None
        self._ignore_acro_form_errors: bool = False
        self._document_merge_mode: DocumentMergeMode = (
            DocumentMergeMode.PDFBOX_LEGACY_MODE
        )
        self._acro_form_merge_mode: AcroFormMergeMode = (
            AcroFormMergeMode.PDFBOX_LEGACY_MODE
        )
        # Counter used by AcroForm legacy uniquification — preserved
        # across consecutive ``append_document`` calls so a multi-source
        # merge keeps generating fresh ``dummyFieldName`` suffixes.
        self._next_field_num: int = 1

    # ---------- properties / config ----------

    def get_document_merge_mode(self) -> DocumentMergeMode:
        return self._document_merge_mode

    def set_document_merge_mode(self, mode: DocumentMergeMode) -> None:
        self._document_merge_mode = mode

    # Property-style aliases — Python flavour of upstream's getter/setter
    # pairs. Upstream test ports occasionally rely on bean-style access.
    @property
    def document_merge_mode_property(self) -> DocumentMergeMode:
        return self._document_merge_mode

    @document_merge_mode_property.setter
    def document_merge_mode_property(self, mode: DocumentMergeMode) -> None:
        self._document_merge_mode = mode

    def get_acro_form_merge_mode(self) -> AcroFormMergeMode:
        return self._acro_form_merge_mode

    def set_acro_form_merge_mode(self, mode: AcroFormMergeMode) -> None:
        self._acro_form_merge_mode = mode

    @property
    def acro_form_merge_mode_property(self) -> AcroFormMergeMode:
        return self._acro_form_merge_mode

    @acro_form_merge_mode_property.setter
    def acro_form_merge_mode_property(self, mode: AcroFormMergeMode) -> None:
        self._acro_form_merge_mode = mode

    def is_ignore_acro_form_errors(self) -> bool:
        return self._ignore_acro_form_errors

    def set_ignore_acro_form_errors(self, value: bool) -> None:
        self._ignore_acro_form_errors = bool(value)

    def get_destination_file_name(self) -> str | os.PathLike[str] | None:
        return self._destination_file_name

    def set_destination_file_name(
        self, destination: str | os.PathLike[str]
    ) -> None:
        self._destination_file_name = destination

    def get_destination_stream(self) -> BinaryIO | None:
        return self._destination_stream

    def set_destination_stream(self, stream: BinaryIO) -> None:
        self._destination_stream = stream

    def get_destination_document_information(self) -> Any:
        return self._destination_document_information

    def set_destination_document_information(self, info: Any) -> None:
        self._destination_document_information = info

    def get_destination_metadata(self) -> Any:
        return self._destination_metadata

    def set_destination_metadata(self, metadata: Any) -> None:
        self._destination_metadata = metadata

    # ---------- source management ----------

    def add_source(self, source: SourceLike) -> None:
        """Add a source document. Accepts a file path, an already-opened
        :class:`PDDocument`, a :class:`RandomAccessRead`, raw ``bytes``,
        or a binary stream.
        """
        self._sources.append(source)

    def add_sources(self, sources: Iterable[SourceLike]) -> None:
        for src in sources:
            self.add_source(src)

    def get_sources(self) -> list[Any]:
        return list(self._sources)

    # Upstream offers an overloaded ``setDestination(File | OutputStream)``;
    # this convenience routes either flavour to the right backing field.
    def set_destination(
        self, destination: str | os.PathLike[str] | BinaryIO
    ) -> None:
        """Set the merge destination.

        Routes path-like inputs to :meth:`set_destination_file_name` and
        binary streams (any object with a ``write`` method) to
        :meth:`set_destination_stream`. Mirrors upstream's overloaded
        ``setDestination``.
        """
        if isinstance(destination, (str, os.PathLike)):
            self.set_destination_file_name(destination)
            return
        if hasattr(destination, "write"):
            self.set_destination_stream(destination)
            return
        raise TypeError(
            f"unsupported destination type: {type(destination).__name__}"
        )

    # ---------- merge entry points ----------

    def merge_documents(self, memory_usage_setting: Any = None) -> None:
        """Run the merge. ``memory_usage_setting`` is accepted for upstream
        signature parity but currently ignored (see ``CHANGES.md``).
        """
        del memory_usage_setting  # parity placeholder — see docstring
        if self._document_merge_mode == DocumentMergeMode.OPTIMIZE_RESOURCES_MODE:
            # OPTIMIZE_RESOURCES_MODE deferred — fall back to legacy.
            _LOG.info(
                "OPTIMIZE_RESOURCES_MODE not yet implemented; "
                "falling back to PDFBOX_LEGACY_MODE."
            )
        self._legacy_merge_documents()

    def merge_documents_random_access_read(
        self,
        sources: Iterable[RandomAccessRead],
        memory_usage_setting: Any = None,
    ) -> None:
        """Merge a sequence of :class:`RandomAccessRead` sources into the
        configured destination.

        Mirrors upstream ``PDFMergerUtility.mergeDocumentsRandomAccessRead``.
        Each :class:`RandomAccessRead` is registered as a source via
        :meth:`add_source` and the merge is then driven through the same
        :meth:`merge_documents` path. Sources passed in by the caller stay
        owned by the caller — the merger does NOT call ``close()`` on
        them, mirroring upstream's contract that
        ``RandomAccessRead`` ownership belongs to the caller.

        ``memory_usage_setting`` is accepted for upstream signature parity
        but is currently ignored (see ``CHANGES.md``).
        """
        del memory_usage_setting  # parity placeholder — see docstring
        for src in sources:
            if not isinstance(src, RandomAccessRead):
                raise TypeError(
                    "merge_documents_random_access_read: every source must "
                    "be a RandomAccessRead instance; got "
                    f"{type(src).__name__}"
                )
            self.add_source(src)
        self.merge_documents()

    def _legacy_merge_documents(self) -> None:
        if not self._sources:
            return
        if self._destination_file_name is None and self._destination_stream is None:
            raise ValueError(
                "Either set_destination_file_name(...) or set_destination_stream(...) "
                "must be configured before merge_documents()."
            )

        from pypdfbox.pdmodel.pd_document import PDDocument

        destination = PDDocument()
        opened_sources: list[tuple[PDDocument, bool]] = []
        try:
            for source in self._sources:
                source_doc, owns = self._open_source(source)
                opened_sources.append((source_doc, owns))
                try:
                    self.append_document(destination, source_doc)
                finally:
                    # Keep upstream behaviour: a source we opened gets closed
                    # immediately after appending. A caller-provided open
                    # PDDocument stays open.
                    if owns:
                        try:
                            source_doc.close()
                        except Exception:  # noqa: BLE001 — best-effort close
                            _LOG.exception("error closing source PDDocument")
                        opened_sources[-1] = (source_doc, False)

            if self._destination_document_information is not None:
                destination.set_document_information(
                    self._destination_document_information
                )
            if self._destination_metadata is not None:
                destination.get_document_catalog().set_metadata(
                    self._destination_metadata
                )

            if self._destination_stream is None:
                destination.save(self._destination_file_name)
            else:
                destination.save(self._destination_stream)
        finally:
            try:
                destination.close()
            except Exception:  # noqa: BLE001
                _LOG.exception("error closing destination PDDocument")
            for src_doc, still_owned in opened_sources:
                if still_owned:
                    try:
                        src_doc.close()
                    except Exception:  # noqa: BLE001
                        _LOG.exception("error closing source PDDocument")

    @staticmethod
    def _open_source(source: SourceLike) -> tuple[PDDocument, bool]:
        """Resolve ``source`` to a (PDDocument, owns_doc) pair.

        Accepts a file path, an already-opened :class:`PDDocument`, a
        :class:`RandomAccessRead`, raw ``bytes`` / ``bytearray``, or a
        binary stream. ``owns_doc`` is ``True`` when the merger created
        the :class:`PDDocument` and is responsible for closing it.
        """
        from pypdfbox.pdmodel.pd_document import PDDocument

        if isinstance(source, PDDocument):
            return source, False
        if isinstance(source, RandomAccessRead):
            # Pass through directly — Loader can take a RandomAccessRead
            # without needing to drain it first. Caller retains ownership
            # of the RandomAccessRead per upstream contract.
            return PDDocument.load(source), True
        if isinstance(source, (str, os.PathLike)):
            return PDDocument.load(source), True
        if isinstance(source, (bytes, bytearray, memoryview)):
            return PDDocument.load(bytes(source)), True
        if hasattr(source, "read"):
            data = source.read()
            return PDDocument.load(data), True
        raise TypeError(
            f"unsupported source type: {type(source).__name__}"
        )

    # ---------- core append ----------

    def append_document(
        self, destination: PDDocument, source: PDDocument
    ) -> None:
        """Append every page of ``source`` to ``destination`` and merge
        the supported catalog substructures.

        Mirrors upstream ``PDFMergerUtility.appendDocument`` happy path.
        """
        if source.is_closed():
            raise OSError("Error: source PDF is closed.")
        if destination.is_closed():
            raise OSError("Error: destination PDF is closed.")

        cloner = PDFCloneUtility(destination)

        src_catalog = source.get_document_catalog()
        if self._is_dynamic_xfa(src_catalog.get_acro_form()):
            raise OSError(
                "Error: can't merge source document containing dynamic XFA form content."
            )

        # ----- /Info -----
        dest_info = destination.get_document_information()
        src_info = source.get_document_information()
        self._merge_into(
            src_info.get_cos_object(),
            dest_info.get_cos_object(),
            cloner,
            frozenset(),
        )

        # ----- PDF version bump -----
        try:
            dest_version = float(destination.get_version())
            src_version = float(source.get_version())
            if dest_version < src_version:
                destination.set_version(src_version)
        except Exception:  # noqa: BLE001 — version lookup may fail on minimal docs
            _LOG.debug("PDF version bump skipped", exc_info=True)

        dest_catalog = destination.get_document_catalog()

        # ----- /AcroForm -----
        self._merge_acro_form(cloner, dest_catalog, src_catalog)

        # ----- /Threads -----
        self._merge_threads(cloner, src_catalog, dest_catalog)

        # ----- /Names + /Dests -----
        self._merge_names(cloner, src_catalog, dest_catalog)

        # ----- /Outlines -----
        self._merge_outline(cloner, src_catalog, dest_catalog)

        # ----- /PageMode -----
        if dest_catalog.get_cos_object().get_dictionary_object(_PAGE_MODE) is None:
            src_pm = src_catalog.get_cos_object().get_dictionary_object(_PAGE_MODE)
            if src_pm is not None:
                cloned = cloner.clone_for_new_document(src_pm)
                if cloned is not None:
                    dest_catalog.get_cos_object().set_item(_PAGE_MODE, cloned)

        # ----- /PageLayout (carried first-source-wins like /PageMode) -----
        if dest_catalog.get_cos_object().get_dictionary_object(_PAGE_LAYOUT) is None:
            src_pl = src_catalog.get_cos_object().get_dictionary_object(_PAGE_LAYOUT)
            if src_pl is not None:
                cloned = cloner.clone_for_new_document(src_pl)
                if cloned is not None:
                    dest_catalog.get_cos_object().set_item(_PAGE_LAYOUT, cloned)

        # ----- /Lang -----
        if dest_catalog.get_cos_object().get_dictionary_object(_LANG) is None:
            src_lang = src_catalog.get_cos_object().get_dictionary_object(_LANG)
            if src_lang is not None:
                cloned = cloner.clone_for_new_document(src_lang)
                if cloned is not None:
                    dest_catalog.get_cos_object().set_item(_LANG, cloned)

        # ----- /ViewerPreferences -----
        if (
            dest_catalog.get_cos_object().get_dictionary_object(_VIEWER_PREFS)
            is None
        ):
            src_vp = src_catalog.get_cos_object().get_dictionary_object(_VIEWER_PREFS)
            if isinstance(src_vp, COSDictionary):
                cloned = cloner.clone_for_new_document(src_vp)
                if cloned is not None:
                    dest_catalog.get_cos_object().set_item(_VIEWER_PREFS, cloned)

        # ----- /PageLabels -----
        self._merge_page_labels(cloner, source, destination)

        # ----- /Metadata -----
        self._merge_metadata(cloner, src_catalog, dest_catalog, destination)

        # ----- /OCProperties -----
        self._merge_oc_properties(cloner, src_catalog, dest_catalog)

        # ----- /OutputIntents -----
        self._merge_output_intents(cloner, src_catalog, dest_catalog)

        # ----- structure-tree merge prep -----
        # Decide up-front whether we'll merge the structure tree, and if so
        # what offset to add to imported /StructParents and /StructParent
        # values so they don't collide with the destination's existing
        # parent-tree keys. Mirrors upstream PDFMergerUtility.appendDocument.
        (
            merge_struct_tree,
            dest_parent_tree_next_key,
            src_number_tree_as_map,
            dest_number_tree_as_map,
            src_struct_tree,
            dest_struct_tree,
        ) = self._prepare_struct_tree_merge(src_catalog, dest_catalog, destination)

        # ----- pages -----
        # When merging the structure tree, we offset /StructParents on the
        # cloned page and /StructParent on its annotations by
        # ``dest_parent_tree_next_key`` and record cloned-from / cloned-to
        # mappings so the source ParentTree's /Pg /Obj references can be
        # re-routed afterwards. When NOT merging the structure tree we fall
        # back to the legacy strip-the-keys behaviour so the destination
        # stays structurally consistent.
        from pypdfbox.pdmodel.pd_page import PDPage

        dest_pages = destination.get_pages()
        obj_mapping: dict[int, COSDictionary] = {}
        for page in src_catalog.get_pages():
            old_page_dict = page.get_cos_object()
            old_annots_dicts: list[COSDictionary] = []
            if merge_struct_tree:
                old_annots_raw = old_page_dict.get_dictionary_object(_ANNOTS)
                if isinstance(old_annots_raw, COSArray):
                    for i in range(old_annots_raw.size()):
                        entry = old_annots_raw.get_object(i)
                        if isinstance(entry, COSDictionary):
                            old_annots_dicts.append(entry)

            new_page_dict = cloner.clone_for_new_document(old_page_dict)
            assert isinstance(new_page_dict, COSDictionary)
            new_page_dict.remove_item(_PARENT)

            if merge_struct_tree:
                self._update_struct_parent_entries(
                    new_page_dict, dest_parent_tree_next_key
                )
                # Build object-mapping rows so updatePageReferences can
                # rewrite /Pg and /Obj on cloned ParentTree leaves to point
                # at the *new* page / annotation dictionaries.
                obj_mapping[id(old_page_dict)] = new_page_dict
                new_annots_raw = new_page_dict.get_dictionary_object(_ANNOTS)
                new_annots_dicts: list[COSDictionary] = []
                if isinstance(new_annots_raw, COSArray):
                    for i in range(new_annots_raw.size()):
                        entry = new_annots_raw.get_object(i)
                        if isinstance(entry, COSDictionary):
                            new_annots_dicts.append(entry)
                for old_a, new_a in zip(
                    old_annots_dicts, new_annots_dicts, strict=False
                ):
                    obj_mapping[id(old_a)] = new_a
            else:
                new_page_dict.remove_item(_STRUCT_PARENTS)
                self._strip_struct_parent_from_annots(new_page_dict)

            dest_pages.add(PDPage(new_page_dict))

        # ----- /OpenAction -----
        self._merge_open_action(cloner, src_catalog, dest_catalog)

        # ----- structure-tree merge proper -----
        if merge_struct_tree:
            self._finish_struct_tree_merge(
                cloner,
                src_struct_tree,
                dest_struct_tree,
                src_number_tree_as_map,
                dest_number_tree_as_map,
                dest_parent_tree_next_key,
                obj_mapping,
            )

    # ---------- helpers ----------

    @staticmethod
    def _is_dynamic_xfa(acro_form: Any) -> bool:
        if acro_form is None:
            return False
        is_dynamic = getattr(acro_form, "xfa_is_dynamic", None)
        if callable(is_dynamic):
            try:
                return bool(is_dynamic())
            except Exception:  # noqa: BLE001
                return False
        return False

    @staticmethod
    def _merge_into(
        src: COSDictionary,
        dst: COSDictionary,
        cloner: PDFCloneUtility,
        exclude: frozenset[COSName] | set[COSName],
    ) -> None:
        for key, value in list(src.entry_set()):
            if key in exclude:
                continue
            if dst.contains_key(key):
                continue
            cloned = cloner.clone_for_new_document(value)
            if cloned is not None:
                dst.set_item(key, cloned)

    def _merge_acro_form(
        self,
        cloner: PDFCloneUtility,
        dest_catalog: Any,
        src_catalog: Any,
    ) -> None:
        try:
            dest_form = dest_catalog.get_acro_form()
            src_form = src_catalog.get_acro_form()
            if dest_form is None and src_form is not None:
                cloned = cloner.clone_for_new_document(src_form.get_cos_object())
                if cloned is not None:
                    dest_catalog.get_cos_object().set_item(_ACRO_FORM, cloned)
                return
            if src_form is None:
                return
            if self._acro_form_merge_mode == AcroFormMergeMode.PDFBOX_LEGACY_MODE:
                self._acro_form_legacy_mode(cloner, dest_form, src_form)
            else:
                self._acro_form_join_fields_mode(cloner, dest_form, src_form)
        except Exception as exc:  # noqa: BLE001
            if not self._ignore_acro_form_errors:
                raise OSError(str(exc)) from exc
            _LOG.warning("AcroForm merge error ignored", exc_info=True)

    def _acro_form_legacy_mode(
        self,
        cloner: PDFCloneUtility,
        dest_form: Any,
        src_form: Any,
    ) -> None:
        """Field-name uniquification mirrors upstream:
        if a destination already has a field with the source field's
        fully-qualified name, the cloned destination field's ``/T`` is
        rewritten to ``dummyFieldNameN`` with a fresh ``N``.
        """
        src_fields = src_form.get_fields()
        if not src_fields:
            return

        prefix = "dummyFieldName"
        prefix_len = len(prefix)

        # Bring _next_field_num up to "1 above the highest existing
        # dummyFieldNameN suffix already in dest" so we never collide.
        for dest_field in dest_form.get_field_tree():
            partial = dest_field.get_partial_name()
            if partial is not None and partial.startswith(prefix):
                suffix = partial[prefix_len:]
                if suffix.isdigit():
                    self._next_field_num = max(
                        self._next_field_num, int(suffix) + 1
                    )

        dest_dict = dest_form.get_cos_object()
        base = dest_dict.get_item(_FIELDS)
        if isinstance(base, COSArray):
            dest_fields_array = base
        else:
            dest_fields_array = COSArray()

        for src_field in src_fields:
            cloned = cloner.clone_for_new_document(src_field.get_cos_object())
            assert isinstance(cloned, COSDictionary)
            try:
                fqn = src_field.get_fully_qualified_name()
            except Exception:  # noqa: BLE001
                fqn = None
            if fqn is not None and dest_form.get_field(fqn) is not None:
                cloned.set_string(_T, f"{prefix}{self._next_field_num}")
                self._next_field_num += 1
            dest_fields_array.add(cloned)

        dest_dict.set_item(_FIELDS, dest_fields_array)

    def _acro_form_join_fields_mode(
        self,
        cloner: PDFCloneUtility,
        dest_form: Any,
        src_form: Any,
    ) -> None:
        """Join-fields mode: append source fields verbatim. Upstream's
        version walks both trees to merge same-named non-terminals; we
        keep the simpler concatenation and document the divergence in
        ``CHANGES.md``."""
        src_fields = src_form.get_fields()
        if not src_fields:
            return
        dest_dict = dest_form.get_cos_object()
        base = dest_dict.get_item(_FIELDS)
        dest_fields_array = base if isinstance(base, COSArray) else COSArray()
        for src_field in src_fields:
            cloned = cloner.clone_for_new_document(src_field.get_cos_object())
            if cloned is not None:
                dest_fields_array.add(cloned)
        dest_dict.set_item(_FIELDS, dest_fields_array)

    def _merge_threads(
        self,
        cloner: PDFCloneUtility,
        src_catalog: Any,
        dest_catalog: Any,
    ) -> None:
        src_threads = src_catalog.get_cos_object().get_dictionary_object(_THREADS)
        if not isinstance(src_threads, COSArray):
            return
        cloned_src = cloner.clone_for_new_document(src_threads)
        dest_threads = dest_catalog.get_cos_object().get_dictionary_object(_THREADS)
        if not isinstance(dest_threads, COSArray):
            if cloned_src is not None:
                dest_catalog.get_cos_object().set_item(_THREADS, cloned_src)
            return
        if isinstance(cloned_src, COSArray):
            for i in range(cloned_src.size()):
                dest_threads.add(cloned_src.get(i))

    def _merge_names(
        self,
        cloner: PDFCloneUtility,
        src_catalog: Any,
        dest_catalog: Any,
    ) -> None:
        src_names_dict = src_catalog.get_cos_object().get_dictionary_object(_NAMES)
        dest_dict = dest_catalog.get_cos_object()
        dest_names_dict = dest_dict.get_dictionary_object(_NAMES)

        if isinstance(src_names_dict, COSDictionary):
            if not isinstance(dest_names_dict, COSDictionary):
                cloned = cloner.clone_for_new_document(src_names_dict)
                if cloned is not None:
                    dest_dict.set_item(_NAMES, cloned)
            else:
                cloner._clone_merge_cos_base(src_names_dict, dest_names_dict)  # noqa: SLF001

        # Re-fetch in case we just installed a /Names dict above.
        dest_names_dict = dest_dict.get_dictionary_object(_NAMES)
        if isinstance(dest_names_dict, COSDictionary) and dest_names_dict.contains_key(
            _ID_TREE
        ):
            dest_names_dict.remove_item(_ID_TREE)
            _LOG.warning(
                "Removed /IDTree from /Names dictionary, doesn't belong there"
            )

        # Legacy /Dests
        src_dests = src_catalog.get_cos_object().get_dictionary_object(_DESTS)
        if isinstance(src_dests, COSDictionary):
            dest_dests = dest_dict.get_dictionary_object(_DESTS)
            if not isinstance(dest_dests, COSDictionary):
                cloned = cloner.clone_for_new_document(src_dests)
                if cloned is not None:
                    dest_dict.set_item(_DESTS, cloned)
            else:
                cloner._clone_merge_cos_base(src_dests, dest_dests)  # noqa: SLF001

    def _merge_outline(
        self,
        cloner: PDFCloneUtility,
        src_catalog: Any,
        dest_catalog: Any,
    ) -> None:
        from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
            PDDocumentOutline,
            PDOutlineItem,
        )

        src_outline = src_catalog.get_document_outline()
        if src_outline is None:
            return
        dest_outline = dest_catalog.get_document_outline()
        if dest_outline is None or dest_outline.get_first_child() is None:
            cloned_dict = cloner.clone_for_new_document(src_outline.get_cos_object())
            assert isinstance(cloned_dict, COSDictionary)
            dest_catalog.set_document_outline(PDDocumentOutline(cloned_dict))
            return

        # Walk to the last sibling under dest's outline root.
        visited: set[int] = set()
        last = dest_outline.get_first_child()
        assert last is not None
        while True:
            if id(last.get_cos_object()) in visited:
                _LOG.warning("Outline ignored: %s", last.get_cos_object())
                return
            visited.add(id(last.get_cos_object()))
            nxt = last.get_next_sibling()
            if nxt is None:
                break
            last = nxt

        for item in src_outline.children():
            cloned_dict = cloner.clone_for_new_document(item.get_cos_object())
            assert isinstance(cloned_dict, COSDictionary)
            cloned_dict.remove_item(_PREV)
            cloned_dict.remove_item(_NEXT)
            cloned_item = PDOutlineItem(cloned_dict)
            last.insert_sibling_after(cloned_item)
            nxt = last.get_next_sibling()
            if nxt is None:
                break
            last = nxt

    def _merge_page_labels(
        self,
        cloner: PDFCloneUtility,
        source: PDDocument,
        destination: PDDocument,
    ) -> None:
        from pypdfbox.cos import COSInteger, COSNumber

        src_catalog = source.get_document_catalog()
        dest_catalog = destination.get_document_catalog()
        src_labels = src_catalog.get_cos_object().get_dictionary_object(_PAGE_LABELS)
        if not isinstance(src_labels, COSDictionary):
            return
        # Page count BEFORE we add the new pages — that's the index offset
        # for source labels.
        dest_page_count = destination.get_number_of_pages()
        dest_labels = dest_catalog.get_cos_object().get_dictionary_object(_PAGE_LABELS)
        if not isinstance(dest_labels, COSDictionary):
            dest_labels = COSDictionary()
            dest_nums = COSArray()
            dest_labels.set_item(_NUMS, dest_nums)
            dest_catalog.get_cos_object().set_item(_PAGE_LABELS, dest_labels)
        else:
            dest_nums_obj = dest_labels.get_dictionary_object(_NUMS)
            if isinstance(dest_nums_obj, COSArray):
                dest_nums = dest_nums_obj
            else:
                dest_nums = COSArray()
                dest_labels.set_item(_NUMS, dest_nums)
        src_nums = src_labels.get_dictionary_object(_NUMS)
        if not isinstance(src_nums, COSArray):
            return
        start_size = dest_nums.size()
        i = 0
        while i + 1 < src_nums.size():
            base = src_nums.get_object(i)
            if not isinstance(base, COSNumber):
                _LOG.error(
                    "page labels ignored, index %d should be a number, but is %s",
                    i,
                    base,
                )
                while dest_nums.size() > start_size:
                    dest_nums.remove_at(start_size)
                return
            label_index_value = int(base.int_value())
            dest_nums.add(COSInteger.get(label_index_value + dest_page_count))
            cloned = cloner.clone_for_new_document(src_nums.get_object(i + 1))
            if cloned is not None:
                dest_nums.add(cloned)
            i += 2

    def _merge_metadata(
        self,
        cloner: PDFCloneUtility,
        src_catalog: Any,
        dest_catalog: Any,
        destination: PDDocument,
    ) -> None:
        dest_dict = dest_catalog.get_cos_object()
        src_dict = src_catalog.get_cos_object()
        dest_metadata = dest_dict.get_dictionary_object(_METADATA)
        src_metadata = src_dict.get_dictionary_object(_METADATA)
        if dest_metadata is not None or not isinstance(src_metadata, COSStream):
            return
        try:
            cloned = cloner.clone_for_new_document(src_metadata)
            if cloned is not None:
                dest_dict.set_item(_METADATA, cloned)
        except Exception:  # noqa: BLE001
            _LOG.exception("Metadata skipped because it could not be read")

    def _merge_oc_properties(
        self,
        cloner: PDFCloneUtility,
        src_catalog: Any,
        dest_catalog: Any,
    ) -> None:
        src_dict = src_catalog.get_cos_object().get_dictionary_object(_OC_PROPERTIES)
        if not isinstance(src_dict, COSDictionary):
            return
        dest_dict = dest_catalog.get_cos_object().get_dictionary_object(_OC_PROPERTIES)
        if not isinstance(dest_dict, COSDictionary):
            cloned = cloner.clone_for_new_document(src_dict)
            if cloned is not None:
                dest_catalog.get_cos_object().set_item(_OC_PROPERTIES, cloned)
            return
        cloner._clone_merge_cos_base(src_dict, dest_dict)  # noqa: SLF001

    def _merge_output_intents(
        self,
        cloner: PDFCloneUtility,
        src_catalog: Any,
        dest_catalog: Any,
    ) -> None:
        src_oi = src_catalog.get_cos_object().get_dictionary_object(_OUTPUT_INTENTS)
        if not isinstance(src_oi, COSArray):
            return
        dest_oi = dest_catalog.get_cos_object().get_dictionary_object(_OUTPUT_INTENTS)
        if not isinstance(dest_oi, COSArray):
            cloned = cloner.clone_for_new_document(src_oi)
            if cloned is not None:
                dest_catalog.get_cos_object().set_item(_OUTPUT_INTENTS, cloned)
            return
        cloned = cloner.clone_for_new_document(src_oi)
        if isinstance(cloned, COSArray):
            for i in range(cloned.size()):
                dest_oi.add(cloned.get(i))

    def _merge_open_action(
        self,
        cloner: PDFCloneUtility,
        src_catalog: Any,
        dest_catalog: Any,
    ) -> None:
        # First-source-wins. /OpenAction often points at a page/destination
        # that we just cloned via the page-tree pass, so the cloner's
        # identity table makes the inner page reference resolve correctly.
        if dest_catalog.get_cos_object().get_dictionary_object(_OPEN_ACTION) is not None:
            return
        src_oa = src_catalog.get_cos_object().get_dictionary_object(_OPEN_ACTION)
        if src_oa is None:
            return
        cloned = cloner.clone_for_new_document(src_oa)
        if cloned is not None:
            dest_catalog.get_cos_object().set_item(_OPEN_ACTION, cloned)

    @staticmethod
    def _strip_struct_parent_from_annots(page_dict: COSDictionary) -> None:
        annots = page_dict.get_dictionary_object(COSName.get_pdf_name("Annots"))
        if not isinstance(annots, COSArray):
            return
        for i in range(annots.size()):
            entry = annots.get_object(i)
            if isinstance(entry, COSDictionary):
                entry.remove_item(_STRUCT_PARENT)

    # ---------- structure tree ----------

    @staticmethod
    def get_number_tree_as_map(tree: Any) -> dict[int, COSBase]:
        """Flatten a ``PDNumberTreeNode`` (or anything with ``get_numbers`` /
        ``get_kids``) into an ordered ``int -> COSBase`` map.

        Mirrors upstream ``PDFMergerUtility.getNumberTreeAsMap``. Walks the
        node and every kid recursively, returning the union of all leaf
        ``/Nums`` arrays. Returns an empty dict when ``tree`` is ``None``.
        Values are returned as raw COS objects so callers can re-clone them
        without an extra wrapper bounce.
        """
        if tree is None:
            return {}
        numbers: dict[int, COSBase] = {}
        getter = getattr(tree, "get_numbers", None)
        if callable(getter):
            local = getter()
            if local:
                for k, v in local.items():
                    numbers[int(k)] = (
                        v.get_cos_object() if hasattr(v, "get_cos_object") else v
                    )
        kids_getter = getattr(tree, "get_kids", None)
        if callable(kids_getter):
            kids = kids_getter()
            if kids:
                for kid in kids:
                    numbers.update(PDFMergerUtility.get_number_tree_as_map(kid))
        return numbers

    @staticmethod
    def get_id_tree_as_map(tree: Any) -> dict[str, COSBase]:
        """Flatten a name-tree node (typically the ``/IDTree`` of a
        ``PDStructureTreeRoot``) into an ordered ``str -> COSBase`` map.

        Mirrors upstream ``PDFMergerUtility.getIDTreeAsMap``. Returns raw
        COS values rather than typed ``PDStructureElement`` instances so
        the merger can clone-and-rewrap without losing identity-table
        coalescing in :class:`PDFCloneUtility`.
        """
        if tree is None:
            return {}
        names: dict[str, COSBase] = {}
        getter = getattr(tree, "get_names", None)
        if callable(getter):
            local = getter()
            if local:
                for k, v in local.items():
                    names[str(k)] = (
                        v.get_cos_object() if hasattr(v, "get_cos_object") else v
                    )
        kids_getter = getattr(tree, "get_kids", None)
        if callable(kids_getter):
            kids = kids_getter()
            if kids:
                for kid in kids:
                    names.update(PDFMergerUtility.get_id_tree_as_map(kid))
        return names

    def _prepare_struct_tree_merge(
        self,
        src_catalog: Any,
        dest_catalog: Any,
        destination: PDDocument,
    ) -> tuple[bool, int, dict[int, COSBase], dict[int, COSBase], Any, Any]:
        """Decide whether a struct-tree merge is needed and build the prep
        state: ``(merge?, dest_parent_tree_next_key, src_map, dest_map,
        src_root, dest_root)``.

        Mirrors the head of upstream ``appendDocument``'s structure-tree
        section verbatim, including the dummy-tree creation when the
        destination has no ``/StructTreeRoot`` but the source does.
        """
        from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
            PDStructureTreeRoot,
        )

        src_struct_tree = src_catalog.get_struct_tree_root()
        dest_struct_tree = dest_catalog.get_struct_tree_root()

        # Bootstrap an empty dest tree when the source has one. We also
        # strip bogus /StructParents on existing dest pages so they don't
        # accidentally point at the brand-new (empty) parent tree
        # (PDFBOX-4429).
        if dest_struct_tree is None and src_struct_tree is not None:
            dest_struct_tree = PDStructureTreeRoot()
            dest_struct_tree.set_parent_tree(COSDictionary())
            dest_catalog.set_struct_tree_root(dest_struct_tree)
            dest_pt = dest_struct_tree.get_parent_tree()
            if dest_pt is not None:
                dest_pt.get_cos_object().set_item(_NUMS, COSArray())
            for page in dest_catalog.get_pages():
                page.get_cos_object().remove_item(_STRUCT_PARENTS)
                annots = page.get_cos_object().get_dictionary_object(_ANNOTS)
                if isinstance(annots, COSArray):
                    for i in range(annots.size()):
                        entry = annots.get_object(i)
                        if isinstance(entry, COSDictionary):
                            entry.remove_item(_STRUCT_PARENT)

        merge_struct_tree = False
        dest_parent_tree_next_key = -1
        src_map: dict[int, COSBase] = {}
        dest_map: dict[int, COSBase] = {}

        if dest_struct_tree is not None:
            dest_parent_tree = dest_struct_tree.get_parent_tree()
            dest_parent_tree_next_key = dest_struct_tree.get_parent_tree_next_key()
            if dest_parent_tree is not None:
                dest_map = self.get_number_tree_as_map(dest_parent_tree)
                if dest_parent_tree_next_key < 0:
                    dest_parent_tree_next_key = (
                        0 if not dest_map else max(dest_map.keys()) + 1
                    )
                if dest_parent_tree_next_key >= 0 and src_struct_tree is not None:
                    src_parent_tree = src_struct_tree.get_parent_tree()
                    if src_parent_tree is not None:
                        src_map = self.get_number_tree_as_map(src_parent_tree)
                        if src_map:
                            merge_struct_tree = True

        return (
            merge_struct_tree,
            dest_parent_tree_next_key,
            src_map,
            dest_map,
            src_struct_tree,
            dest_struct_tree,
        )

    def _finish_struct_tree_merge(
        self,
        cloner: PDFCloneUtility,
        src_struct_tree: Any,
        dest_struct_tree: Any,
        src_number_tree_as_map: dict[int, COSBase],
        dest_number_tree_as_map: dict[int, COSBase],
        dest_parent_tree_next_key: int,
        obj_mapping: dict[int, COSDictionary],
    ) -> None:
        """Merge ``/ParentTree``, ``/K``, ``/RoleMap``, and ``/IDTree``
        from ``src_struct_tree`` into ``dest_struct_tree``.

        ``obj_mapping`` maps ``id(old_dict) -> new_dict`` for every page
        and annotation we just imported, used by
        :meth:`_update_page_references` to rewrite ``/Pg`` / ``/Obj``
        references on cloned parent-tree leaves.
        """
        from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
            PDStructureElementNumberTreeNode,
        )

        # Update /Pg, /Obj references on every source ParentTree leaf so
        # they point at the freshly-cloned destination page / annotation
        # dictionaries. We do this BEFORE re-keying so the leaves we
        # promote into dest_number_tree_as_map already carry destination
        # references.
        self._update_page_references_map(
            cloner, src_number_tree_as_map, obj_mapping
        )

        max_src_key = -1
        for src_key, value in src_number_tree_as_map.items():
            max_src_key = max(max_src_key, src_key)
            if value is not None:
                cloned = cloner.clone_for_new_document(value)
                if cloned is not None:
                    dest_number_tree_as_map[
                        dest_parent_tree_next_key + src_key
                    ] = cloned
        dest_parent_tree_next_key += max_src_key + 1

        # Rebuild /ParentTree as a flat /Nums leaf. PDFBox does the same
        # and notes that this is suboptimal for very large files; we
        # follow upstream's choice and document the trade-off in
        # CHANGES.md.
        new_parent_tree = PDStructureElementNumberTreeNode()
        new_parent_tree.set_numbers(dest_number_tree_as_map)
        dest_struct_tree.set_parent_tree(new_parent_tree)
        dest_struct_tree.set_parent_tree_next_key(dest_parent_tree_next_key)

        self._merge_k_entries(cloner, src_struct_tree, dest_struct_tree)
        self._merge_role_map(cloner, src_struct_tree, dest_struct_tree)
        self._merge_id_tree(cloner, src_struct_tree, dest_struct_tree)

    def _update_page_references_map(
        self,
        cloner: PDFCloneUtility,
        number_tree_as_map: dict[int, COSBase],
        obj_mapping: dict[int, COSDictionary],
    ) -> None:
        """Walk every value in a flattened parent-tree map and rewrite
        ``/Pg`` / ``/Obj`` references using ``obj_mapping``. Mirrors the
        ``Map<Integer, COSObjectable>`` overload of upstream
        ``updatePageReferences``."""
        for value in number_tree_as_map.values():
            if value is None:
                continue
            if isinstance(value, COSArray):
                self._update_page_references_array(cloner, value, obj_mapping)
            elif isinstance(value, COSDictionary):
                self._update_page_references_dict(cloner, value, obj_mapping)

    def _update_page_references_dict(
        self,
        cloner: PDFCloneUtility,
        parent_tree_entry: COSDictionary,
        obj_mapping: dict[int, COSDictionary],
    ) -> None:
        """Rewrite ``/Pg`` and ``/Obj`` on a single parent-tree dict leaf.
        Recurses into ``/K`` when present."""
        page_dict = parent_tree_entry.get_dictionary_object(_PG)
        if isinstance(page_dict, COSDictionary) and id(page_dict) in obj_mapping:
            parent_tree_entry.set_item(_PG, obj_mapping[id(page_dict)])

        obj_dict = parent_tree_entry.get_dictionary_object(_OBJ)
        if isinstance(obj_dict, COSDictionary):
            if id(obj_dict) in obj_mapping:
                parent_tree_entry.set_item(_OBJ, obj_mapping[id(obj_dict)])
            else:
                # Orphan reference — clone it into the destination so the
                # new struct-tree leaf doesn't dangle into the source doc.
                _LOG.debug(
                    "clone potential orphan object in structure tree: "
                    "Type=%s Subtype=%s",
                    obj_dict.get_name(_TYPE),
                    obj_dict.get_name(COSName.get_pdf_name("Subtype")),
                )
                cloned = cloner.clone_for_new_document(obj_dict)
                if cloned is not None:
                    parent_tree_entry.set_item(_OBJ, cloned)

        k_sub_entry = parent_tree_entry.get_dictionary_object(_K)
        if isinstance(k_sub_entry, COSArray):
            self._update_page_references_array(cloner, k_sub_entry, obj_mapping)
        elif isinstance(k_sub_entry, COSDictionary):
            self._update_page_references_dict(cloner, k_sub_entry, obj_mapping)

    def _update_page_references_array(
        self,
        cloner: PDFCloneUtility,
        parent_tree_entry: COSArray,
        obj_mapping: dict[int, COSDictionary],
    ) -> None:
        for i in range(parent_tree_entry.size()):
            sub_entry = parent_tree_entry.get_object(i)
            if isinstance(sub_entry, COSArray):
                self._update_page_references_array(cloner, sub_entry, obj_mapping)
            elif isinstance(sub_entry, COSDictionary):
                self._update_page_references_dict(cloner, sub_entry, obj_mapping)

    @staticmethod
    def _update_struct_parent_entries(
        page_dict: COSDictionary, struct_parent_offset: int
    ) -> None:
        """Bump ``/StructParents`` on a page and ``/StructParent`` on each
        of its annotations by ``struct_parent_offset`` so the imported
        page now points at the relocated parent-tree slot.

        Mirrors upstream ``updateStructParentEntries``. Negative existing
        values (sentinel "no parent tree entry") are left alone."""
        from pypdfbox.cos import COSInteger, COSNumber

        sp = page_dict.get_dictionary_object(_STRUCT_PARENTS)
        if isinstance(sp, COSNumber):
            current = sp.int_value()
            if current >= 0:
                page_dict.set_item(
                    _STRUCT_PARENTS, COSInteger.get(current + struct_parent_offset)
                )

        annots = page_dict.get_dictionary_object(_ANNOTS)
        if isinstance(annots, COSArray):
            for i in range(annots.size()):
                entry = annots.get_object(i)
                if not isinstance(entry, COSDictionary):
                    continue
                ap = entry.get_dictionary_object(_STRUCT_PARENT)
                if isinstance(ap, COSNumber):
                    current = ap.int_value()
                    if current >= 0:
                        entry.set_item(
                            _STRUCT_PARENT,
                            COSInteger.get(current + struct_parent_offset),
                        )

    def _merge_k_entries(
        self,
        cloner: PDFCloneUtility,
        src_struct_tree: Any,
        dest_struct_tree: Any,
    ) -> None:
        """Merge ``/K`` arrays under the destination ``/StructTreeRoot``.

        Mirrors upstream ``mergeKEntries``: if the destination's existing
        top-level /K is a single ``/Document`` whose own /K is a list of
        only Documents-or-Parts, the source's /K children are appended
        directly. Otherwise the source and destination /K entries are
        wrapped under a fresh top-level ``/Document`` dict."""
        src_root = src_struct_tree.get_cos_object()
        dest_root = dest_struct_tree.get_cos_object()
        src_k_entry = src_root.get_dictionary_object(_K)

        src_k_array = COSArray()
        cloned_src_k = cloner.clone_for_new_document(src_k_entry)
        if isinstance(cloned_src_k, COSArray):
            for i in range(cloned_src_k.size()):
                src_k_array.add(cloned_src_k.get(i))
        elif isinstance(cloned_src_k, COSDictionary):
            src_k_array.add(cloned_src_k)

        if src_k_array.size() == 0:
            return

        dst_k_array = COSArray()
        dst_k_entry = dest_root.get_dictionary_object(_K)
        if isinstance(dst_k_entry, COSArray):
            for i in range(dst_k_entry.size()):
                dst_k_array.add(dst_k_entry.get(i))
        elif isinstance(dst_k_entry, COSDictionary):
            dst_k_array.add(dst_k_entry)

        if dst_k_array.size() == 1 and isinstance(
            dst_k_array.get_object(0), COSDictionary
        ):
            top_k_dict = dst_k_array.get_object(0)
            assert isinstance(top_k_dict, COSDictionary)
            if top_k_dict.get_name(_S) == _DOCUMENT.get_name():
                k_level_one = top_k_dict.get_dictionary_object(_K)
                if isinstance(
                    k_level_one, COSArray
                ) and self._has_only_documents_or_parts(k_level_one):
                    for i in range(src_k_array.size()):
                        k_level_one.add(src_k_array.get(i))
                    self._update_parent_entry(k_level_one, top_k_dict, _PART)
                    return

        if dst_k_array.size() == 0:
            self._update_parent_entry(src_k_array, dest_root, None)
            dest_root.set_item(_K, src_k_array)
            return

        for i in range(src_k_array.size()):
            dst_k_array.add(src_k_array.get(i))
        k_level_zero = COSDictionary()
        new_struct_type = (
            _PART if self._has_only_documents_or_parts(dst_k_array) else None
        )
        self._update_parent_entry(dst_k_array, k_level_zero, new_struct_type)
        k_level_zero.set_item(_K, dst_k_array)
        k_level_zero.set_item(_P, dest_root)
        k_level_zero.set_item(_S, _DOCUMENT)
        dest_root.set_item(_K, k_level_zero)

    @staticmethod
    def _has_only_documents_or_parts(k_array: COSArray) -> bool:
        for i in range(k_array.size()):
            base = k_array.get_object(i)
            if not isinstance(base, COSDictionary):
                return False
            s = base.get_name(_S)
            if s != _DOCUMENT.get_name() and s != _PART.get_name():
                return False
        return True

    @staticmethod
    def _update_parent_entry(
        k_array: COSArray,
        new_parent: COSDictionary,
        new_structure_type: COSName | None,
    ) -> None:
        """Re-point each ``/P`` entry under ``k_array``'s child dicts at
        ``new_parent``, and (when given) overwrite their ``/S`` with
        ``new_structure_type``. Mirrors upstream ``updateParentEntry``."""
        for i in range(k_array.size()):
            sub = k_array.get_object(i)
            if isinstance(sub, COSDictionary):
                sub.set_item(_P, new_parent)
                if new_structure_type is not None:
                    sub.set_item(_S, new_structure_type)

    def _merge_role_map(
        self,
        cloner: PDFCloneUtility,
        src_struct_tree: Any,
        dest_struct_tree: Any,
    ) -> None:
        """Overlay the source ``/RoleMap`` on the destination's. The
        destination wins on conflict — duplicate keys log a warning and
        the source value is dropped, matching upstream
        ``mergeRoleMap``."""
        src_dict = src_struct_tree.get_cos_object().get_dictionary_object(_ROLE_MAP)
        if not isinstance(src_dict, COSDictionary):
            return
        dest_root = dest_struct_tree.get_cos_object()
        dest_dict = dest_root.get_dictionary_object(_ROLE_MAP)
        if not isinstance(dest_dict, COSDictionary):
            cloned = cloner.clone_for_new_document(src_dict)
            if cloned is not None:
                dest_root.set_item(_ROLE_MAP, cloned)
            return
        for key, value in list(src_dict.entry_set()):
            existing = dest_dict.get_dictionary_object(key)
            if existing is not None and existing == value:
                continue
            if dest_dict.contains_key(key):
                _LOG.warning(
                    "key '%s' already exists in destination RoleMap", key
                )
            else:
                cloned = cloner.clone_for_new_document(value)
                if cloned is not None:
                    dest_dict.set_item(key, cloned)

    def _merge_id_tree(
        self,
        cloner: PDFCloneUtility,
        src_struct_tree: Any,
        dest_struct_tree: Any,
    ) -> None:
        """Fold the source ``/IDTree`` into the destination's. Duplicate
        keys log a warning and the source entry is dropped (dest wins),
        matching upstream ``mergeIDTree``."""
        from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
            PDStructureElementNameTreeNode,
        )

        src_id_tree = src_struct_tree.get_id_tree()
        if src_id_tree is None:
            return
        dest_id_tree = dest_struct_tree.get_id_tree()
        src_names = self.get_id_tree_as_map(src_id_tree)
        dest_names = (
            self.get_id_tree_as_map(dest_id_tree) if dest_id_tree is not None else {}
        )
        for key, value in src_names.items():
            if key in dest_names:
                _LOG.warning(
                    "key '%s' already exists in destination IDTree", key
                )
                continue
            if value is None:
                continue
            cloned = cloner.clone_for_new_document(value)
            if cloned is not None:
                dest_names[key] = cloned
        new_id_tree = PDStructureElementNameTreeNode()
        # set_names on a name-tree wraps into PDStructureElement; feed it
        # the raw COS dict so the wrap step is a no-op.
        from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
            PDStructureElement,
        )

        wrapped = {
            k: PDStructureElement(v) if isinstance(v, COSDictionary) else v
            for k, v in dest_names.items()
        }
        new_id_tree.set_names(wrapped)
        dest_struct_tree.set_id_tree(new_id_tree)


__all__ = [
    "AcroFormMergeMode",
    "DocumentMergeMode",
    "PDFMergerUtility",
]
