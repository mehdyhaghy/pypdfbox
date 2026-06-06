from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSObject,
)

if TYPE_CHECKING:
    from pypdfbox.io import MemoryUsageSetting
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage


_LOG = logging.getLogger(__name__)

_TYPE: COSName = COSName.get_pdf_name("Type")
_RESOURCES: COSName = COSName.get_pdf_name("Resources")
_B: COSName = COSName.get_pdf_name("B")
_PARENT: COSName = COSName.get_pdf_name("Parent")
_POPUP: COSName = COSName.get_pdf_name("Popup")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_FT: COSName = COSName.get_pdf_name("FT")
_SIG: COSName = COSName.get_pdf_name("Sig")
_V: COSName = COSName.get_pdf_name("V")
_ACROFORM: COSName = COSName.get_pdf_name("AcroForm")
_SIG_FLAGS: COSName = COSName.get_pdf_name("SigFlags")
_FIELDS: COSName = COSName.get_pdf_name("Fields")

# struct-tree clone helpers
_K: COSName = COSName.get_pdf_name("K")
_P: COSName = COSName.get_pdf_name("P")
_PG: COSName = COSName.get_pdf_name("Pg")
_S: COSName = COSName.get_pdf_name("S")
_ID: COSName = COSName.get_pdf_name("ID")
_OBJ: COSName = COSName.get_pdf_name("Obj")
_OBJR: COSName = COSName.get_pdf_name("OBJR")
_MCR: COSName = COSName.get_pdf_name("MCR")
_ANNOT: COSName = COSName.get_pdf_name("Annot")
_LINK: COSName = COSName.get_pdf_name("Link")
_ANNOTS: COSName = COSName.get_pdf_name("Annots")
_ROLE_MAP: COSName = COSName.get_pdf_name("RoleMap")
_CLASS_MAP: COSName = COSName.get_pdf_name("ClassMap")


class Splitter:
    """
    Split a ``PDDocument`` into one or more smaller documents. Mirrors
    ``org.apache.pdfbox.multipdf.Splitter``.

    Public surface:

    - :meth:`set_split_at_page` (alias :meth:`set_split`) — pages per chunk;
    - :meth:`set_start_page`, :meth:`set_end_page` — 1-based inclusive
      page range;
    - :meth:`set_memory_usage_setting` /
      :meth:`set_stream_cache_create_function` — recorded but advisory in
      this port (see ``CHANGES.md``);
    - :meth:`split` — returns ``list[PDDocument]``.

    Subclassing hooks (mirroring upstream ``protected`` methods):
    :meth:`split_at_page`, :meth:`create_new_document`,
    :meth:`process_page`, :meth:`get_source_document`,
    :meth:`get_destination_document`.

    The structure-tree / parent-tree / id-tree / role-map cloning that
    upstream performs after the page walk is implemented here in full —
    see :meth:`clone_structure_tree`. Cross-chunk link-annotation
    destinations are nulled out in :meth:`fix_destinations` so the
    chunk's `/Dest` payloads don't carry refs to pages that didn't
    follow the split.
    """

    # ---------- defaults & sentinels (class constants) ----------
    #
    # Mirrors the field initialisers on upstream
    # ``org.apache.pdfbox.multipdf.Splitter``. Surfacing them as class
    # constants lets callers compare ``get_start_page() ==
    # Splitter.START_PAGE_DEFAULT`` (or use :meth:`has_start_page`) to
    # distinguish "untouched" from "explicitly set to N" — same semantic
    # as upstream's ``Integer.MIN_VALUE`` / ``Integer.MAX_VALUE`` sentinels.

    #: Default split granularity — every page becomes a new document.
    DEFAULT_SPLIT_LENGTH: int = 1

    #: Sentinel meaning "no lower clamp". Mirrors upstream's
    #: ``Integer.MIN_VALUE`` initialiser on ``startPage``.
    START_PAGE_DEFAULT: int = -(2**31)

    #: Sentinel meaning "no upper clamp". Mirrors upstream's
    #: ``Integer.MAX_VALUE`` initialiser on ``endPage``.
    END_PAGE_DEFAULT: int = 2**31 - 1

    def __init__(self) -> None:
        self._source_document: PDDocument | None = None
        self._current_destination_document: PDDocument | None = None

        self._split_length: int = self.DEFAULT_SPLIT_LENGTH
        # Sentinels used to mean "no clamp"; mirror upstream
        # Integer.MIN_VALUE / Integer.MAX_VALUE.
        self._start_page: int = self.START_PAGE_DEFAULT
        self._end_page: int = self.END_PAGE_DEFAULT

        self._destination_documents: list[PDDocument] = []
        self._page_dict_map: dict[int, COSDictionary] = {}
        self._page_dict_maps: list[dict[int, COSDictionary]] = []
        self._annot_dict_map: dict[int, COSDictionary] = {}
        self._annot_dict_maps: list[dict[int, COSDictionary]] = []
        # struct-tree clone state, reset per chunk
        self._struct_dict_map: dict[int, COSDictionary] = {}
        self._id_set: set[str] = set()
        self._role_set: set[str] = set()
        # destToFixMap mirror — list of (cloned_dest_array, source_host_page_dict,
        # source_target_page_dict) per chunk. Deferred to after the page walk
        # so we can decide whether each destination's target page lives in
        # the chunk.
        #
        # ``source_target_page_dict`` is the page the destination *points to*,
        # captured before ``import_page``'s deep-copy replaced the indirect
        # ref's resolved target with a fresh COSDictionary instance. Without
        # that snapshot, the post-pass ``_page_dict_map`` lookup keyed by
        # ``id()`` misses cross-page targets (wave 1294).
        self._dest_to_fix: list[
            tuple[COSArray, COSDictionary, COSDictionary | None]
        ] = []
        self._dest_to_fix_per_chunk: list[
            list[tuple[COSArray, COSDictionary, COSDictionary | None]]
        ] = []
        # Wave-1379 side-table keyed by ``id(cloned_array)`` carrying the
        # cloned link annotation that hosts each cloned destination. Drained
        # by :meth:`fix_destinations` only when the cross-chunk resolver
        # opted into a GoToR rewrite — we need direct access to the
        # annotation dict to swap its ``/Dest`` (or ``/A GoTo``) entry for a
        # ``/A GoToR`` action. Kept separate from ``_dest_to_fix`` so the
        # historical 3-tuple shape (and the legacy 2-tuple fallback in
        # :meth:`fix_destinations`) remain wire-compatible.
        self._dest_to_link_map: dict[int, COSDictionary] = {}
        self._dest_to_link_map_per_chunk: list[dict[int, COSDictionary]] = []
        # Per-chunk queue of (cloned_annotations, source_annots_array,
        # imported_page_dict) tuples populated by ``_process_annotations``'
        # first pass and drained by ``_finalize_annotation_links`` after
        # *every* page in the chunk has been imported. Deferring the
        # second pass lets a markup annotation on chunk page A correctly
        # rewrite its ``/Popup`` to a popup annotation on chunk page B
        # (wave 1373): the per-page run order otherwise meant page A's
        # second pass executed before page B's first pass populated
        # ``_annot_dict_map`` with the cloned popup. Mirrors the upstream
        # invariant that ``annotDictMap`` is chunk-wide; the only behaviour
        # change is that we look up the same map *later* so cross-page
        # annotation refs in the same chunk resolve to cloned dicts.
        self._pending_annot_passes: list[
            tuple[list[Any], COSArray | None, COSDictionary | None]
        ] = []
        self._pending_annot_passes_per_chunk: list[
            list[tuple[list[Any], COSArray | None, COSDictionary | None]]
        ] = []

        self._current_page_number: int = 0

        self._stream_cache_create_function: Callable[[], Any] | None = None
        self._memory_usage_setting: MemoryUsageSetting | None = None

        # Wave 1379: opt-in callback that the post-pass calls when a cloned
        # link's target page lives outside the chunk that hosts the link. The
        # resolver receives the *source* target page COSDictionary and may
        # return:
        #
        #   * ``None`` — keep the historical null-out behaviour (the cloned
        #     destination's ``/D[0]`` slot becomes ``COSNull``);
        #   * ``str`` — interpret the returned value as a relative file name
        #     and rewrite the link's destination into a GoToR action targeting
        #     that file. The original explicit-fit-mode array (``[null /XYZ
        #     left top zoom]`` etc.) is preserved verbatim except for the
        #     ``[0]`` page slot, which is replaced by the *integer page index*
        #     within the target file. The caller is responsible for arranging
        #     the per-chunk filename mapping (typically by computing it from
        #     ``Splitter.split()``'s return order).
        #
        # Mirrors the PDFBox forum / mailing-list pattern of post-processing
        # split outputs to retarget cross-chunk links — upstream's
        # ``Splitter`` ships only the null-out strategy, so this is a strict
        # parity extension.
        self._cross_chunk_destination_resolver: (
            Callable[[COSDictionary], tuple[str, int] | str | None] | None
        ) = None

    # ---------- configuration ----------

    def set_split_at_page(self, split: int) -> Splitter:
        """Set the split granularity. Mirrors upstream
        ``setSplitAtPage(int)`` — rejects ``split <= 0``. Returns ``self``
        so callers can chain configuration calls."""
        if split <= 0:
            raise ValueError("Number of pages is smaller than one")
        self._split_length = split
        return self

    def set_split(self, split: int) -> Splitter:
        """Alias for :meth:`set_split_at_page`. Returns ``self`` for
        fluent chaining."""
        return self.set_split_at_page(split)

    def get_split_at_page(self) -> int:
        """Return the configured split granularity. Defaults to
        :attr:`DEFAULT_SPLIT_LENGTH` (= 1) when no setter has been called.
        Upstream lacks this getter — surfaced here so callers and tests
        don't need to read the private field directly."""
        return self._split_length

    def set_start_page(self, start: int) -> Splitter:
        """Set the 1-based inclusive lower page bound. Mirrors upstream
        ``setStartPage(int)`` — rejects ``start <= 0``. Returns ``self``
        for fluent chaining."""
        if start <= 0:
            raise ValueError("Start page is smaller than one")
        self._start_page = start
        return self

    def get_start_page(self) -> int:
        """Return the configured start page. Defaults to
        :attr:`START_PAGE_DEFAULT` (= ``Integer.MIN_VALUE``) when no
        setter has been called — use :meth:`has_start_page` to
        distinguish "untouched" from "explicitly set"."""
        return self._start_page

    def has_start_page(self) -> bool:
        """``True`` when :meth:`set_start_page` has been called with an
        explicit value (i.e. the field is not the default sentinel).
        Predicate helper that lets callers branch on "user supplied a
        bound" vs "no clamp" without having to know the sentinel value."""
        return self._start_page != self.START_PAGE_DEFAULT

    def set_end_page(self, end: int) -> Splitter:
        """Set the 1-based inclusive upper page bound. Mirrors upstream
        ``setEndPage(int)`` — rejects ``end <= 0`` and ``end <
        startPage`` (when start was explicitly set). Returns ``self``
        for fluent chaining."""
        if end <= 0:
            raise ValueError("End page is smaller than one")
        if end < self._start_page:
            raise ValueError("End page is smaller than startPage")
        self._end_page = end
        return self

    def get_end_page(self) -> int:
        """Return the configured end page. Defaults to
        :attr:`END_PAGE_DEFAULT` (= ``Integer.MAX_VALUE``) when no
        setter has been called — use :meth:`has_end_page` to
        distinguish "untouched" from "explicitly set"."""
        return self._end_page

    def has_end_page(self) -> bool:
        """``True`` when :meth:`set_end_page` has been called with an
        explicit value (i.e. the field is not the default sentinel)."""
        return self._end_page != self.END_PAGE_DEFAULT

    def get_stream_cache_create_function(self) -> Callable[[], Any] | None:
        return self._stream_cache_create_function

    def set_stream_cache_create_function(
        self, fn: Callable[[], Any] | None
    ) -> Splitter:
        """Record the stream-cache factory used for new destination
        documents. Returns ``self`` for fluent chaining."""
        self._stream_cache_create_function = fn
        return self

    def has_stream_cache_create_function(self) -> bool:
        """``True`` when a stream-cache factory has been registered."""
        return self._stream_cache_create_function is not None

    def set_memory_usage_setting(
        self, setting: MemoryUsageSetting | None
    ) -> Splitter:
        """Record a :class:`MemoryUsageSetting` for newly-created destination
        documents. Recorded only — destination ``PDDocument`` construction
        in this port does not yet thread the setting through (see
        ``CHANGES.md``). Returns ``self`` for fluent chaining."""
        self._memory_usage_setting = setting
        return self

    def get_memory_usage_setting(self) -> MemoryUsageSetting | None:
        return self._memory_usage_setting

    def has_memory_usage_setting(self) -> bool:
        """``True`` when a :class:`MemoryUsageSetting` has been registered."""
        return self._memory_usage_setting is not None

    def set_cross_chunk_destination_resolver(
        self,
        resolver: (
            Callable[[COSDictionary], tuple[str, int] | str | None] | None
        ),
    ) -> Splitter:
        """Register a callback used by :meth:`fix_destinations` to rewrite
        cross-chunk link destinations as ``GoToR`` actions.

        Wave-1379 extension closing the DEFERRED entry for the splitter's
        full §12.3.2.3 destination-rewrite coverage. The resolver receives
        the *source* target page :class:`COSDictionary` (the page the cloned
        link points at, captured before ``import_page``'s deep-copy) and
        returns one of:

        * ``None`` — keep historical null-out behaviour;
        * a plain ``str`` — interpret as the relative file name of the
          sibling chunk file that contains the target page; the link's
          ``/D[0]`` slot is replaced by the *integer page index* the
          resolver reports via the second tuple form below, or by ``0``
          when only a string is returned (caller should prefer the tuple
          form to retain page identity);
        * a ``(file_name, page_index)`` tuple — explicit file + 0-based
          page index pair, matching the canonical PDF 32000-1 §12.6.4.3
          ``GoToR`` payload.

        Returns ``self`` for fluent chaining."""
        self._cross_chunk_destination_resolver = resolver
        return self

    def get_cross_chunk_destination_resolver(
        self,
    ) -> Callable[[COSDictionary], tuple[str, int] | str | None] | None:
        """Return the cross-chunk destination resolver registered via
        :meth:`set_cross_chunk_destination_resolver`, or ``None``."""
        return self._cross_chunk_destination_resolver

    def has_cross_chunk_destination_resolver(self) -> bool:
        """``True`` when a cross-chunk destination resolver is registered."""
        return self._cross_chunk_destination_resolver is not None

    # ---------- core ----------

    def split(self, document: PDDocument) -> list[PDDocument]:
        """Split ``document`` and return a list of fresh ``PDDocument``
        instances. The caller owns each returned document and must save
        them before closing ``document`` (cross-document resource sharing
        means the source must outlive its splits)."""
        self._current_page_number = 0
        self._current_destination_document = None
        self._destination_documents = []
        self._source_document = document
        self._page_dict_maps = []
        self._annot_dict_maps = []
        self._dest_to_fix_per_chunk = []
        self._dest_to_link_map_per_chunk = []
        self._pending_annot_passes_per_chunk = []
        self._id_set = set()
        self._role_set = set()
        # Track whether any chunk dropped a signature widget; clear
        # /SigFlags + scrub /AcroForm in destination catalogs at the end.
        self._signatures_dropped: bool = False

        self._process_pages()

        # Post-pass per chunk: structure tree clone + destination fix-up.
        for index, destination_document in enumerate(self._destination_documents):
            self._page_dict_map = self._page_dict_maps[index]
            self._annot_dict_map = self._annot_dict_maps[index]
            self._dest_to_fix = self._dest_to_fix_per_chunk[index]
            self._dest_to_link_map = self._dest_to_link_map_per_chunk[index]
            self._pending_annot_passes = (
                self._pending_annot_passes_per_chunk[index]
            )
            # Drain the deferred markup/popup linkage pass once
            # ``_annot_dict_map`` reflects every page in the chunk.
            try:
                self._finalize_annotation_links()
            except Exception:  # noqa: BLE001
                _LOG.exception(
                    "annotation linkage finalisation failed for chunk %d; "
                    "popup/markup back-pointers may dangle",
                    index,
                )
            try:
                # Dispatch via the underscored alias so subclasses can
                # override either the public ``clone_structure_tree`` or
                # the upstream-private ``_clone_structure_tree`` and have
                # the override picked up.
                self._clone_structure_tree(destination_document)
            except Exception:  # noqa: BLE001
                _LOG.exception(
                    "structure-tree clone failed for chunk %d; chunk will "
                    "ship without /StructTreeRoot",
                    index,
                )
            try:
                self._fix_destinations(destination_document)
            except Exception:  # noqa: BLE001
                _LOG.exception(
                    "destination fix-up failed for chunk %d; cross-chunk "
                    "/Dest links may dangle",
                    index,
                )
            try:
                self._scrub_acroform(destination_document)
            except Exception:  # noqa: BLE001
                _LOG.exception(
                    "AcroForm scrub failed for chunk %d; signature flags "
                    "may persist in chunk catalog",
                    index,
                )
        return self._destination_documents

    # ---------- pagination loop ----------

    def _process_pages(self) -> None:
        assert self._source_document is not None
        for page in self._source_document.get_pages():
            page_one_based = self._current_page_number + 1
            if self._start_page <= page_one_based <= self._end_page:
                self.process_page(page)
                self._current_page_number += 1
            else:
                if self._current_page_number > self._end_page:
                    break
                self._current_page_number += 1

    def process_pages(self) -> None:
        """Public-named hook for the pagination loop.

        Mirrors upstream ``processPages`` (protected in Java). Subclasses
        can override either this method or the underscored
        :py:meth:`_process_pages`; the default :py:meth:`split` driver
        always calls the underscored variant so internal callers do not
        accidentally pick up a subclass override they didn't ask for.
        """
        self._process_pages()

    # ---------- subclass hooks (mirror upstream protected methods) ----------

    def split_at_page(self, page_number: int) -> bool:
        """Return ``True`` when a new destination document should be
        created before processing ``page_number`` (0-based). Default
        behaviour matches upstream:

            (page_number + 1 - max(1, start_page)) % split_length == 0
        """
        return (
            page_number + 1 - max(1, self._start_page)
        ) % self._split_length == 0

    def create_new_document(self) -> PDDocument:
        """Build the next destination ``PDDocument``. Copies version and
        a sanitised ``/Info`` dictionary from the source, plus the
        catalog-level entries upstream copies (``/ViewerPreferences``,
        ``/Lang``, ``/MarkInfo``, ``/Metadata``) when the corresponding
        accessors are available."""
        from pypdfbox.pdmodel.pd_document import PDDocument
        from pypdfbox.pdmodel.pd_document_information import (
            PDDocumentInformation,
        )

        assert self._source_document is not None
        document = PDDocument()
        document.get_document().set_version(
            self.get_source_document().get_version()
        )

        src_info = self.get_source_document().get_document_information()
        if src_info is not None:
            src_info_dict = src_info.get_cos_object()
            dst_info_dict = COSDictionary()
            src_catalog_dict = (
                self.get_source_document().get_document_catalog().get_cos_object()
            )
            for key in list(src_info_dict.key_set()):
                value = src_info_dict.get_dictionary_object(key)
                if isinstance(value, COSDictionary):
                    _LOG.warning(
                        "Nested entry for key '%s' skipped in document "
                        "information dictionary",
                        key.get_name(),
                    )
                    if src_catalog_dict is src_info_dict:
                        _LOG.warning("/Root and /Info share the same dictionary")
                    continue
                if key == _TYPE:
                    continue
                dst_info_dict.set_item(key, value)
            document.set_document_information(
                PDDocumentInformation(dst_info_dict)
            )

        dst_catalog = document.get_document_catalog()
        src_catalog = self.get_source_document().get_document_catalog()
        with contextlib.suppress(AttributeError, NotImplementedError):
            dst_catalog.set_viewer_preferences(src_catalog.get_viewer_preferences())
        with contextlib.suppress(AttributeError, NotImplementedError):
            dst_catalog.set_language(src_catalog.get_language())
        with contextlib.suppress(AttributeError, NotImplementedError):
            dst_catalog.set_mark_info(src_catalog.get_mark_info())
        with contextlib.suppress(AttributeError, NotImplementedError):
            dst_catalog.set_metadata(src_catalog.get_metadata())
        return document

    def process_page(self, page: PDPage) -> None:
        """Import ``page`` into the current destination document, opening
        a fresh destination first when :meth:`split_at_page` says so."""
        self._create_new_document_if_necessary()
        assert self._current_destination_document is not None

        imported = self._current_destination_document.import_page(page)

        # Materialise the inheritable page-geometry attributes on the
        # imported page dict. Upstream's ``Splitter.processPage`` gets this
        # for free because ``PDDocument.importPage`` (PDDocument.java lines
        # 700-702) explicitly re-applies ``setCropBox`` / ``setMediaBox`` /
        # ``setRotation`` from the *resolved* source values right after the
        # shallow page-dict copy + ``/Parent`` removal. Our port's
        # ``PDDocument.import_page`` does a deep-copy + ``/Parent`` strip but
        # does NOT re-apply those three setters, so a source page that
        # *inherited* its ``/MediaBox`` / ``/CropBox`` / ``/Rotate`` from a
        # page-tree node loses them once detached from the source tree and
        # falls back to the Letter / 0 defaults. Re-applying here keeps the
        # Splitter (and the PageExtractor that delegates to it) byte-for-byte
        # aligned with upstream's importPage materialisation. Each setter is
        # guarded because a malformed source page may raise while resolving
        # the inherited value — upstream would throw, but we prefer to ship
        # the chunk with whatever geometry survived rather than abort the
        # whole split.
        try:
            imported.set_crop_box(page.get_crop_box())
        except Exception as exc:  # noqa: BLE001
            _LOG.debug("set_crop_box failed during split: %s", exc)
        try:
            imported.set_media_box(page.get_media_box())
        except Exception as exc:  # noqa: BLE001
            _LOG.debug("set_media_box failed during split: %s", exc)
        try:
            imported.set_rotation(page.get_rotation())
        except Exception as exc:  # noqa: BLE001
            _LOG.debug("set_rotation failed during split: %s", exc)

        # Mirror upstream: if the source page had a /Resources but the
        # imported one didn't carry it through (because the inheritable
        # path was used), copy the resources dict directly so the chunk
        # is self-sufficient.
        try:
            page_resources = page.get_resources()
        except Exception:  # noqa: BLE001
            page_resources = None
        if (
            page_resources is not None
            and not page.get_cos_object().contains_key(_RESOURCES)
        ):
            try:
                imported.set_resources(page_resources)
                _LOG.info("Resources imported in Splitter")
            except Exception:  # noqa: BLE001
                pass

        if imported.get_cos_object().contains_key(_B):
            imported.get_cos_object().remove_item(_B)
            _LOG.warning("/B entry (beads) removed by splitter")

        self._process_annotations(page, imported)

        self._page_dict_map[id(page.get_cos_object())] = imported.get_cos_object()

    def get_source_document(self) -> PDDocument:
        assert self._source_document is not None
        return self._source_document

    def get_destination_document(self) -> PDDocument:
        assert self._current_destination_document is not None
        return self._current_destination_document

    # ---------- internals ----------

    def _create_new_document_if_necessary(self) -> None:
        if (
            self.split_at_page(self._current_page_number)
            or self._current_destination_document is None
        ):
            self._current_destination_document = self.create_new_document()
            self._destination_documents.append(self._current_destination_document)
            self._page_dict_map = {}
            self._page_dict_maps.append(self._page_dict_map)
            self._annot_dict_map = {}
            self._annot_dict_maps.append(self._annot_dict_map)
            self._dest_to_fix = []
            self._dest_to_fix_per_chunk.append(self._dest_to_fix)
            self._dest_to_link_map = {}
            self._dest_to_link_map_per_chunk.append(self._dest_to_link_map)
            self._pending_annot_passes = []
            self._pending_annot_passes_per_chunk.append(
                self._pending_annot_passes
            )

    def create_new_document_if_necessary(self) -> None:
        """Public-named hook mirroring upstream ``createNewDocumentIfNecessary``.

        Allocates the next destination document when :py:meth:`split_at_page`
        signals a chunk boundary (or when no destination has been
        created yet). Delegates to :py:meth:`_create_new_document_if_necessary`.
        """
        self._create_new_document_if_necessary()

    def process_annotations(self, imported: PDPage) -> None:
        """Public-named hook for annotation handling.

        Mirrors upstream protected ``processAnnotations(PDPage)`` —
        accepts the imported page only (upstream signature) and delegates
        to the underscored impl with a ``None`` source page. Most
        subclasses will simply override this entry point; the internal
        :py:meth:`_process_annotations` retains its richer signature so
        the default link-destination plumbing still has access to the
        original source page.
        """
        self._process_annotations(imported, imported)

    def _process_annotations(self, source_page: PDPage, imported: PDPage) -> None:
        """Shallow-clone every annotation on ``imported`` so structure-tree
        edits and ``/Parent`` rewrites (e.g. for widget annotations) don't
        bleed back into the source document. Mirrors upstream's
        ``processAnnotations``.

        Signature widgets are dropped entirely (split documents have a
        different byte range, so any contained signature would be invalid
        anyway — see :meth:`_is_signature_widget`).

        Annotation ``/P`` back-pointers are rewritten to the *imported*
        page's COSDictionary so ``ann.get_page() == dst_doc.get_page(N)``
        holds for callers walking the chunk (upstream relies on Java
        default ``Object.equals`` = identity; we mirror that by replacing
        the back-pointer with the cloned page's dict).

        Each cloned annot dict is mapped from BOTH its source-annot id and
        the imported (deep-copy) annot id in ``_annot_dict_map`` so the
        second pass's ``/Popup`` lookup hits regardless of whether the
        deep-copy's cycle-break path returned the source instance or a
        fresh clone for cross-annotation refs in the same page.
        """
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation import (
            PDAnnotation,
        )
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
            PDAnnotationLink,
        )

        try:
            annotations = imported.get_annotations()
        except Exception:  # noqa: BLE001
            return
        if not annotations:
            return
        try:
            imported_page_dict = imported.get_cos_object()
        except AttributeError:
            imported_page_dict = None

        # Source-side /Annots array (when available) lets us index into
        # the original annot dicts. Upstream iterates the imported page
        # which still shares /Annots with the source (shallow page copy);
        # our import_page does a deep page-graph clone, so the source
        # array gives us the only handle on the original-identity annot
        # dicts that downstream consumers (e.g. struct-tree clone's OBJR
        # rewrites) expect as keys.
        source_annots_array = None
        try:
            source_page_dict = source_page.get_cos_object()
        except AttributeError:
            source_page_dict = None
        if isinstance(source_page_dict, COSDictionary):
            value = source_page_dict.get_dictionary_object(_ANNOTS)
            if isinstance(value, COSArray):
                source_annots_array = value

        cloned: list[PDAnnotation] = []
        for index, ann in enumerate(annotations):
            ann_dict = ann.get_cos_object()

            # Skip signature widgets entirely. Either the widget IS the
            # field (merged) and /FT=Sig, or its /Parent chain leads to
            # a /FT=Sig field, or it has /V pointing at a signature dict.
            if self._is_signature_widget(ann_dict):
                self._signatures_dropped = True
                continue

            cloned_dict = COSDictionary(list(ann_dict.entry_set()))
            self._annot_dict_map[id(ann_dict)] = cloned_dict
            # Map the source-side annot dict too — downstream consumers
            # (struct-tree clone's OBJR lookup, popup back-ref rewriting)
            # use source ids as keys.
            if source_annots_array is not None and index < source_annots_array.size():
                source_ann_dict = source_annots_array.get_object(index)
                if isinstance(source_ann_dict, COSDictionary):
                    self._annot_dict_map[id(source_ann_dict)] = cloned_dict
            cloned_ann = PDAnnotation.create(cloned_dict)
            cloned.append(cloned_ann)

            # Drop /Parent for widget annotations to avoid orphan /Parent
            # references into form fields that didn't follow the split.
            try:
                subtype = cloned_dict.get_name(_SUBTYPE)
            except AttributeError:
                subtype = None
            if subtype == "Widget" and cloned_dict.contains_key(_PARENT):
                cloned_dict.remove_item(_PARENT)

            # Link annotations: clone /Dest (or the action's /D) and
            # remember the cloned destination so the post-pass can either
            # rewrite its /D[0] to the cloned destination page or null it
            # out when the target page is in a different chunk.
            #
            # Pass the *source* annot dict (when available) so the staging
            # step can resolve the destination's target page through the
            # un-deep-copied source object graph. ``import_page``'s deep-copy
            # replaces each indirect-ref target with a fresh COSDictionary,
            # so reading ``/A /D [0]`` off ``cloned_ann`` (which wraps the
            # imported annot's clone) would lose source-page identity and
            # break the post-pass ``_page_dict_map`` lookup.
            if isinstance(cloned_ann, PDAnnotationLink):
                source_link_dict: COSDictionary | None = None
                if (
                    source_annots_array is not None
                    and index < source_annots_array.size()
                ):
                    candidate = source_annots_array.get_object(index)
                    if isinstance(candidate, COSDictionary):
                        source_link_dict = candidate
                self._stage_link_destination(
                    cloned_ann,
                    source_page.get_cos_object(),
                    source_link_dict,
                )

            # Rewrite the cloned annot's /P back-pointer to the imported
            # page dict whenever the source had a page back-ref. Mirrors
            # upstream ``processAnnotations`` (Splitter.java line 921-924):
            # ``if (annotation.getPage() != null) annotationClone.setPage(imported)``.
            # Without this, the deep-copy cycle-break path in
            # ``_deep_copy_cos`` leaves /P pointing at the *source* page,
            # breaking annotation/page identity for chunk consumers.
            if (
                imported_page_dict is not None
                and hasattr(ann, "get_page")
                and ann.get_page() is not None
            ):
                cloned_ann.set_page(imported_page_dict)

        # Second pass (popup/markup linkage) is deferred to
        # :meth:`_finalize_annotation_links`. Running it inline here would
        # only see this page's contribution to ``_annot_dict_map`` — a
        # markup on chunk page A whose ``/Popup`` lives on chunk page B
        # would be processed before page B's first pass populated the
        # cloned popup dict, so the second-pass lookup would miss and
        # leave the markup's ``/Popup`` pointing at a deep-copy dict that
        # isn't the chunk's actual popup (wave 1373). Stash the per-page
        # context and drain after every page in the chunk has been
        # imported.
        self._pending_annot_passes.append(
            (cloned, source_annots_array, imported_page_dict)
        )

        with contextlib.suppress(Exception):
            imported.set_annotations(cloned)

    def _finalize_annotation_links(self) -> None:
        """Run the deferred markup/popup second pass for every page in
        the current chunk.

        Mirrors upstream ``processAnnotations`` second loop
        (Splitter.java lines 926-967) — rewrites ``/Popup`` on markup
        annots to the chunk's cloned popup dict, ``/Parent`` on popups
        to the chunk's cloned markup dict, and clones orphan popups (not
        in any page's ``/Annots``) re-linking them via ``/Popup`` ↔
        ``/Parent`` with ``/P`` pinned to the markup's imported page.
        Defers the second-pass walk relative to upstream so the lookup
        sees ``_annot_dict_map`` populated by *every* page in the chunk,
        not just the page that hosts the markup — without this, a markup
        on page A whose popup lives on page B of the same chunk would
        leave the markup's ``/Popup`` pointing at the deep-copied source
        popup instead of the chunk's cloned popup.

        Popup-side ``/Parent`` resolution still falls back to nulling the
        entry when the markup annotation didn't follow the split, per
        upstream's ``setItem(PARENT, null)`` behaviour for orphan markups.
        """
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (  # noqa: E501
            PDAnnotationMarkup,
        )
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation_popup import (  # noqa: E501
            PDAnnotationPopup,
        )

        for entry in self._pending_annot_passes:
            cloned, source_annots_array, imported_page_dict = entry
            clone_index = 0
            for ann in cloned:
                ann_dict = ann.get_cos_object()
                source_ann_dict: COSBase | None = None
                if source_annots_array is not None:
                    while clone_index < source_annots_array.size():
                        candidate = source_annots_array.get_object(clone_index)
                        clone_index += 1
                        if not isinstance(candidate, COSDictionary):
                            continue
                        if self._is_signature_widget(candidate):
                            continue
                        source_ann_dict = candidate
                        break

                if isinstance(ann, PDAnnotationMarkup):
                    source_popup_value: Any = None
                    if isinstance(source_ann_dict, COSDictionary):
                        source_popup_value = (
                            source_ann_dict.get_dictionary_object(_POPUP)
                        )
                    popup_value = (
                        source_popup_value
                        if isinstance(source_popup_value, COSDictionary)
                        else ann_dict.get_dictionary_object(_POPUP)
                    )
                    if isinstance(popup_value, COSDictionary):
                        cloned_popup = self._annot_dict_map.get(
                            id(popup_value)
                        )
                        if cloned_popup is not None:
                            ann_dict.set_item(_POPUP, cloned_popup)
                        else:
                            # Orphan popup — not in any /Annots array of
                            # any chunk page. Clone it, hook /P back to
                            # the markup's imported page, re-link
                            # Popup ↔ Parent. Mirrors upstream
                            # ``Splitter.java:944-954``.
                            cloned_popup = COSDictionary(
                                list(popup_value.entry_set())
                            )
                            self._annot_dict_map[id(popup_value)] = (
                                cloned_popup
                            )
                            popup_clone = PDAnnotationPopup(cloned_popup)
                            popup_clone.set_parent(ann_dict)
                            ann_dict.set_item(_POPUP, cloned_popup)
                            if (
                                imported_page_dict is not None
                                and popup_clone.get_page() is not None
                            ):
                                popup_clone.set_page(imported_page_dict)

                if isinstance(ann, PDAnnotationPopup):
                    source_parent_value: Any = None
                    if isinstance(source_ann_dict, COSDictionary):
                        source_parent_value = (
                            source_ann_dict.get_dictionary_object(_PARENT)
                        )
                    parent_value = (
                        source_parent_value
                        if isinstance(source_parent_value, COSDictionary)
                        else ann_dict.get_dictionary_object(_PARENT)
                    )
                    if isinstance(parent_value, COSDictionary):
                        cloned_markup = self._annot_dict_map.get(
                            id(parent_value)
                        )
                        if cloned_markup is not None:
                            ann_dict.set_item(_PARENT, cloned_markup)
                        else:
                            ann_dict.remove_item(_PARENT)

    @staticmethod
    def _is_signature_widget(ann_dict: COSDictionary) -> bool:
        """Return ``True`` when ``ann_dict`` is a Widget annotation that
        is part of a signature field. Tested in three ways:

        - the widget IS the field (merged form field+widget) and
          ``/FT == /Sig``;
        - the widget's ``/Parent`` chain ends at a field with
          ``/FT == /Sig``;
        - ``/V`` resolves to a signature dictionary
          (``/Type == /Sig`` or contains ``/ByteRange``).

        Split documents have a different byte range than the source, so
        any signature carried into them would be invalid; upstream's
        approach is to leave AcroForm out of the chunk catalog entirely
        (we mirror that in :meth:`_scrub_acroform`), but defensively
        dropping the widget itself avoids orphan annotations on the
        page when an AcroForm cleanup is incomplete.
        """
        try:
            subtype = ann_dict.get_name(_SUBTYPE)
        except AttributeError:
            return False
        if subtype != "Widget":
            return False

        # Direct merged widget+field: /FT lives on the widget dict itself.
        ft = ann_dict.get_name(_FT)
        if ft == "Sig":
            return True

        # Walk /Parent chain.
        seen: set[int] = set()
        parent = ann_dict.get_dictionary_object(_PARENT)
        while isinstance(parent, COSDictionary) and id(parent) not in seen:
            seen.add(id(parent))
            ft = parent.get_name(_FT)
            if ft == "Sig":
                return True
            if ft is not None:
                # Field with a non-Sig FT — definitely not a sig widget.
                return False
            parent = parent.get_dictionary_object(_PARENT)

        # /V signature dictionary check (handles fields with no /FT but a
        # populated signature value — unusual but seen in the wild).
        v = ann_dict.get_dictionary_object(_V)
        if isinstance(v, COSDictionary):
            v_type = v.get_name(_TYPE)
            if v_type == "Sig":
                return True
            if v.contains_key(COSName.get_pdf_name("ByteRange")):
                return True
        return False

    def _scrub_acroform(self, destination_document: PDDocument) -> None:
        """Remove signature-bearing state from the destination catalog.
        Mirrors upstream's "split documents lose AcroForm" behaviour:

        - if any signature widget was dropped, clear ``/SigFlags`` and
          remove signature-typed fields from the chunk's ``/AcroForm
          /Fields`` array;
        - if the resulting fields list is empty, remove ``/AcroForm``
          from the catalog entirely.

        Upstream's :class:`Splitter` doesn't carry AcroForm into chunks
        at all because :meth:`create_new_document` only copies a small
        whitelist of catalog entries (``/ViewerPreferences``, ``/Lang``,
        ``/MarkInfo``, ``/Metadata``). We follow that approach but also
        defensively scrub if a subclass added ``/AcroForm`` via an
        override.
        """
        catalog = destination_document.get_document_catalog()
        cos_catalog = catalog.get_cos_object()
        acroform_dict = cos_catalog.get_dictionary_object(_ACROFORM)
        if not isinstance(acroform_dict, COSDictionary):
            return

        # Always clear /SigFlags — split chunks have invalid signatures.
        if acroform_dict.contains_key(_SIG_FLAGS):
            acroform_dict.remove_item(_SIG_FLAGS)

        fields = acroform_dict.get_dictionary_object(_FIELDS)
        if isinstance(fields, COSArray):
            kept = COSArray()
            for i in range(fields.size()):
                field = fields.get_object(i)
                if isinstance(field, COSDictionary) and field.get_name(_FT) == "Sig":
                    continue
                if field is not None:
                    kept.add(field)
            if kept.size() == 0:
                acroform_dict.remove_item(_FIELDS)
            else:
                acroform_dict.set_item(_FIELDS, kept)

        # If AcroForm is now effectively empty, drop it.
        remaining_keys = [
            k for k in acroform_dict.key_set() if k != _TYPE
        ]
        if not remaining_keys:
            cos_catalog.remove_item(_ACROFORM)

    def _stage_link_destination(
        self,
        link: Any,
        source_page_dict: COSDictionary,
        source_link_dict: COSDictionary | None = None,
    ) -> None:
        """Clone the link's destination array, install the clone, and
        remember it for the :meth:`fix_destinations` post-pass.

        Mirrors upstream's ``destToFixMap`` book-keeping. Named
        destinations are resolved up front via the source catalog's
        ``find_named_destination_page`` (mirrors upstream's
        ``findNamedDestinationPage`` — ``/Names /Dests`` name-tree first,
        then legacy catalog ``/Dests`` flat dictionary) so the cloned
        destination is a concrete :class:`PDPageDestination` rather than
        a name that won't resolve in the chunk's name tree.

        ``source_link_dict`` is the *un-deep-copied* link annot dict from
        the source document. When supplied, the destination's target page
        is resolved through that source dict so the captured page-dict
        identity stays stable across ``import_page``'s deep-copy. Upstream
        gets this for free (its ``import_page`` does a shallow page-graph
        copy that preserves indirect-ref identities); our deep-copy clones
        each indirect-ref target into a fresh ``COSDictionary``, so reading
        the destination off the imported link would point at that fresh
        dict instead of the source page (wave 1294).
        """
        from pypdfbox.pdmodel.interactive.action.pd_action_go_to import (
            PDActionGoTo,
        )
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
            PDAnnotationLink,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
            PDDestination,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (  # noqa: E501
            PDNamedDestination,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (  # noqa: E501
            PDPageDestination,
        )

        # Prefer the source-side link wrapper for destination resolution so
        # we don't trip over ``import_page``'s deep-copied page targets. Fall
        # back to the cloned link when no source dict was supplied (e.g.
        # subclass override that calls this directly).
        if source_link_dict is not None:
            resolution_link: Any = PDAnnotationLink(source_link_dict)
        else:
            resolution_link = link

        try:
            src_destination = resolution_link.get_destination()
        except Exception:  # noqa: BLE001
            _LOG.warning(
                "Incorrect destination in link annotation on page %d "
                "is removed",
                self._current_page_number + 1,
            )
            link.set_destination(None)
            return

        action = None
        if src_destination is None:
            try:
                action = resolution_link.get_action()
            except Exception:  # noqa: BLE001
                action = None
            if isinstance(action, PDActionGoTo):
                try:
                    src_destination = action.get_destination()
                except Exception:  # noqa: BLE001
                    _LOG.warning(
                        "GoToAction with incorrect destination in link "
                        "annotation on page %d is removed",
                        self._current_page_number + 1,
                    )
                    link.set_action(None)
                    src_destination = None

        # Resolve a named destination through the source catalog's
        # /Names /Dests name-tree (then legacy /Dests) so it becomes a
        # PDPageDestination. Upstream comment (Splitter.java ~876):
        # "we do not use the named destination anymore because names get
        # modified, e.g. 0xAD becomes 0, see file 410609.pdf where the
        # name no longer matches with the entry in the new name tree".
        #
        # PDActionGoTo.get_destination() / PDAnnotationLink.get_destination()
        # return a ``PDNamedDestination`` for a name/string ``/D`` (upstream
        # parity — see wave 1491). Resolve it through the catalog's
        # /Names /Dests name tree so it becomes a concrete PDPageDestination.
        # (A bare ``str`` is tolerated defensively for any caller still
        # handing one in.)
        if isinstance(src_destination, str):
            src_destination = PDNamedDestination(src_destination)
        if isinstance(src_destination, PDNamedDestination):
            try:
                src_catalog = self.get_source_document().get_document_catalog()
                resolved = src_catalog.find_named_destination_page(src_destination)
            except Exception:  # noqa: BLE001
                resolved = None
            src_destination = resolved

        # Skip non-page destinations (anything we couldn't resolve to a
        # concrete PDPageDestination — including unresolved named refs).
        if not isinstance(src_destination, PDPageDestination):
            return

        src_dest_array = src_destination.get_cos_object()
        if not isinstance(src_dest_array, COSArray):
            return

        # Snapshot the *source* target-page dict before any cloning. This
        # is what ``_page_dict_map`` is keyed by (every ``process_page``
        # stores ``id(page.get_cos_object())``); reading the deep-copied
        # ``cloned_array.get_object(0)`` later would miss because the deep
        # copy minted a fresh dict per indirect-ref target.
        source_target_page_dict: COSDictionary | None = None
        try:
            candidate_target = src_destination.get_page()
            if isinstance(candidate_target, COSDictionary):
                source_target_page_dict = candidate_target
        except Exception:  # noqa: BLE001
            source_target_page_dict = None

        # Clone destination as a flat shallow array (just rewrite /D[0]
        # later — leave fit / params alone).
        cloned_array = COSArray()
        for i in range(src_dest_array.size()):
            cloned_array.add(src_dest_array.get(i))
        try:
            cloned_destination = PDDestination.create(cloned_array)
        except Exception:  # noqa: BLE001
            return
        if cloned_destination is None:
            return

        # Re-read the *cloned* link's action when we have one, so the
        # cloned destination installs onto the chunk-side annot rather
        # than mutating the source link.
        cloned_action = None
        if action is not None:
            try:
                cloned_action = link.get_action()
            except Exception:  # noqa: BLE001
                cloned_action = None

        if isinstance(action, PDActionGoTo):
            base_action_dict = (
                cloned_action.get_cos_object()
                if isinstance(cloned_action, PDActionGoTo)
                else action.get_cos_object()
            )
            cloned_action_dict = COSDictionary(list(base_action_dict.entry_set()))
            cloned_action_wrapper = PDActionGoTo(cloned_action_dict)
            cloned_action_wrapper.set_destination(cloned_destination)
            with contextlib.suppress(Exception):
                link.set_action(cloned_action_wrapper)
        else:
            with contextlib.suppress(Exception):
                link.set_destination(cloned_destination)

        self._dest_to_fix.append(
            (cloned_array, source_page_dict, source_target_page_dict)
        )
        # Wave-1379: remember which cloned link annotation hosts this
        # destination so the post-pass can rewrite it into a /A GoToR action
        # when the cross-chunk resolver opts in. Defaults to a no-op when
        # the resolver isn't registered (the link reference simply isn't
        # consulted).
        with contextlib.suppress(AttributeError):
            self._dest_to_link_map[id(cloned_array)] = link.get_cos_object()

    # ---------- destination fix-up post-pass ----------

    def fix_destinations(self, destination_document: PDDocument) -> None:
        """Rewrite or null out staged ``/Dest`` arrays per upstream's
        ``fixDestinations``. For each cloned destination array:

        - if the *source page that hosts the link* doesn't live in this
          chunk, leave it (caller already discarded the link as part of
          a different chunk's import);
        - if the *destination page the link points to* lives in this
          chunk, rewrite the array's first slot to the cloned page dict;
        - otherwise null out the array's first slot so the destination
          becomes a no-op rather than dangling into the source doc.
        """
        if not self._dest_to_fix:
            return
        from pypdfbox.cos import COSNull

        page_tree = destination_document.get_pages()
        for entry in self._dest_to_fix:
            # Backwards-compatible unpacking — older subclass overrides that
            # called the pre-wave-1294 two-tuple form still work.
            if len(entry) == 3:
                cloned_array, source_page_dict, source_target_page_dict = entry
            else:  # pragma: no cover - legacy two-tuple form
                cloned_array, source_page_dict = entry  # type: ignore[misc]
                source_target_page_dict = None
            # Where did the link itself originate? If the host page isn't
            # in this chunk, skip — another chunk owns this rewrite.
            cloned_host_dict = self._page_dict_map.get(id(source_page_dict))
            if cloned_host_dict is None:
                continue
            if page_tree.index_of(cloned_host_dict) < 0:
                continue
            # Resolve the target page through the source-side snapshot
            # captured at staging time (wave 1294) — the deep-copied
            # cloned_array[0] doesn't keep source-page identity, so we
            # can't key ``_page_dict_map`` off it.
            target_source: COSDictionary | None = source_target_page_dict
            if target_source is None and cloned_array.size() > 0:
                # Legacy fallback: if no source snapshot, try the cloned
                # array's first entry. Matches pre-wave-1294 behavior.
                raw_target = cloned_array.get_object(0)
                if isinstance(raw_target, COSDictionary):
                    target_source = raw_target
            if target_source is None:
                # Integer / null target — nothing to fix.
                continue
            cloned_target = self._page_dict_map.get(id(target_source))
            if cloned_target is not None and page_tree.index_of(cloned_target) >= 0:
                cloned_array.set(0, cloned_target)
            else:
                # Cross-chunk target. Wave-1379 cross-chunk resolver path:
                # when registered, let the caller retarget the link as a
                # /A GoToR action pointing at the chunk file that owns
                # ``target_source``. Falls back to the historical null-out
                # behaviour when the resolver returns ``None`` (or isn't
                # registered).
                if not self._rewrite_cross_chunk_destination(
                    cloned_array, target_source
                ):
                    cloned_array.set(0, COSNull.NULL)

    def _rewrite_cross_chunk_destination(
        self,
        cloned_array: COSArray,
        source_target_page_dict: COSDictionary,
    ) -> bool:
        """Apply the registered cross-chunk destination resolver to a single
        out-of-chunk destination array. Returns ``True`` when the resolver
        opted into a rewrite (in which case ``cloned_array``'s ``/D[0]``
        slot has been replaced with the integer page index inside the
        target file and the hosting link annotation's ``/A`` has been set
        to a fresh ``GoToR`` action), or ``False`` when no resolver is
        registered / the resolver returned ``None`` (null-out fallback
        path).
        """
        resolver = self._cross_chunk_destination_resolver
        if resolver is None:
            return False
        try:
            resolved = resolver(source_target_page_dict)
        except Exception:  # noqa: BLE001 - defensive: resolver is caller code
            _LOG.exception(
                "cross_chunk_destination_resolver raised for target page; "
                "falling back to null-out"
            )
            return False
        if resolved is None:
            return False

        if isinstance(resolved, tuple):
            if len(resolved) != 2:
                _LOG.warning(
                    "cross_chunk_destination_resolver returned a tuple of "
                    "length %d; expected 2 (filename, page_index). Falling "
                    "back to null-out.",
                    len(resolved),
                )
                return False
            file_name_obj, page_index_obj = resolved
            if not isinstance(file_name_obj, str) or not isinstance(
                page_index_obj, int
            ):
                _LOG.warning(
                    "cross_chunk_destination_resolver returned non-(str,int) "
                    "tuple; falling back to null-out"
                )
                return False
            file_name = file_name_obj
            page_index = page_index_obj
        elif isinstance(resolved, str):
            file_name = resolved
            page_index = 0
        else:
            _LOG.warning(
                "cross_chunk_destination_resolver returned unsupported type "
                "%s; falling back to null-out",
                type(resolved).__name__,
            )
            return False

        from pypdfbox.pdmodel.interactive.action.pd_action_remote_go_to import (
            PDActionRemoteGoTo,
        )

        # Replace ``/D[0]`` with the integer page index inside the target
        # file. The remaining slots (fit type + coordinates) are preserved
        # so explicit-fit-mode destinations (XYZ / FitH / FitV / FitB /
        # FitBH / FitBV / FitR) round-trip through the rewrite unchanged.
        cloned_array.set(0, COSInteger.get(page_index))

        link_dict = self._dest_to_link_map.get(id(cloned_array))
        if link_dict is None:
            # No link record — the destination is orphaned (e.g. from a
            # legacy /Dests entry promoted into a chunk by a subclass).
            # Mutating ``cloned_array`` alone is the best we can do.
            return True

        # Build a fresh /A GoToR action carrying the file + dest array.
        # Mirrors upstream's typical user pattern: an explicit
        # ``PDActionRemoteGoTo`` with ``/F`` (string) + ``/D`` (array).
        action = PDActionRemoteGoTo()
        action.set_file(file_name)
        action.set_destination(cloned_array)
        link_dict.set_item(
            COSName.get_pdf_name("A"), action.get_cos_object()
        )
        # Remove the historical /Dest if present — /A takes precedence
        # per PDF 32000-1 §12.5.6.5 Table 173 but a redundant /Dest
        # confuses some viewers (Foxit) into picking the now-stale array.
        link_dict.remove_item(COSName.get_pdf_name("Dest"))
        return True

    # ---------- structure-tree cloning ----------

    def clone_structure_tree(self, destination_document: PDDocument) -> None:
        """Clone the source ``/StructTreeRoot`` into ``destination_document``,
        keeping only structure elements that pertain to pages in this
        chunk. Mirrors upstream ``Splitter.cloneStructureTree``.

        Uses the per-chunk ``_page_dict_map`` / ``_annot_dict_map`` to
        translate page and annotation references; produces a fresh
        ``/ParentTree``, ``/IDTree``, ``/RoleMap``, and ``/ClassMap`` for
        the chunk.
        """
        from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (  # noqa: E501
            PDStructureElementNameTreeNode,
            PDStructureElementNumberTreeNode,
            PDStructureTreeRoot,
        )

        src_catalog = self.get_source_document().get_document_catalog()
        src_struct_root = src_catalog.get_struct_tree_root()
        if src_struct_root is None:
            return

        # Reset per-chunk struct-clone state. Note: ``_id_set`` and
        # ``_role_set`` are intentionally NOT reset here — upstream
        # initialises them once in ``split()`` and lets them accumulate
        # across chunks (Splitter.java lines 136-137 vs line 200), so a
        # chunk's /RoleMap and /IDTree can include entries first
        # introduced by an earlier chunk. Resetting per chunk produced
        # off-by-one role-map narrowing on PDFBOX-5792-240045.pdf (wave
        # 1295).
        self._struct_dict_map = {}

        dst_struct_root = PDStructureTreeRoot()
        dst_struct_root_cos = dst_struct_root.get_cos_object()
        page_tree = destination_document.get_pages()

        # Clone /K, also fills _struct_dict_map.
        src_k = src_struct_root.get_cos_object().get_dictionary_object(_K)
        cloned_k = self._k_create_clone(
            src_k, dst_struct_root_cos, None, page_tree
        )
        if cloned_k is not None:
            dst_struct_root_cos.set_item(_K, cloned_k)

        # Build a fresh /ParentTree containing only entries referenced by
        # this chunk's pages.
        src_parent_tree = src_struct_root.get_parent_tree()
        if src_parent_tree is not None:
            src_numbers = self._get_number_tree_as_map(src_parent_tree)
        else:
            src_numbers = {}
        dst_numbers: dict[int, COSBase] = {}

        for page_index in range(len(page_tree)):
            page = page_tree.get(page_index)
            try:
                sp1 = page.get_struct_parents()
            except Exception:  # noqa: BLE001
                sp1 = -1
            if sp1 != -1:
                self.clone_tree_element(src_numbers, dst_numbers, sp1)
            try:
                annots = page.get_annotations()
            except Exception:  # noqa: BLE001
                annots = []
            for ann in annots:
                try:
                    sp2 = ann.get_struct_parent()
                except Exception:  # noqa: BLE001
                    sp2 = -1
                if sp2 != -1:
                    self.clone_tree_element(src_numbers, dst_numbers, sp2)
                # Mirrors upstream Splitter.cloneStructureTree (Java
                # line 229-234): walk an annotation's normal appearance
                # stream resources for /StructParent links.
                try:
                    normal_app = ann.get_normal_appearance_stream()
                except Exception:  # noqa: BLE001
                    normal_app = None
                if normal_app is not None:
                    try:
                        app_resources = normal_app.get_resources()
                    except Exception:  # noqa: BLE001
                        app_resources = None
                    self.process_resources(
                        app_resources, src_numbers, dst_numbers, set()
                    )
            # Walk page resources for /StructParent / /StructParents
            # references used by Form/Image XObjects (Java line 235).
            try:
                page_resources = page.get_resources()
            except Exception:  # noqa: BLE001
                page_resources = None
            self.process_resources(
                page_resources, src_numbers, dst_numbers, set()
            )

        if dst_numbers:
            # Build a fresh number-tree leaf node from the filtered map.
            dst_pt_dict = COSDictionary()
            dst_pt_node = PDStructureElementNumberTreeNode(dst_pt_dict)
            # Wrap raw COS values so the number-tree set_numbers path
            # stores them verbatim (PDStructureElementNumberTreeNode
            # convert_value_to_cos returns the value unchanged for
            # COSBase inputs).
            dst_pt_node.set_numbers(dst_numbers)
            dst_struct_root.set_parent_tree(dst_pt_node)
            upper = dst_pt_node.get_upper_limit()
            if upper is not None:
                dst_struct_root.set_parent_tree_next_key(upper + 1)

        # /ClassMap — carry verbatim from source. Class entries may be
        # referenced by retained struct elements via /C.
        src_class_map = src_struct_root.get_cos_object().get_dictionary_object(
            _CLASS_MAP
        )
        if isinstance(src_class_map, COSDictionary):
            dst_struct_root_cos.set_item(_CLASS_MAP, src_class_map)

        # /RoleMap — narrow to roles actually used by retained elements.
        self.clone_role_map(src_struct_root, dst_struct_root)

        # /IDTree — filter to ids actually referenced by retained
        # elements, mapped through _struct_dict_map.
        self.clone_id_tree(
            src_struct_root, dst_struct_root, PDStructureElementNameTreeNode
        )

        destination_document.get_document_catalog().set_struct_tree_root(
            dst_struct_root
        )

    # ---- structure-tree helpers (private; mirror upstream KCloner) ----

    def _k_create_clone(
        self,
        src: COSBase | None,
        dst_parent: COSBase,
        current_page_dict: COSDictionary | None,
        page_tree: Any,
    ) -> COSBase | None:
        if src is None:
            return None
        if isinstance(src, COSObject):
            return self._k_create_clone(
                src.get_object(), dst_parent, current_page_dict, page_tree
            )
        if isinstance(src, COSArray):
            return self._k_clone_array(src, dst_parent, current_page_dict, page_tree)
        if isinstance(src, COSDictionary):
            return self._k_clone_dictionary(
                src, dst_parent, current_page_dict, page_tree
            )
        return src

    def _k_clone_array(
        self,
        src: COSArray,
        dst_parent: COSBase,
        current_page_dict: COSDictionary | None,
        page_tree: Any,
    ) -> COSBase | None:
        dst = COSArray()
        for i in range(src.size()):
            entry = src.get(i)
            if isinstance(entry, COSObject):
                cloned = self._k_create_clone(
                    entry.get_object(), dst_parent, current_page_dict, page_tree
                )
            else:
                cloned = self._k_create_clone(
                    entry, dst_parent, current_page_dict, page_tree
                )
            if cloned is not None:
                dst.add(cloned)
        return dst if dst.size() > 0 else None

    def _k_clone_dictionary(
        self,
        src: COSDictionary,
        dst_parent: COSBase,
        current_page_dict: COSDictionary | None,
        page_tree: Any,
    ) -> COSDictionary | None:
        existing = self._struct_dict_map.get(id(src))
        if existing is not None:
            return existing

        src_page_dict = src.get_dictionary_object(_PG)
        if not isinstance(src_page_dict, COSDictionary):
            src_page_dict = None
        dst_page_dict: COSDictionary | None = None
        kid = src.get_dictionary_object(_K)
        type_name = src.get_name(_TYPE)

        if src_page_dict is not None:
            dst_page_dict = self._page_dict_map.get(id(src_page_dict))
            if dst_page_dict is not None:
                if page_tree.index_of(dst_page_dict) == -1:
                    return None
            else:
                # PDFBOX-6009: src has /Pg pointing somewhere not in this
                # chunk. Quit on MCID/MCR/OBJR — they need a /Pg — else
                # keep as an intermediate.
                if (
                    type_name == "MCR"
                    or type_name == "OBJR"
                    or self._has_mcids(kid)
                ):
                    return None

        # MCR with no resolvable destination page and no inherited /Pg
        # from parent — drop it (PAC rule).
        if (
            type_name == "MCR"
            and dst_page_dict is None
            and isinstance(dst_parent, COSDictionary)
            and dst_parent.get_dictionary_object(_PG) is None
        ):
            return None

        dst = COSDictionary()
        self._struct_dict_map[id(src)] = dst
        for key, value in src.entry_set():
            if key != _K and key != _PG and key != _P:
                dst.set_item(key, value)

        # OBJR special handling — replace /Obj with the cloned annotation
        # dict (or remove when the source annotation isn't on the page).
        if type_name == "OBJR":
            src_obj = src.get_dictionary_object(_OBJ)
            if isinstance(src_obj, COSDictionary):
                dst_obj = self._annot_dict_map.get(id(src_obj))
                if dst_obj is not None:
                    dst.set_item(_OBJ, dst_obj)
                else:
                    self._remove_possible_orphan_annotation(
                        src_obj, src, current_page_dict, dst
                    )
            if dst.size() == 1:
                # Only a /Type entry remains — no useful payload.
                self._struct_dict_map.pop(id(src), None)
                return None
            if (
                dst_page_dict is None
                and isinstance(dst_parent, COSDictionary)
                and dst_parent.get_dictionary_object(_PG) is None
            ):
                self._struct_dict_map.pop(id(src), None)
                return None

        if type_name != "OBJR" and type_name != "MCR":
            dst.set_item(_P, dst_parent)

        if dst_page_dict is not None:
            dst.set_item(_PG, dst_page_dict)

        next_page_dict = dst_page_dict if dst_page_dict is not None else current_page_dict
        cloned_kid = self._k_create_clone(kid, dst, next_page_dict, page_tree)
        if cloned_kid is None and kid is not None:
            # The kids array wasn't empty, but became empty after narrowing —
            # this element is now an orphan, drop its placeholder so the
            # /IDTree / /ParentTree narrowing doesn't surface a half-empty
            # struct dict.
            self._struct_dict_map.pop(id(src), None)
            return None

        # Orphan check: no parent page, no own page, and no kids.
        if dst_page_dict is None and cloned_kid is None and current_page_dict is None:
            self._struct_dict_map.pop(id(src), None)
            return None

        if cloned_kid is not None:
            dst.set_item(_K, cloned_kid)

        # Track ids and roles for /IDTree / /RoleMap narrowing.
        id_value = dst.get_string(_ID)
        if id_value is not None:
            self._id_set.add(id_value)
        role = dst.get_name(_S)
        if role is not None:
            self._role_set.add(role)
        return dst

    @staticmethod
    def _has_mcids(kid: COSBase | None) -> bool:
        if isinstance(kid, COSInteger):
            return True
        if isinstance(kid, COSArray):
            for i in range(kid.size()):
                entry = kid.get_object(i)
                if isinstance(entry, COSInteger):
                    return True
        return False

    def _remove_possible_orphan_annotation(
        self,
        src_obj: COSDictionary,
        src_dict: COSDictionary,
        current_page_dict: COSDictionary | None,
        dst_dict: COSDictionary,
    ) -> None:
        obj_type = src_obj.get_dictionary_object(_TYPE)
        obj_subtype = src_obj.get_dictionary_object(_SUBTYPE)
        is_annot = isinstance(obj_type, COSName) and obj_type.get_name() == "Annot"
        is_link = isinstance(obj_subtype, COSName) and obj_subtype.get_name() == "Link"
        if not is_annot and not is_link:
            return
        host_page = src_dict.get_dictionary_object(_PG)
        if not isinstance(host_page, COSDictionary):
            host_page = current_page_dict
        if host_page is None:
            return
        annots_array = host_page.get_dictionary_object(_ANNOTS)
        if not isinstance(annots_array, COSArray):
            _LOG.warning(
                "An annotation OBJ that isn't in the page has been removed "
                "from the structure tree"
            )
            dst_dict.remove_item(_OBJ)
            return
        for i in range(annots_array.size()):
            if annots_array.get_object(i) is src_obj:
                return
        _LOG.warning(
            "An annotation OBJ that isn't in the page has been removed "
            "from the structure tree"
        )
        dst_dict.remove_item(_OBJ)

    def clone_tree_element(
        self,
        src_numbers: dict[int, COSBase],
        dst_numbers: dict[int, COSBase],
        sp: int,
    ) -> None:
        src_obj = src_numbers.get(sp)
        if src_obj is None:
            return
        if isinstance(src_obj, COSArray):
            cloned_arr = COSArray()
            for i in range(src_obj.size()):
                element = src_obj.get_object(i)
                cloned_entry = self._struct_dict_map.get(id(element))
                if cloned_entry is not None:
                    cloned_arr.add(cloned_entry)
                else:
                    # null placeholder — the array is indexed by MCID, so
                    # holes must be preserved.
                    from pypdfbox.cos import COSNull

                    cloned_arr.add(COSNull.NULL)
            dst_numbers[sp] = cloned_arr
        elif isinstance(src_obj, COSDictionary):
            cloned_entry = self._struct_dict_map.get(id(src_obj))
            if cloned_entry is None:
                _LOG.warning("ParentTree index %d dictionary not found in /K", sp)
                return
            dst_numbers[sp] = cloned_entry
        else:
            _LOG.warning(
                "tree element neither dictionary nor array, but %s",
                type(src_obj).__name__,
            )

    def clone_role_map(self, src_root: Any, dst_root: Any) -> None:
        src_dict = src_root.get_cos_object().get_dictionary_object(_ROLE_MAP)
        if not isinstance(src_dict, COSDictionary):
            return
        dst_dict = COSDictionary()
        for key, value in src_dict.entry_set():
            if key.get_name() in self._role_set:
                dst_dict.set_item(key, value)
        dst_root.get_cos_object().set_item(_ROLE_MAP, dst_dict)

    def clone_id_tree(
        self, src_root: Any, dst_root: Any, name_tree_cls: type
    ) -> None:
        src_id_tree = src_root.get_id_tree()
        if src_id_tree is None:
            return
        src_id_map = self._get_id_tree_as_map(src_id_tree)
        if not src_id_map:
            return
        from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (  # noqa: E501
            PDStructureElement,
        )

        dst_names: dict[str, PDStructureElement] = {}
        for key, val in src_id_map.items():
            if key not in self._id_set:
                continue
            src_dict = (
                val.get_cos_object() if hasattr(val, "get_cos_object") else val
            )
            cloned_dict = self._struct_dict_map.get(id(src_dict))
            if cloned_dict is not None:
                dst_names[key] = PDStructureElement(cloned_dict)
        if not dst_names:
            return
        dst_id_tree = name_tree_cls()
        dst_id_tree.set_names(dst_names)
        dst_root.set_id_tree(dst_id_tree)

    @staticmethod
    def _get_number_tree_as_map(node: Any) -> dict[int, COSBase]:
        """Walk a number-tree node into a flat ``{int: COSBase}`` map.
        Local mirror of upstream ``PDFMergerUtility.getNumberTreeAsMap``
        — kept private so we don't have to wait on the merger-utility
        helper to land."""
        out: dict[int, COSBase] = {}
        Splitter._walk_number_tree(node, out)
        return out

    @staticmethod
    def _walk_number_tree(node: Any, out: dict[int, COSBase]) -> None:
        try:
            numbers = node.get_numbers()
        except Exception:  # noqa: BLE001
            numbers = None
        if numbers:
            for key, value in numbers.items():
                base = value.get_cos_object() if hasattr(value, "get_cos_object") else value
                out[int(key)] = base
            return
        try:
            kids = node.get_kids()
        except Exception:  # noqa: BLE001
            kids = None
        if kids:
            for child in kids:
                Splitter._walk_number_tree(child, out)

    @staticmethod
    def _get_id_tree_as_map(node: Any) -> dict[str, Any]:
        """Walk an ID name-tree into a flat ``{str: PDStructureElement}``
        map. Local mirror of upstream ``PDFMergerUtility.getIDTreeAsMap``."""
        out: dict[str, Any] = {}
        Splitter._walk_id_tree(node, out)
        return out

    @staticmethod
    def _walk_id_tree(node: Any, out: dict[str, Any]) -> None:
        try:
            names = node.get_names()
        except Exception:  # noqa: BLE001
            names = None
        if names:
            out.update(names)
            return
        try:
            kids = node.get_kids()
        except Exception:  # noqa: BLE001
            kids = None
        if kids:
            for child in kids:
                Splitter._walk_id_tree(child, out)

    # ---------- resource walking ----------

    def process_resources(
        self,
        resources: Any,
        src_numbers: dict[int, COSBase],
        dst_numbers: dict[int, COSBase],
        visited: set[int],
    ) -> None:
        """Walk ``resources`` for Form/Image XObjects with ``/StructParent``
        or ``/StructParents`` references, copying any retained entries
        from ``src_numbers`` into ``dst_numbers`` (mirrors upstream
        ``Splitter.processResources`` at Java line 586).

        ``visited`` tracks resource dictionary identities to break cycles
        — upstream PDFBox guards 002874.pdf this way.
        """
        if resources is None:
            return
        try:
            resources_cos = resources.get_cos_object()
        except AttributeError:
            return
        cos_id = id(resources_cos)
        if cos_id in visited:
            return
        visited.add(cos_id)

        try:
            x_object_names = resources.get_xobject_names()
        except Exception:  # noqa: BLE001
            return
        for name in x_object_names:
            try:
                x_object = resources.get_x_object(name)
            except Exception:  # noqa: BLE001
                continue
            sp = -1
            # Form XObjects carry /StructParents (note plural) and have
            # nested /Resources of their own that need recursion.
            from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (
                PDFormXObject,
            )
            from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
                PDImageXObject,
            )

            if isinstance(x_object, PDFormXObject):
                try:
                    sp = x_object.get_struct_parents()
                except Exception:  # noqa: BLE001
                    sp = -1
                try:
                    nested = x_object.get_resources()
                except Exception:  # noqa: BLE001
                    nested = None
                self.process_resources(nested, src_numbers, dst_numbers, visited)
            elif isinstance(x_object, PDImageXObject):
                try:
                    sp = x_object.get_struct_parent()
                except Exception:  # noqa: BLE001
                    sp = -1
            if sp != -1:
                self.clone_tree_element(src_numbers, dst_numbers, sp)

    # ---------- private-name aliases (back-compat) ----------
    #
    # Upstream Splitter exposes the structure-tree clone helpers as
    # ``private``. We mirror them as public methods so the Java naming
    # round-trips through the parity tracker and so subclasses can hook
    # the same surface area as upstream subclasses do (e.g. via
    # ``protected`` accessors). The leading-underscore aliases below
    # preserve compatibility with internal callers and existing tests
    # that exercise the implementation directly.
    _clone_structure_tree = clone_structure_tree
    _clone_tree_element = clone_tree_element
    _clone_role_map = clone_role_map
    _clone_id_tree = clone_id_tree
    _fix_destinations = fix_destinations


__all__ = ["Splitter"]
