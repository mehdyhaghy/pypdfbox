from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString

from .page_layout import PageLayout
from .page_mode import PageMode
from .pd_developer_extension import PDDeveloperExtension
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
_THREADS: COSName = COSName.get_pdf_name("Threads")
_PERMS: COSName = COSName.get_pdf_name("Perms")
_LEGAL: COSName = COSName.get_pdf_name("Legal")
_COLLECTION: COSName = COSName.get_pdf_name("Collection")
_EXTENSIONS: COSName = COSName.get_pdf_name("Extensions")
_URI: COSName = COSName.get_pdf_name("URI")
_REQUIREMENTS: COSName = COSName.get_pdf_name("Requirements")
_AF: COSName = COSName.get_pdf_name("AF")
_PIECE_INFO: COSName = COSName.get_pdf_name("PieceInfo")


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
        # Cached :class:`PDAcroForm` wrapper. Mirrors upstream's
        # ``cachedAcroForm`` field — the same wrapper instance is returned
        # across calls so the AcroForm stays reference-stable. Cleared by
        # :meth:`set_acro_form`.
        self._cached_acro_form: Any = None

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

    def set_pages(self, pages: PDPageTree | None) -> None:
        """Set the catalog's ``/Pages`` entry to a page tree, or remove
        it when ``None``.

        Upstream PDFBox does not currently expose a public ``setPages``
        — the catalog wires a fresh page tree internally on document
        construction. Surfaced here for callers that swap in a custom
        tree (e.g. multipdf merge / split flows). Pass ``None`` only if
        you intend to leave the catalog without a pages root (rarely
        legal — most consumers will then re-create one via
        :meth:`get_pages`)."""
        if pages is None:
            self._catalog.remove_item(_PAGES)
            return
        self._catalog.set_item(_PAGES, pages.get_cos_object())

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

    def get_page_layout(self) -> PageLayout | None:
        """Return the catalog's ``/PageLayout`` as a :class:`PageLayout`,
        or ``None`` if the entry is absent or not a recognised value.

        ``PageLayout`` is a :class:`enum.StrEnum`, so the returned value
        compares equal to its underlying PDF string (e.g.
        ``cat.get_page_layout() == "OneColumn"``). This keeps callers that
        still expect a plain string working unchanged.
        """
        v = self._catalog.get_dictionary_object(_PAGE_LAYOUT)
        if isinstance(v, COSName):
            try:
                return PageLayout.from_string(v.get_name())
            except ValueError:
                return None
        return None

    def set_page_layout(self, layout: PageLayout | str | None) -> None:
        """Set the catalog's ``/PageLayout``.

        Accepts a :class:`PageLayout` enum value or the raw PDF name
        string for back-compat. Pass ``None`` to remove the entry.
        """
        if layout is None:
            self._catalog.remove_item(_PAGE_LAYOUT)
            return
        if isinstance(layout, PageLayout):
            self._catalog.set_item(_PAGE_LAYOUT, layout.to_cos_name())
            return
        self._catalog.set_item(_PAGE_LAYOUT, COSName.get_pdf_name(layout))

    def get_page_mode(self) -> PageMode | None:
        """Return the catalog's ``/PageMode`` as a :class:`PageMode`,
        or ``None`` if the entry is absent or not a recognised value.

        ``PageMode`` is a :class:`enum.StrEnum`, so the returned value
        compares equal to its underlying PDF string (e.g.
        ``cat.get_page_mode() == "UseOutlines"``). This keeps callers that
        still expect a plain string working unchanged.
        """
        v = self._catalog.get_dictionary_object(_PAGE_MODE)
        if isinstance(v, COSName):
            try:
                return PageMode.from_string(v.get_name())
            except ValueError:
                return None
        return None

    def set_page_mode(self, mode: PageMode | str | None) -> None:
        """Set the catalog's ``/PageMode``.

        Accepts a :class:`PageMode` enum value or the raw PDF name string
        for back-compat. Pass ``None`` to remove the entry.
        """
        if mode is None:
            self._catalog.remove_item(_PAGE_MODE)
            return
        if isinstance(mode, PageMode):
            self._catalog.set_item(_PAGE_MODE, mode.to_cos_name())
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

    # Upstream-named aliases (PDFBox: getStructureTreeRoot /
    # setStructureTreeRoot — note the longer ``Structure`` spelling).
    def get_structure_tree_root(self) -> Any:
        return self.get_struct_tree_root()

    def set_structure_tree_root(self, root: Any) -> None:
        self.set_struct_tree_root(root)

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

    # MarkInfo convenience accessors — catalog-level shortcuts that read
    # / write the boolean flags inside the ``/MarkInfo`` sub-dictionary
    # (PDF 32000-1 §14.7 Table 321). They mirror the upstream PDMarkInfo
    # surface but stay reachable from the catalog so callers don't need
    # to materialise the wrapper for the common case. Reads return
    # ``False`` when ``/MarkInfo`` is missing (per Table 321 defaults).

    def is_document_marked(self) -> bool:
        """Return ``/MarkInfo /Marked`` (defaults to ``False``)."""
        from .documentinterchange.logicalstructure import PDMarkInfo

        v = self._catalog.get_dictionary_object(_MARK_INFO)
        if isinstance(v, COSDictionary):
            return PDMarkInfo(v).is_marked()
        return False

    def set_document_marked(self, marked: bool) -> None:
        """Write ``/MarkInfo /Marked``. Creates ``/MarkInfo`` on demand."""
        from .documentinterchange.logicalstructure import PDMarkInfo

        v = self._catalog.get_dictionary_object(_MARK_INFO)
        if not isinstance(v, COSDictionary):
            v = COSDictionary()
            self._catalog.set_item(_MARK_INFO, v)
        PDMarkInfo(v).set_marked(marked)

    def has_user_properties(self) -> bool:
        """Return ``/MarkInfo /UserProperties`` (defaults to ``False``)."""
        from .documentinterchange.logicalstructure import PDMarkInfo

        v = self._catalog.get_dictionary_object(_MARK_INFO)
        if isinstance(v, COSDictionary):
            return PDMarkInfo(v).is_user_properties()
        return False

    def set_user_properties(self, value: bool) -> None:
        """Write ``/MarkInfo /UserProperties``. Creates ``/MarkInfo`` on demand."""
        from .documentinterchange.logicalstructure import PDMarkInfo

        v = self._catalog.get_dictionary_object(_MARK_INFO)
        if not isinstance(v, COSDictionary):
            v = COSDictionary()
            self._catalog.set_item(_MARK_INFO, v)
        PDMarkInfo(v).set_user_properties(value)

    def has_suspects(self) -> bool:
        """Return ``/MarkInfo /Suspects`` (defaults to ``False``)."""
        from .documentinterchange.logicalstructure import PDMarkInfo

        v = self._catalog.get_dictionary_object(_MARK_INFO)
        if isinstance(v, COSDictionary):
            return PDMarkInfo(v).is_suspects()
        return False

    def set_suspects(self, value: bool) -> None:
        """Write ``/MarkInfo /Suspects``. Creates ``/MarkInfo`` on demand."""
        from .documentinterchange.logicalstructure import PDMarkInfo

        v = self._catalog.get_dictionary_object(_MARK_INFO)
        if not isinstance(v, COSDictionary):
            v = COSDictionary()
            self._catalog.set_item(_MARK_INFO, v)
        PDMarkInfo(v).set_suspects(value)

    # ---------- /AcroForm ----------

    def get_acro_form(self) -> Any:
        """Return the document's ``/AcroForm`` as a :class:`PDAcroForm`,
        or ``None`` when absent.

        The wrapper is cached after the first call — mirrors upstream's
        ``cachedAcroForm`` field. Cleared by :meth:`set_acro_form` and by
        any swap that would invalidate the underlying dictionary
        identity."""
        from .interactive.form import PDAcroForm

        if self._cached_acro_form is not None:
            return self._cached_acro_form
        v = self._catalog.get_dictionary_object(_ACRO_FORM)
        if isinstance(v, COSDictionary):
            self._cached_acro_form = PDAcroForm(self._document, v)
            return self._cached_acro_form
        return None

    def set_acro_form(self, acro_form: Any) -> None:
        """Replace ``/AcroForm`` and clear the cached wrapper so the next
        :meth:`get_acro_form` call materialises the new value (mirrors
        upstream's ``cachedAcroForm = null`` reset)."""
        if acro_form is None:
            self._catalog.remove_item(_ACRO_FORM)
            self._cached_acro_form = None
            return
        self._catalog.set_item(_ACRO_FORM, acro_form.get_cos_object())
        self._cached_acro_form = None

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

    # Upstream alias: ``getOutlines()`` / ``setOutlines()``.
    def get_outlines(self) -> Any:
        return self.get_document_outline()

    def set_outlines(self, outline: Any) -> None:
        self.set_document_outline(outline)

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
        """Write the catalog's ``/OCProperties`` dictionary. Mirrors
        upstream's side effect: optional content groups require PDF 1.5,
        so when a non-``None`` value is set the document version is
        bumped to 1.5 if it is currently lower (matches upstream
        ``setOCProperties``)."""
        if oc_properties is None:
            self._catalog.remove_item(_OC_PROPERTIES)
            return
        self._catalog.set_item(_OC_PROPERTIES, oc_properties.get_cos_object())
        # Upstream: if (ocProperties != null && document.getVersion() < 1.5)
        #              document.setVersion(1.5f);
        try:
            if self._document.get_version() < 1.5:
                self._document.set_version(1.5)
        except Exception:  # noqa: BLE001 — defensive: catalogs without a doc
            pass

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

    def set_dests(self, dests: Any) -> None:
        """Set the catalog's legacy ``/Dests`` dictionary.

        Mirrors upstream ``PDDocumentCatalog.setDests``. ``None`` removes
        the direct catalog entry. Modern ``/Names /Dests`` name-tree wiring
        remains the job of :class:`PDDocumentNameDictionary`.
        """
        if dests is None:
            self._catalog.remove_item(_DESTS)
            return
        self._catalog.set_item(_DESTS, dests.get_cos_object())

    def find_named_destination_page(self, named_dest: Any) -> Any:
        """Resolve a :class:`PDNamedDestination` against the catalog's
        name dictionaries. Mirrors upstream
        ``PDDocumentCatalog.findNamedDestinationPage(PDNamedDestination)``.

        Lookup order matches upstream:

        1. ``/Names /Dests`` name tree (modern, PDF 1.2+).
        2. Legacy ``/Dests`` flat dictionary on the catalog (PDF 1.1).

        Returns the resolved :class:`PDPageDestination` (or its subclass)
        or ``None`` when the name is not registered."""
        from .pd_document_name_destination_dictionary import (
            PDDocumentNameDestinationDictionary,
        )

        if named_dest is None:
            return None
        try:
            name = named_dest.get_named_destination()
        except AttributeError:
            return None
        if name is None:
            return None

        # 1) /Names /Dests name tree.
        names_dict = self.get_names()
        if names_dict is not None:
            try:
                dests_tree = names_dict.get_dests()
            except Exception:  # noqa: BLE001 — defensive on malformed names
                dests_tree = None
            if dests_tree is not None:
                # PDDestinationNameTreeNode (the proper name-tree shape) has
                # get_value(); the legacy PDDocumentNameDestinationDictionary
                # has get_destination(). Cover both for robustness.
                getter = getattr(dests_tree, "get_value", None) or getattr(
                    dests_tree, "get_destination", None
                )
                if getter is not None:
                    page_dest = getter(name)
                    if page_dest is not None:
                        return page_dest

        # 2) Legacy catalog /Dests flat dictionary.
        cat_dests = self._catalog.get_dictionary_object(_DESTS)
        if isinstance(cat_dests, COSDictionary):
            page_dest = PDDocumentNameDestinationDictionary(
                cat_dests
            ).get_destination(name)
            if page_dest is not None:
                return page_dest

        return None

    def get_open_action(self) -> Any:
        from pypdfbox.pdmodel.common.pd_destination_or_action import (
            PDDestinationOrAction,
        )

        value = self._catalog.get_dictionary_object(_OPEN_ACTION)
        return PDDestinationOrAction.create(value)

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

    # Upstream alias: ``getViewPreferences()`` / ``setViewPreferences()``.
    def get_view_preferences(self) -> PDViewerPreferences | None:
        return self.get_viewer_preferences()

    def set_view_preferences(self, prefs: PDViewerPreferences | None) -> None:
        self.set_viewer_preferences(prefs)

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

    def set_output_intents(self, intents: list[Any] | None) -> None:
        """Replace the ``/OutputIntents`` array with ``intents``. Pass
        ``None`` or an empty list to remove the entry entirely. Mirrors
        upstream ``setOutputIntents(List<PDOutputIntent>)``."""
        if not intents:
            self._catalog.remove_item(_OUTPUT_INTENTS)
            return
        arr = COSArray()
        for intent in intents:
            arr.add(intent.get_cos_object())
        self._catalog.set_item(_OUTPUT_INTENTS, arr)

    # ---------- /Threads ----------

    def get_threads(self) -> list[Any]:
        """Return the article-thread list as :class:`PDThread` wrappers.

        ``/Threads`` is an array of indirect references to thread
        dictionaries. Returns an empty list when the entry is absent.
        Non-dictionary entries (rare but legal under defensive parsing)
        are skipped.
        """
        from pypdfbox.pdmodel.interactive.pagenavigation import PDThread

        arr = self._catalog.get_dictionary_object(_THREADS)
        if not isinstance(arr, COSArray):
            return []
        result: list[Any] = []
        for i in range(arr.size()):
            entry = arr.get_object(i)
            if isinstance(entry, COSDictionary):
                result.append(PDThread(entry))
        return result

    def set_threads(self, threads: list[Any] | None) -> None:
        """Replace ``/Threads`` with a fresh array. ``None`` removes the
        entry. Each item must be a :class:`PDThread`."""
        from pypdfbox.pdmodel.interactive.pagenavigation import PDThread

        if threads is None:
            self._catalog.remove_item(_THREADS)
            return
        arr = COSArray()
        for thread in threads:
            if not isinstance(thread, PDThread):
                raise TypeError(
                    "PDDocumentCatalog.set_threads entries must be PDThread; "
                    f"got {type(thread).__name__}"
                )
            arr.add(thread.get_cos_object())
        self._catalog.set_item(_THREADS, arr)

    # ---------- /Perms ----------

    def get_perms(self) -> COSDictionary | None:
        v = self._catalog.get_dictionary_object(_PERMS)
        if isinstance(v, COSDictionary):
            return v
        return None

    def set_perms(self, perms: COSDictionary | None) -> None:
        if perms is None:
            self._catalog.remove_item(_PERMS)
            return
        self._catalog.set_item(_PERMS, perms)

    # ---------- /Legal ----------

    def get_legal(self) -> COSDictionary | None:
        v = self._catalog.get_dictionary_object(_LEGAL)
        if isinstance(v, COSDictionary):
            return v
        return None

    def set_legal(self, legal: COSDictionary | None) -> None:
        if legal is None:
            self._catalog.remove_item(_LEGAL)
            return
        self._catalog.set_item(_LEGAL, legal)

    # ---------- /Collection ----------

    def get_collection(self) -> COSDictionary | None:
        v = self._catalog.get_dictionary_object(_COLLECTION)
        if isinstance(v, COSDictionary):
            return v
        return None

    def set_collection(self, collection: COSDictionary | None) -> None:
        if collection is None:
            self._catalog.remove_item(_COLLECTION)
            return
        self._catalog.set_item(_COLLECTION, collection)

    # ---------- /Extensions (developer extensions) ----------

    def get_developer_extensions(self) -> dict[str, PDDeveloperExtension]:
        """Return the catalog's ``/Extensions`` mapping (PDF 32000-1
        §7.12.2 / ISO 32000-2 §7.12.3) as a snapshot ``dict`` keyed by
        the registered prefix name (e.g. ``"ADBE"``) with
        :class:`PDDeveloperExtension` values.

        Returns an empty ``dict`` when ``/Extensions`` is absent or
        malformed. The returned mapping is a snapshot — mutating it does
        not write back; use :meth:`set_developer_extensions` or
        :meth:`add_developer_extension` to persist changes."""
        v = self._catalog.get_dictionary_object(_EXTENSIONS)
        if not isinstance(v, COSDictionary):
            return {}
        result: dict[str, PDDeveloperExtension] = {}
        for key in v.key_set():
            entry = v.get_dictionary_object(key)
            if isinstance(entry, COSDictionary):
                result[key.get_name()] = PDDeveloperExtension(entry)
        return result

    def set_developer_extensions(
        self, extensions: dict[str, PDDeveloperExtension] | None
    ) -> None:
        """Replace the catalog's ``/Extensions`` mapping. Pass ``None``
        or an empty mapping to remove the entry entirely.

        Each key is the registered prefix name (e.g. ``"ADBE"``); each
        value is a :class:`PDDeveloperExtension`."""
        if not extensions:
            self._catalog.remove_item(_EXTENSIONS)
            return
        ext_dict = COSDictionary()
        for prefix, ext in extensions.items():
            ext_dict.set_item(
                COSName.get_pdf_name(prefix), ext.get_cos_object()
            )
        self._catalog.set_item(_EXTENSIONS, ext_dict)

    def add_developer_extension(
        self, prefix: str, extension: PDDeveloperExtension
    ) -> None:
        """Add (or replace) a single developer extension under
        ``prefix`` in ``/Extensions``. Creates the ``/Extensions``
        dictionary on demand."""
        v = self._catalog.get_dictionary_object(_EXTENSIONS)
        if not isinstance(v, COSDictionary):
            v = COSDictionary()
            self._catalog.set_item(_EXTENSIONS, v)
        v.set_item(COSName.get_pdf_name(prefix), extension.get_cos_object())

    def remove_developer_extension(self, prefix: str) -> None:
        """Remove the developer extension stored under ``prefix`` in
        ``/Extensions``. Removes the ``/Extensions`` dictionary itself
        when the last entry is removed."""
        v = self._catalog.get_dictionary_object(_EXTENSIONS)
        if not isinstance(v, COSDictionary):
            return
        v.remove_item(COSName.get_pdf_name(prefix))
        if v.is_empty():
            self._catalog.remove_item(_EXTENSIONS)

    # ---------- /URI (URI dictionary, PDF 32000-1 §12.6.4.7) ----------

    def get_uri(self) -> Any:
        """Return the catalog's ``/URI`` dictionary as a typed
        :class:`PDURIDictionary` (PDF 32000-1 §12.6.4.7), or ``None``
        when absent.

        The ``/URI`` dictionary holds document-level URI information,
        most notably the ``/Base`` entry — a string used as the base
        URI for resolving any relative URIs in URI actions. Mirrors
        upstream ``PDDocumentCatalog.getURI()`` returning
        ``PDURIDictionary``."""
        from .interactive.action import PDURIDictionary

        v = self._catalog.get_dictionary_object(_URI)
        if isinstance(v, COSDictionary):
            return PDURIDictionary(v)
        return None

    def set_uri(self, uri_dict: Any) -> None:
        """Set the catalog's ``/URI`` dictionary. Pass ``None`` to
        remove the entry. Accepts a :class:`PDURIDictionary` (preferred,
        mirrors upstream) or a raw :class:`COSDictionary` for
        back-compat with earlier pypdfbox callers."""
        if uri_dict is None:
            self._catalog.remove_item(_URI)
            return
        if isinstance(uri_dict, COSDictionary):
            self._catalog.set_item(_URI, uri_dict)
            return
        self._catalog.set_item(_URI, uri_dict.get_cos_object())

    # ---------- /Requirements (PDF 32000-1 §12.10) ----------

    def get_requirements(self) -> list[COSDictionary]:
        """Return the catalog's ``/Requirements`` array as a list of
        requirement-handler dictionaries (PDF 32000-1 §12.10).

        Each entry declares processor capabilities the document expects
        (e.g. ``EnableJavaScripts``). Returns an empty list when the
        entry is absent. Non-dictionary array entries are skipped under
        defensive parsing.

        Upstream PDFBox does not yet expose a typed
        ``PDRequirementsDictionary`` wrapper; pypdfbox surfaces the raw
        ``COSDictionary`` entries until the requirements cluster is
        ported."""
        arr = self._catalog.get_dictionary_object(_REQUIREMENTS)
        if not isinstance(arr, COSArray):
            return []
        result: list[COSDictionary] = []
        for i in range(arr.size()):
            entry = arr.get_object(i)
            if isinstance(entry, COSDictionary):
                result.append(entry)
        return result

    def set_requirements(
        self, requirements: list[COSDictionary] | None
    ) -> None:
        """Replace the catalog's ``/Requirements`` array. Pass ``None``
        or an empty list to remove the entry entirely."""
        if not requirements:
            self._catalog.remove_item(_REQUIREMENTS)
            return
        arr = COSArray()
        for req in requirements:
            if not isinstance(req, COSDictionary):
                raise TypeError(
                    "PDDocumentCatalog.set_requirements entries must be "
                    f"COSDictionary; got {type(req).__name__}"
                )
            arr.add(req)
        self._catalog.set_item(_REQUIREMENTS, arr)

    def add_requirement(self, requirement: COSDictionary) -> None:
        """Append a single requirement-handler dictionary to
        ``/Requirements``. Creates the array on demand."""
        if not isinstance(requirement, COSDictionary):
            raise TypeError(
                "PDDocumentCatalog.add_requirement expected COSDictionary; "
                f"got {type(requirement).__name__}"
            )
        arr = self._catalog.get_dictionary_object(_REQUIREMENTS)
        if not isinstance(arr, COSArray):
            arr = COSArray()
            self._catalog.set_item(_REQUIREMENTS, arr)
        arr.add(requirement)

    # ---------- /AF (AssociatedFiles, PDF 2.0 / ISO 32000-2 §14.13) ----------

    def get_associated_files(self) -> list[Any]:
        """Return the catalog's ``/AF`` array as a list of typed
        :class:`PDFileSpecification` wrappers (PDF 2.0 / ISO 32000-2
        §14.13). Returns an empty list when the entry is absent.

        Upstream PDFBox 3.0 does not yet expose a typed AF accessor on
        the catalog; pypdfbox surfaces it for forward parity with the
        4.x line which adds it. Non-dictionary / non-string entries are
        skipped under defensive parsing."""
        from .common.filespecification import PDFileSpecification

        arr = self._catalog.get_dictionary_object(_AF)
        if not isinstance(arr, COSArray):
            return []
        result: list[Any] = []
        for i in range(arr.size()):
            entry = arr.get_object(i)
            spec = PDFileSpecification.create_fs(entry)
            if spec is not None:
                result.append(spec)
        return result

    def set_associated_files(self, files: list[Any] | None) -> None:
        """Replace the catalog's ``/AF`` array. Pass ``None`` or an empty
        list to remove the entry entirely. Each entry must be a
        :class:`PDFileSpecification`."""
        if not files:
            self._catalog.remove_item(_AF)
            return
        arr = COSArray()
        for spec in files:
            arr.add(spec.get_cos_object())
        self._catalog.set_item(_AF, arr)

    # ---------- /PieceInfo (PDF 32000-1 §14.5) ----------

    def get_piece_info(self) -> COSDictionary | None:
        """Return the catalog's ``/PieceInfo`` page-piece dictionary, or
        ``None`` when absent. PDF 32000-1 §14.5: an opaque per-application
        data store keyed by application registration name. Returned raw
        because the contents are application-defined."""
        v = self._catalog.get_dictionary_object(_PIECE_INFO)
        if isinstance(v, COSDictionary):
            return v
        return None

    def set_piece_info(self, piece_info: COSDictionary | None) -> None:
        """Set the catalog's ``/PieceInfo`` dictionary. Pass ``None`` to
        remove the entry."""
        if piece_info is None:
            self._catalog.remove_item(_PIECE_INFO)
            return
        self._catalog.set_item(_PIECE_INFO, piece_info)

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
