from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_action import PDAction

_FIELDS: COSName = COSName.get_pdf_name("Fields")
_FLAGS: COSName = COSName.get_pdf_name("Flags")


class PDActionResetForm(PDAction):
    """ResetForm action. Mirrors PDFBox ``PDActionResetForm`` lite surface."""

    SUB_TYPE = "ResetForm"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_fields(self) -> COSArray | None:
        value = self._action.get_dictionary_object(_FIELDS)
        if isinstance(value, COSArray):
            return value
        return None

    def set_fields(self, fields: COSArray | None) -> None:
        if fields is None:
            self._action.remove_item(_FIELDS)
            return
        self._action.set_item(_FIELDS, fields)

    def get_flags(self) -> int:
        return self._action.get_int(_FLAGS, 0)

    def set_flags(self, flags: int) -> None:
        self._action.set_int(_FLAGS, flags)


__all__ = ["PDActionResetForm"]
