from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName

from .pd_annotation import PDAnnotation

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.action import PDAction
    from pypdfbox.pdmodel.interactive.documentnavigation.destination import PDDestination

_A: COSName = COSName.get_pdf_name("A")
_DEST: COSName = COSName.get_pdf_name("Dest")
_H: COSName = COSName.get_pdf_name("H")
_BS: COSName = COSName.get_pdf_name("BS")


class PDAnnotationLink(PDAnnotation):
    """
    Link annotation — ``/Subtype /Link``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink``.

    Either ``/A`` (action) or ``/Dest`` (destination) carries the target —
    not both, per PDF 32000-1:2008 §12.5.6.5.
    """

    SUB_TYPE: str = "Link"

    HIGHLIGHT_MODE_NONE: str = "N"
    HIGHLIGHT_MODE_INVERT: str = "I"  # PDF spec default
    HIGHLIGHT_MODE_OUTLINE: str = "O"
    HIGHLIGHT_MODE_PUSH: str = "P"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /A (action) ----------

    def get_action(self) -> PDAction | None:
        from pypdfbox.pdmodel.interactive.action import PDAction

        value = self._dict.get_dictionary_object(_A)
        if isinstance(value, COSDictionary):
            return PDAction.create(value)
        return None

    def set_action(self, action: PDAction | COSDictionary | None) -> None:
        if action is None:
            self._dict.remove_item(_A)
            return
        self._dict.set_item(
            _A,
            action.get_cos_object() if hasattr(action, "get_cos_object") else action,
        )

    # ---------- /Dest (destination) ----------

    def get_destination(self) -> PDDestination | None:
        from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
            PDDestination,
        )

        value = self._dict.get_dictionary_object(_DEST)
        return PDDestination.create(value)

    def set_destination(self, dest: PDDestination | COSBase | None) -> None:
        if dest is None:
            self._dict.remove_item(_DEST)
            return
        self._dict.set_item(
            _DEST,
            dest.get_cos_object() if hasattr(dest, "get_cos_object") else dest,
        )

    # ---------- /H (highlight mode) ----------

    def get_highlight_mode(self) -> str:
        """Default per spec is INVERT (``I``)."""
        value = self._dict.get_name(_H)
        return value if value is not None else self.HIGHLIGHT_MODE_INVERT

    def set_highlight_mode(self, mode: str | None) -> None:
        if mode is None:
            self._dict.remove_item(_H)
            return
        self._dict.set_name(_H, mode)

    # ---------- /BS (border style) ----------

    def get_border_style(self) -> "PDBorderStyleDictionary | None":
        from .pd_border_style_dictionary import PDBorderStyleDictionary

        value = self._dict.get_dictionary_object(_BS)
        if isinstance(value, COSDictionary):
            return PDBorderStyleDictionary(value)
        return None

    def set_border_style(
        self, bs: "PDBorderStyleDictionary | COSDictionary | None"
    ) -> None:
        if bs is None:
            self._dict.remove_item(_BS)
            return
        self._dict.set_item(
            _BS,
            bs.get_cos_object() if hasattr(bs, "get_cos_object") else bs,
        )

    # ---------- /QuadPoints — exposed as raw array (deferred typed wrapper) ----------

    def get_quad_points(self) -> COSArray | None:
        value = self._dict.get_dictionary_object(COSName.get_pdf_name("QuadPoints"))
        if isinstance(value, COSArray):
            return value
        return None

    def set_quad_points(self, quad_points: COSArray | None) -> None:
        key = COSName.get_pdf_name("QuadPoints")
        if quad_points is None:
            self._dict.remove_item(key)
            return
        self._dict.set_item(key, quad_points)


__all__ = ["PDAnnotationLink"]
