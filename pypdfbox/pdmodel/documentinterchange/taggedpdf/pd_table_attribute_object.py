from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSString

from .pd_standard_attribute_object import PDStandardAttributeObject


class PDTableAttributeObject(PDStandardAttributeObject):
    """
    A table attribute object (``/O /Table``). Mirrors PDFBox
    ``PDTableAttributeObject``.
    """

    # Upstream-parity owner constant.
    OWNER_TABLE: str = "Table"
    # Pypdfbox-style alias kept for prior callers.
    OWNER: str = "Table"

    # Dictionary keys (upstream protected static finals).
    ROW_SPAN: str = "RowSpan"
    COL_SPAN: str = "ColSpan"
    HEADERS: str = "Headers"
    SCOPE: str = "Scope"
    SUMMARY: str = "Summary"

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

    def add_header(self, value: str) -> None:
        """Append a single ``/Headers`` entry, creating the array if needed.

        pypdfbox convenience — upstream PDFBox only exposes the bulk
        ``setHeaders`` overload, but pypdfbox callers often build the
        ``/Headers`` list incrementally as TH structure elements are
        emitted. Encodes ``value`` as UTF-8 to match :meth:`set_headers`.
        """
        existing = self._get_array("Headers")
        if existing is None:
            existing = COSArray()
            self._dictionary.set_item("Headers", existing)
        existing.add(COSString(value.encode("utf-8")))

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

    # ---------- per-key presence predicates (pypdfbox ergonomics) ----------
    #
    # Upstream relies on ``is_specified(KEY)`` from the abstract base for both
    # ``toString`` and conditional logic. These named predicates mirror the
    # idiom used elsewhere in pypdfbox (``PDViewerPreferences.is_*``) so
    # callers don't have to remember the dictionary-key spelling.

    def is_row_span_specified(self) -> bool:
        """``True`` iff the ``/RowSpan`` entry is explicitly written."""
        return self.is_specified(self.ROW_SPAN)

    def is_col_span_specified(self) -> bool:
        """``True`` iff the ``/ColSpan`` entry is explicitly written."""
        return self.is_specified(self.COL_SPAN)

    def is_headers_specified(self) -> bool:
        """``True`` iff the ``/Headers`` entry is explicitly written."""
        return self.is_specified(self.HEADERS)

    def is_scope_specified(self) -> bool:
        """``True`` iff the ``/Scope`` entry is explicitly written."""
        return self.is_specified(self.SCOPE)

    def is_summary_specified(self) -> bool:
        """``True`` iff the ``/Summary`` entry is explicitly written."""
        return self.is_specified(self.SUMMARY)

    def __str__(self) -> str:
        """Mirror upstream ``PDTableAttributeObject.toString()`` which
        appends ``", <FieldName>=<value>"`` for each entry that is
        explicitly specified, in the dictionary-key order defined in the
        upstream class. ``/Headers`` is formatted via
        :meth:`PDAttributeObject.array_to_string` (the upstream Java
        ``arrayToString(String[])`` helper)."""
        sb = super().__str__()
        if self.is_specified(self.ROW_SPAN):
            sb = f"{sb}, RowSpan={self.get_row_span()}"
        if self.is_specified(self.COL_SPAN):
            sb = f"{sb}, ColSpan={self.get_col_span()}"
        if self.is_specified(self.HEADERS):
            sb = f"{sb}, Headers={self.array_to_string(self.get_headers())}"
        if self.is_specified(self.SCOPE):
            sb = f"{sb}, Scope={self.get_scope()}"
        if self.is_specified(self.SUMMARY):
            sb = f"{sb}, Summary={self.get_summary()}"
        return sb

    def __repr__(self) -> str:
        return (
            f"PDTableAttributeObject(O={self.get_owner()}, "
            f"RowSpan={self.get_row_span()}, ColSpan={self.get_col_span()})"
        )


__all__ = ["PDTableAttributeObject"]
