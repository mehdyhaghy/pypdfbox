from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString

from .pd_page_labels import PDPageLabels
from .pd_page_tree import PDPageTree
from .pd_viewer_preferences import PDViewerPreferences

if TYPE_CHECKING:
    from .pd_document import PDDocument


_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_CATALOG: COSName = COSName.CATALOG  # type: ignore[attr-defined]
_PAGES: COSName = COSName.PAGES  # type: ignore[attr-defined]
_VERSION: COSName = COSName.get_pdf_name("Version")
_LANG: COSName = COSName.get_pdf_name("Lang")
_PAGE_LAYOUT: COSName = COSName.get_pdf_name("PageLayout")
_PAGE_MODE: COSName = COSName.get_pdf_name("PageMode")
_PAGE_LABELS: COSName = COSName.get_pdf_name("PageLabels")
_VIEWER_PREFERENCES: COSName = COSName.get_pdf_name("ViewerPreferences")
_OUTLINES: COSName = COSName.get_pdf_name("Outlines")
_OPEN_ACTION: COSName = COSName.get_pdf_name("OpenAction")
_DESTS: COSName = COSName.get_pdf_name("Dests")
_NAMES: COSName = COSName.get_pdf_name("Names")
_STRUCT_TREE_ROOT: COSName = COSName.get_pdf_name("StructTreeRoot")
_MARK_INFO: COSName = COSName.get_pdf_name("MarkInfo")
_OC_PROPERTIES: COSName = COSName.get_pdf_name("OCProperties")
_ACRO_FORM: COSName = COSName.get_pdf_name("AcroForm")
_OUTPUT_INTENTS: COSName = COSName.get_pdf_name("OutputIntents")
_METADATA: COSName = COSName.get_pdf_name("Metadata")
_AA: COSName = COSName.get_pdf_name("AA")


class PDDocumentCatalog:
    """
    Wrapper around the document's ``/Catalog`` (root) dictionary.
    Mirrors ``org.apache.pdfbox.pdmodel.PDDocumentCatalog``.

    Cluster #1 ships the high-traffic accessors (pages, version,
    language, page layout, page mode). Everything else (struct tree,
    AcroForm, outlines, metadata, …) is stubbed with cluster pointers
    — see the per-method docstrings.
    """

    def __init__(
        self,
        document: PDDocument,
        catalog: COSDictionary | None = None,
    ) -> None:
        self._document = document
        if catalog is None:
            cos_doc = document.get_document()
            catalog = cos_doc.get_catalog()
            if catalog is None:
                # Synthesise a minimal Catalog and wire it through the
                # trailer so the writer picks it up.
                catalog = COSDictionary()
                catalog.set_item(_TYPE, _CATALOG)
                trailer = cos_doc.get_trailer()
                if trailer is None:
                    trailer = COSDictionary()
                    cos_doc.set_trailer(trailer)
                trailer.set_item(COSName.ROOT, catalog)  # type: ignore[attr-defined]
        # Make sure /Type is set even on hand-built catalogs.
        if catalog.get_dictionary_object(_TYPE) is None:
            catalog.set_item(_TYPE, _CATALOG)
        self._catalog = catalog

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._catalog

    # ---------- pages ----------

    def get_pages(self) -> PDPageTree:
        """Return the page tree rooted at ``/Pages``. Creates an empty
        tree (and links it under ``/Pages``) when absent."""
        pages = self._catalog.get_dictionary_object(_PAGES)
        if not isinstance(pages, COSDictionary):
            tree = PDPageTree(document=self._document)
            self._catalog.set_item(_PAGES, tree.get_cos_object())
            return tree
        return PDPageTree(pages, document=self._document)

    # ---------- version ----------

    def get_version(self) -> str | None:
        """``/Version`` override (PDF 1.4+ may upgrade the version inside
        the catalog past whatever the header says). Returns the name's
        text, or ``None`` if absent."""
        v = self._catalog.get_dictionary_object(_VERSION)
        if isinstance(v, COSName):
            return v.get_name()
        return None

    def set_version(self, version: str | None) -> None:
        if version is None:
            self._catalog.remove_item(_VERSION)
            return
        self._catalog.set_item(_VERSION, COSName.get_pdf_name(version))

    # ---------- language ----------

    def get_language(self) -> str | None:
        v = self._catalog.get_dictionary_object(_LANG)
        if isinstance(v, COSString):
            return v.get_string()
        return None

    def set_language(self, language: str | None) -> None:
        if language is None:
            self._catalog.remove_item(_LANG)
            return
        self._catalog.set_item(_LANG, COSString(language))

    # ---------- page layout / mode ----------

    def get_page_layout(self) -> str | None:
        v = self._catalog.get_dictionary_object(_PAGE_LAYOUT)
        if isinstance(v, COSName):
            return v.get_name()
        return None

    def set_page_layout(self, layout: str | None) -> None:
        if layout is None:
            self._catalog.remove_item(_PAGE_LAYOUT)
            return
        self._catalog.set_item(_PAGE_LAYOUT, COSName.get_pdf_name(layout))

    def get_page_mode(self) -> str | None:
        v = self._catalog.get_dictionary_object(_PAGE_MODE)
        if isinstance(v, COSName):
            return v.get_name()
        return None

    def set_page_mode(self, mode: str | None) -> None:
        if mode is None:
            self._catalog.remove_item(_PAGE_MODE)
            return
        self._catalog.set_item(_PAGE_MODE, COSName.get_pdf_name(mode))

    # ---------- /StructTreeRoot ----------

    def get_struct_tree_root(self) -> Any:
        from .documentinterchange.logicalstructure import PDStructureTreeRoot

        v = self._catalog.get_dictionary_object(_STRUCT_TREE_ROOT)
        if isinstance(v, COSDictionary):
            return PDStructureTreeRoot(v)
        return None

    def set_struct_tree_root(self, root: Any) -> None:
        if root is None:
            self._catalog.remove_item(_STRUCT_TREE_ROOT)
            return
        self._catalog.set_item(_STRUCT_TREE_ROOT, root.get_cos_object())

    # ---------- /MarkInfo ----------

    def get_mark_info(self) -> Any:
        from .documentinterchange.logicalstructure import PDMarkInfo

        v = self._catalog.get_dictionary_object(_MARK_INFO)
        if isinstance(v, COSDictionary):
            return PDMarkInfo(v)
        return None

    def set_mark_info(self, mark_info: Any) -> None:
        if mark_info is None:
            self._catalog.remove_item(_MARK_INFO)
            return
        self._catalog.set_item(_MARK_INFO, mark_info.get_cos_object())

    # ---------- /AcroForm ----------

    def get_acro_form(self) -> Any:
        from .interactive.form import PDAcroForm

        v = self._catalog.get_dictionary_object(_ACRO_FORM)
        if isinstance(v, COSDictionary):
            return PDAcroForm(self._document, v)
        return None

    def set_acro_form(self, acro_form: Any) -> None:
        if acro_form is None:
            self._catalog.remove_item(_ACRO_FORM)
            return
        self._catalog.set_item(_ACRO_FORM, acro_form.get_cos_object())

    # ---------- stubs for later clusters ----------

    def get_document_outline(self) -> Any:
        from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
            PDDocumentOutline,
        )

        value = self._catalog.get_dictionary_object(_OUTLINES)
        if isinstance(value, COSDictionary):
            return PDDocumentOutline(value)
        return None

    def set_document_outline(self, outline: Any) -> None:
        if outline is None:
            self._catalog.remove_item(_OUTLINES)
            return
        self._catalog.set_item(_OUTLINES, outline.get_cos_object())

    def get_metadata(self) -> Any:
        from pypdfbox.cos import COSStream

        from .common.pd_metadata import PDMetadata

        v = self._catalog.get_dictionary_object(_METADATA)
        if isinstance(v, COSStream):
            return PDMetadata(v)
        return None

    def set_metadata(self, metadata: Any) -> None:
        if metadata is None:
            self._catalog.remove_item(_METADATA)
            return
        self._catalog.set_item(_METADATA, metadata.get_cos_object())

    def get_actions(self) -> Any:
        from .interactive.action import PDDocumentCatalogAdditionalActions

        v = self._catalog.get_dictionary_object(_AA)
        if isinstance(v, COSDictionary):
            return PDDocumentCatalogAdditionalActions(v)
        return None

    def set_actions(self, aa: Any) -> None:
        if aa is None:
            self._catalog.remove_item(_AA)
            return
        self._catalog.set_item(_AA, aa.get_cos_object())

    def get_oc_properties(self) -> Any:
        from .graphics.optionalcontent import PDOptionalContentProperties

        v = self._catalog.get_dictionary_object(_OC_PROPERTIES)
        if isinstance(v, COSDictionary):
            return PDOptionalContentProperties(v)
        return None

    def set_oc_properties(self, oc_properties: Any) -> None:
        if oc_properties is None:
            self._catalog.remove_item(_OC_PROPERTIES)
            return
        self._catalog.set_item(_OC_PROPERTIES, oc_properties.get_cos_object())

    def get_names(self) -> Any:
        from .pd_document_name_dictionary import PDDocumentNameDictionary

        v = self._catalog.get_dictionary_object(_NAMES)
        if isinstance(v, COSDictionary):
            return PDDocumentNameDictionary(self, v)
        return None

    def set_names(self, names: Any) -> None:
        if names is None:
            self._catalog.remove_item(_NAMES)
            return
        self._catalog.set_item(_NAMES, names.get_cos_object())

    def get_dests(self) -> Any:
        from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
            PDDestinationNameTreeNode,
        )

        value = self._catalog.get_dictionary_object(_DESTS)
        if isinstance(value, COSDictionary):
            return PDDestinationNameTreeNode(value)
        return None

    def get_open_action(self) -> Any:
        from pypdfbox.pdmodel.interactive.action import PDAction
        from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
            PDDestination,
        )

        value = self._catalog.get_dictionary_object(_OPEN_ACTION)
        if isinstance(value, COSDictionary):
            return PDAction.create(value)
        if isinstance(value, (COSArray, COSName, COSString)):
            return PDDestination.create(value)
        return None

    def set_open_action(self, action: Any) -> None:
        if action is None:
            self._catalog.remove_item(_OPEN_ACTION)
            return
        self._catalog.set_item(_OPEN_ACTION, action.get_cos_object())

    def get_viewer_preferences(self) -> PDViewerPreferences | None:
        """Return the catalog's ``/ViewerPreferences`` wrapped, or ``None``
        if the entry is absent."""
        v = self._catalog.get_dictionary_object(_VIEWER_PREFERENCES)
        if isinstance(v, COSDictionary):
            return PDViewerPreferences(v)
        return None

    def set_viewer_preferences(self, prefs: PDViewerPreferences | None) -> None:
        if prefs is None:
            self._catalog.remove_item(_VIEWER_PREFERENCES)
            return
        self._catalog.set_item(_VIEWER_PREFERENCES, prefs.get_cos_object())

    # ---------- page labels ----------

    def get_page_labels(self) -> PDPageLabels | None:
        """Return the catalog's ``/PageLabels`` wrapped, or ``None`` if
        the entry is absent."""
        v = self._catalog.get_dictionary_object(_PAGE_LABELS)
        if isinstance(v, COSDictionary):
            return PDPageLabels(self._document, v)
        return None

    def set_page_labels(self, labels: PDPageLabels | None) -> None:
        if labels is None:
            self._catalog.remove_item(_PAGE_LABELS)
            return
        self._catalog.set_item(_PAGE_LABELS, labels.get_cos_object())

    def get_output_intents(self) -> list[Any]:
        from .graphics.color import PDOutputIntent

        arr = self._catalog.get_dictionary_object(_OUTPUT_INTENTS)
        if not isinstance(arr, COSArray):
            return []
        result: list[Any] = []
        for i in range(arr.size()):
            entry = arr.get_object(i)
            if isinstance(entry, COSDictionary):
                result.append(PDOutputIntent(entry))
        return result

    def add_output_intent(self, intent: Any) -> None:
        arr = self._catalog.get_dictionary_object(_OUTPUT_INTENTS)
        if not isinstance(arr, COSArray):
            arr = COSArray()
            self._catalog.set_item(_OUTPUT_INTENTS, arr)
        arr.add(intent.get_cos_object())

    # ---------- raw COS passthrough used by tests ----------

    def get_cos_dictionary(self) -> COSDictionary:
        """Alias for ``get_cos_object`` — some upstream code calls it via
        ``COSObjectable``. Kept for parity."""
        return self._catalog

    # Convenience: expose names directly. Helps tests that want to peek at
    # the dict without round-tripping through COSDictionary's API.
    def __contains__(self, key: COSName | str) -> bool:
        return self._catalog.contains_key(key)

    def __repr__(self) -> str:
        return f"PDDocumentCatalog(version={self.get_version()!r})"


# Convenience for callers that need a generic tag value type.
__all__ = ["PDDocumentCatalog"]


# Suppress unused-import in typing-only branch.
_ = COSArray
