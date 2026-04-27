from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)

from .pd_action import PDAction

_F: COSName = COSName.get_pdf_name("F")


class PDActionImportData(PDAction):
    """ImportData action. Mirrors PDFBox ``PDActionImportData`` lite surface.

    PDF 32000-1 §12.7.5.4."""

    SUB_TYPE = "ImportData"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # /F — file specification of the FDF/XFDF/XML data to import.
    def get_file(self) -> PDFileSpecification | None:
        return PDFileSpecification.create_fs(self._action.get_dictionary_object(_F))

    def set_file(self, file_spec: PDFileSpecification | COSBase | str | bytes | None) -> None:
        if file_spec is None:
            self._action.remove_item(_F)
            return
        if isinstance(file_spec, PDFileSpecification):
            self._action.set_item(_F, file_spec.get_cos_object())
            return
        if isinstance(file_spec, (str, bytes)):
            self._action.set_string(_F, file_spec)
            return
        self._action.set_item(_F, file_spec)


__all__ = ["PDActionImportData"]
