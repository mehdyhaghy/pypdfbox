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
_S_KEY: COSName = COSName.get_pdf_name("S")
_DESTS: COSName = COSName.get_pdf_name("Dests")
_NAMES: COSName = COSName.get_pdf_name("Names")
_STRUCT_TREE_ROOT: COSName = COSName.get_pdf_name("StructTreeRoot")
_MARK_INFO: COSName = COSName.get_pdf_name("MarkInfo")
_OC_PROPERTIES: COSName = COSName.get_pdf_name("OCProperties")
_ACRO_FORM: COSName = COSName.get_pdf_name("AcroForm")

# Sentinel distinguishing "no argument supplied" (apply the default fixup,
# mirroring the upstream no-arg ``getAcroForm()``) from an explicit ``None``
# (apply no fixup, mirroring ``getAcroForm(null)``).
_NO_FIXUP_ARG = object()
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
_NEEDS_RENDERING: COSName = COSName.get_pdf_name("NeedsRendering")


class PDDocumentCatalog:
    """
    Wrapper around the document's ``/Catalog`` (root) dictionary.
    Mirrors ``org.apache.pdfbox.pdmodel.PDDocumentCatalog``.

    The catalog is intentionally a thin typed facade over the root
    dictionary. Accessors validate the expected COS shape and treat
    malformed values as absent unless the matching PDFBox method
    materialises a replacement dictionary/array on read.
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
        # Mirrors upstream's ``acroFormFixupApplied`` field — the most
        # recently applied fixup object is remembered so subsequent calls
        # to :meth:`get_acro_form` with the same fixup don't re-apply it.
        self._acro_form_fixup_applied: Any = None

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
        text, or ``None`` if absent.

        Mirrors upstream ``getVersion`` which delegates to
        ``COSDictionary.getNameAsString`` — accepts both a ``COSName``
        (the spec-correct form) and a ``COSString`` (occasionally seen
        in malformed producer output)."""
        v = self._catalog.get_dictionary_object(_VERSION)
        if isinstance(v, COSName):
            return v.get_name()
        if isinstance(v, COSString):
            return v.get_string()
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

        Mirrors upstream ``getPageLayout`` which delegates to
        ``COSDictionary.getNameAsString`` — accepts both a ``COSName``
        (the spec-correct form) and a ``COSString`` (occasionally seen
        in malformed producer output).
        """
        v = self._catalog.get_dictionary_object(_PAGE_LAYOUT)
        raw: str | None = None
        if isinstance(v, COSName):
            raw = v.get_name()
        elif isinstance(v, COSString):
            raw = v.get_string()
        if not raw:
            return None
        try:
            return PageLayout.from_string(raw)
        except ValueError:
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

        Mirrors upstream ``getPageMode`` which delegates to
        ``COSDictionary.getNameAsString`` — accepts both a ``COSName``
        (the spec-correct form) and a ``COSString`` (occasionally seen
        in malformed producer output).
        """
        v = self._catalog.get_dictionary_object(_PAGE_MODE)
        raw: str | None = None
        if isinstance(v, COSName):
            raw = v.get_name()
        elif isinstance(v, COSString):
            raw = v.get_string()
        if not raw:
            return None
        try:
            return PageMode.from_string(raw)
        except ValueError:
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

    def get_page_mode_or_default(self) -> PageMode:
        """Return the catalog's ``/PageMode`` with the spec default applied.

        Mirrors upstream Java ``PDDocumentCatalog.getPageMode()`` exactly:
        when ``/PageMode`` is absent or carries an unrecognised name, the
        document's open-mode is implicitly ``UseNone`` (PDF 32000-1
        §7.7.3.3 Table 28). pypdfbox's :meth:`get_page_mode` keeps the
        more tolerant ``None`` posture for callers that want to
        distinguish "explicit" vs "default"; this helper provides the
        upstream-compatible default-applying read.
        """
        mode = self.get_page_mode()
        return PageMode.USE_NONE if mode is None else mode

    def get_page_layout_or_default(self) -> PageLayout:
        """Return the catalog's ``/PageLayout`` with the spec default applied.

        Mirrors upstream Java ``PDDocumentCatalog.getPageLayout()`` exactly:
        when ``/PageLayout`` is absent, empty, or carries an unrecognised
        name, the implicit layout is ``SinglePage`` (PDF 32000-1 §7.7.3.3
        Table 28). pypdfbox's :meth:`get_page_layout` keeps the more
        tolerant ``None`` posture for callers that want to distinguish
        "explicit" vs "default"; this helper provides the upstream-
        compatible default-applying read.
        """
        layout = self.get_page_layout()
        return PageLayout.SINGLE_PAGE if layout is None else layout

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

    def get_acro_form(self, acro_form_fixup: Any = _NO_FIXUP_ARG) -> Any:
        """Return the document's ``/AcroForm`` as a :class:`PDAcroForm`,
        or ``None`` when absent.

        The wrapper is cached after the first call — mirrors upstream's
        ``cachedAcroForm`` field. Cleared by :meth:`set_acro_form` and by
        any swap that would invalidate the underlying dictionary
        identity.

        Mirrors the two upstream overloads:

        * ``get_acro_form()`` (no argument) → upstream's no-arg
          ``getAcroForm()``, which is ``getAcroForm(new
          AcroFormDefaultFixup(document))``. A fresh
          :class:`AcroFormDefaultFixup` is applied so the returned form has
          the Adobe defaults: ``/DA`` seeded to ``/Helv 0 Tf 0 g``,
          ``/Helv`` + ``/ZaDb`` injected into ``/DR``, and orphan widgets
          adopted when ``/NeedAppearances`` is set and ``/Fields`` is empty
          (PDFBOX-4985). A new fixup instance is created on every no-arg
          call so it is re-applied each time exactly like upstream — the
          processors are idempotent, so it is a no-op after the first.

        * ``get_acro_form(fixup)`` → upstream's
          ``getAcroForm(PDDocumentFixup)``: the given fixup (any object
          exposing ``apply()``) is applied once and remembered when it
          differs from the last-applied fixup; subsequent calls with the
          same instance skip re-application. Passing ``None`` applies no
          fixup at all (parity with upstream's ``getAcroForm(null)`` — used
          internally by the fixup processors to break the recursion). The
          cache is cleared whenever a fresh fixup is applied so the next
          read materialises the post-fixup ``/AcroForm`` dictionary."""
        from .interactive.form import PDAcroForm

        if acro_form_fixup is _NO_FIXUP_ARG:
            from .fixup import AcroFormDefaultFixup

            acro_form_fixup = AcroFormDefaultFixup(self._document)

        if (
            acro_form_fixup is not None
            and acro_form_fixup is not self._acro_form_fixup_applied
        ):
            acro_form_fixup.apply()
            self._cached_acro_form = None
            self._acro_form_fixup_applied = acro_form_fixup
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

    def get_acro_form_or_create(self) -> Any:
        """Return the document's ``/AcroForm``, materialising an empty one
        on demand when the catalog has no well-formed AcroForm entry.

        Convenience for code paths that need to mutate fields without
        having to nil-check every call site (e.g. "I'm about to add a text
        field, give me a form to add it to"). Mirrors the upstream-style
        auto-create idiom that :meth:`get_actions` and :meth:`get_threads`
        already follow on the catalog. The newly-created
        :class:`PDAcroForm` is cached and wired back into the catalog so
        subsequent reads see the same instance.

        Unlike :meth:`get_acro_form`, this method always returns a
        non-``None`` :class:`PDAcroForm`.

        Reads use ``get_acro_form(None)`` (no fixup) so the returned
        wrapper is the stable cached instance — the no-arg
        ``get_acro_form()`` would mint a fresh wrapper on every call (it
        applies a new ``AcroFormDefaultFixup`` each time), which would
        break the "same instance across calls" contract this helper
        relies on."""
        existing = self.get_acro_form(None)
        if existing is not None:
            return existing
        from .interactive.form import PDAcroForm

        acro_form = PDAcroForm(self._document)
        self.set_acro_form(acro_form)
        # Re-read so the cache is populated and the wrapper is the same
        # instance subsequent ``get_acro_form(None)`` calls return.
        return self.get_acro_form(None)

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
        """Set the catalog's ``/Metadata`` stream. Pass ``None`` to remove
        the entry. Accepts a :class:`PDMetadata` wrapper (preferred,
        mirrors upstream) or a raw :class:`COSStream` for back-compat with
        low-level callers — upstream Java's ``setItem`` resolves
        ``COSObjectable``/``COSBase`` polymorphically; we surface both
        forms explicitly."""
        from pypdfbox.cos import COSStream

        if metadata is None:
            self._catalog.remove_item(_METADATA)
            return
        if isinstance(metadata, COSStream):
            self._catalog.set_item(_METADATA, metadata)
            return
        self._catalog.set_item(_METADATA, metadata.get_cos_object())

    def get_actions(self) -> Any:
        """Return the catalog's additional-actions ``/AA`` wrapper.

        Mirrors upstream's auto-create behaviour — if ``/AA`` is absent
        the entry is materialised in place as an empty dictionary so the
        caller can attach trigger actions without having to wire the
        sub-dictionary first. Always returns a non-``None``
        :class:`PDDocumentCatalogAdditionalActions`."""
        from .interactive.action import PDDocumentCatalogAdditionalActions

        v = self._catalog.get_dictionary_object(_AA)
        if not isinstance(v, COSDictionary):
            v = COSDictionary()
            self._catalog.set_item(_AA, v)
        return PDDocumentCatalogAdditionalActions(v)

    def set_actions(self, aa: Any) -> None:
        """Set the catalog's ``/AA`` additional-actions dictionary. Pass
        ``None`` to remove the entry. Accepts a
        :class:`PDDocumentCatalogAdditionalActions` wrapper (preferred,
        mirrors upstream) or a raw :class:`COSDictionary` for back-compat
        with low-level callers."""
        if aa is None:
            self._catalog.remove_item(_AA)
            return
        if isinstance(aa, COSDictionary):
            self._catalog.set_item(_AA, aa)
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
        ``setOCProperties``).

        Accepts a :class:`PDOptionalContentProperties` wrapper (preferred,
        mirrors upstream) or a raw :class:`COSDictionary` for back-compat
        with low-level callers."""
        if oc_properties is None:
            self._catalog.remove_item(_OC_PROPERTIES)
            return
        if isinstance(oc_properties, COSDictionary):
            self._catalog.set_item(_OC_PROPERTIES, oc_properties)
        else:
            self._catalog.set_item(
                _OC_PROPERTIES, oc_properties.get_cos_object()
            )
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
        """Return the catalog's ``/OpenAction`` decoded the way PDFBox 3.0.7
        does in ``PDDocumentCatalog.getOpenAction()``:

        * ``COSDictionary`` → :meth:`PDAction.create` (returns ``None`` when
          the dict has no recognized ``/S`` subtype — upstream's
          ``PDActionFactory.createAction`` returns null for that case).
        * ``COSArray`` → :meth:`PDDestination.create`.
        * anything else (including ``COSName`` / ``COSString`` shorthand) →
          ``None``.

        This mirrors the upstream catalog dispatch byte-for-byte, including
        the "/D without /S → null" arm. The looser
        :meth:`PDDestinationOrAction.create` factory still handles the
        shorthand for callers that want it — but the catalog itself behaves
        like upstream.
        """
        from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
        from pypdfbox.pdmodel.interactive.action.pd_action_unknown import (
            PDActionUnknown,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
            PDDestination,
        )

        value = self._catalog.get_dictionary_object(_OPEN_ACTION)
        if isinstance(value, COSDictionary):
            # Upstream PDActionFactory.createAction returns null for dicts
            # with no /S; match that exactly so a /D-only shorthand dict
            # round-trips through both stacks as the same None.
            sub_type = value.get_name_as_string(_S_KEY)
            if sub_type is None:
                return None
            action = PDAction.create(value)
            # PDFBox's factory has no PDActionUnknown fallback — unknown /S
            # subtypes yield null. pypdfbox's PDAction.create returns a
            # PDActionUnknown; collapse that arm to match upstream behavior
            # at the catalog dispatch boundary.
            if isinstance(action, PDActionUnknown):
                return None
            return action
        if isinstance(value, COSArray):
            return PDDestination.create(value)
        return None

    def set_open_action(self, action: Any) -> None:
        """Set the catalog's ``/OpenAction`` (an action dictionary or a
        destination array). Pass ``None`` to remove the entry. Accepts a
        :class:`PDDestinationOrAction` wrapper (preferred, mirrors
        upstream) or a raw :class:`COSDictionary` / :class:`COSArray` for
        back-compat with low-level callers — upstream Java's
        ``setItem(COSName, COSObjectable)`` overload resolves both
        polymorphically; we surface the raw COS forms explicitly."""
        if action is None:
            self._catalog.remove_item(_OPEN_ACTION)
            return
        if isinstance(action, COSDictionary | COSArray):
            self._catalog.set_item(_OPEN_ACTION, action)
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
        upstream ``setOutputIntents(List<PDOutputIntent>)``.

        Each entry must be a :class:`PDOutputIntent` (or any object with a
        ``get_cos_object()`` method); a :class:`TypeError` is raised on
        invalid input — matches the upstream Java generic-list contract
        where a non-``PDOutputIntent`` would never compile."""
        from .graphics.color import PDOutputIntent

        if not intents:
            self._catalog.remove_item(_OUTPUT_INTENTS)
            return
        arr = COSArray()
        for intent in intents:
            if not isinstance(intent, PDOutputIntent):
                raise TypeError(
                    "PDDocumentCatalog.set_output_intents entries must be "
                    f"PDOutputIntent; got {type(intent).__name__}"
                )
            arr.add(intent.get_cos_object())
        self._catalog.set_item(_OUTPUT_INTENTS, arr)

    # ---------- /Threads ----------

    def get_threads(self) -> list[Any]:
        """Return the article-thread list as :class:`PDThread` wrappers.

        ``/Threads`` is an array of indirect references to thread
        dictionaries. Mirrors upstream's auto-create behaviour — if
        ``/Threads`` is absent the entry is materialised in place as an
        empty array. The returned Python list is a snapshot of typed
        wrappers; use :meth:`set_threads` to persist list-level changes.
        Non-dictionary entries (rare but legal under defensive parsing)
        are skipped.
        """
        from pypdfbox.pdmodel.interactive.pagenavigation import PDThread

        arr = self._catalog.get_dictionary_object(_THREADS)
        if not isinstance(arr, COSArray):
            arr = COSArray()
            self._catalog.set_item(_THREADS, arr)
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
        if not isinstance(perms, COSDictionary):
            raise TypeError(
                "PDDocumentCatalog.set_perms expected COSDictionary or None; "
                f"got {type(perms).__name__}"
            )
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
        if not isinstance(legal, COSDictionary):
            raise TypeError(
                "PDDocumentCatalog.set_legal expected COSDictionary or None; "
                f"got {type(legal).__name__}"
            )
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
        if not isinstance(collection, COSDictionary):
            raise TypeError(
                "PDDocumentCatalog.set_collection expected COSDictionary or None; "
                f"got {type(collection).__name__}"
            )
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
            try:
                spec = PDFileSpecification.create_fs(entry)
            except OSError:
                spec = None
            if spec is not None:
                result.append(spec)
        return result

    def set_associated_files(self, files: list[Any] | None) -> None:
        """Replace the catalog's ``/AF`` array. Pass ``None`` or an empty
        list to remove the entry entirely. Each entry must be a
        :class:`PDFileSpecification`; a :class:`TypeError` is raised on
        invalid input — matches the upstream Java generic-list contract."""
        from .common.filespecification import PDFileSpecification

        if not files:
            self._catalog.remove_item(_AF)
            return
        arr = COSArray()
        for spec in files:
            if not isinstance(spec, PDFileSpecification):
                raise TypeError(
                    "PDDocumentCatalog.set_associated_files entries must be "
                    f"PDFileSpecification; got {type(spec).__name__}"
                )
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
        if not isinstance(piece_info, COSDictionary):
            raise TypeError(
                "PDDocumentCatalog.set_piece_info expected COSDictionary or None; "
                f"got {type(piece_info).__name__}"
            )
        self._catalog.set_item(_PIECE_INFO, piece_info)

    # ---------- /NeedsRendering (PDF 1.7+, §7.7.3.4 Table 28) ----------

    def is_needs_rendering(self) -> bool:
        """Return the catalog's ``/NeedsRendering`` flag (PDF 32000-1
        §7.7.3.4 Table 28; PDF 1.7+).

        ``True`` indicates that the document, when consumed by an XFA-aware
        viewer, must regenerate its appearance from the form data before
        being displayed (Forms Architecture / dynamic XFA). Defaults to
        ``False`` when the entry is absent — matches the upstream PDF spec
        default. Upstream PDFBox does not yet surface this flag; pypdfbox
        ports it for forward parity (PDF 4.x line and PDF 2.0 ISO 32000-2
        §7.7.2 retain the entry)."""
        return self._catalog.get_boolean(_NEEDS_RENDERING, False)

    def set_needs_rendering(self, needs_rendering: bool | None) -> None:
        """Write the catalog's ``/NeedsRendering`` flag. Pass ``None`` to
        remove the entry entirely (returns to the implicit default)."""
        if needs_rendering is None:
            self._catalog.remove_item(_NEEDS_RENDERING)
            return
        self._catalog.set_boolean(_NEEDS_RENDERING, needs_rendering)

    # ---------- /OCProperties long-form alias ----------

    def get_optional_content_properties(self) -> Any:
        """Long-form alias for :meth:`get_oc_properties`. Mirrors the
        spec name ("Optional Content Properties Dictionary",
        PDF 32000-1 §8.11.4) for callers preferring the descriptive
        spelling over the abbreviated upstream ``getOCProperties``."""
        return self.get_oc_properties()

    def set_optional_content_properties(self, oc_properties: Any) -> None:
        """Long-form alias for :meth:`set_oc_properties`. Same side
        effects (auto-bumps document version to 1.5 when ``oc_properties``
        is non-``None``)."""
        self.set_oc_properties(oc_properties)

    # ---------- /URI /Base catalog-level shortcut ----------

    def get_base_uri(self) -> str | None:
        """Return the catalog's ``/URI /Base`` string, or ``None`` when
        either ``/URI`` or ``/URI /Base`` is absent.

        Catalog-level shortcut that reads the ``/Base`` entry inside the
        ``/URI`` sub-dictionary (PDF 32000-1 §12.6.4.7). Mirrors the
        :meth:`is_document_marked` / :meth:`has_user_properties` style of
        ``MarkInfo`` shortcuts — saves callers from materialising
        :class:`PDURIDictionary` for the common single-string case."""
        v = self._catalog.get_dictionary_object(_URI)
        if not isinstance(v, COSDictionary):
            return None
        from .interactive.action import PDURIDictionary

        return PDURIDictionary(v).get_base()

    def set_base_uri(self, base: str | None) -> None:
        """Write the catalog's ``/URI /Base`` string. Creates ``/URI`` on
        demand. Pass ``None`` to clear the ``/Base`` entry; the
        ``/URI`` dictionary itself is removed when emptied."""
        from .interactive.action import PDURIDictionary

        v = self._catalog.get_dictionary_object(_URI)
        if not isinstance(v, COSDictionary):
            if base is None:
                return
            v = COSDictionary()
            self._catalog.set_item(_URI, v)
        wrapper = PDURIDictionary(v)
        wrapper.set_base(base)
        if base is None and v.is_empty():
            self._catalog.remove_item(_URI)

    # ---------- presence predicates ----------

    # Lightweight ``has_*`` predicates that ask "does the catalog carry a
    # well-formed entry of the expected COS shape?" without materialising
    # the typed wrapper. Cheaper than ``get_<x>() is not None`` for hot
    # paths (no wrapper allocation), and clearer at the call site than a
    # raw ``contains_key`` check (which doesn't validate the value's type).

    def has_acro_form(self) -> bool:
        """Return ``True`` when the catalog has a well-formed ``/AcroForm``
        dictionary entry."""
        return isinstance(
            self._catalog.get_dictionary_object(_ACRO_FORM), COSDictionary
        )

    def has_struct_tree_root(self) -> bool:
        """Return ``True`` when the catalog has a well-formed
        ``/StructTreeRoot`` dictionary entry."""
        return isinstance(
            self._catalog.get_dictionary_object(_STRUCT_TREE_ROOT),
            COSDictionary,
        )

    def has_metadata(self) -> bool:
        """Return ``True`` when the catalog has a well-formed ``/Metadata``
        stream entry. Mirrors :meth:`get_metadata`'s type-check posture
        — a stray non-stream value reads as absent."""
        from pypdfbox.cos import COSStream

        return isinstance(
            self._catalog.get_dictionary_object(_METADATA), COSStream
        )

    def has_outline(self) -> bool:
        """Return ``True`` when the catalog has a well-formed ``/Outlines``
        dictionary entry."""
        return isinstance(
            self._catalog.get_dictionary_object(_OUTLINES), COSDictionary
        )

    def has_page_labels(self) -> bool:
        """Return ``True`` when the catalog has a well-formed
        ``/PageLabels`` number-tree entry."""
        return isinstance(
            self._catalog.get_dictionary_object(_PAGE_LABELS), COSDictionary
        )

    def has_open_action(self) -> bool:
        """Return ``True`` when the catalog has a well-formed
        ``/OpenAction`` entry — either an action dictionary or a
        destination array (PDF 32000-1 §12.6.4.4)."""
        v = self._catalog.get_dictionary_object(_OPEN_ACTION)
        return isinstance(v, COSDictionary | COSArray)

    def has_names(self) -> bool:
        """Return ``True`` when the catalog has a well-formed ``/Names``
        name-dictionary entry."""
        return isinstance(
            self._catalog.get_dictionary_object(_NAMES), COSDictionary
        )

    def has_oc_properties(self) -> bool:
        """Return ``True`` when the catalog has a well-formed
        ``/OCProperties`` dictionary entry (optional content groups)."""
        return isinstance(
            self._catalog.get_dictionary_object(_OC_PROPERTIES),
            COSDictionary,
        )

    def has_viewer_preferences(self) -> bool:
        """Return ``True`` when the catalog has a well-formed
        ``/ViewerPreferences`` dictionary entry."""
        return isinstance(
            self._catalog.get_dictionary_object(_VIEWER_PREFERENCES),
            COSDictionary,
        )

    def has_mark_info(self) -> bool:
        """Return ``True`` when the catalog has a well-formed ``/MarkInfo``
        dictionary entry. Note this does *not* imply ``/MarkInfo /Marked
        = true`` — see :meth:`is_tagged` / :meth:`is_document_marked` for
        the spec-tagged check."""
        return isinstance(
            self._catalog.get_dictionary_object(_MARK_INFO), COSDictionary
        )

    def has_threads(self) -> bool:
        """Return ``True`` when the catalog has a well-formed (non-empty)
        ``/Threads`` array entry. An empty array reads as absent — matches
        upstream's "no article threads to navigate" semantics."""
        arr = self._catalog.get_dictionary_object(_THREADS)
        return isinstance(arr, COSArray) and arr.size() > 0

    def has_dests(self) -> bool:
        """Return ``True`` when the catalog has a well-formed legacy
        ``/Dests`` dictionary entry (PDF 1.1 named destinations). The
        modern ``/Names /Dests`` name tree is checked via
        :meth:`has_names`."""
        return isinstance(
            self._catalog.get_dictionary_object(_DESTS), COSDictionary
        )

    def has_uri(self) -> bool:
        """Return ``True`` when the catalog has a well-formed ``/URI``
        dictionary entry (PDF 32000-1 §12.6.4.7)."""
        return isinstance(
            self._catalog.get_dictionary_object(_URI), COSDictionary
        )

    def has_associated_files(self) -> bool:
        """Return ``True`` when the catalog has at least one resolvable
        ``/AF`` file specification (PDF 2.0 / ISO 32000-2 §14.13).

        Malformed arrays containing only non-file-spec entries read as
        absent, matching :meth:`get_associated_files` which skips them.
        """
        arr = self._catalog.get_dictionary_object(_AF)
        if not isinstance(arr, COSArray):
            return False
        from .common.filespecification import PDFileSpecification

        for i in range(arr.size()):
            try:
                if PDFileSpecification.create_fs(arr.get_object(i)) is not None:
                    return True
            except OSError:
                continue
        return False

    def has_output_intents(self) -> bool:
        """Return ``True`` when the catalog has at least one well-formed
        ``/OutputIntents`` dictionary entry.

        Malformed arrays containing only non-dictionaries read as absent,
        matching :meth:`get_output_intents` which skips those entries.
        """
        arr = self._catalog.get_dictionary_object(_OUTPUT_INTENTS)
        if not isinstance(arr, COSArray):
            return False
        return any(
            isinstance(arr.get_object(i), COSDictionary)
            for i in range(arr.size())
        )

    def has_requirements(self) -> bool:
        """Return ``True`` when the catalog has at least one well-formed
        ``/Requirements`` dictionary entry (PDF 32000-1 §12.10).

        Malformed arrays containing only non-dictionaries read as absent,
        matching :meth:`get_requirements` which skips those entries.
        """
        arr = self._catalog.get_dictionary_object(_REQUIREMENTS)
        if not isinstance(arr, COSArray):
            return False
        return any(
            isinstance(arr.get_object(i), COSDictionary)
            for i in range(arr.size())
        )

    def has_developer_extensions(self) -> bool:
        """Return ``True`` when the catalog has a well-formed (non-empty)
        ``/Extensions`` dictionary entry (PDF 32000-1 §7.12.2). An empty
        dictionary reads as absent."""
        v = self._catalog.get_dictionary_object(_EXTENSIONS)
        return isinstance(v, COSDictionary) and not v.is_empty()

    def has_collection(self) -> bool:
        """Return ``True`` when the catalog has a well-formed ``/Collection``
        dictionary entry — i.e. the document is a PDF Portfolio
        (PDF 32000-1 §7.11.5 / §12.3.5)."""
        return isinstance(
            self._catalog.get_dictionary_object(_COLLECTION), COSDictionary
        )

    def is_collection(self) -> bool:
        """Return ``True`` when the document is a PDF Portfolio collection.
        Synonym for :meth:`has_collection` — the spec calls a document
        "a PDF collection" iff its catalog carries a ``/Collection``
        dictionary (PDF 32000-1 §7.11.5)."""
        return self.has_collection()

    def has_perms(self) -> bool:
        """Return ``True`` when the catalog has a well-formed ``/Perms``
        dictionary entry (PDF 32000-1 §12.8.5 — usage-rights / DocMDP
        permissions)."""
        return isinstance(
            self._catalog.get_dictionary_object(_PERMS), COSDictionary
        )

    def has_legal(self) -> bool:
        """Return ``True`` when the catalog has a well-formed ``/Legal``
        dictionary entry (PDF 32000-1 §12.8.6 — legal-attestation
        signature data)."""
        return isinstance(
            self._catalog.get_dictionary_object(_LEGAL), COSDictionary
        )

    def has_piece_info(self) -> bool:
        """Return ``True`` when the catalog has a well-formed ``/PieceInfo``
        page-piece dictionary entry (PDF 32000-1 §14.5)."""
        return isinstance(
            self._catalog.get_dictionary_object(_PIECE_INFO), COSDictionary
        )

    def has_actions(self) -> bool:
        """Return ``True`` when the catalog has a non-empty ``/AA`` dict.

        This is a read-only probe: unlike :meth:`get_actions`, it does not
        auto-materialise an empty additional-actions dictionary.
        """
        actions = self._catalog.get_dictionary_object(_AA)
        return isinstance(actions, COSDictionary) and len(actions) > 0

    def has_language(self) -> bool:
        """Return ``True`` when the catalog has a well-formed ``/Lang``
        text-string entry (PDF 32000-1 §14.9.2 — RFC 3066 / BCP 47
        language tag)."""
        v = self._catalog.get_dictionary_object(_LANG)
        return isinstance(v, COSString)

    def has_page_layout(self) -> bool:
        """Return ``True`` when ``/PageLayout`` is present and recognised."""
        return self.get_page_layout() is not None

    def has_page_mode(self) -> bool:
        """Return ``True`` when ``/PageMode`` is present and recognised."""
        return self.get_page_mode() is not None

    def has_version(self) -> bool:
        """Return ``True`` when the catalog has a well-formed ``/Version``
        override (a name or — defensively — a string). When present this
        upgrades the document's effective version past whatever the file
        header declares (PDF 32000-1 §7.5.2)."""
        v = self._catalog.get_dictionary_object(_VERSION)
        return isinstance(v, COSName | COSString)

    def has_dests_name_tree(self) -> bool:
        """Return ``True`` when the catalog reaches a ``/Names /Dests``
        name-tree entry — i.e. modern (PDF 1.2+) named-destination wiring
        is present. Distinct from :meth:`has_dests` which checks the
        legacy (PDF 1.1) flat ``/Dests`` dictionary."""
        names = self._catalog.get_dictionary_object(_NAMES)
        if not isinstance(names, COSDictionary):
            return False
        dests_name = COSName.get_pdf_name("Dests")
        return isinstance(
            names.get_dictionary_object(dests_name), COSDictionary
        )

    def has_base_uri(self) -> bool:
        """Return ``True`` when ``/URI /Base`` is present as a text string."""
        uri = self._catalog.get_dictionary_object(_URI)
        if not isinstance(uri, COSDictionary):
            return False
        return isinstance(
            uri.get_dictionary_object(COSName.get_pdf_name("Base")),
            COSString,
        )

    def has_needs_rendering(self) -> bool:
        """Return ``True`` when ``/NeedsRendering`` is explicitly present."""
        return self._catalog.contains_key(_NEEDS_RENDERING)

    def is_tagged(self) -> bool:
        """Return ``True`` when the document advertises a tagged-PDF
        accessibility tree.

        Spec-wise (PDF 32000-1 §14.8.1) a document is "tagged" iff its
        ``/MarkInfo`` dictionary has ``/Marked = true``. ``/StructTreeRoot``
        on its own indicates structural information without the producer's
        commitment that the structure tree fully complies with §14.8 — so
        we follow the strict spec definition (``/MarkInfo /Marked``)
        rather than the looser "structure tree exists" heuristic some
        readers use. Defaults to ``False`` when ``/MarkInfo`` is absent."""
        return self.is_document_marked()

    # ---------- clear_* helpers ----------
    #
    # One-call removers matching the local pypdfbox style used by info,
    # viewer-preference, action, and resource wrappers. These are equivalent
    # to passing ``None`` to the paired setter, but make call sites that only
    # want to remove catalog entries explicit and cache-safe.

    def clear_version(self) -> None:
        """Remove ``/Version``. No-op if absent."""
        self.set_version(None)

    def clear_language(self) -> None:
        """Remove ``/Lang``. No-op if absent."""
        self.set_language(None)

    def clear_page_layout(self) -> None:
        """Remove ``/PageLayout``. No-op if absent."""
        self.set_page_layout(None)

    def clear_page_mode(self) -> None:
        """Remove ``/PageMode``. No-op if absent."""
        self.set_page_mode(None)

    def clear_struct_tree_root(self) -> None:
        """Remove ``/StructTreeRoot``. No-op if absent."""
        self.set_struct_tree_root(None)

    def clear_structure_tree_root(self) -> None:
        """Remove ``/StructTreeRoot`` using the upstream spelling."""
        self.clear_struct_tree_root()

    def clear_mark_info(self) -> None:
        """Remove ``/MarkInfo``. No-op if absent."""
        self.set_mark_info(None)

    def clear_acro_form(self) -> None:
        """Remove ``/AcroForm`` and invalidate the cached wrapper."""
        self.set_acro_form(None)

    def clear_document_outline(self) -> None:
        """Remove ``/Outlines``. No-op if absent."""
        self.set_document_outline(None)

    def clear_outlines(self) -> None:
        """Remove ``/Outlines`` using the upstream alias spelling."""
        self.clear_document_outline()

    def clear_metadata(self) -> None:
        """Remove ``/Metadata``. No-op if absent."""
        self.set_metadata(None)

    def clear_actions(self) -> None:
        """Remove ``/AA`` additional actions. No-op if absent."""
        self.set_actions(None)

    def clear_oc_properties(self) -> None:
        """Remove ``/OCProperties``. No-op if absent."""
        self.set_oc_properties(None)

    def clear_optional_content_properties(self) -> None:
        """Remove ``/OCProperties`` using the long-form alias spelling."""
        self.clear_oc_properties()

    def clear_names(self) -> None:
        """Remove ``/Names``. No-op if absent."""
        self.set_names(None)

    def clear_dests(self) -> None:
        """Remove legacy catalog-level ``/Dests``. No-op if absent."""
        self.set_dests(None)

    def clear_open_action(self) -> None:
        """Remove ``/OpenAction``. No-op if absent."""
        self.set_open_action(None)

    def clear_viewer_preferences(self) -> None:
        """Remove ``/ViewerPreferences``. No-op if absent."""
        self.set_viewer_preferences(None)

    def clear_view_preferences(self) -> None:
        """Remove ``/ViewerPreferences`` using the upstream alias spelling."""
        self.clear_viewer_preferences()

    def clear_page_labels(self) -> None:
        """Remove ``/PageLabels``. No-op if absent."""
        self.set_page_labels(None)

    def clear_output_intents(self) -> None:
        """Remove ``/OutputIntents``. No-op if absent."""
        self.set_output_intents(None)

    def clear_threads(self) -> None:
        """Remove ``/Threads``. No-op if absent."""
        self.set_threads(None)

    def clear_perms(self) -> None:
        """Remove ``/Perms``. No-op if absent."""
        self.set_perms(None)

    def clear_legal(self) -> None:
        """Remove ``/Legal``. No-op if absent."""
        self.set_legal(None)

    def clear_collection(self) -> None:
        """Remove ``/Collection``. No-op if absent."""
        self.set_collection(None)

    def clear_developer_extensions(self) -> None:
        """Remove ``/Extensions``. No-op if absent."""
        self.set_developer_extensions(None)

    def clear_uri(self) -> None:
        """Remove the catalog-level ``/URI`` dictionary. No-op if absent."""
        self.set_uri(None)

    def clear_base_uri(self) -> None:
        """Remove only ``/URI /Base`` and drop ``/URI`` if it becomes empty."""
        self.set_base_uri(None)

    def clear_requirements(self) -> None:
        """Remove ``/Requirements``. No-op if absent."""
        self.set_requirements(None)

    def clear_associated_files(self) -> None:
        """Remove ``/AF`` associated files. No-op if absent."""
        self.set_associated_files(None)

    def clear_piece_info(self) -> None:
        """Remove ``/PieceInfo``. No-op if absent."""
        self.set_piece_info(None)

    def clear_needs_rendering(self) -> None:
        """Remove ``/NeedsRendering``. No-op if absent."""
        self.set_needs_rendering(None)

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
