from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_action import PDAction

_K: COSName = COSName.get_pdf_name("K")
_F: COSName = COSName.get_pdf_name("F")
_V: COSName = COSName.get_pdf_name("V")
_C: COSName = COSName.C  # type: ignore[attr-defined]


class PDFormFieldAdditionalActions:
    """
    Form-field additional-actions dictionary. Mirrors PDFBox
    ``PDFormFieldAdditionalActions`` for the keystroke (``/K``), format
    (``/F``), validate (``/V``) and calculate (``/C``) triggers (PDF
    32000-1:2008 §12.6.3, Table 196).
    """

    def __init__(self, actions: COSDictionary | None = None) -> None:
        self._actions = actions if actions is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._actions

    def get_k(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_K)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_k(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_K)
            return
        self._actions.set_item(_K, action.get_cos_object())

    def get_f(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_F)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_f(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_F)
            return
        self._actions.set_item(_F, action.get_cos_object())

    def get_v(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_V)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_v(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_V)
            return
        self._actions.set_item(_V, action.get_cos_object())

    def get_c(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_C)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_c(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_C)
            return
        self._actions.set_item(_C, action.get_cos_object())


__all__ = ["PDFormFieldAdditionalActions"]
