"""OpenType LookupList table.

Mirrors ``org.apache.fontbox.ttf.table.common.LookupListTable``
(upstream ``LookupListTable.java`` L28-55). ``LookupTable`` lives at
``pypdfbox.fontbox.ttf.gsub.lookup_table``.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...gsub.lookup_table import LookupTable


class LookupListTable:
    """List of OpenType lookup tables.

    Mirrors ``LookupListTable.java`` L28-54. A bare value holder over
    ``(int lookupCount, LookupTable[] lookups)``.
    """

    def __init__(
        self,
        lookup_count: int,
        lookups: Sequence[LookupTable],
    ) -> None:
        self._lookup_count = int(lookup_count)
        self._lookups: tuple[LookupTable, ...] = tuple(lookups)

    def get_lookup_count(self) -> int:
        """Mirror ``getLookupCount()`` (LookupListTable.java L39-42)."""
        return self._lookup_count

    def get_lookups(self) -> tuple[LookupTable, ...]:
        """Mirror ``getLookups()`` (LookupListTable.java L44-47).

        Returns a tuple for immutability; ``list(...)`` it if mutation
        is needed.
        """
        return self._lookups

    def to_string(self) -> str:
        """Mirror ``toString()`` (LookupListTable.java L49-53).

        Format: ``LookupListTable[lookupCount=<n>]``.
        """
        return f"LookupListTable[lookupCount={self._lookup_count}]"

    def __str__(self) -> str:
        return self.to_string()


__all__ = ["LookupListTable"]
