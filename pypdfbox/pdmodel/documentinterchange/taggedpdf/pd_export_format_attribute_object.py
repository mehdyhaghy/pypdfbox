from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSString

from .pd_layout_attribute_object import PDLayoutAttributeObject
from .pd_list_attribute_object import PDListAttributeObject
from .pd_table_attribute_object import PDTableAttributeObject


class PDExportFormatAttributeObject(PDLayoutAttributeObject):
    """
    An ExportFormat attribute object covering one of the format-specific
    owners defined in PDF 32000-1:2008 §14.8.5.2 (``XML-1.00``,
    ``HTML-3.2``, ``HTML-4.01``, ``OEB-1.00``, ``RTF-1.05``, ``CSS-1.00``,
    ``CSS-2.00``). Mirrors PDFBox ``PDExportFormatAttributeObject``.

    Upstream extends ``PDLayoutAttributeObject``, exposing the entire layout
    accessor surface in addition to the cross-cutting ``ListNumbering``,
    ``RowSpan``, ``ColSpan``, ``Headers``, ``Scope`` and ``Summary``
    accessors that this class adds. We mirror that hierarchy.
    """

    # Owner constants (upstream PDFBox public statics).
    OWNER_XML_1_00: str = "XML-1.00"
    OWNER_HTML_3_20: str = "HTML-3.2"
    OWNER_HTML_4_01: str = "HTML-4.01"
    OWNER_OEB_1_00: str = "OEB-1.00"
    OWNER_RTF_1_05: str = "RTF-1.05"
    OWNER_CSS_1_00: str = "CSS-1.00"
    OWNER_CSS_2_00: str = "CSS-2.00"

    # Pypdfbox-style default owner kept for prior callers.
    OWNER: str = "XML-1.00"

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
        value = self._get_name(
            PDListAttributeObject.LIST_NUMBERING, self.LIST_NUMBERING_NONE
        )
        return value if value is not None else self.LIST_NUMBERING_NONE

    def set_list_numbering(self, list_numbering: str) -> None:
        self._set_name(PDListAttributeObject.LIST_NUMBERING, list_numbering)

    # ---------- /RowSpan ----------

    def get_row_span(self) -> int:
        return self._get_integer(PDTableAttributeObject.ROW_SPAN, 1)

    def set_row_span(self, row_span: int) -> None:
        self._set_integer(PDTableAttributeObject.ROW_SPAN, row_span)

    # ---------- /ColSpan ----------

    def get_col_span(self) -> int:
        return self._get_integer(PDTableAttributeObject.COL_SPAN, 1)

    def set_col_span(self, col_span: int) -> None:
        self._set_integer(PDTableAttributeObject.COL_SPAN, col_span)

    # ---------- /Headers ----------

    def get_headers(self) -> list[str]:
        array = self._get_array(PDTableAttributeObject.HEADERS)
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
            self._dictionary.remove_item(PDTableAttributeObject.HEADERS)
            return
        array = COSArray()
        for value in headers:
            array.add(COSString(value.encode("utf-8")))
        self._dictionary.set_item(PDTableAttributeObject.HEADERS, array)

    # ---------- /Scope ----------

    def get_scope(self) -> str | None:
        return self._get_name(PDTableAttributeObject.SCOPE)

    def set_scope(self, scope: str | None) -> None:
        self._set_name(PDTableAttributeObject.SCOPE, scope)

    # ---------- /Summary ----------

    def get_summary(self) -> str | None:
        return self._get_string(PDTableAttributeObject.SUMMARY)

    def set_summary(self, summary: str | None) -> None:
        self._set_string(PDTableAttributeObject.SUMMARY, summary)

    # ---------- per-key presence / clear helpers ----------

    def is_list_numbering_specified(self) -> bool:
        """``True`` iff ``/ListNumbering`` is explicitly written."""
        return self.is_specified(PDListAttributeObject.LIST_NUMBERING)

    def has_list_numbering(self) -> bool:
        """Alias for :meth:`is_list_numbering_specified`."""
        return self.is_list_numbering_specified()

    def clear_list_numbering(self) -> None:
        """Remove the ``/ListNumbering`` entry if present."""
        self.clear_attribute(PDListAttributeObject.LIST_NUMBERING)

    def is_row_span_specified(self) -> bool:
        """``True`` iff ``/RowSpan`` is explicitly written."""
        return self.is_specified(PDTableAttributeObject.ROW_SPAN)

    def has_row_span(self) -> bool:
        """Alias for :meth:`is_row_span_specified`."""
        return self.is_row_span_specified()

    def clear_row_span(self) -> None:
        """Remove the ``/RowSpan`` entry if present."""
        self.clear_attribute(PDTableAttributeObject.ROW_SPAN)

    def is_col_span_specified(self) -> bool:
        """``True`` iff ``/ColSpan`` is explicitly written."""
        return self.is_specified(PDTableAttributeObject.COL_SPAN)

    def has_col_span(self) -> bool:
        """Alias for :meth:`is_col_span_specified`."""
        return self.is_col_span_specified()

    def clear_col_span(self) -> None:
        """Remove the ``/ColSpan`` entry if present."""
        self.clear_attribute(PDTableAttributeObject.COL_SPAN)

    def is_headers_specified(self) -> bool:
        """``True`` iff ``/Headers`` is explicitly written."""
        return self.is_specified(PDTableAttributeObject.HEADERS)

    def has_headers(self) -> bool:
        """Alias for :meth:`is_headers_specified`."""
        return self.is_headers_specified()

    def clear_headers(self) -> None:
        """Remove the ``/Headers`` entry if present."""
        self.clear_attribute(PDTableAttributeObject.HEADERS)

    def is_scope_specified(self) -> bool:
        """``True`` iff ``/Scope`` is explicitly written."""
        return self.is_specified(PDTableAttributeObject.SCOPE)

    def has_scope(self) -> bool:
        """Alias for :meth:`is_scope_specified`."""
        return self.is_scope_specified()

    def clear_scope(self) -> None:
        """Remove the ``/Scope`` entry if present."""
        self.clear_attribute(PDTableAttributeObject.SCOPE)

    def is_summary_specified(self) -> bool:
        """``True`` iff ``/Summary`` is explicitly written."""
        return self.is_specified(PDTableAttributeObject.SUMMARY)

    def has_summary(self) -> bool:
        """Alias for :meth:`is_summary_specified`."""
        return self.is_summary_specified()

    def clear_summary(self) -> None:
        """Remove the ``/Summary`` entry if present."""
        self.clear_attribute(PDTableAttributeObject.SUMMARY)

    # ---------- owner predicate (parity helper) ----------

    @classmethod
    def is_valid_owner(cls, owner: str | None) -> bool:
        """Return ``True`` when ``owner`` is one of the seven export-format
        owner names defined in PDF 32000-1:2008 §14.8.5.2 (``XML-1.00``,
        ``HTML-3.2``, ``HTML-4.01``, ``OEB-1.00``, ``RTF-1.05``, ``CSS-1.00``,
        ``CSS-2.00``).

        Predicate-only helper — upstream's ``setOwner(String)`` does not
        validate the name; this method is provided so callers (and the
        ``PDAttributeObject.create`` factory) can centralise the membership
        test rather than open-coding the constant set."""
        if owner is None:
            return False
        return owner in cls._VALID_OWNERS

    def __str__(self) -> str:
        """Mirror upstream ``PDExportFormatAttributeObject.toString()`` which
        extends the layout-level ``toString()`` by appending
        ``", ListNumbering=<v>"``, ``", RowSpan=<v>"``, ``", ColSpan=<v>"``,
        ``", Headers=<v>"``, ``", Scope=<v>"`` and ``", Summary=<v>"``
        for each entry that :meth:`is_specified` reports.

        Headers is rendered via :meth:`PDAttributeObject.array_to_string`
        to match upstream's ``arrayToString(this.getHeaders())`` formatting
        (``"[a, b, c]"``)."""
        sb = super().__str__()
        if self.is_specified(PDListAttributeObject.LIST_NUMBERING):
            sb = f"{sb}, ListNumbering={self.get_list_numbering()}"
        if self.is_specified(PDTableAttributeObject.ROW_SPAN):
            sb = f"{sb}, RowSpan={self.get_row_span()}"
        if self.is_specified(PDTableAttributeObject.COL_SPAN):
            sb = f"{sb}, ColSpan={self.get_col_span()}"
        if self.is_specified(PDTableAttributeObject.HEADERS):
            sb = f"{sb}, Headers={self.array_to_string(self.get_headers())}"
        if self.is_specified(PDTableAttributeObject.SCOPE):
            sb = f"{sb}, Scope={self.get_scope()}"
        if self.is_specified(PDTableAttributeObject.SUMMARY):
            sb = f"{sb}, Summary={self.get_summary()}"
        return sb

    def __repr__(self) -> str:
        return f"PDExportFormatAttributeObject(O={self.get_owner()})"


__all__ = ["PDExportFormatAttributeObject"]
