from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSName

from .interactive.annotation.pd_appearance_stream_name_tree_node import (
    PDAppearanceStreamNameTreeNode,
)
from .interactive.documentnavigation.destination import PDDestinationNameTreeNode
from .pd_alternate_presentations_name_tree_node import (
    PDAlternatePresentationsNameTreeNode,
)
from .pd_document_name_destination_dictionary import PDDocumentNameDestinationDictionary
from .pd_embedded_files_name_tree_node import PDEmbeddedFilesNameTreeNode
from .pd_ids_name_tree_node import PDIDSNameTreeNode
from .pd_javascript_name_tree_node import PDJavascriptNameTreeNode
from .pd_pages_name_tree_node import PDPagesNameTreeNode
from .pd_renditions_name_tree_node import PDRenditionsNameTreeNode
from .pd_templates_name_tree_node import PDTemplatesNameTreeNode
from .pd_urls_name_tree_node import PDURLSNameTreeNode

_NAMES: COSName = COSName.get_pdf_name("Names")
_DESTS: COSName = COSName.get_pdf_name("Dests")
_AP: COSName = COSName.get_pdf_name("AP")
_EMBEDDED_FILES: COSName = COSName.get_pdf_name("EmbeddedFiles")
_JAVA_SCRIPT: COSName = COSName.get_pdf_name("JavaScript")
_PAGES: COSName = COSName.get_pdf_name("Pages")
_TEMPLATES: COSName = COSName.get_pdf_name("Templates")
_IDS: COSName = COSName.get_pdf_name("IDS")
_URLS: COSName = COSName.get_pdf_name("URLS")
_ALTERNATE_PRESENTATIONS: COSName = COSName.get_pdf_name("AlternatePresentations")
_RENDITIONS: COSName = COSName.get_pdf_name("Renditions")


_NAME_KEYS: tuple[COSName, ...] = (
    _DESTS,
    _AP,
    _EMBEDDED_FILES,
    _JAVA_SCRIPT,
    _PAGES,
    _TEMPLATES,
    _IDS,
    _URLS,
    _ALTERNATE_PRESENTATIONS,
    _RENDITIONS,
)


class PDDocumentNameDictionary:
    """
    Catalog ``/Names`` typed wrapper. Mirrors PDFBox
    ``PDDocumentNameDictionary``.

    Holds the per-category named-resource sub-dictionaries available at
    the document level: ``/Dests``, ``/AP``, ``/EmbeddedFiles``,
    ``/JavaScript``, ``/Pages``, ``/Templates``, ``/IDS``, ``/URLS``,
    ``/AlternatePresentations`` and ``/Renditions``. ``/AP`` resolves to
    a :class:`PDAppearanceStreamNameTreeNode` whose leaves are
    ``PDAppearanceStream`` Form XObjects.
    """

    # ``/Names`` sub-dictionary key constants (PDF 32000-1 §7.7.4, Table 31).
    # Upstream PDFBox reads these directly from ``COSName`` shared instances;
    # pypdfbox surfaces them on the wrapper class so callers can iterate over
    # the full set of name-tree keys without re-deriving the spelling.
    KEY_DESTS: COSName = _DESTS
    KEY_AP: COSName = _AP
    KEY_EMBEDDED_FILES: COSName = _EMBEDDED_FILES
    KEY_JAVA_SCRIPT: COSName = _JAVA_SCRIPT
    KEY_PAGES: COSName = _PAGES
    KEY_TEMPLATES: COSName = _TEMPLATES
    KEY_IDS: COSName = _IDS
    KEY_URLS: COSName = _URLS
    KEY_ALTERNATE_PRESENTATIONS: COSName = _ALTERNATE_PRESENTATIONS
    KEY_RENDITIONS: COSName = _RENDITIONS

    #: Tuple of every ``/Names`` sub-dictionary key in PDF 32000-1 Table 31
    #: order. Useful for iteration, validation, and round-trip enumeration.
    NAME_KEYS: tuple[COSName, ...] = _NAME_KEYS

    def __init__(
        self,
        catalog: Any | None = None,
        names: COSDictionary | None = None,
    ) -> None:
        self._catalog = catalog
        if names is not None:
            self._name_dictionary: COSDictionary = names
        elif catalog is not None:
            cat_cos = catalog.get_cos_object()
            existing = cat_cos.get_dictionary_object(_NAMES)
            if isinstance(existing, COSDictionary):
                self._name_dictionary = existing
            else:
                self._name_dictionary = COSDictionary()
                cat_cos.set_item(_NAMES, self._name_dictionary)
        else:
            self._name_dictionary = COSDictionary()

    # ---------- COS plumbing ----------

    def get_cos_object(self) -> COSDictionary:
        return self._name_dictionary

    def get_cos_dictionary(self) -> COSDictionary:
        return self._name_dictionary

    def is_empty(self) -> bool:
        """``True`` when the underlying ``/Names`` sub-dictionary has no entries.

        Python-friendly convenience; upstream PDFBox does not expose an
        equivalent. Mirrors ``COSDictionary.isEmpty()`` semantics.
        """
        return self._name_dictionary.is_empty()

    def __bool__(self) -> bool:  # pragma: no cover - thin wrapper
        return not self.is_empty()

    # ---------- presence predicates ----------
    #
    # Cheap "is this sub-dictionary present?" checks that don't allocate
    # a typed wrapper. Useful when callers only need to know whether a
    # category exists (e.g. preflight-style enumeration). Upstream PDFBox
    # has no equivalent; callers there reach through
    # ``getCOSObject().getCOSDictionary(KEY) != null``.
    #
    # Each predicate considers the entry "present" iff the underlying
    # ``/Names`` sub-dictionary contains the key AND the resolved value is
    # a ``COSDictionary``. A key with a non-dict value (e.g. a stray name
    # or array) reports ``False`` so callers don't trip over malformed
    # inputs when they expect a typed wrapper to follow.

    def _has_dict_entry(self, key: COSName) -> bool:
        return isinstance(self._name_dictionary.get_dictionary_object(key), COSDictionary)

    def has_dests(self) -> bool:
        """``True`` when ``/Names /Dests`` is a dictionary, or — matching
        :meth:`get_dests` fallback — when the catalog carries a legacy
        ``/Dests`` dict. This mirrors the lookup order in ``get_dests``."""
        if self._has_dict_entry(_DESTS):
            return True
        if self._catalog is not None:
            cat_dests = self._catalog.get_cos_object().get_dictionary_object(_DESTS)
            if isinstance(cat_dests, COSDictionary):
                return True
        return False

    def has_ap(self) -> bool:
        """``True`` when ``/Names /AP`` is a dictionary."""
        return self._has_dict_entry(_AP)

    def has_embedded_files(self) -> bool:
        """``True`` when ``/Names /EmbeddedFiles`` is a dictionary."""
        return self._has_dict_entry(_EMBEDDED_FILES)

    def has_javascript(self) -> bool:
        """``True`` when ``/Names /JavaScript`` is a dictionary."""
        return self._has_dict_entry(_JAVA_SCRIPT)

    def has_pages(self) -> bool:
        """``True`` when ``/Names /Pages`` is a dictionary."""
        return self._has_dict_entry(_PAGES)

    def has_templates(self) -> bool:
        """``True`` when ``/Names /Templates`` is a dictionary."""
        return self._has_dict_entry(_TEMPLATES)

    def has_ids(self) -> bool:
        """``True`` when ``/Names /IDS`` is a dictionary."""
        return self._has_dict_entry(_IDS)

    def has_urls(self) -> bool:
        """``True`` when ``/Names /URLS`` is a dictionary."""
        return self._has_dict_entry(_URLS)

    def has_alternate_presentations(self) -> bool:
        """``True`` when ``/Names /AlternatePresentations`` is a dictionary."""
        return self._has_dict_entry(_ALTERNATE_PRESENTATIONS)

    def has_renditions(self) -> bool:
        """``True`` when ``/Names /Renditions`` is a dictionary."""
        return self._has_dict_entry(_RENDITIONS)

    # ---------- /Dests ----------

    def get_dests(
        self,
    ) -> PDDestinationNameTreeNode | None:
        dic = self._name_dictionary.get_dictionary_object(_DESTS)
        if isinstance(dic, COSDictionary):
            return PDDestinationNameTreeNode(dic)
        if self._catalog is not None:
            cat_dests = self._catalog.get_cos_object().get_dictionary_object(_DESTS)
            if isinstance(cat_dests, COSDictionary):
                return PDDestinationNameTreeNode(cat_dests)
        return None

    def set_dests(
        self,
        dests: PDDestinationNameTreeNode | PDDocumentNameDestinationDictionary | None,
    ) -> None:
        if dests is None:
            self._name_dictionary.remove_item(_DESTS)
        else:
            self._name_dictionary.set_item(_DESTS, dests.get_cos_object())
        # Per upstream: when /Dests is set on /Names, clear the catalog's
        # legacy direct /Dests entry to avoid two competing sources.
        if self._catalog is not None:
            self._catalog.get_cos_object().remove_item(_DESTS)

    # ---------- /EmbeddedFiles ----------

    def get_embedded_files(self) -> PDEmbeddedFilesNameTreeNode | None:
        dic = self._name_dictionary.get_dictionary_object(_EMBEDDED_FILES)
        if isinstance(dic, COSDictionary):
            return PDEmbeddedFilesNameTreeNode(dic)
        return None

    def set_embedded_files(
        self, embedded_files: PDEmbeddedFilesNameTreeNode | None
    ) -> None:
        if embedded_files is None:
            self._name_dictionary.remove_item(_EMBEDDED_FILES)
        else:
            self._name_dictionary.set_item(
                _EMBEDDED_FILES, embedded_files.get_cos_object()
            )

    # ---------- /JavaScript ----------

    def get_javascript(self) -> PDJavascriptNameTreeNode | None:
        dic = self._name_dictionary.get_dictionary_object(_JAVA_SCRIPT)
        if isinstance(dic, COSDictionary):
            return PDJavascriptNameTreeNode(dic)
        return None

    def get_java_script(self) -> PDJavascriptNameTreeNode | None:
        """Strict snake_case translation of upstream ``getJavaScript()``.

        Upstream is inconsistent — ``getJavaScript`` (camelCase) but
        ``setJavascript`` (lowercase 's'). pypdfbox originally surfaced
        only the lowercase ``get_javascript`` form; this alias matches the
        mechanical camelCase → snake_case translation.
        """
        return self.get_javascript()

    def set_javascript(self, javascript: PDJavascriptNameTreeNode | None) -> None:
        if javascript is None:
            self._name_dictionary.remove_item(_JAVA_SCRIPT)
        else:
            self._name_dictionary.set_item(
                _JAVA_SCRIPT, javascript.get_cos_object()
            )

    # ---------- /Pages ----------

    def get_pages(self) -> PDPagesNameTreeNode | None:
        dic = self._name_dictionary.get_dictionary_object(_PAGES)
        if isinstance(dic, COSDictionary):
            return PDPagesNameTreeNode(dic)
        return None

    def set_pages(self, pages: PDPagesNameTreeNode | None) -> None:
        if pages is None:
            self._name_dictionary.remove_item(_PAGES)
        else:
            self._name_dictionary.set_item(_PAGES, pages.get_cos_object())

    # ---------- /Templates ----------

    def get_templates(self) -> PDTemplatesNameTreeNode | None:
        dic = self._name_dictionary.get_dictionary_object(_TEMPLATES)
        if isinstance(dic, COSDictionary):
            return PDTemplatesNameTreeNode(dic)
        return None

    def set_templates(self, templates: PDTemplatesNameTreeNode | None) -> None:
        if templates is None:
            self._name_dictionary.remove_item(_TEMPLATES)
        else:
            self._name_dictionary.set_item(_TEMPLATES, templates.get_cos_object())

    # ---------- /IDS ----------

    def get_ids(self) -> PDIDSNameTreeNode | None:
        dic = self._name_dictionary.get_dictionary_object(_IDS)
        if isinstance(dic, COSDictionary):
            return PDIDSNameTreeNode(dic)
        return None

    def set_ids(self, ids: PDIDSNameTreeNode | None) -> None:
        if ids is None:
            self._name_dictionary.remove_item(_IDS)
        else:
            self._name_dictionary.set_item(_IDS, ids.get_cos_object())

    # ---------- /URLS ----------

    def get_urls(self) -> PDURLSNameTreeNode | None:
        dic = self._name_dictionary.get_dictionary_object(_URLS)
        if isinstance(dic, COSDictionary):
            return PDURLSNameTreeNode(dic)
        return None

    def set_urls(self, urls: PDURLSNameTreeNode | None) -> None:
        if urls is None:
            self._name_dictionary.remove_item(_URLS)
        else:
            self._name_dictionary.set_item(_URLS, urls.get_cos_object())

    # ---------- /AlternatePresentations ----------

    def get_alternate_presentations(
        self,
    ) -> PDAlternatePresentationsNameTreeNode | None:
        dic = self._name_dictionary.get_dictionary_object(_ALTERNATE_PRESENTATIONS)
        if isinstance(dic, COSDictionary):
            return PDAlternatePresentationsNameTreeNode(dic)
        return None

    def set_alternate_presentations(
        self, alternate_presentations: PDAlternatePresentationsNameTreeNode | None
    ) -> None:
        if alternate_presentations is None:
            self._name_dictionary.remove_item(_ALTERNATE_PRESENTATIONS)
        else:
            self._name_dictionary.set_item(
                _ALTERNATE_PRESENTATIONS,
                alternate_presentations.get_cos_object(),
            )

    # ---------- /Renditions ----------

    def get_renditions(self) -> PDRenditionsNameTreeNode | None:
        dic = self._name_dictionary.get_dictionary_object(_RENDITIONS)
        if isinstance(dic, COSDictionary):
            return PDRenditionsNameTreeNode(dic)
        return None

    def set_renditions(self, renditions: PDRenditionsNameTreeNode | None) -> None:
        if renditions is None:
            self._name_dictionary.remove_item(_RENDITIONS)
        else:
            self._name_dictionary.set_item(_RENDITIONS, renditions.get_cos_object())

    # ---------- /AP ----------

    def get_ap(self) -> PDAppearanceStreamNameTreeNode | None:
        """Return ``/AP`` as a typed appearance-stream name tree, or
        ``None`` when absent.

        ``/AP`` is the document-level name tree mapping name strings to
        appearance streams (PDF 32000-1 §7.7.4, Table 31). Upstream
        PDFBox 3.x does not expose a public accessor for ``/AP`` on
        ``PDDocumentNameDictionary``; pypdfbox surfaces it as
        :class:`PDAppearanceStreamNameTreeNode` so the leaf values are
        typed as ``PDAppearanceStream`` (matching the shape of the
        sibling typed name-tree wrappers exposed on this class).
        """
        dic = self._name_dictionary.get_dictionary_object(_AP)
        if isinstance(dic, COSDictionary):
            return PDAppearanceStreamNameTreeNode(dic)
        return None

    def get_ap_raw(self) -> COSDictionary | None:
        """Return the raw ``/AP`` name-tree dictionary, or ``None``.

        Lower-level escape hatch kept for callers that need to bypass the
        typed wrapper (e.g. FDF round-trips that read/write the raw node
        without value conversion).
        """
        dic = self._name_dictionary.get_dictionary_object(_AP)
        if isinstance(dic, COSDictionary):
            return dic
        return None

    def set_ap(
        self, ap: PDAppearanceStreamNameTreeNode | COSDictionary | None
    ) -> None:
        """Set or clear the ``/AP`` name-tree dictionary.

        Accepts either a :class:`PDAppearanceStreamNameTreeNode` or a raw
        ``COSDictionary`` (the latter for callers that still hold an
        un-wrapped node).
        """
        if ap is None:
            self._name_dictionary.remove_item(_AP)
        elif isinstance(ap, COSDictionary):
            self._name_dictionary.set_item(_AP, ap)
        else:
            self._name_dictionary.set_item(_AP, ap.get_cos_object())


__all__ = ["PDDocumentNameDictionary"]
