from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSString

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

    def set_row_span(self, value: int) -> None:
        self._set_integer("RowSpan", value)

    # ---------- /ColSpan ----------

    def get_col_span(self) -> int:
        return self._get_integer("ColSpan", 1)

    def set_col_span(self, value: int) -> None:
        self._set_integer("ColSpan", value)

    # ---------- /Headers ----------

    def get_headers(self) -> list[str]:
        array = self._get_array("Headers")
        if array is None:
            return []
        out: list[str] = []
        for index in range(array.size()):
            item = array.get_object(index)
            if isinstance(item, COSString):
                raw = item.get_bytes()
                try:
                    out.append(raw.decode("utf-8"))
                except UnicodeDecodeError:
                    out.append(raw.decode("latin-1"))
        return out

    def set_headers(self, values: list[str]) -> None:
        if not values:
            self._dictionary.remove_item("Headers")
            return
        array = COSArray()
        for value in values:
            array.add(COSString(value.encode("utf-8")))
        self._dictionary.set_item("Headers", array)

    # ---------- /Scope ----------

    def get_scope(self) -> str | None:
        return self._get_name("Scope")

    def set_scope(self, value: str | None) -> None:
        self._set_name("Scope", value)

    # ---------- /Summary ----------

    def get_summary(self) -> str | None:
        return self._get_string("Summary")

    def set_summary(self, value: str | None) -> None:
        self._set_string("Summary", value)

    def __repr__(self) -> str:
        return (
            f"PDTableAttributeObject(O={self.get_owner()}, "
            f"RowSpan={self.get_row_span()}, ColSpan={self.get_col_span()})"
        )


__all__ = ["PDTableAttributeObject"]
