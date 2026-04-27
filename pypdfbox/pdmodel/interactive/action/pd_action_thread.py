from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)

from .pd_action import PDAction

_B: COSName = COSName.get_pdf_name("B")
_D: COSName = COSName.D  # type: ignore[attr-defined]
_F: COSName = COSName.get_pdf_name("F")


class PDActionThread(PDAction):
    """Thread action. Mirrors PDFBox ``PDActionThread`` lite surface.

    PDF 32000-1 §12.6.4.7."""

    SUB_TYPE = "Thread"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # /F — file containing the thread (optional; defaults to current document).
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

    # /D — thread to jump to: integer index, name string, or thread dict. Raw COS.
    def get_thread(self) -> COSBase | None:
        return self._action.get_dictionary_object(_D)

    def set_thread(self, thread: COSBase | None) -> None:
        if thread is None:
            self._action.remove_item(_D)
            return
        self._action.set_item(_D, thread)

    # Back-compat aliases mirroring the historical ``get_d``/``set_d`` surface.
    def get_d(self) -> COSBase | None:
        return self.get_thread()

    def set_d(self, thread: COSBase | None) -> None:
        self.set_thread(thread)

    # /B — bead within the thread: integer index, bead dict, etc. Raw COS.
    def get_bead(self) -> COSBase | None:
        return self._action.get_dictionary_object(_B)

    def set_bead(self, bead: COSBase | None) -> None:
        if bead is None:
            self._action.remove_item(_B)
            return
        self._action.set_item(_B, bead)

    # Back-compat aliases mirroring the historical ``get_b``/``set_b`` surface.
    def get_b(self) -> COSBase | None:
        return self.get_bead()

    def set_b(self, bead: COSBase | None) -> None:
        self.set_bead(bead)


__all__ = ["PDActionThread"]
