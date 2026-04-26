from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_action import PDAction

_F: COSName = COSName.get_pdf_name("F")


class PDActionImportData(PDAction):
    """ImportData action. Mirrors PDFBox ``PDActionImportData`` lite surface."""

    SUB_TYPE = "ImportData"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_file(self) -> COSBase | None:
        return self._action.get_dictionary_object(_F)

    def set_file(self, file_spec: COSBase | str | bytes | None) -> None:
        if file_spec is None:
            self._action.remove_item(_F)
        elif isinstance(file_spec, (str, bytes)):
            self._action.set_string(_F, file_spec)
        else:
            self._action.set_item(_F, file_spec)


__all__ = ["PDActionImportData"]
