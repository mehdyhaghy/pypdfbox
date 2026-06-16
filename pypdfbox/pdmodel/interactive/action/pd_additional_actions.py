from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_action import PDAction
from .pd_action_factory import PDActionFactory

_F: COSName = COSName.get_pdf_name("F")


class PDAdditionalActions:
    """Generic additional-actions dictionary. Mirrors PDFBox
    ``PDAdditionalActions`` for the ``/F`` trigger."""

    TRIGGER_F: COSName = _F

    def __init__(self, actions: COSDictionary | None = None) -> None:
        self._actions = actions if actions is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._actions

    def get_f(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_F)
        return PDActionFactory.create_action(value) if isinstance(value, COSDictionary) else None

    def set_f(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_F)
            return
        self._actions.set_item(_F, action.get_cos_object())


__all__ = ["PDAdditionalActions"]
