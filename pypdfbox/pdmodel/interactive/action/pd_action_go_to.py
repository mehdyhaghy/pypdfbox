from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.documentnavigation.destination import PDDestination

from .pd_action import PDAction

_D: COSName = COSName.D  # type: ignore[attr-defined]


class PDActionGoTo(PDAction):
    """GoTo action. Mirrors PDFBox ``PDActionGoTo``."""

    SUB_TYPE = "GoTo"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_destination(self) -> PDDestination | None:
        return PDDestination.create(self._action.get_dictionary_object(_D))

    def set_destination(self, destination: PDDestination | COSBase | None) -> None:
        if destination is None:
            self._action.remove_item(_D)
            return
        if isinstance(destination, PDDestination):
            self._action.set_item(_D, destination.get_cos_object())
        else:
            self._action.set_item(_D, destination)


__all__ = ["PDActionGoTo"]
