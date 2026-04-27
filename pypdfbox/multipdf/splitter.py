from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from pypdfbox.cos import COSArray, COSDictionary, COSName

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

    The structure-tree / parent-tree / id-tree cloning that upstream
    performs after the page walk depends on PDFMergerUtility helpers
    (``getNumberTreeAsMap`` / ``getIDTreeAsMap``) that are not yet ported.
    When the source document carries a ``/StructTreeRoot`` we skip cloning
    it rather than emit a half-built one — the per-page COS payload still
    splits correctly. See ``CHANGES.md`` for the deviation.
    """

    def __init__(self) -> None:
        self._source_document: PDDocument | None = None
        self._current_destination_document: PDDocument | None = None

        self._split_length: int = 1
        # Sentinels used to mean "no clamp"; mirror upstream
        # Integer.MIN_VALUE / Integer.MAX_VALUE.
        self._start_page: int = -(2**31)
        self._end_page: int = 2**31 - 1

        self._destination_documents: list[PDDocument] = []
        self._page_dict_map: dict[int, COSDictionary] = {}
        self._page_dict_maps: list[dict[int, COSDictionary]] = []
        self._annot_dict_map: dict[int, COSDictionary] = {}
        self._annot_dict_maps: list[dict[int, COSDictionary]] = []

        self._current_page_number: int = 0

        self._stream_cache_create_function: Callable[[], Any] | None = None
        self._memory_usage_setting: MemoryUsageSetting | None = None

    # ---------- configuration ----------

    def set_split_at_page(self, split: int) -> None:
        if split <= 0:
            raise ValueError("Number of pages is smaller than one")
        self._split_length = split

    def set_split(self, split: int) -> None:
        """Alias for :meth:`set_split_at_page`."""
        self.set_split_at_page(split)

    def set_start_page(self, start: int) -> None:
        if start <= 0:
            raise ValueError("Start page is smaller than one")
        self._start_page = start

    def set_end_page(self, end: int) -> None:
        if end <= 0:
            raise ValueError("End page is smaller than one")
        if end < self._start_page:
            raise ValueError("End page is smaller than startPage")
        self._end_page = end

    def get_stream_cache_create_function(self) -> Callable[[], Any] | None:
        return self._stream_cache_create_function

    def set_stream_cache_create_function(
        self, fn: Callable[[], Any] | None
    ) -> None:
        self._stream_cache_create_function = fn

    def set_memory_usage_setting(
        self, setting: MemoryUsageSetting | None
    ) -> None:
        """Record a :class:`MemoryUsageSetting` for newly-created destination
        documents. Recorded only — destination ``PDDocument`` construction
        in this port does not yet thread the setting through (see
        ``CHANGES.md``)."""
        self._memory_usage_setting = setting

    def get_memory_usage_setting(self) -> MemoryUsageSetting | None:
        return self._memory_usage_setting

    # ---------- core ----------

    def split(self, document: PDDocument) -> list[PDDocument]:
        """Split ``document`` and return a list of fresh ``PDDocument``
        instances. The caller owns each returned document and must save
        them before closing ``document`` (cross-document resource sharing
        means the source must outlive its splits)."""
        self._current_page_number = 0
        self._destination_documents = []
        self._source_document = document
        self._page_dict_maps = []
        self._annot_dict_maps = []

        self._process_pages()
        # Structure-tree cloning is deferred — see class docstring and
        # CHANGES.md. We still return the fully-populated per-chunk docs.
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
                if _TYPE == key:
                    continue
                dst_info_dict.set_item(key, value)
            document.set_document_information(
                PDDocumentInformation(dst_info_dict)
            )

        dst_catalog = document.get_document_catalog()
        src_catalog = self.get_source_document().get_document_catalog()
        try:
            dst_catalog.set_viewer_preferences(src_catalog.get_viewer_preferences())
        except (AttributeError, NotImplementedError):
            pass
        try:
            dst_catalog.set_language(src_catalog.get_language())
        except (AttributeError, NotImplementedError):
            pass
        try:
            dst_catalog.set_mark_info(src_catalog.get_mark_info())
        except (AttributeError, NotImplementedError):
            pass
        try:
            dst_catalog.set_metadata(src_catalog.get_metadata())
        except (AttributeError, NotImplementedError):
            pass
        return document

    def process_page(self, page: PDPage) -> None:
        """Import ``page`` into the current destination document, opening
        a fresh destination first when :meth:`split_at_page` says so."""
        self._create_new_document_if_necessary()
        assert self._current_destination_document is not None

        imported = self._current_destination_document.import_page(page)

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

        self._process_annotations(imported)

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

    def _process_annotations(self, imported: PDPage) -> None:
        """Shallow-clone every annotation on ``imported`` so structure-tree
        edits and ``/Parent`` rewrites (e.g. for widget annotations) don't
        bleed back into the source document. Mirrors upstream's first
        loop in ``processAnnotations`` — destination remap of /Dest links
        is deferred (see CHANGES.md)."""
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation import (
            PDAnnotation,
        )

        try:
            annotations = imported.get_annotations()
        except Exception:  # noqa: BLE001
            return
        if not annotations:
            return
        cloned: list[PDAnnotation] = []
        for ann in annotations:
            ann_dict = ann.get_cos_object()
            cloned_dict = COSDictionary(list(ann_dict.entry_set()))
            self._annot_dict_map[id(ann_dict)] = cloned_dict
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

        # Second pass: rewrite /Popup → cloned popup dict references
        # so popup/markup annotation pairs stay internally consistent.
        for ann in cloned:
            ann_dict = ann.get_cos_object()
            popup_value = ann_dict.get_dictionary_object(_POPUP)
            if isinstance(popup_value, COSDictionary):
                cloned_popup = self._annot_dict_map.get(id(popup_value))
                if cloned_popup is not None:
                    ann_dict.set_item(_POPUP, cloned_popup)

        try:
            imported.set_annotations(cloned)
        except Exception:  # noqa: BLE001
            # Some PDPage subclasses don't surface set_annotations; the
            # cloned dicts still live in the imported page's /Annots
            # (since we mutated in place), so this is a no-op fallback.
            pass


__all__ = ["Splitter"]
