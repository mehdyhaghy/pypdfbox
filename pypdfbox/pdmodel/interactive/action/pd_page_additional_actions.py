from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_action import PDAction

_O: COSName = COSName.get_pdf_name("O")
_C: COSName = COSName.C  # type: ignore[attr-defined]


class PDPageAdditionalActions:
    """
    Page additional-actions dictionary. Mirrors PDFBox
    ``PDPageAdditionalActions`` for the page-open (``/O``) and page-close
    (``/C``) triggers.
    """

    def __init__(self, actions: COSDictionary | None = None) -> None:
        self._actions = actions if actions is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._actions

    def get_o(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_O)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_o(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_O)
            return
        self._actions.set_item(_O, action.get_cos_object())

    def get_c(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_C)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_c(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_C)
            return
        self._actions.set_item(_C, action.get_cos_object())


__all__ = ["PDPageAdditionalActions"]
