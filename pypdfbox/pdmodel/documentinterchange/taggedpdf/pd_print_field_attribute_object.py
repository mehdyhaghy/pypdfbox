from __future__ import annotations

from pypdfbox.cos import COSDictionary

from .pd_standard_attribute_object import PDStandardAttributeObject


class PDPrintFieldAttributeObject(PDStandardAttributeObject):
    """
    A PrintField attribute object (``/O /PrintField``). Mirrors PDFBox
    ``PDPrintFieldAttributeObject``.
    """

    OWNER: str = "PrintField"

    ROLE_RB: str = "rb"
    ROLE_CB: str = "cb"
    ROLE_PB: str = "pb"
    ROLE_TV: str = "tv"

    CHECKED_STATE_ON: str = "on"
    CHECKED_STATE_OFF: str = "off"
    CHECKED_STATE_NEUTRAL: str = "neutral"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        if dictionary is None:
            self.set_owner(self.OWNER)

    # ---------- /Role ----------

    def get_role(self) -> str | None:
        return self._get_name("Role")

    def set_role(self, role: str) -> None:
        self._set_name("Role", role)

    # ---------- /checked ----------

    def get_checked(self) -> str | None:
        return self._get_name("checked", self.CHECKED_STATE_OFF)

    def set_checked(self, checked: str) -> None:
        self._set_name("checked", checked)

    # ---------- /Desc ----------

    def get_desc(self) -> str | None:
        return self._get_string("Desc")

    def set_desc(self, desc: str) -> None:
        self._set_string("Desc", desc)

    def __repr__(self) -> str:
        return (
            f"PDPrintFieldAttributeObject(O={self.get_owner()}, "
            f"Role={self.get_role()}, checked={self.get_checked()})"
        )


__all__ = ["PDPrintFieldAttributeObject"]
