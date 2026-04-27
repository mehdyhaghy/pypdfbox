from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSString

from .pd_standard_attribute_object import PDStandardAttributeObject


class PDExportFormatAttributeObject(PDStandardAttributeObject):
    """
    An ExportFormat attribute object covering one of the format-specific
    owners defined in PDF 32000-1:2008 §14.8.5.2 (``XML-1.00``,
    ``HTML-3.2``, ``HTML-4.01``, ``OEB-1.00``, ``RTF-1.05``, ``CSS-1.00``,
    ``CSS-2.00``). Mirrors PDFBox ``PDExportFormatAttributeObject``.

    The accessors mirror the layout / list / table cross-cutting subset
    upstream exposes here. Constants for the cross-cutting attribute values
    (``ListNumbering``, ``Scope``) are re-exposed locally so callers can
    avoid importing the sibling owner classes solely for the constant.
    """

    OWNER: str = "XML-1.00"

    OWNER_XML_1_00: str = "XML-1.00"
    OWNER_HTML_3_20: str = "HTML-3.2"
    OWNER_HTML_4_01: str = "HTML-4.01"
    OWNER_OEB_1_00: str = "OEB-1.00"
    OWNER_RTF_1_05: str = "RTF-1.05"
    OWNER_CSS_1_00: str = "CSS-1.00"
    OWNER_CSS_2_00: str = "CSS-2.00"

    _VALID_OWNERS: frozenset[str] = frozenset(
        {
            OWNER_XML_1_00,
            OWNER_HTML_3_20,
            OWNER_HTML_4_01,
            OWNER_OEB_1_00,
            OWNER_RTF_1_05,
            OWNER_CSS_1_00,
            OWNER_CSS_2_00,
        }
    )

    # ---------- /ListNumbering values (mirrors PDListAttributeObject) ----------

    LIST_NUMBERING_NONE: str = "None"
    LIST_NUMBERING_DISC: str = "Disc"
    LIST_NUMBERING_CIRCLE: str = "Circle"
    LIST_NUMBERING_SQUARE: str = "Square"
    LIST_NUMBERING_DECIMAL: str = "Decimal"
    LIST_NUMBERING_UPPER_ROMAN: str = "UpperRoman"
    LIST_NUMBERING_LOWER_ROMAN: str = "LowerRoman"
    LIST_NUMBERING_UPPER_ALPHA: str = "UpperAlpha"
    LIST_NUMBERING_LOWER_ALPHA: str = "LowerAlpha"

    # ---------- /Scope values (mirrors PDTableAttributeObject) ----------

    SCOPE_ROW: str = "Row"
    SCOPE_COLUMN: str = "Column"
    SCOPE_BOTH: str = "Both"

    def __init__(
        self,
        dictionary: COSDictionary | None = None,
        owner: str | None = None,
    ) -> None:
        super().__init__(dictionary)
        if dictionary is None:
            self.set_owner(owner if owner is not None else self.OWNER)

    # ---------- /ListNumbering ----------

    def get_list_numbering(self) -> str:
        value = self._get_name("ListNumbering", self.LIST_NUMBERING_NONE)
        return value if value is not None else self.LIST_NUMBERING_NONE

    def set_list_numbering(self, list_numbering: str) -> None:
        self._set_name("ListNumbering", list_numbering)

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

    def set_headers(self, headers: list[str]) -> None:
        if not headers:
            self._dictionary.remove_item("Headers")
            return
        array = COSArray()
        for value in headers:
            array.add(COSString(value.encode("utf-8")))
        self._dictionary.set_item("Headers", array)

    # ---------- /Scope ----------

    def get_scope(self) -> str | None:
        return self._get_name("Scope")

    def set_scope(self, scope: str | None) -> None:
        self._set_name("Scope", scope)

    # ---------- /Summary ----------

    def get_summary(self) -> str | None:
        return self._get_string("Summary")

    def set_summary(self, summary: str | None) -> None:
        self._set_string("Summary", summary)

    def __repr__(self) -> str:
        return f"PDExportFormatAttributeObject(O={self.get_owner()})"


__all__ = ["PDExportFormatAttributeObject"]
