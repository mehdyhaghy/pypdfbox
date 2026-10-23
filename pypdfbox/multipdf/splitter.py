import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSString,
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
_DESTS: COSName = COSName.get_pdf_name("Dests")
_NAMES: COSName = COSName.get_pdf_name("Names")
_NUMS: COSName = COSName.get_pdf_name("Nums")
_LIMITS: COSName = COSName.get_pdf_name("Limits")

# struct-tree clone helpers
_K: COSName = COSName.get_pdf_name("K")
_P: COSName = COSName.get_pdf_name("P")
_PG: COSName = COSName.get_pdf_name("Pg")
_S: COSName = COSName.get_pdf_name("S")
_ID: COSName = COSName.get_pdf_name("ID")
_OBJ: COSName = COSName.get_pdf_name("Obj")
_ANNOTS: COSName = COSName.get_pdf_name("Annots")
_ROLE_MAP: COSName = COSName.get_pdf_name("RoleMap")
_CLASS_MAP: COSName = COSName.get_pdf_name("ClassMap")


def _set_flat_names(node: COSDictionary, names: dict[str, COSBase]) -> None:
    """Write ``names`` as a single ``/Names`` leaf on a name-tree root.

    Mirrors upstream ``PDNameTreeNode.setNames`` on a root node: one sorted
    ``/Names`` array and no ``/Limits``. (pypdfbox's ``PDNameTreeNode``
    splits large maps into balanced ``/Kids``; the split output follows
    upstream's flat shape instead.)"""
    array = COSArray()
    for key in sorted(names):
        array.add(COSString(key))
        array.add(names[key])
    node.set_item(_NAMES, array)
    node.remove_item(_LIMITS)


def _set_flat_numbers(node: COSDictionary, numbers: dict[int, COSBase]) -> None:
    """Write ``numbers`` as a single ``/Nums`` leaf.

    Mirrors upstream ``PDNumberTreeNode.setNumbers``: ``/Limits [lower
    upper]`` (``[null null]`` for an empty map) is stamped before ``/Nums``,
    even on the root node, and no ``/Kids`` split is made."""
    keys = sorted(numbers)
    array = COSArray()
    for key in keys:
        array.add(COSInteger.get(key))
        value = numbers[key]
        array.add(COSNull.NULL if value is None else value)
    limits = COSArray()
    if keys:
        limits.add(COSInteger.get(keys[0]))
        limits.add(COSInteger.get(keys[-1]))
    else:
        limits.add(COSNull.NULL)
        limits.add(COSNull.NULL)
    node.set_item(_LIMITS, limits)
    node.set_item(_NUMS, array)


class Splitter:
    """
    Split a ``PDDocument`` into one or more smaller documents. Mirrors
    ``org.apache.pdfbox.multipdf.Splitter`` (PDFBox 3.0.8, plus the
    PDFBOX-6283 named-destination handling of the 3.0 branch).

    Public surface:

    - :meth:`set_split_at_page` (alias :meth:`set_split`) — pages per chunk;
    - :meth:`set_start_page`, :meth:`set_end_page` — 1-based inclusive
      page range;
    - :meth:`set_memory_usage_setting` /
      :meth:`set_stream_cache_create_function` — recorded but advisory in
      this port (see ``CHANGES.md``);
    - :meth:`set_cross_chunk_destination_resolver` — opt-in pypdfbox
      extension that retargets cross-chunk links as ``GoToR`` actions;
    - :meth:`split` — returns ``list[PDDocument]``.

    Subclassing hooks (mirroring upstream ``protected`` methods):
    :meth:`split_at_page`, :meth:`create_new_document`,
    :meth:`process_page`, :meth:`get_source_document`,
    :meth:`get_destination_document`.

    Pages are imported with the shallow :meth:`PDDocument.import_page`, so
    chunks share resources with the source document (as upstream); the
    source must stay open until every chunk has been saved.
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
        # pageDictMap: {id(source page dict): imported page dict} for the
        # current destination document, plus the list of these maps.
        self._page_dict_map: dict[int, COSDictionary] = {}
        self._page_dict_maps: list[dict[int, COSDictionary]] = []
        # pageToDocNumMap (PDFBOX-6283): {id(source page dict): index of
        # the destination document that received the page}.
        self._page_to_doc_num_map: dict[int, int] = {}
        # annotDictMap: {id(source annotation dict): cloned annotation dict}
        # for the current destination document, plus the list of maps.
        self._annot_dict_map: dict[int, COSDictionary] = {}
        self._annot_dict_maps: list[dict[int, COSDictionary]] = []
        # structDictMap: {id(source structure dict): clone}, per chunk.
        self._struct_dict_map: dict[int, COSDictionary] = {}
        # idSet / roleSet: initialised once per split() and shared by every
        # chunk, as upstream.
        self._id_set: set[str] = set()
        self._role_set: set[str] = set()
        # destToFixMap: (cloned page destination, imported host page dict)
        # for every staged link destination of the whole split() run.
        self._dest_to_fix: list[tuple[Any, COSDictionary]] = []
        # {id(cloned destination array): cloned link dict}; only consulted
        # by the opt-in cross-chunk destination resolver.
        self._dest_to_link_map: dict[int, COSDictionary] = {}
        # ids of the page dictionaries of the chunk being post-processed;
        # an O(1) stand-in for ``PDPageTree.indexOf(page) >= 0``.
        self._chunk_page_ids: set[int] = set()
        self._chunk_page_tree: Any = None
        # Per-run caches of the read-only source structure tree: resolved
        # element fields ({id(src): [src, /Pg, /K, /Type, mask, live,
        # parent]}, see _build_k_skip_info) and the flattened /ParentTree and
        # /IDTree maps. ``None`` outside split().
        self._k_node_cache: dict[int, list[Any]] | None = None
        self._src_number_tree_map: dict[int, COSBase] | None = None
        self._src_id_tree_map: dict[str, Any] | None = None
        # Subtree skipping (see _build_k_skip_info): enabled per split() run
        # when the source /K tree has no shared nodes; ``_k_skipped`` holds
        # the subtrees skipped in the chunk being cloned ({id(src): (src,
        # dst_parent)}), materialised on demand by _struct_lookup.
        self._k_skip_enabled: bool = False
        self._k_skip_pending: bool = False
        self._k_chunk_index: int = 0
        self._k_skipped: dict[int, tuple[COSDictionary, COSBase]] = {}
        self._k_page_tree: Any = None

        self._current_page_number: int = 0

        self._stream_cache_create_function: Callable[[], Any] | None = None
        self._memory_usage_setting: MemoryUsageSetting | None = None

        # Opt-in pypdfbox extension (no upstream counterpart): called by
        # fix_destinations when a cloned link's target page lives outside
        # the chunk that hosts the link. See
        # set_cross_chunk_destination_resolver.
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
        explicit value (i.e. the field is not the default sentinel)."""
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

        pypdfbox extension; upstream always nulls the page slot of a link
        destination whose target page is not in the link's chunk, which is
        also what happens here when no resolver is registered or it returns
        ``None``. The resolver receives the *source* target page
        :class:`COSDictionary` and returns one of:

        * ``None`` — keep the upstream null-out behaviour;
        * a plain ``str`` — the relative file name of the sibling chunk file
          that contains the target page; the destination's page slot
          becomes ``0``;
        * a ``(file_name, page_index)`` tuple — explicit file + 0-based
          page index pair, matching the PDF 32000-1 §12.6.4.3 ``GoToR``
          payload.

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
        them before closing ``document`` (the chunks share resources with
        the source)."""
        # reset the current page number in case split() is called again
        self._current_page_number = 0
        self._current_destination_document = None
        self._destination_documents = []
        self._source_document = document
        self._page_dict_maps = []
        self._page_to_doc_num_map = {}
        self._annot_dict_maps = []
        self._dest_to_fix = []
        self._dest_to_link_map = {}
        self._id_set = set()
        self._role_set = set()
        self._k_node_cache = {}
        self._src_number_tree_map = None
        self._src_id_tree_map = None
        self._k_skip_enabled = False
        self._k_skip_pending = True

        try:
            self._process_pages()

            for index, destination_document in enumerate(
                self._destination_documents
            ):
                self._page_dict_map = self._page_dict_maps[index]
                self._annot_dict_map = self._annot_dict_maps[index]
                self._k_chunk_index = index
                try:
                    # Dispatch via the underscored alias so subclasses can
                    # override either the public ``clone_structure_tree``
                    # or the upstream-private ``_clone_structure_tree``.
                    self._clone_structure_tree(destination_document)
                except Exception:
                    _LOG.exception(
                        "structure-tree clone failed for chunk %d; chunk will "
                        "ship without /StructTreeRoot",
                        index,
                    )
                try:
                    self._fix_destinations(destination_document)
                except Exception:
                    _LOG.exception(
                        "destination fix-up failed for chunk %d; cross-chunk "
                        "/Dest links may dangle",
                        index,
                    )
            # PDFBOX-6283: carry the named destinations (/Names /Dests name
            # tree and legacy /Root/Dests) over to the chunks that own their
            # pages.
            try:
                self.fix_name_destinations()
            except Exception:
                _LOG.exception(
                    "named destinations fix-up failed; chunks will ship "
                    "without /Names /Dests"
                )
            try:
                self.fix_name_destinations2()
            except Exception:
                _LOG.exception(
                    "named destinations fix-up failed; chunks will ship "
                    "without /Root/Dests"
                )
        finally:
            self._k_node_cache = None
            self._src_number_tree_map = None
            self._src_id_tree_map = None
            self._k_skip_enabled = False
            self._k_skip_pending = False
            self._k_skipped = {}
            self._k_page_tree = None
            self._chunk_page_ids = set()
            self._chunk_page_tree = None
        return self._destination_documents

    # ---------- named destinations (PDFBOX-6283) ----------

    def fix_name_destinations(self) -> None:
        """PDFBOX-6283: fix the destinations in ``/Root/Names/Dests`` by
        creating clones only for the destinations that are in the
        destination documents.

        Mirrors upstream ``Splitter.fixNameDestinations`` (3.0 branch). Each
        entry of the source name tree whose target page went into a chunk is
        cloned (shallow array copy), retargeted at that chunk's imported
        page, and written to a fresh ``/Names /Dests`` name tree on that
        chunk. Entries pointing to pages outside the split, and broken
        entries, are dropped.
        """
        from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
            PDDestination,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination_name_tree_node import (  # noqa: E501
            PDDestinationNameTreeNode,
        )
        from pypdfbox.pdmodel.pd_document_name_dictionary import (
            PDDocumentNameDictionary,
        )

        src_names = self.get_source_document().get_document_catalog().get_names()
        if src_names is None:
            return
        src_dests = src_names.get_dests()
        if src_dests is None:
            return

        dst_tree_as_map_list: list[dict[str, COSBase]] = [
            {} for _ in self._destination_documents
        ]

        # map all named destinations to the pages in the new documents
        src_tree_as_map = src_dests.get_tree_as_map()
        for key, value in src_tree_as_map.items():
            if value is None:
                # happens with file 000671.pdf, entry "Raff1"
                continue
            page_in_tree_dest = value.get_page()
            # find out in which destination document this should be added
            doc_index = (
                None
                if page_in_tree_dest is None
                else self._page_to_doc_num_map.get(id(page_in_tree_dest))
            )
            if doc_index is None:
                # wasn't part of the split
                continue
            # get appropriate mapping
            self._page_dict_map = self._page_dict_maps[doc_index]
            dst_page_dict = self._page_dict_map.get(id(page_in_tree_dest))

            # clone destination
            src_array = value.get_cos_object()
            cloned_destination_array = COSArray(
                [src_array.get(i) for i in range(src_array.size())]
            )
            dst_destination = PDDestination.create(cloned_destination_array)
            dst_destination.set_page(dst_page_dict)

            # add to the tree map of the appropriate destination document
            dst_tree_as_map_list[doc_index][key] = (
                dst_destination.get_cos_object()
            )

        # Assign all non empty tree maps to the new documents
        for i, dst_tree_as_map in enumerate(dst_tree_as_map_list):
            if not dst_tree_as_map:
                continue
            destination_document = self._destination_documents[i]
            dst_document_catalog = destination_document.get_document_catalog()
            dst_document_name_dictionary = PDDocumentNameDictionary(
                dst_document_catalog
            )
            dst_dests = PDDestinationNameTreeNode()
            dst_document_name_dictionary.set_dests(dst_dests)
            dst_document_catalog.set_names(dst_document_name_dictionary)
            _set_flat_names(dst_dests.get_cos_object(), dst_tree_as_map)

    def fix_name_destinations2(self) -> None:
        """PDFBOX-6283: fix the destinations in ``/Root/Dests`` by creating
        clones only for the destinations that are in the destination
        documents.

        Mirrors upstream ``Splitter.fixNameDestinations2`` (3.0 branch). Page
        destinations are cloned and retargeted at the chunk that received
        their page (dropped when the page is outside the split); any other
        resolvable destination doesn't reference a specific page and is
        added to every chunk.
        """
        from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
            PDDestination,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (  # noqa: E501
            PDPageDestination,
        )
        from pypdfbox.pdmodel.pd_document_name_destination_dictionary import (
            PDDocumentNameDestinationDictionary,
        )

        name_destination_dictionary = (
            self.get_source_document().get_document_catalog().get_dests()
        )
        if (
            name_destination_dictionary is None
            or name_destination_dictionary.get_cos_object().size() == 0
        ):
            return

        dst_dests: list[COSDictionary] = [
            COSDictionary() for _ in self._destination_documents
        ]

        # map all named destinations to the pages in the new documents
        for key in list(name_destination_dictionary.get_cos_object().key_set()):
            dest = name_destination_dictionary.get_destination(key.get_name())
            if isinstance(dest, PDPageDestination):
                page_in_tree_dest = dest.get_page()
                # find out in which destination document this should be added
                doc_index = (
                    None
                    if page_in_tree_dest is None
                    else self._page_to_doc_num_map.get(id(page_in_tree_dest))
                )
                if doc_index is None:
                    # wasn't part of the split
                    continue
                # get appropriate mapping
                self._page_dict_map = self._page_dict_maps[doc_index]
                dst_page_dict = self._page_dict_map.get(id(page_in_tree_dest))

                # clone destination
                src_array = dest.get_cos_object()
                cloned_destination_array = COSArray(
                    [src_array.get(i) for i in range(src_array.size())]
                )
                dst_destination = PDDestination.create(cloned_destination_array)
                dst_destination.set_page(dst_page_dict)

                # add to the dictionary of the appropriate destination document
                dst_dests[doc_index].set_item(
                    key, dst_destination.get_cos_object()
                )
            elif dest is not None:
                # add it everywhere, it doesn't reference a specific page
                for dst_dict in dst_dests:
                    dst_dict.set_item(key, dest.get_cos_object())

        # Assign all non empty dictionaries to the new documents
        for i, dst_dict in enumerate(dst_dests):
            if dst_dict.size() == 0:
                continue
            destination_document = self._destination_documents[i]
            dst_document_catalog = destination_document.get_document_catalog()
            # catalog.setDests() doesn't exist upstream, maybe because it
            # feels obsolete
            dst_document_catalog.get_cos_object().set_item(
                _DESTS,
                PDDocumentNameDestinationDictionary(dst_dict).get_cos_object(),
            )

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

        Mirrors upstream ``processPages`` (private in Java). Subclasses
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
        ``/Lang``, ``/MarkInfo``, ``/Metadata``)."""
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
            # PDFBOX-5317: Image Capture Plus files where /Root and /Info
            # share the same dictionary. Only copy simple elements to avoid
            # huge files.
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
                    # there is no /Type in the document information dictionary
                    continue
                dst_info_dict.set_item(key, value)
            document.set_document_information(
                PDDocumentInformation(dst_info_dict)
            )

        dst_catalog = document.get_document_catalog()
        src_catalog = self.get_source_document().get_document_catalog()
        dst_catalog.set_viewer_preferences(src_catalog.get_viewer_preferences())
        dst_catalog.set_language(src_catalog.get_language())
        dst_catalog.set_mark_info(src_catalog.get_mark_info())
        dst_catalog.set_metadata(src_catalog.get_metadata())
        # PDFBOX-6203: reset reused object keys to avoid gaps in the xref
        # table of the split output.
        dst_catalog.get_cos_object().reset_imported_object_keys()
        return document

    def process_page(self, page: PDPage) -> None:
        """Import ``page`` into the current destination document, opening
        a fresh destination first when :meth:`split_at_page` says so.
        Mirrors upstream ``processPage``."""
        self._create_new_document_if_necessary()

        imported = self.get_destination_document().import_page(page)
        page_resources = page.get_resources()
        if page_resources is not None and not page.get_cos_object().contains_key(
            _RESOURCES
        ):
            imported.set_resources(page_resources)
            # follow-up to warning in import_page
            _LOG.info("Resources imported in Splitter")

        if imported.get_cos_object().contains_key(_B):
            imported.get_cos_object().remove_item(_B)
            _LOG.warning("/B entry (beads) removed by splitter")

        # remove page links to avoid copying not needed resources
        self._process_annotations(imported)

        self._page_dict_map[id(page.get_cos_object())] = imported.get_cos_object()
        self._page_to_doc_num_map[id(page.get_cos_object())] = (
            len(self._destination_documents) - 1
        )

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

    def create_new_document_if_necessary(self) -> None:
        """Public-named hook mirroring upstream ``createNewDocumentIfNecessary``.

        Allocates the next destination document when :py:meth:`split_at_page`
        signals a chunk boundary (or when no destination has been
        created yet). Delegates to :py:meth:`_create_new_document_if_necessary`.
        """
        self._create_new_document_if_necessary()

    def process_annotations(self, imported: PDPage) -> None:
        """Public-named hook for upstream's private
        ``processAnnotations(PDPage)``; delegates to
        :py:meth:`_process_annotations`."""
        self._process_annotations(imported)

    def _process_annotations(self, imported: PDPage) -> None:
        """Replace the imported page's annotations by shallow clones.

        Mirrors upstream ``processAnnotations``: every annotation dictionary
        is shallow-copied (and recorded in the chunk's annotation map, used
        by the structure-tree ``OBJR`` rewrite), link destinations to pages
        are cloned and staged for :meth:`fix_destinations`, widget
        ``/Parent`` entries are dropped (non-terminal fields may lead to
        orphan pages), ``/P`` is pointed at the imported page, and markup /
        popup cross references are re-pointed at the clones.
        """
        from pypdfbox.pdmodel.interactive.action.pd_action_factory import (
            PDActionFactory,
        )
        from pypdfbox.pdmodel.interactive.action.pd_action_go_to import (
            PDActionGoTo,
        )
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation import (
            PDAnnotation,
        )
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
            PDAnnotationLink,
        )
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
            PDAnnotationMarkup,
        )
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation_popup import (
            PDAnnotationPopup,
        )
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
            PDAnnotationWidget,
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

        annotations = imported.get_annotations()
        if not annotations:
            return
        imported_page_dict = imported.get_cos_object()

        cloned_annotations: list[Any] = []
        for annotation in annotations:
            # create a shallow clone
            annotation_dict = annotation.get_cos_object()
            cloned_dict = COSDictionary(list(annotation_dict.entry_set()))
            annotation_clone = PDAnnotation.create_annotation(cloned_dict)
            self._annot_dict_map[id(annotation_dict)] = cloned_dict
            cloned_annotations.append(annotation_clone)

            if isinstance(annotation_clone, PDAnnotationLink):
                link = annotation_clone
                src_destination = None
                try:
                    src_destination = link.get_destination()
                except OSError:
                    _LOG.warning(
                        "Incorrect destination in link annotation on page %d "
                        "is removed",
                        self._current_page_number + 1,
                        exc_info=True,
                    )
                    link.set_destination(None)
                action = None
                if src_destination is None:
                    action = link.get_action()
                    if isinstance(action, PDActionGoTo):
                        try:
                            src_destination = action.get_destination()
                        except OSError:
                            _LOG.warning(
                                "GoToAction with incorrect destination in link "
                                "annotation on page %d is removed",
                                self._current_page_number + 1,
                                exc_info=True,
                            )
                            link.set_action(None)
                if isinstance(src_destination, PDNamedDestination):
                    # PDFBOX-5840 / PDFBOX-6283: In a few cases, e.g. in
                    # PDFBOX-5840-410609.pdf 0xAD becomes 0 so the name would
                    # no longer match the entry in the new name tree, so we
                    # replace the name with the actual destination.
                    named_destination_string = (
                        src_destination.get_named_destination()
                    )
                    if (
                        named_destination_string is not None
                        and "\x00" in named_destination_string
                    ):
                        src_destination = (
                            self.get_source_document()
                            .get_document_catalog()
                            .find_named_destination_page(src_destination)
                        )
                if isinstance(src_destination, PDPageDestination):
                    # preserve links to pages within the split result: not
                    # fully possible here because we don't have the full
                    # target document yet. However we're cloning as needed
                    # and remember what to do later.
                    destination_page = src_destination.get_page()
                    if destination_page is not None:
                        # clone destination
                        src_array = src_destination.get_cos_object()
                        cloned_destination_array = COSArray(
                            [src_array.get(i) for i in range(src_array.size())]
                        )
                        dst_destination = PDDestination.create(
                            cloned_destination_array
                        )
                        # remember the destination to adjust / remove page later
                        self._dest_to_fix.append(
                            (dst_destination, imported_page_dict)
                        )
                        self._dest_to_link_map[id(cloned_destination_array)] = (
                            cloned_dict
                        )
                        if action is not None:
                            # if action is not null, then the destination came
                            # from an action, thus clone action as well, then
                            # assign destination clone, then action
                            cloned_action_dict = COSDictionary(
                                list(action.get_cos_object().entry_set())
                            )
                            dst_action = PDActionFactory.create_action(
                                cloned_action_dict
                            )
                            dst_action.set_destination(dst_destination)
                            link.set_action(dst_action)
                        else:
                            # just assign destination clone
                            link.set_destination(dst_destination)

            if isinstance(
                annotation_clone, PDAnnotationWidget
            ) and cloned_dict.contains_key(_PARENT):
                # remove non-terminal field /Parent reference, because this
                # may lead to orphan pages
                cloned_dict.remove_item(_PARENT)
            if annotation.get_page() is not None:
                annotation_clone.set_page(imported)

        # Second loop for markup and popup annotations, which reference
        # annotations themselves
        for annotation in cloned_annotations:
            if isinstance(annotation, PDAnnotationMarkup):
                annotation_popup = annotation.get_popup()
                if annotation_popup is not None:
                    popup_dict = annotation_popup.get_cos_object()
                    cloned_popup_dict = self._annot_dict_map.get(id(popup_dict))
                    if cloned_popup_dict is not None:
                        annotation.get_cos_object().set_item(
                            _POPUP, cloned_popup_dict
                        )
                    else:
                        # orphan popup (not in annotation list); clone it and
                        # fix references
                        cloned_popup_dict = COSDictionary(
                            list(popup_dict.entry_set())
                        )
                        self._annot_dict_map[id(popup_dict)] = cloned_popup_dict
                        annotation_popup_clone = PDAnnotation.create_annotation(
                            cloned_popup_dict
                        )
                        annotation_popup_clone.set_parent(annotation)
                        annotation.set_popup(annotation_popup_clone)
                        if annotation_popup_clone.get_page() is not None:
                            annotation_popup_clone.set_page(imported)
            if isinstance(annotation, PDAnnotationPopup):
                annotation_markup = annotation.get_parent()
                if annotation_markup is None:
                    continue
                cloned_markup_dict = self._annot_dict_map.get(
                    id(annotation_markup.get_cos_object())
                )
                # cloned_markup_dict will be None if the markup annotation is
                # an orphan (not in the annotation list)
                annotation.get_cos_object().set_item(_PARENT, cloned_markup_dict)
        imported.set_annotations(cloned_annotations)

    # ---------- destination fix-up post-pass ----------

    def fix_destinations(self, destination_document: PDDocument) -> None:
        """Retarget or null out the staged link destinations. Mirrors
        upstream ``fixDestinations``: for every staged destination whose
        host page is in ``destination_document``, the page slot becomes the
        chunk's imported copy of the target page when that page is in the
        chunk, else it is nulled (or, with a registered cross-chunk
        resolver, the link becomes a ``GoToR`` action)."""
        page_tree = destination_document.get_pages()
        self._ensure_chunk_page_ids(page_tree)
        for page_destination, src_page_dict in self._dest_to_fix:
            # Find whether source page is inside or outside
            if not self._in_page_tree(page_tree, src_page_dict):
                continue
            target_page_dict = page_destination.get_page()
            if target_page_dict is None:
                continue
            dst_page_dict = self._page_dict_map.get(id(target_page_dict))
            # Find whether destination page is inside or outside
            if dst_page_dict is not None and self._in_page_tree(
                page_tree, dst_page_dict
            ):
                page_destination.set_page(dst_page_dict)
            elif not self._rewrite_cross_chunk_destination(
                page_destination.get_cos_object(), target_page_dict
            ):
                page_destination.set_page(None)

    def _rewrite_cross_chunk_destination(
        self,
        cloned_array: COSArray,
        source_target_page_dict: COSDictionary,
    ) -> bool:
        """Apply the registered cross-chunk destination resolver to a single
        out-of-chunk destination array. Returns ``True`` when the resolver
        opted into a rewrite (``cloned_array``'s page slot now holds the
        integer page index inside the target file and the hosting link's
        ``/A`` is a fresh ``GoToR`` action), or ``False`` when no resolver is
        registered / the resolver returned ``None`` (upstream null-out).
        """
        resolver = self._cross_chunk_destination_resolver
        if resolver is None:
            return False
        try:
            resolved = resolver(source_target_page_dict)
        except Exception:  # defensive: resolver is caller code
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

        # The remaining slots (fit type + coordinates) are preserved.
        cloned_array.set(0, COSInteger.get(page_index))

        link_dict = self._dest_to_link_map.get(id(cloned_array))
        if link_dict is None:
            return True

        action = PDActionRemoteGoTo()
        action.set_file(file_name)
        action.set_destination(cloned_array)
        link_dict.set_item(COSName.get_pdf_name("A"), action.get_cos_object())
        # /A takes precedence per PDF 32000-1 Table 173, but a redundant
        # /Dest confuses some viewers into picking the stale array.
        link_dict.remove_item(COSName.get_pdf_name("Dest"))
        return True

    def _ensure_chunk_page_ids(self, page_tree: Any) -> list[Any]:
        """Return the pages of ``page_tree`` (the chunk being post-processed)
        and snapshot their dictionaries so page-membership tests are O(1).
        Page trees that only offer ``len`` / ``get`` (or pages without a COS
        object) fall back to ``index_of`` lookups."""
        try:
            pages = list(page_tree)
        except TypeError:
            pages = [page_tree.get(i) for i in range(len(page_tree))]
        try:
            self._chunk_page_ids = {id(page.get_cos_object()) for page in pages}
            self._chunk_page_tree = page_tree
        except AttributeError:
            self._chunk_page_ids = set()
            self._chunk_page_tree = None
        return pages

    def _in_page_tree(self, page_tree: Any, page_dict: COSDictionary) -> bool:
        """``PDPageTree.indexOf(page) >= 0``; O(1) for the chunk page tree
        snapshotted by :meth:`_ensure_chunk_page_ids`."""
        if page_tree is self._chunk_page_tree:
            return id(page_dict) in self._chunk_page_ids
        return page_tree.index_of(page_dict) >= 0

    # ---------- structure-tree cloning ----------

    def clone_structure_tree(self, destination_document: PDDocument) -> None:
        """Clone the source ``/StructTreeRoot`` into ``destination_document``,
        keeping only structure elements that pertain to pages in this
        chunk. Mirrors upstream ``Splitter.cloneStructureTree``.
        """
        from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
            PDStructureTreeRoot,
        )

        src_struct_root = (
            self.get_source_document().get_document_catalog().get_struct_tree_root()
        )
        if src_struct_root is None:
            return

        # ``_id_set`` and ``_role_set`` are NOT reset here: upstream
        # initialises them once in ``split()`` and lets them accumulate
        # across chunks.
        self._struct_dict_map = {}
        self._k_skipped = {}

        dst_struct_root = PDStructureTreeRoot()
        dst_struct_root_cos = dst_struct_root.get_cos_object()
        dst_page_tree = destination_document.get_pages()
        dst_pages = self._ensure_chunk_page_ids(dst_page_tree)
        self._k_page_tree = dst_page_tree

        # clone /K, also fills the struct dict map
        src_k = src_struct_root.get_cos_object().get_dictionary_object(_K)
        if self._k_skip_pending:
            self._k_skip_pending = False
            self._build_k_skip_info(src_k)
        cloned_k = self._k_create_clone(
            src_k, dst_struct_root_cos, None, dst_page_tree
        )
        dst_struct_root.set_k(cloned_k)

        # transfer ParentTree using the map because the dictionaries are all
        # found in the /K structure.
        src_parent_tree = src_struct_root.get_parent_tree()
        if src_parent_tree is None:
            src_numbers: dict[int, COSBase] = {}
        elif self._k_node_cache is not None:
            # the source is read-only during split(): flatten it once
            if self._src_number_tree_map is None:
                self._src_number_tree_map = self._get_number_tree_as_map(
                    src_parent_tree
                )
            src_numbers = self._src_number_tree_map
        else:
            src_numbers = self._get_number_tree_as_map(src_parent_tree)
        dst_numbers: dict[int, COSBase] = {}
        for page in dst_pages:
            sp1 = page.get_struct_parents()
            if sp1 != -1:
                self.clone_tree_element(src_numbers, dst_numbers, sp1)
            for ann in page.get_annotations():
                sp2 = ann.get_struct_parent()
                if sp2 != -1:
                    self.clone_tree_element(src_numbers, dst_numbers, sp2)
                normal_appearance_stream = ann.get_normal_appearance_stream()
                if normal_appearance_stream is not None:
                    self.process_resources(
                        normal_appearance_stream.get_resources(),
                        src_numbers,
                        dst_numbers,
                        set(),
                    )
            self.process_resources(
                page.get_resources(), src_numbers, dst_numbers, set()
            )

        dst_number_tree_node = COSDictionary()
        _set_flat_numbers(dst_number_tree_node, dst_numbers)
        dst_struct_root.set_parent_tree(dst_number_tree_node)
        if dst_numbers:
            dst_struct_root.set_parent_tree_next_key(max(dst_numbers) + 1)

        self._clone_class_map(src_struct_root, dst_struct_root)
        self.clone_role_map(src_struct_root, dst_struct_root)
        self.clone_id_tree(src_struct_root, dst_struct_root)

        destination_document.get_document_catalog().set_struct_tree_root(
            dst_struct_root
        )

    @staticmethod
    def _clone_class_map(src_root: Any, dst_root: Any) -> None:
        """``dstRoot.setClassMap(srcRoot.getClassMap())``: upstream reads
        the source ``/ClassMap`` into a ``Map`` of attribute objects (only
        dictionary values and arrays of dictionaries survive) and writes a
        fresh dictionary; an empty map removes the entry."""
        src_dict = src_root.get_cos_object().get_dictionary_object(_CLASS_MAP)
        dst_dict = COSDictionary()
        if isinstance(src_dict, COSDictionary):
            for key, value in src_dict.entry_set():
                if isinstance(value, COSObject):
                    value = value.get_object()
                if isinstance(value, COSDictionary):
                    dst_dict.set_item(key, value)
                elif isinstance(value, COSArray):
                    array = COSArray()
                    for i in range(value.size()):
                        item = value.get_object(i)
                        if isinstance(item, COSDictionary):
                            array.add(item)
                    dst_dict.set_item(key, array)
        if dst_dict.size() == 0:
            dst_root.get_cos_object().remove_item(_CLASS_MAP)
        else:
            dst_root.get_cos_object().set_item(_CLASS_MAP, dst_dict)

    # ---- structure-tree helpers (private; mirror upstream KCloner) ----

    def _k_create_clone(
        self,
        src: COSBase | None,
        dst_parent: COSBase,
        current_page_dict: COSDictionary | None,
        page_tree: Any,
    ) -> COSBase | None:
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
                entry = entry.get_object()
            cloned = self._k_create_clone(
                entry, dst_parent, current_page_dict, page_tree
            )
            # if this is None then they don't belong to the destination
            # document
            if cloned is not None:
                dst.add(cloned)
        return dst if dst.size() > 0 else None

    def _k_node_info(self, src: COSDictionary) -> list[Any]:
        """Return ``[src, /Pg, /K, /Type, ...]`` for a source structure
        dictionary, cached per split() run. The entry pins ``src`` so a
        recycled id() can never match."""
        node_cache = self._k_node_cache
        info = node_cache.get(id(src)) if node_cache is not None else None
        if info is None or info[0] is not src:
            src_page_dict = src.get_dictionary_object(_PG)
            if not isinstance(src_page_dict, COSDictionary):
                src_page_dict = None
            info = [
                src,
                src_page_dict,
                src.get_dictionary_object(_K),
                src.get_name(_TYPE),
            ]
            if node_cache is not None:
                node_cache[id(src)] = info
        return info

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

        info = self._k_node_info(src)
        # Subtree skip (see _build_k_skip_info): with no in-chunk page above
        # and none anywhere below, the subtree's clone is provably None. Its
        # only effect would be the half-built entries upstream leaves in the
        # struct dict map; _struct_lookup recreates those on demand.
        if (
            current_page_dict is None
            and self._k_skip_enabled
            and len(info) > 4
            and not info[5]
            and not (info[4] >> self._k_chunk_index) & 1
        ):
            self._k_skipped[id(src)] = (src, dst_parent)
            return None

        dst, dst_page_dict = self._k_clone_head(
            info, dst_parent, current_page_dict, page_tree
        )
        if dst is None:
            return None
        kid = info[2]
        cloned_kid = self._k_create_clone(
            kid,
            dst,
            dst_page_dict if dst_page_dict is not None else current_page_dict,
            page_tree,
        )
        if cloned_kid is None and kid is not None:
            # kids array wasn't empty, but is empty now => ignore
            return None

        # removes orphan nodes: if no parent page and no page here and no
        # kids, assume this is an orphan
        if dst_page_dict is None and cloned_kid is None and current_page_dict is None:
            return None

        dst.set_item(_K, cloned_kid)

        id_value = dst.get_string(_ID)
        if id_value is not None:
            self._id_set.add(id_value)
        role = dst.get_name(_S)
        if role is not None:
            self._role_set.add(role)
        return dst

    def _k_clone_head(
        self,
        info: list[Any],
        dst_parent: COSBase,
        current_page_dict: COSDictionary | None,
        page_tree: Any,
    ) -> tuple[COSDictionary | None, COSDictionary | None]:
        """The part of upstream ``createDictionaryClone`` before the kids
        are cloned. Returns ``(clone, dst_page_dict)``; ``clone`` is
        ``None`` when the element is dropped before its kids are visited
        (it may still have been registered in the struct dict map)."""
        src, src_page_dict, kid, type_name = info[0], info[1], info[2], info[3]
        dst_page_dict: COSDictionary | None = None

        if src_page_dict is not None:
            dst_page_dict = self._page_dict_map.get(id(src_page_dict))
            if dst_page_dict is not None:
                if not self._in_page_tree(page_tree, dst_page_dict):
                    return None, None
            elif (
                type_name == "MCR"
                or type_name == "OBJR"
                or self._has_mcids(kid)
            ):
                # PDFBOX-6009: "wrong" /Pg entry. Quit if MCIDs because
                # these need a /Pg entry, or if MCR/OBJR dicts; else keep
                # this as an intermediate element for now.
                return None, None

        # special handling for MCR items ("marked-content reference
        # dictionary"). PAC: /Pg entry of marked-content reference and of
        # parent structure is null.
        if (
            type_name == "MCR"
            and dst_page_dict is None
            and isinstance(dst_parent, COSDictionary)
            and dst_parent.get_dictionary_object(_PG) is None
        ):
            return None, None

        # Create and fill clone. Upstream registers the clone before the
        # checks below and never unregisters it, so a dropped element still
        # resolves through the map (e.g. for /ParentTree and /IDTree).
        dst = COSDictionary()
        self._struct_dict_map[id(src)] = dst
        for key, value in src.entry_set():
            if key != _K and key != _PG and key != _P:
                dst.set_item(key, value)

        # special handling for OBJR items ("object reference dictionary")
        if type_name == "OBJR":
            src_obj = src.get_dictionary_object(_OBJ)
            dst_obj = (
                self._annot_dict_map.get(id(src_obj))
                if isinstance(src_obj, COSDictionary)
                else None
            )
            if dst_obj is not None:
                # replace annotation with clone
                dst.set_item(_OBJ, dst_obj)
            elif isinstance(src_obj, COSDictionary):
                self._remove_possible_orphan_annotation(
                    src_obj, src, current_page_dict, dst
                )
            if dst.size() == 1:
                return None, None
            if (
                dst_page_dict is None
                and isinstance(dst_parent, COSDictionary)
                and dst_parent.get_dictionary_object(_PG) is None
            ):
                # Pg entry of object reference dictionary and of parent
                # structure is null
                return None, None

        if type_name != "OBJR" and type_name != "MCR":
            # /P not needed for OBJR or MCR items
            dst.set_item(_P, dst_parent)
        dst.set_item(_PG, dst_page_dict)
        return dst, dst_page_dict

    def _build_k_skip_info(self, src_k: COSBase | None) -> None:
        """Annotate every source structure element once per split() run so
        each chunk's clone can skip subtrees that cannot contribute to it.

        Upstream's KCloner re-walks the complete source /K tree for every
        output document, which makes an N-chunk split of a tagged file
        O(N * tree). For each element reachable from /K this extends its
        ``_k_node_cache`` entry with ``mask`` (bit ``i`` set when some /Pg
        in the subtree is a page of destination document ``i``), ``live``
        (the subtree can yield a clone even when no /Pg in it belongs to the
        chunk and no ancestor supplied an in-chunk page) and the parent
        element (``None`` at the top level).

        With no in-chunk page above (``current_page_dict is None``), a
        subtree with neither the chunk's bit nor ``live`` clones to ``None``.
        Walking it would still register half-built clones in the struct dict
        map (upstream never removes them, and they surface through
        /ParentTree and /IDTree), so a skipped subtree is recorded and
        :meth:`_struct_lookup` replays exactly that part of the walk for any
        element that is looked up later. ``live`` mirrors the clone rules
        for that context: scalars survive; ``MCR`` and ``OBJR`` never do; an
        element whose out-of-chunk /Pg carries MCIDs is dropped; otherwise
        an element survives iff its /K does. If any element or array is
        reachable twice (shared node or cycle), or the tree is too deep,
        skipping is disabled for the run.
        """
        if self._k_node_cache is None:
            return
        page_chunk = self._page_to_doc_num_map
        seen: set[int] = set()
        shared = False

        def visit(
            node: COSBase | None, parent: COSDictionary | None, depth: int
        ) -> tuple[int, bool]:
            nonlocal shared
            if isinstance(node, COSObject):
                node = node.get_object()
            if node is None:
                return 0, False
            if not isinstance(node, (COSArray, COSDictionary)):
                return 0, True
            if id(node) in seen or depth > 500:
                shared = True
                return 0, True
            seen.add(id(node))
            if isinstance(node, COSArray):
                mask = 0
                live = False
                for i in range(node.size()):
                    m, alive = visit(node.get(i), parent, depth + 1)
                    mask |= m
                    live = live or alive
                return mask, live
            info = self._k_node_info(node)
            src_page_dict, kid, type_name = info[1], info[2], info[3]
            mask, kid_live = visit(kid, node, depth + 1)
            if src_page_dict is not None:
                chunk = page_chunk.get(id(src_page_dict))
                if chunk is not None:
                    mask |= 1 << chunk
            if (
                type_name == "MCR"
                or type_name == "OBJR"
                or (src_page_dict is not None and self._has_mcids(kid))
            ):
                live = False
            else:
                live = kid_live
            del info[4:]
            info.extend((mask, live, parent))
            return mask, live

        try:
            visit(src_k, None, 0)
        except RecursionError:
            shared = True
        self._k_skip_enabled = not shared

    def _struct_lookup(self, src: COSBase | None) -> COSDictionary | None:
        """``structDictMap.get(src)`` for the chunk being cloned.

        When the element sits in a subtree that :meth:`_k_clone_dictionary`
        skipped, the skipped part of upstream's walk is replayed along the
        path down to ``src`` first: every element on it gets the clone
        upstream would have registered (the head of ``createDictionaryClone``
        with no in-chunk page), and its kids become pending skipped subtrees.
        """
        hit = self._struct_dict_map.get(id(src))
        if hit is not None or not self._k_skipped or self._k_node_cache is None:
            return hit
        # climb to the nearest pending skipped subtree
        path: list[COSDictionary] = []
        node = src
        while id(node) not in self._k_skipped:
            if id(node) in self._struct_dict_map:
                return None
            info = self._k_node_cache.get(id(node))
            if info is None or info[0] is not node or len(info) < 7:
                return None
            path.append(node)
            node = info[6]
            if node is None:
                return None
        # replay the walk from the skipped subtree down to src
        while True:
            _, dst_parent = self._k_skipped.pop(id(node))
            info = self._k_node_info(node)
            dst, _ = self._k_clone_head(info, dst_parent, None, self._k_page_tree)
            if dst is None:
                break
            self._k_register_skipped_kids(info[2], dst)
            if not path:
                break
            node = path.pop()
            if id(node) not in self._k_skipped:
                break
        return self._struct_dict_map.get(id(src))

    def _k_register_skipped_kids(self, kid: COSBase | None, dst: COSDictionary) -> None:
        """Record the structure dictionaries among ``kid`` (a /K value) as
        pending skipped subtrees whose clones get ``dst`` as /P."""
        if isinstance(kid, COSObject):
            kid = kid.get_object()
        if isinstance(kid, COSDictionary):
            self._k_skipped[id(kid)] = (kid, dst)
        elif isinstance(kid, COSArray):
            # nested arrays pass the same parent down, as in the walk
            for i in range(kid.size()):
                self._k_register_skipped_kids(kid.get(i), dst)

    @staticmethod
    def _has_mcids(kid: COSBase | None) -> bool:
        if isinstance(kid, COSInteger):
            return True
        if isinstance(kid, COSArray):
            for i in range(kid.size()):
                if isinstance(kid.get_object(i), COSInteger):
                    return True
        return False

    def _remove_possible_orphan_annotation(
        self,
        src_obj: COSDictionary,
        src_dict: COSDictionary,
        current_page_dict: COSDictionary | None,
        dst_dict: COSDictionary,
    ) -> None:
        # PDFBOX-5929: Check whether this is an "orphan" annotation that
        # isn't in the page
        obj_type = src_obj.get_dictionary_object(_TYPE)
        obj_subtype = src_obj.get_dictionary_object(_SUBTYPE)
        is_annot = isinstance(obj_type, COSName) and obj_type.get_name() == "Annot"
        is_link = isinstance(obj_subtype, COSName) and obj_subtype.get_name() == "Link"
        if not is_annot and not is_link:
            return
        src_page_dict = src_dict.get_dictionary_object(_PG)
        if not isinstance(src_page_dict, COSDictionary):
            # /Pg entry is not always on this level
            src_page_dict = current_page_dict
        if src_page_dict is None:
            return
        annotation_array = src_page_dict.get_dictionary_object(_ANNOTS)
        if isinstance(annotation_array, COSArray):
            for i in range(annotation_array.size()):
                if annotation_array.get_object(i) is src_obj:
                    return
        # Ideally the entire OBJR entry should be removed. Removing the OBJ
        # entry is done to avoid potential page orphans from the annotation
        # destination.
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
        """Clone a ``/ParentTree`` value using the struct dict map so that
        structure elements are replaced. Mirrors upstream
        ``cloneTreeElement``."""
        src_obj = src_numbers.get(sp)
        if src_obj is None:
            return
        dst_obj: COSBase | None = None
        if isinstance(src_obj, COSArray):
            # create a clone of the array; elements may be null
            dst_array = COSArray()
            for i in range(src_obj.size()):
                element = src_obj.get_object(i)
                cloned_entry = self._struct_lookup(element)
                dst_array.add(COSNull.NULL if cloned_entry is None else cloned_entry)
            dst_obj = dst_array
        elif isinstance(src_obj, COSDictionary):
            # get the clone from the map
            dst_obj = self._struct_lookup(src_obj)
            if dst_obj is None:
                _LOG.warning("ParentTree index %d dictionary not found in /K", sp)
        else:
            _LOG.warning(
                "tree element neither dictionary nor array, but %s",
                type(src_obj).__name__,
            )
        if dst_obj is not None:
            dst_numbers[sp] = dst_obj

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
        self, src_root: Any, dst_root: Any, name_tree_cls: type | None = None
    ) -> None:
        """Mirror upstream ``cloneIDTree``: a fresh flat ``/IDTree`` with the
        ids seen so far whose source element has a clone in this chunk
        (always written when the source has an ``/IDTree``)."""
        src_id_tree = src_root.get_id_tree()
        if src_id_tree is None:
            return
        if name_tree_cls is None:
            from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (  # noqa: E501
                PDStructureElementNameTreeNode,
            )

            name_tree_cls = PDStructureElementNameTreeNode
        if self._k_node_cache is not None:
            # the source is read-only during split(): flatten it once
            if self._src_id_tree_map is None:
                self._src_id_tree_map = self._get_id_tree_as_map(src_id_tree)
            src_id_map = self._src_id_tree_map
        else:
            src_id_map = self._get_id_tree_as_map(src_id_tree)
        dst_names: dict[str, COSBase] = {}
        for key, val in src_id_map.items():
            if key not in self._id_set:
                continue
            src_dict = val.get_cos_object() if hasattr(val, "get_cos_object") else val
            cloned_dict = self._struct_lookup(src_dict)
            if cloned_dict is not None:
                dst_names[key] = cloned_dict
        dst_id_tree = name_tree_cls()
        _set_flat_names(dst_id_tree.get_cos_object(), dst_names)
        dst_root.set_id_tree(dst_id_tree)

    @staticmethod
    def _get_number_tree_as_map(node: Any) -> dict[int, COSBase]:
        """Flatten a number tree into ``{int: COSBase}`` (values unwrapped).
        Mirrors upstream ``getTreeAsMap`` on the source ``/ParentTree``."""
        out: dict[int, COSBase] = {}
        for key, value in node.get_tree_as_map().items():
            out[int(key)] = (
                value.get_cos_object() if hasattr(value, "get_cos_object") else value
            )
        return out

    @staticmethod
    def _get_id_tree_as_map(node: Any) -> dict[str, Any]:
        """Flatten an ID name tree. Mirrors upstream ``getTreeAsMap`` on the
        source ``/IDTree``."""
        return node.get_tree_as_map()

    # ---------- resource walking ----------

    def process_resources(
        self,
        resources: Any,
        src_numbers: dict[int, COSBase],
        dst_numbers: dict[int, COSBase],
        visited: set[int],
    ) -> None:
        """Look for ``/StructParent`` and ``/StructParents`` of form and
        image XObjects in ``resources`` and add them to the destination
        tree (mirrors upstream ``Splitter.processResources``).

        ``visited`` tracks resource dictionary identities to break cycles
        (upstream: 002874.pdf).
        """
        from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (
            PDFormXObject,
        )
        from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
            PDImageXObject,
        )

        if resources is None:
            return
        cos_id = id(resources.get_cos_object())
        if cos_id in visited:
            # avoid endless recursion
            return
        visited.add(cos_id)

        for name in resources.get_xobject_names():
            x_object = resources.get_x_object(name)
            sp = -1
            if isinstance(x_object, PDFormXObject):
                sp = x_object.get_struct_parents()
                self.process_resources(
                    x_object.get_resources(), src_numbers, dst_numbers, visited
                )
            elif isinstance(x_object, PDImageXObject):
                sp = x_object.get_struct_parent()
            if sp != -1:
                self.clone_tree_element(src_numbers, dst_numbers, sp)

    # ---------- private-name aliases ----------
    #
    # Upstream keeps these private; the public names make the Java naming
    # round-trip through the parity tracker, and the underscored aliases keep
    # internal callers and subclass overrides working.
    _clone_structure_tree = clone_structure_tree
    _clone_tree_element = clone_tree_element
    _clone_role_map = clone_role_map
    _clone_id_tree = clone_id_tree
    _fix_destinations = fix_destinations


__all__ = ["Splitter"]
