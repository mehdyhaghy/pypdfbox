from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary

from .pd_standard_attribute_object import PDStandardAttributeObject


class PDExportFormatAttributeObject(PDStandardAttributeObject):
    """
    An ExportFormat attribute object covering one of the format-specific
    owners defined in PDF 32000-1:2008 §14.8.5.2 (``XML-1.00``,
    ``HTML-3.2``, ``HTML-4.01``, ``OEB-1.00``, ``RTF-1.05``, ``CSS-1.00``,
    ``CSS-2.00``). Mirrors PDFBox ``PDExportFormatAttributeObject``.

    The accessors mirror the layout / list / table cross-cutting subset
    upstream exposes here.
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

    def __init__(
        self,
        dictionary: COSDictionary | None = None,
        owner: str | None = None,
    ) -> None:
        super().__init__(dictionary)
        if dictionary is None:
            self.set_owner(owner if owner is not None else self.OWNER)

    # ---------- /ListNumbering ----------

    def get_list_numbering(self) -> str | None:
        return self._get_name("ListNumbering", "None")

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
        return f"PDExportFormatAttributeObject(O={self.get_owner()})"


__all__ = ["PDExportFormatAttributeObject"]
