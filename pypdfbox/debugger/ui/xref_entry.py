"""Tree-view abstraction of a single cross-reference table entry.

Ported from ``org.apache.pdfbox.debugger.ui.XrefEntry``.
"""

from __future__ import annotations

from pypdfbox.cos import COSBase, COSObject, COSObjectKey


class XrefEntry:
    """Abstract view of one row of the cross reference table."""

    def __init__(
        self,
        index: int,
        key: COSObjectKey | None,
        offset: int,
        cos_object: COSObject | None,
    ) -> None:
        self._index = index
        self._key = key
        self._offset = offset
        self._cos_object = cos_object

    def get_key(self) -> COSObjectKey | None:
        """Return the indirect object key for this entry."""
        return self._key

    def get_index(self) -> int:
        """Return the 0-based index inside :class:`XrefEntries`."""
        return self._index

    def get_cos_object(self) -> COSObject | None:
        """Return the wrapping :class:`COSObject`, if any."""
        return self._cos_object

    def get_object(self) -> COSBase | None:
        """Return the dereferenced object, if any."""
        return self._cos_object.get_object() if self._cos_object is not None else None

    def get_path(self) -> str:
        """Return the tree-path for this entry."""
        # Imported lazily to avoid a circular import with ``XrefEntries``.
        from .xref_entries import XrefEntries

        return f"{XrefEntries.PATH}/{self}"

    def to_string(self) -> str:
        """Return the upstream ``toString`` rendering of this entry."""
        if self._key is None:
            return "(null)"
        if self._offset >= 0:
            return f"Offset: {self._offset} [{self._key}]"
        return f"Compressed object stream: {-self._offset} [{self._key}]"

    def __str__(self) -> str:
        return self.to_string()
