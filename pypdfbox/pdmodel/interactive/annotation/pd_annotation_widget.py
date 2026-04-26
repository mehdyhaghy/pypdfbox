from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

from .pd_annotation import PDAnnotation

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.action import PDAction


_H: COSName = COSName.get_pdf_name("H")
_A: COSName = COSName.get_pdf_name("A")
_AA: COSName = COSName.get_pdf_name("AA")
_BS: COSName = COSName.get_pdf_name("BS")
_MK: COSName = COSName.get_pdf_name("MK")
_PARENT: COSName = COSName.get_pdf_name("Parent")


class PDAnnotationWidget(PDAnnotation):
    """
    Widget annotation — ``/Subtype /Widget``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget``.

    Widget annotations represent the visual appearance of interactive form
    fields (PDF 32000-1:2008 §12.5.6.19). When a field has a single
    associated widget, the widget dictionary is typically merged with the
    field dictionary; when there are multiple widgets per field, each is a
    separate annotation pointing back at the field via ``/Parent``.
    """

    SUB_TYPE: str = "Widget"

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /H (highlighting mode) ----------

    def get_highlighting_mode(self) -> str:
        """Default per spec is INVERT (``I``)."""
        value = self._dict.get_name(_H)
        return value if value is not None else "I"

    def set_highlighting_mode(self, mode: str | None) -> None:
        if mode is None:
            self._dict.remove_item(_H)
            return
        if mode not in ("N", "I", "O", "P", "T"):
            raise ValueError(
                f"Invalid highlighting mode {mode!r}; expected one of N, I, O, P, T"
            )
        self._dict.set_name(_H, mode)

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

    # ---------- /AA (additional actions) ----------

    def get_actions(self) -> COSDictionary | None:
        """Cluster lite stub — returns the raw additional-actions dict.
        ``PDFormFieldAdditionalActions`` typed wrapper is deferred to a
        later cluster."""
        value = self._dict.get_dictionary_object(_AA)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_actions(self, actions: COSDictionary | None) -> None:
        if actions is None:
            self._dict.remove_item(_AA)
            return
        self._dict.set_item(_AA, actions)

    # ---------- /BS (border style) ----------

    def get_border_style(self) -> COSDictionary | None:
        """Cluster lite stub — returns the raw border-style dict.
        ``PDBorderStyleDictionary`` typed wrapper is deferred."""
        value = self._dict.get_dictionary_object(_BS)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_border_style(self, bs: COSDictionary | None) -> None:
        if bs is None:
            self._dict.remove_item(_BS)
            return
        self._dict.set_item(_BS, bs)

    # ---------- /MK (appearance characteristics) ----------

    def get_appearance_characteristics(self) -> COSDictionary | None:
        """Cluster lite stub — returns the raw ``/MK`` dict.
        ``PDAppearanceCharacteristicsDictionary`` typed wrapper is deferred."""
        value = self._dict.get_dictionary_object(_MK)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_appearance_characteristics(self, ac: COSDictionary | None) -> None:
        if ac is None:
            self._dict.remove_item(_MK)
            return
        self._dict.set_item(_MK, ac)

    # ---------- /Parent (field) ----------

    def get_parent(self) -> COSDictionary | None:
        """Cluster lite stub — returns the raw parent field dict. Typed
        ``PDField`` wrapper would create a circular import between the
        annotation and form packages, so ``/Parent`` stays raw COS for now.
        """
        value = self._dict.get_dictionary_object(_PARENT)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_parent(self, field: COSDictionary | None) -> None:
        if field is None:
            self._dict.remove_item(_PARENT)
            return
        self._dict.set_item(
            _PARENT,
            field.get_cos_object() if hasattr(field, "get_cos_object") else field,
        )


__all__ = ["PDAnnotationWidget"]
