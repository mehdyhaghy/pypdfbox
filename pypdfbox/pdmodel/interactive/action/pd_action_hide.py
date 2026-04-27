from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_action import PDAction

_H: COSName = COSName.get_pdf_name("H")
_T: COSName = COSName.T  # type: ignore[attr-defined]


class PDActionHide(PDAction):
    """Hide action. Mirrors PDFBox ``PDActionHide`` lite surface.

    PDF 32000-1 §12.6.4.10."""

    SUB_TYPE = "Hide"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # /T — annotation, field-name string, or array thereof. Raw COS for now.
    def get_target(self) -> COSBase | None:
        return self._action.get_dictionary_object(_T)

    def set_target(self, target: COSBase | None) -> None:
        if target is None:
            self._action.remove_item(_T)
            return
        self._action.set_item(_T, target)

    # Back-compat aliases mirroring the historical ``get_t``/``set_t`` surface.
    def get_t(self) -> COSBase | None:
        return self.get_target()

    def set_t(self, target: COSBase | None) -> None:
        self.set_target(target)

    # /H — hide flag, defaults to True per PDF 32000-1 Table 200.
    def get_h(self) -> bool:
        return self._action.get_boolean(_H, True)

    def set_h(self, hide: bool) -> None:
        self._action.set_boolean(_H, hide)


__all__ = ["PDActionHide"]
