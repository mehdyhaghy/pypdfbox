from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.pagenavigation.pd_transition import PDTransition

from .pd_action import PDAction

_TRANS: COSName = COSName.get_pdf_name("Trans")


class PDActionTransition(PDAction):
    """Transition action. Mirrors PDFBox ``PDActionTransition`` lite surface."""

    SUB_TYPE = "Trans"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_trans(self) -> PDTransition | None:
        value = self._action.get_dictionary_object(_TRANS)
        if isinstance(value, COSDictionary):
            return PDTransition(value)
        return None

    def set_trans(self, trans: PDTransition | None) -> None:
        if trans is None:
            self._action.remove_item(_TRANS)
            return
        self._action.set_item(_TRANS, trans.get_cos_object())


__all__ = ["PDActionTransition"]
