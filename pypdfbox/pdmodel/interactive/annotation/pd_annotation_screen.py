from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

from .pd_annotation import PDAnnotation

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
    from pypdfbox.pdmodel.interactive.action.pd_annotation_additional_actions import (
        PDAnnotationAdditionalActions,
    )

_T: COSName = COSName.get_pdf_name("T")
_MK: COSName = COSName.get_pdf_name("MK")
_A: COSName = COSName.get_pdf_name("A")
_AA: COSName = COSName.get_pdf_name("AA")


class PDAnnotationScreen(PDAnnotation):
    """
    Screen annotation — ``/Subtype /Screen``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationScreen``.

    A screen annotation specifies a region of a page upon which media
    clips may be played; it also serves as an object from which actions
    can be triggered (PDF 32000-1:2008 §12.5.6.18, Table 187). Not a
    markup annotation — extends :class:`PDAnnotation` directly.
    """

    SUB_TYPE: str = "Screen"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /T (annotation title) ----------

    def get_title(self) -> str | None:
        return self._dict.get_string(_T)

    def set_title(self, value: str | None) -> None:
        self._dict.set_string(_T, value)

    # ---------- /MK (appearance characteristics dictionary) ----------

    def get_appearance_characteristics(self) -> "PDAppearanceCharacteristicsDictionary | None":
        from .pd_appearance_characteristics_dictionary import (
            PDAppearanceCharacteristicsDictionary,
        )

        value = self._dict.get_dictionary_object(_MK)
        if isinstance(value, COSDictionary):
            return PDAppearanceCharacteristicsDictionary(value)
        return None

    def set_appearance_characteristics(
        self,
        mk: "PDAppearanceCharacteristicsDictionary | COSDictionary | None",
    ) -> None:
        if mk is None:
            self._dict.remove_item(_MK)
            return
        self._dict.set_item(
            _MK,
            mk.get_cos_object() if hasattr(mk, "get_cos_object") else mk,
        )

    # ---------- /A (action) ----------

    def get_action(self) -> "PDAction | None":
        from pypdfbox.pdmodel.interactive.action.pd_action import PDAction

        value = self._dict.get_dictionary_object(_A)
        if isinstance(value, COSDictionary):
            return PDAction.create(value)
        return None

    def set_action(self, action: "PDAction | COSDictionary | None") -> None:
        if action is None:
            self._dict.remove_item(_A)
            return
        self._dict.set_item(
            _A,
            action.get_cos_object() if hasattr(action, "get_cos_object") else action,
        )

    # ---------- /AA (additional actions) ----------

    def get_additional_actions(self) -> "PDAnnotationAdditionalActions | None":
        from pypdfbox.pdmodel.interactive.action.pd_annotation_additional_actions import (
            PDAnnotationAdditionalActions,
        )

        value = self._dict.get_dictionary_object(_AA)
        if isinstance(value, COSDictionary):
            return PDAnnotationAdditionalActions(value)
        return None

    def set_additional_actions(
        self, aa: "PDAnnotationAdditionalActions | COSDictionary | None"
    ) -> None:
        if aa is None:
            self._dict.remove_item(_AA)
            return
        self._dict.set_item(
            _AA,
            aa.get_cos_object() if hasattr(aa, "get_cos_object") else aa,
        )


__all__ = ["PDAnnotationScreen"]
