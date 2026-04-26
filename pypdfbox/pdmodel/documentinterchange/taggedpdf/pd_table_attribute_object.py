from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary

from .pd_standard_attribute_object import PDStandardAttributeObject


class PDTableAttributeObject(PDStandardAttributeObject):
    """
    A table attribute object (``/O /Table``). Mirrors PDFBox
    ``PDTableAttributeObject``.
    """

    OWNER: str = "Table"

    SCOPE_ROW: str = "Row"
    SCOPE_COLUMN: str = "Column"
    SCOPE_BOTH: str = "Both"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        if dictionary is None:
            self.set_owner(self.OWNER)

    # ---------- /RowSpan ----------

    def get_row_span(self) -> int:
        return self._get_integer("RowSpan", 1)

    def set_row_span(self, row_span: int) -> None:
        self._set_integer("RowSpan", row_span)

    # ---------- /ColSpan ----------

    def get_col_span(self) -> int:
        return self._get_integer("ColSpan", 1)

    def set_col_span(self, col_span: int) -> None:
        self._set_integer("ColSpan", col_span)

    # ---------- /Headers ----------

    def get_headers(self) -> COSArray | None:
        return self._get_array("Headers")

    def set_headers(self, headers: list[str]) -> None:
        self._set_array_of_string("Headers", headers)

    # ---------- /Scope ----------

    def get_scope(self) -> str | None:
        return self._get_name("Scope")

    def set_scope(self, scope: str) -> None:
        self._set_name("Scope", scope)

    # ---------- /Summary ----------

    def get_summary(self) -> str | None:
        return self._get_string("Summary")

    def set_summary(self, summary: str) -> None:
        self._set_string("Summary", summary)

    def __repr__(self) -> str:
        return (
            f"PDTableAttributeObject(O={self.get_owner()}, "
            f"RowSpan={self.get_row_span()}, ColSpan={self.get_col_span()})"
        )


__all__ = ["PDTableAttributeObject"]
