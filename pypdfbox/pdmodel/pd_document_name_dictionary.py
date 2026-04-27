from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSName

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


class PDDocumentNameDictionary:
    """
    Catalog ``/Names`` typed wrapper. Mirrors PDFBox
    ``PDDocumentNameDictionary``.

    Holds the per-category named-resource sub-dictionaries available at
    the document level: ``/Dests``, ``/AP``, ``/EmbeddedFiles``,
    ``/JavaScript``, ``/Pages``, ``/Templates``, ``/IDS``, ``/URLS``,
    ``/AlternatePresentations`` and ``/Renditions``. The ``/AP`` entry
    is exposed as a raw ``COSDictionary`` (no typed wrapper yet).
    """

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

    # ---------- /Dests (flat dict, NOT a name tree) ----------

    def get_dests(self) -> PDDocumentNameDestinationDictionary | None:
        dic = self._name_dictionary.get_dictionary_object(_DESTS)
        if not isinstance(dic, COSDictionary) and self._catalog is not None:
            cat_dests = self._catalog.get_cos_object().get_dictionary_object(_DESTS)
            if isinstance(cat_dests, COSDictionary):
                dic = cat_dests
        if isinstance(dic, COSDictionary):
            return PDDocumentNameDestinationDictionary(dic)
        return None

    def set_dests(self, dests: PDDocumentNameDestinationDictionary | None) -> None:
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

    # ---------- /AP (deferred placeholder) ----------

    def get_ap(self) -> COSDictionary | None:
        """Return the raw ``/AP`` name-tree dictionary, or ``None`` if absent.

        Mirrors PDFBox ``PDDocumentNameDictionary.getAP()``. The ``/AP`` entry
        is a name tree mapping name strings to appearance streams (PDF
        32000-1 §7.7.4, Table 31). A typed wrapper is not yet provided —
        callers receive the raw ``COSDictionary``.
        """
        dic = self._name_dictionary.get_dictionary_object(_AP)
        if isinstance(dic, COSDictionary):
            return dic
        return None

    def set_ap(self, ap: COSDictionary | None) -> None:
        """Set or clear the ``/AP`` name-tree dictionary.

        Mirrors PDFBox ``PDDocumentNameDictionary.setAP()``. Accepts the
        raw ``COSDictionary`` since no typed wrapper is yet provided.
        """
        if ap is None:
            self._name_dictionary.remove_item(_AP)
        else:
            self._name_dictionary.set_item(_AP, ap)


__all__ = ["PDDocumentNameDictionary"]
