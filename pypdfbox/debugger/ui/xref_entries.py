"""Tree-view abstraction of the document cross-reference table.

Ported from ``org.apache.pdfbox.debugger.ui.XrefEntries``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDocument, COSObjectKey

from .xref_entry import XrefEntry

if TYPE_CHECKING:
    from pypdfbox.pdmodel import PDDocument


class XrefEntries:
    """Abstract view of the cross references of a pdf."""

    PATH = "CRT"

    def __init__(self, document: PDDocument) -> None:
        cos_document: COSDocument = document.get_document()
        xref_table = cos_document.get_xref_table()
        # Sorted by object number, matching the upstream stream pipeline.
        self._entries: list[tuple[COSObjectKey, int]] = sorted(
            xref_table.items(),
            key=lambda kv: kv[0].get_number(),
        )
        self._document = cos_document

    def get_xref_entry_count(self) -> int:
        """Return the number of xref entries."""
        return len(self._entries)

    def get_xref_entry(self, index: int) -> XrefEntry:
        """Materialise a :class:`XrefEntry` at ``index``."""
        key, offset = self._entries[index]
        object_from_pool = self._document.get_object_from_pool(key)
        return XrefEntry(index, key, offset, object_from_pool)

    def index_of(self, xref_entry: XrefEntry) -> int:
        """Return the position of ``xref_entry`` in this view."""
        key = xref_entry.get_key()
        for idx, (entry_key, _) in enumerate(self._entries):
            if entry_key == key:
                return idx
        return 0

    def to_string(self) -> str:
        """Return the upstream ``toString`` rendering — the constant ``CRT``."""
        return self.PATH

    def __str__(self) -> str:
        return self.to_string()
