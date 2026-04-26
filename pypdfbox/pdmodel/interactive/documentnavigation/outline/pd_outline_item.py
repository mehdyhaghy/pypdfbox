from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName

from .pd_outline_node import PDOutlineNode

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
        PDDestination,
    )


_TITLE: COSName = COSName.get_pdf_name("Title")
_DEST: COSName = COSName.get_pdf_name("Dest")
_A: COSName = COSName.A  # type: ignore[attr-defined]
_C: COSName = COSName.C  # type: ignore[attr-defined]
_F: COSName = COSName.get_pdf_name("F")
_NEXT: COSName = COSName.get_pdf_name("Next")
_PREV: COSName = COSName.PREV  # type: ignore[attr-defined]
_SE: COSName = COSName.get_pdf_name("SE")

_ITALIC_FLAG = 1
_BOLD_FLAG = 2


class PDOutlineItem(PDOutlineNode):
    """
    Single entry in the outline tree. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem``.

    Inherits children-management from :class:`PDOutlineNode` (an item can
    itself be a parent) and adds sibling navigation plus the spec-defined
    ``/Title``, ``/Dest``, ``/A``, ``/C`` (RGB color) and ``/F`` (style
    flags) keys.
    """

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

    def set_destination(self, dest: PDDestination | None) -> None:
        if dest is None:
            self._dictionary.remove_item(_DEST)
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

    def get_text_color(self) -> tuple[float, float, float]:
        """Return the RGB text colour as a 3-tuple in [0, 1]. Default
        black when ``/C`` is absent or malformed (matches upstream)."""
        arr = self._dictionary.get_dictionary_object(_C)
        if isinstance(arr, COSArray) and arr.size() >= 3:
            vals = arr.to_float_array()[:3]
            return (vals[0], vals[1], vals[2])
        return (0.0, 0.0, 0.0)

    def set_text_color(self, rgb: tuple[float, float, float]) -> None:
        arr = COSArray([COSFloat(float(c)) for c in rgb])
        self._dictionary.set_item(_C, arr)

    # ---------- /F (style flags) ----------

    def _get_flag(self, mask: int) -> bool:
        return bool(self._dictionary.get_int(_F, 0) & mask)

    def _set_flag(self, mask: int, value: bool) -> None:
        current = self._dictionary.get_int(_F, 0)
        if value:
            current |= mask
        else:
            current &= ~mask
        self._dictionary.set_item(_F, COSInteger.get(current))

    def is_italic(self) -> bool:
        return self._get_flag(_ITALIC_FLAG)

    def set_italic(self, italic: bool) -> None:
        self._set_flag(_ITALIC_FLAG, italic)

    def is_bold(self) -> bool:
        return self._get_flag(_BOLD_FLAG)

    def set_bold(self, bold: bool) -> None:
        self._set_flag(_BOLD_FLAG, bold)


__all__ = ["PDOutlineItem"]
