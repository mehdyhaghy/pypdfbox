"""Index + value pair used by ``PDFTreeModel`` to expose ``COSArray`` items.

Ported from ``org.apache.pdfbox.debugger.ui.ArrayEntry``.
"""

from __future__ import annotations

from pypdfbox.cos import COSBase


class ArrayEntry:
    """A simple class that contains an index and a value."""

    def __init__(self) -> None:
        self._index: int = 0
        self._value: COSBase | None = None
        self._item: COSBase | None = None

    # --- value -------------------------------------------------------------

    def get_value(self) -> COSBase | None:
        """Return the dereferenced value for this entry."""
        return self._value

    def set_value(self, val: COSBase | None) -> None:
        """Set the dereferenced value for this entry."""
        self._value = val

    # --- raw item (possibly a ``COSObject`` reference) ---------------------

    def get_item(self) -> COSBase | None:
        """Return the raw item for this entry (may be a ``COSObject``)."""
        return self._item

    def set_item(self, val: COSBase | None) -> None:
        """Set the raw item for this entry."""
        self._item = val

    # --- index -------------------------------------------------------------

    def get_index(self) -> int:
        """Return the 0-based index into the parent array."""
        return self._index

    def set_index(self, i: int) -> None:
        """Set the index value."""
        self._index = i
