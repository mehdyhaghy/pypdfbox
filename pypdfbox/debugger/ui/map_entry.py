"""Key + value pair used by ``PDFTreeModel`` to expose ``COSDictionary`` items.

Ported from ``org.apache.pdfbox.debugger.ui.MapEntry``.
"""

from __future__ import annotations

from pypdfbox.cos import COSBase, COSName


class MapEntry:
    """A simple class that contains a key and a value."""

    def __init__(self) -> None:
        self._key: COSName | None = None
        self._value: COSBase | None = None
        self._item: COSBase | None = None

    # --- key ---------------------------------------------------------------

    def get_key(self) -> COSName | None:
        """Return the entry's key."""
        return self._key

    def set_key(self, k: COSName | None) -> None:
        """Set the key for this entry."""
        self._key = k

    # --- value -------------------------------------------------------------

    def get_value(self) -> COSBase | None:
        """Return the dereferenced value for this entry."""
        return self._value

    def set_value(self, val: COSBase | None) -> None:
        """Set the dereferenced value for this entry."""
        self._value = val

    # --- raw item ----------------------------------------------------------

    def get_item(self) -> COSBase | None:
        """Return the raw item for this entry (may be a ``COSObject``)."""
        return self._item

    def set_item(self, val: COSBase | None) -> None:
        """Set the raw item for this entry."""
        self._item = val

    def __str__(self) -> str:
        if self._key is not None:
            return self._key.get_name()
        return "(null)"
