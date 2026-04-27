from __future__ import annotations

from pypdfbox.cos import COSDictionary

from .pd_standard_attribute_object import PDStandardAttributeObject


class PDListAttributeObject(PDStandardAttributeObject):
    """
    A list attribute object (``/O /List``). Mirrors PDFBox
    ``PDListAttributeObject``.
    """

    # Upstream-parity owner constant.
    OWNER_LIST: str = "List"
    # Pypdfbox-style alias kept for prior callers.
    OWNER: str = "List"

    # Dictionary key (upstream protected static).
    LIST_NUMBERING: str = "ListNumbering"

    LIST_NUMBERING_NONE: str = "None"
    LIST_NUMBERING_DISC: str = "Disc"
    LIST_NUMBERING_CIRCLE: str = "Circle"
    LIST_NUMBERING_SQUARE: str = "Square"
    LIST_NUMBERING_DECIMAL: str = "Decimal"
    LIST_NUMBERING_UPPER_ROMAN: str = "UpperRoman"
    LIST_NUMBERING_LOWER_ROMAN: str = "LowerRoman"
    LIST_NUMBERING_UPPER_ALPHA: str = "UpperAlpha"
    LIST_NUMBERING_LOWER_ALPHA: str = "LowerAlpha"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        if dictionary is None:
            self.set_owner(self.OWNER)

    # ---------- /ListNumbering ----------

    def get_list_numbering(self) -> str:
        value = self._get_name("ListNumbering", self.LIST_NUMBERING_NONE)
        return value if value is not None else self.LIST_NUMBERING_NONE

    def set_list_numbering(self, list_numbering: str) -> None:
        self._set_name("ListNumbering", list_numbering)

    def __repr__(self) -> str:
        return (
            f"PDListAttributeObject(O={self.get_owner()}, "
            f"ListNumbering={self.get_list_numbering()})"
        )


__all__ = ["PDListAttributeObject"]
