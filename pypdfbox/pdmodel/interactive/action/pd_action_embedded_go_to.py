from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)

from .pd_action import PDAction

_F: COSName = COSName.get_pdf_name("F")
_D: COSName = COSName.D  # type: ignore[attr-defined]
_NEW_WINDOW: COSName = COSName.get_pdf_name("NewWindow")
_T: COSName = COSName.get_pdf_name("T")


class PDActionEmbeddedGoTo(PDAction):
    """Embedded GoTo action. Mirrors PDFBox ``PDActionEmbeddedGoTo`` lite
    surface. The ``/T`` (target dictionary) entry is returned as raw
    ``COSBase``; a typed ``PDTargetDirectory`` wrapper is deferred."""

    SUB_TYPE = "GoToE"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_file(self) -> PDFileSpecification | None:
        return PDFileSpecification.create_fs(self._action.get_dictionary_object(_F))

    def set_file(self, fs: PDFileSpecification | None) -> None:
        if fs is None:
            self._action.remove_item(_F)
            return
        self._action.set_item(_F, fs.get_cos_object())

    def get_d(self) -> PDDestination | None:
        return PDDestination.create(self._action.get_dictionary_object(_D))

    def set_d(self, destination: PDDestination | None) -> None:
        if destination is None:
            self._action.remove_item(_D)
            return
        self._action.set_item(_D, destination.get_cos_object())

    def is_new_window(self) -> bool:
        return self._action.get_boolean(_NEW_WINDOW, False)

    def set_new_window(self, new_window: bool) -> None:
        self._action.set_boolean(_NEW_WINDOW, new_window)

    def get_target(self) -> COSBase | None:
        return self._action.get_dictionary_object(_T)

    def set_target(self, target: COSBase | None) -> None:
        if target is None:
            self._action.remove_item(_T)
            return
        self._action.set_item(_T, target)


__all__ = ["PDActionEmbeddedGoTo"]
