from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString

from .pd_page_tree import PDPageTree

if TYPE_CHECKING:
    from .pd_document import PDDocument


_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_CATALOG: COSName = COSName.CATALOG  # type: ignore[attr-defined]
_PAGES: COSName = COSName.PAGES  # type: ignore[attr-defined]
_VERSION: COSName = COSName.get_pdf_name("Version")
_LANG: COSName = COSName.get_pdf_name("Lang")
_PAGE_LAYOUT: COSName = COSName.get_pdf_name("PageLayout")
_PAGE_MODE: COSName = COSName.get_pdf_name("PageMode")


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

    # ---------- stubs for later clusters ----------

    def get_struct_tree_root(self) -> Any:
        raise NotImplementedError(
            "PDDocumentCatalog.get_struct_tree_root requires PDStructTreeRoot — "
            "pdmodel cluster #8"
        )

    def get_acro_form(self) -> Any:
        raise NotImplementedError(
            "PDDocumentCatalog.get_acro_form requires PDAcroForm — pdmodel cluster #6"
        )

    def get_document_outline(self) -> Any:
        raise NotImplementedError(
            "PDDocumentCatalog.get_document_outline requires PDOutlineNode — "
            "pdmodel cluster #7"
        )

    def get_metadata(self) -> Any:
        raise NotImplementedError(
            "PDDocumentCatalog.get_metadata requires PDMetadata (xmpbox cluster)"
        )

    def get_oc_properties(self) -> Any:
        raise NotImplementedError(
            "PDDocumentCatalog.get_oc_properties requires PDOptionalContentProperties — "
            "pdmodel cluster #2"
        )

    def get_names(self) -> Any:
        raise NotImplementedError(
            "PDDocumentCatalog.get_names requires PDDocumentNameDictionary — "
            "pdmodel cluster #2"
        )

    def get_dests(self) -> Any:
        raise NotImplementedError(
            "PDDocumentCatalog.get_dests requires PDDestinationNameTreeNode — "
            "pdmodel cluster #7"
        )

    def get_open_action(self) -> Any:
        raise NotImplementedError(
            "PDDocumentCatalog.get_open_action requires PDDestination/PDAction — "
            "pdmodel cluster #7"
        )

    def get_viewer_preferences(self) -> Any:
        raise NotImplementedError(
            "PDDocumentCatalog.get_viewer_preferences requires PDViewerPreferences — "
            "pdmodel cluster #2"
        )

    def get_output_intents(self) -> list[Any]:
        raise NotImplementedError(
            "PDDocumentCatalog.get_output_intents requires PDOutputIntent — "
            "pdmodel cluster #2"
        )

    def get_mark_info(self) -> Any:
        raise NotImplementedError(
            "PDDocumentCatalog.get_mark_info requires PDMarkInfo — pdmodel cluster #8"
        )

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
