from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)

from .pd_action import PDAction

_D: COSName = COSName.D  # type: ignore[attr-defined]
_F: COSName = COSName.get_pdf_name("F")


class PDActionRemoteGoTo(PDAction):
    """Remote GoTo action. Mirrors PDFBox ``PDActionRemoteGoTo`` lite surface."""

    SUB_TYPE = "GoToR"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_file(self) -> str | None:
        return self._action.get_string(_F)

    def set_file(self, file_name: str | None) -> None:
        self._action.set_string(_F, file_name)

    def get_d(self) -> COSBase | None:
        return self._action.get_dictionary_object(_D)

    def set_d(self, destination: COSBase | None) -> None:
        if destination is None:
            self._action.remove_item(_D)
            return
        self._action.set_item(_D, destination)

    def get_named_destination(self) -> str | None:
        """Return ``/D`` when it is a string-form named destination."""
        d = self._action.get_dictionary_object(_D)
        if isinstance(d, COSString):
            return d.get_string()
        return None

    def get_destination(self) -> PDDestination | str | None:
        """Return ``/D`` dispatched to its appropriate type:

        - ``PDDestination`` instance for explicit page-target arrays
          (``COSArray`` form);
        - ``str`` for named destinations (``COSString`` or ``COSName`` form);
        - ``None`` when ``/D`` is absent.
        """
        d = self._action.get_dictionary_object(_D)
        if d is None:
            return None
        if isinstance(d, COSArray):
            return PDDestination.create(d)
        if isinstance(d, COSString):
            return d.get_string()
        if isinstance(d, COSName):
            return d.get_name()
        return None

    def set_named_destination(self, name: str | None) -> None:
        if name is None:
            self._action.remove_item(_D)
            return
        self._action.set_string(_D, name)


__all__ = ["PDActionRemoteGoTo"]
