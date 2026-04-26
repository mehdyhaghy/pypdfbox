from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSName

from .pd_document_name_destination_dictionary import PDDocumentNameDestinationDictionary
from .pd_embedded_files_name_tree_node import PDEmbeddedFilesNameTreeNode
from .pd_javascript_name_tree_node import PDJavascriptNameTreeNode

_NAMES: COSName = COSName.get_pdf_name("Names")
_DESTS: COSName = COSName.get_pdf_name("Dests")
_EMBEDDED_FILES: COSName = COSName.get_pdf_name("EmbeddedFiles")
_JAVA_SCRIPT: COSName = COSName.get_pdf_name("JavaScript")


class PDDocumentNameDictionary:
    """
    Catalog ``/Names`` typed wrapper. Mirrors PDFBox
    ``PDDocumentNameDictionary``.

    Holds the per-category named-resource sub-dictionaries available at
    the document level. Only the most common categories
    (``/Dests``, ``/EmbeddedFiles``, ``/JavaScript``) are exposed here;
    rarely-used categories (``/AP``, ``/Pages``, ``/Templates``,
    ``/IDS``, ``/URLS``, ``/AlternatePresentations``, ``/Renditions``)
    are not yet wrapped.
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


__all__ = ["PDDocumentNameDictionary"]
