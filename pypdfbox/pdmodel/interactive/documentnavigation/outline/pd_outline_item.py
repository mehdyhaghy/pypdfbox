from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName

from .pd_outline_node import PDOutlineNode

if TYPE_CHECKING:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
        PDStructureElement,
    )
    from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
    from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
        PDDestination,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage


_TITLE: COSName = COSName.get_pdf_name("Title")
_DEST: COSName = COSName.get_pdf_name("Dest")
_A: COSName = COSName.A  # type: ignore[attr-defined]
_C: COSName = COSName.C  # type: ignore[attr-defined]
_F: COSName = COSName.get_pdf_name("F")
_COUNT: COSName = COSName.COUNT  # type: ignore[attr-defined]
_NEXT: COSName = COSName.get_pdf_name("Next")
_PREV: COSName = COSName.PREV  # type: ignore[attr-defined]
_SE: COSName = COSName.get_pdf_name("SE")


class PDOutlineItem(PDOutlineNode):
    """
    Single entry in the outline tree. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem``.

    Inherits children-management from :class:`PDOutlineNode` (an item can
    itself be a parent) and adds sibling navigation plus the spec-defined
    ``/Title``, ``/Dest``, ``/A``, ``/C`` (RGB color), ``/F`` (style
    flags), ``/SE`` (structure element) and ``/Count`` (signed open/closed
    descendant counter) keys.
    """

    # ---------- /F flag bits (PDF 32000-1:2008 §12.3.3) ----------

    FLAG_ITALIC: int = 1 << 0
    FLAG_BOLD: int = 1 << 1

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)

    # ---------- siblings ----------

    def get_previous_sibling(self) -> PDOutlineItem | None:
        return self._get_outline_item(_PREV)

    def get_next_sibling(self) -> PDOutlineItem | None:
        return self._get_outline_item(_NEXT)

    def _set_previous_sibling(self, node: PDOutlineNode) -> None:
        self._dictionary.set_item(_PREV, node.get_cos_object())

    def _set_next_sibling(self, node: PDOutlineNode) -> None:
        self._dictionary.set_item(_NEXT, node.get_cos_object())

    # Test-only setter exposed by upstream PDOutlineItemIteratorTest.
    def set_next_sibling(self, node: PDOutlineNode) -> None:
        """Public alias of the internal next-sibling setter — upstream
        exposes this for hand-built test fixtures and we mirror that."""
        self._set_next_sibling(node)

    # ---------- sibling insertion ----------

    def insert_sibling_after(self, new_sibling: PDOutlineItem) -> None:
        """Insert ``new_sibling`` immediately after this item."""
        self._require_single_node(new_sibling)
        parent = self.get_parent()
        if parent is not None:
            new_sibling._set_parent(parent)
        nxt = self.get_next_sibling()
        self._set_next_sibling(new_sibling)
        new_sibling._set_previous_sibling(self)
        if nxt is not None:
            new_sibling._set_next_sibling(nxt)
            nxt._set_previous_sibling(new_sibling)
        elif parent is not None:
            parent._set_last_child(new_sibling)
        self._update_parent_open_count_for_added_child(new_sibling)

    def insert_sibling_before(self, new_sibling: PDOutlineItem) -> None:
        """Insert ``new_sibling`` immediately before this item."""
        self._require_single_node(new_sibling)
        parent = self.get_parent()
        if parent is not None:
            new_sibling._set_parent(parent)
        prev = self.get_previous_sibling()
        self._set_previous_sibling(new_sibling)
        new_sibling._set_next_sibling(self)
        if prev is not None:
            prev._set_next_sibling(new_sibling)
            new_sibling._set_previous_sibling(prev)
        elif parent is not None:
            parent._set_first_child(new_sibling)
        self._update_parent_open_count_for_added_child(new_sibling)

    # ---------- /Title ----------

    def get_title(self) -> str | None:
        return self._dictionary.get_string(_TITLE)

    def set_title(self, title: str | None) -> None:
        self._dictionary.set_string(_TITLE, title)

    # ---------- /Dest ----------

    def get_destination(self) -> PDDestination | None:
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
            PDDestination,
        )

        raw = self._dictionary.get_dictionary_object(_DEST)
        return PDDestination.create(raw)

    def set_destination(self, dest: "PDDestination | PDPage | None") -> None:
        """Set the outline's ``/Dest``.

        Accepts:

        - ``PDDestination`` — written verbatim.
        - ``PDPage`` — upstream convenience overload that creates a
          default ``PDPageXYZDestination`` pointing at the given page
          (mirrors ``PDOutlineItem#setDestination(PDPage)``).
        - ``None`` — removes ``/Dest``.
        """
        if dest is None:
            self._dictionary.remove_item(_DEST)
            return
        # Upstream convenience: PDPage in → wrap as a default XYZ destination.
        from pypdfbox.pdmodel.pd_page import PDPage

        if isinstance(dest, PDPage):
            from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_xyz_destination import (
                PDPageXYZDestination,
            )

            xyz = PDPageXYZDestination()
            xyz.set_page(dest)
            self._dictionary.set_item(_DEST, xyz.get_cos_object())
            return
        self._dictionary.set_item(_DEST, dest.get_cos_object())

    # ---------- /A ----------

    def get_action(self) -> PDAction | None:
        from pypdfbox.pdmodel.interactive.action.pd_action import PDAction

        raw = self._dictionary.get_dictionary_object(_A)
        if isinstance(raw, COSDictionary):
            return PDAction.create(raw)
        return None

    def set_action(self, action: PDAction | None) -> None:
        if action is None:
            self._dictionary.remove_item(_A)
            return
        self._dictionary.set_item(_A, action.get_cos_object())

    # ---------- /C (RGB color triple) ----------

    def get_text_color(self) -> tuple[float, float, float] | None:
        """Return the RGB text colour as a 3-tuple in [0, 1], or ``None``
        when ``/C`` is absent or malformed.

        **Pypdfbox divergence from upstream**: upstream's
        ``getTextColor()`` materializes a ``[0,0,0]`` ``COSArray`` on the
        outline dictionary if ``/C`` is missing and never returns
        ``null``. We return ``None`` here so callers can distinguish
        "unset" from "explicitly black" without paying the side-effect
        write. For an upstream-shaped ``PDColor`` accessor that *does*
        materialize the default, see :meth:`get_text_color_pd_color`.
        See ``CHANGES.md``.
        """
        arr = self._dictionary.get_dictionary_object(_C)
        if isinstance(arr, COSArray) and arr.size() >= 3:
            vals = arr.to_float_array()[:3]
            return (vals[0], vals[1], vals[2])
        return None

    def get_text_color_pd_color(self) -> "PDColor":
        """Return a typed ``PDColor`` for ``/C`` against
        ``PDDeviceRGB.INSTANCE``, mirroring upstream
        ``PDOutlineItem#getTextColor()`` exactly.

        Upstream behaviour: when ``/C`` is absent, upstream materializes a
        zero-filled 3-element ``COSArray`` on the outline dictionary
        (so the next read sees ``[0,0,0]`` rather than absent) and wraps
        it. We mirror that side-effect for parity with callers that round-trip
        the dictionary.
        """
        from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
        from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB

        arr = self._dictionary.get_dictionary_object(_C)
        if not isinstance(arr, COSArray):
            arr = COSArray()
            arr.grow_to_size(3, COSFloat(0.0))
            self._dictionary.set_item(_C, arr)
        return PDColor(arr, PDDeviceRGB.INSTANCE)

    def set_text_color(
        self, rgb: "tuple[float, float, float] | PDColor | None"
    ) -> None:
        """Set the outline's RGB ``/C`` colour.

        Accepts:

        - ``tuple[float, float, float]`` — three components in [0, 1].
        - ``PDColor`` — written via :meth:`PDColor.to_cos_array` (upstream
          ``setTextColor(PDColor)``).
        - ``None`` — removes ``/C``.
        """
        if rgb is None:
            self._dictionary.remove_item(_C)
            return
        # Local import to avoid cycles via graphics/color → fontbox at
        # module-import time.
        from pypdfbox.pdmodel.graphics.color.pd_color import PDColor

        if isinstance(rgb, PDColor):
            self._dictionary.set_item(_C, rgb.to_cos_array())
            return
        arr = COSArray([COSFloat(float(c)) for c in rgb])
        self._dictionary.set_item(_C, arr)

    # ---------- /F (style flags) ----------

    def get_text_flags(self) -> int:
        """Return the raw ``/F`` integer (default ``0``)."""
        return self._dictionary.get_int(_F, 0)

    def set_text_flags(self, flags: int) -> None:
        self._dictionary.set_item(_F, COSInteger.get(int(flags)))

    # Upstream-compatibility aliases — Apache PDFBox names the same
    # ``/F`` accessor pair ``getTextStyle`` / ``setTextStyle``.
    def get_text_style(self) -> int:
        """Upstream alias for :meth:`get_text_flags` — returns the raw
        ``/F`` integer (default ``0``). Mirrors
        ``PDOutlineItem#getTextStyle`` in the Java API."""
        return self.get_text_flags()

    def set_text_style(self, style: int) -> None:
        """Upstream alias for :meth:`set_text_flags`. Mirrors
        ``PDOutlineItem#setTextStyle(int)`` in the Java API."""
        self.set_text_flags(style)

    def _get_flag(self, mask: int) -> bool:
        return bool(self.get_text_flags() & mask)

    def _set_flag(self, mask: int, value: bool) -> None:
        current = self.get_text_flags()
        if value:
            current |= mask
        else:
            current &= ~mask
        self.set_text_flags(current)

    def is_italic(self) -> bool:
        return self._get_flag(self.FLAG_ITALIC)

    def set_italic(self, italic: bool) -> None:
        self._set_flag(self.FLAG_ITALIC, italic)

    def is_bold(self) -> bool:
        return self._get_flag(self.FLAG_BOLD)

    def set_bold(self, bold: bool) -> None:
        self._set_flag(self.FLAG_BOLD, bold)

    # ---------- /SE (structure element) ----------

    def get_structure_element(self) -> "PDStructureElement | None":
        """Return the typed ``/SE`` :class:`PDStructureElement` or
        ``None`` when absent. Mirrors
        ``PDOutlineItem#getStructureElement()``.

        ``PDStructureElement`` is imported lazily to avoid pulling the
        logical-structure cluster into ``outline``'s import graph at
        module load time.
        """
        value = self._dictionary.get_dictionary_object(_SE)
        if not isinstance(value, COSDictionary):
            return None
        from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
            PDStructureElement,
        )

        return PDStructureElement(value)

    def set_structure_element(
        self, elem: "PDStructureElement | COSDictionary | None"
    ) -> None:
        if elem is None:
            self._dictionary.remove_item(_SE)
            return
        self._dictionary.set_item(
            _SE,
            elem.get_cos_object() if hasattr(elem, "get_cos_object") else elem,
        )

    # ---------- /Count (signed: negative ⇒ collapsed) ----------

    def get_count(self) -> int:
        """Return the raw signed ``/Count`` (default ``0``).

        Per PDF 32000-1:2008 §12.3.3 a negative count means the item is
        collapsed and ``abs(count)`` is the number of visible descendants
        when expanded; a positive count means open. Upstream stores this
        signed value verbatim and so do we."""
        return self._dictionary.get_int(_COUNT, 0)

    def set_count(self, count: int) -> None:
        self._dictionary.set_item(_COUNT, COSInteger.get(int(count)))

    def is_collapsed(self) -> bool:
        """``True`` when ``/Count`` is negative (item is collapsed)."""
        return self.get_count() < 0

    # ---------- destination page resolution ----------

    def find_destination_page(self, document: "PDDocument") -> COSDictionary | None:
        """Resolve this outline's ``/Dest`` (or its ``/A`` action's
        destination) to a page ``COSDictionary`` against ``document``.

        Resolves:

        - explicit page-index destinations (``/D[0]`` is an integer);
        - direct page-dict destinations (``/D[0]`` is already a page
          ``COSDictionary``);
        - ``PDNamedDestination`` (string or name) — looked up first in
          the catalog ``/Dests`` dictionary (PDF 1.1) and then in the
          ``/Names/Dests`` name tree (PDF 1.2+).

        **Pypdfbox divergence from upstream**: upstream returns a typed
        ``PDPage``; we return the page's ``COSDictionary`` so existing
        in-tree consumers (``listbookmarks``, ``PDFTextStripper``) can
        keep their identity-comparison shape. See ``CHANGES.md``.
        Returns ``None`` when no destination is present or it can't be
        resolved.
        """
        from pypdfbox.pdmodel.interactive.action.pd_action_go_to import (
            PDActionGoTo,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
            PDNamedDestination,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (
            PDPageDestination,
        )

        destination = self.get_destination()
        if destination is None:
            action = self.get_action()
            if isinstance(action, PDActionGoTo):
                resolved_action_dest = action.get_destination()
                if isinstance(resolved_action_dest, str):
                    # Upstream's PDActionGoTo returns a `PDNamedDestination`
                    # for the string form; our PDActionGoTo returns the bare
                    # string (see CHANGES.md). Re-wrap so the named-destination
                    # resolution path below kicks in.
                    destination = PDNamedDestination(resolved_action_dest)
                else:
                    destination = resolved_action_dest
        if destination is None:
            return None
        # PDNamedDestination → catalog lookup.
        if isinstance(destination, PDNamedDestination):
            destination = self._resolve_named_destination(document, destination)
            if destination is None:
                return None
        if not isinstance(destination, PDPageDestination):
            return None
        # Direct page-dict reference: the destination already points at
        # the page we want.
        page = destination.get_page()
        if page is not None:
            return page
        page_number = destination.get_page_number()
        if page_number < 0:
            return None
        pages = document.get_pages()
        if page_number >= len(pages):
            return None
        return pages[page_number].get_cos_object()

    @staticmethod
    def _resolve_named_destination(
        document: "PDDocument", named: "object"
    ) -> "PDDestination | None":
        """Resolve a ``PDNamedDestination`` via the catalog's ``/Dests``
        dictionary (PDF 1.1) and ``/Names/Dests`` name tree (PDF 1.2+).

        Returns the typed ``PDDestination`` whose ``/D`` array was
        looked up, or ``None`` when the name is missing from both
        sources. The lookup prefers the catalog ``/Dests`` entry to
        match upstream ``PDDocumentCatalog#findNamedDestinationPage``
        precedence.
        """
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
            PDDestination,
        )

        get_named = getattr(named, "get_named_destination", None)
        if not callable(get_named):
            return None
        name = get_named()
        if not isinstance(name, str):
            return None
        catalog = document.get_document_catalog()
        # /Dests dictionary (PDF 1.1).
        dests = catalog.get_dests()
        if dests is not None:
            entry = None
            # PDDestinationNameTreeNode-shaped wrappers expose get_value(name);
            # plain COSDictionary wrappers may expose get_dictionary_object.
            get_value = getattr(dests, "get_value", None)
            if callable(get_value):
                entry = get_value(name)
            if entry is None:
                cos = getattr(dests, "get_cos_object", None)
                raw = cos() if callable(cos) else None
                if isinstance(raw, COSDictionary):
                    entry = raw.get_dictionary_object(COSName.get_pdf_name(name))
            if entry is not None:
                # Dest entries may be wrapped in a dictionary with a /D key.
                if isinstance(entry, COSDictionary):
                    inner = entry.get_dictionary_object(COSName.get_pdf_name("D"))
                    if inner is not None:
                        entry = inner
                resolved = PDDestination.create(entry)
                if resolved is not None:
                    return resolved
        # /Names/Dests name tree (PDF 1.2+).
        names = catalog.get_names()
        if names is None:
            return None
        get_dests_tree = getattr(names, "get_dests", None)
        if not callable(get_dests_tree):
            return None
        tree = get_dests_tree()
        if tree is None:
            return None
        get_value = getattr(tree, "get_value", None)
        if not callable(get_value):
            return None
        entry = get_value(name)
        if entry is None:
            return None
        if isinstance(entry, COSDictionary):
            inner = entry.get_dictionary_object(COSName.get_pdf_name("D"))
            if inner is not None:
                entry = inner
        return PDDestination.create(entry)


__all__ = ["PDOutlineItem"]
