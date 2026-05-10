"""cmap Format 2 sub-header.

Mirrors the private ``SubHeader`` inner class of
``org.apache.fontbox.ttf.CmapSubtable`` (upstream ``CmapSubtable.java``
L702-754). The cmap format 2 layout describes character-to-glyph
mappings for mixed single- and double-byte encodings (typically Asian
encodings — Shift-JIS, Big5, ...): each first byte selects one
``SubHeader``, whose four fields drive the second-byte → glyph-id
calculation.

Promoted from a nested private class to a top-level module so that
external consumers (notably the cmap-format-2 decoder) can construct
sub-headers without reaching into private state. This matches the
pypdfbox naming convention of one top-level class per file.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubHeader:
    """Format-2 cmap sub-header.

    Mirrors ``CmapSubtable$SubHeader`` (CmapSubtable.java L702-754).

    * ``first_code`` (uint16) — the first valid second-byte value for the
      sub-array selected by this sub-header.
    * ``entry_count`` (uint16) — the count of valid second-byte values
      starting at ``first_code``.
    * ``id_delta`` (int16) — added (mod 65536) to the value retrieved
      from ``glyph_index_array`` to obtain the final glyph index.
    * ``id_range_offset`` (uint16, pre-adjusted) — number of bytes to
      skip from this sub-header's ``id_range_offset`` field to reach the
      first entry in ``glyph_index_array``. Upstream pre-adjusts the
      raw on-disk value, subtracting the per-sub-header header bytes —
      see ``CmapSubtable#processSubtype2`` (CmapSubtable.java L511).
    """

    first_code: int = 0
    entry_count: int = 0
    id_delta: int = 0
    id_range_offset: int = 0

    def get_first_code(self) -> int:
        """Mirror ``getFirstCode()`` (CmapSubtable.java L726-729)."""
        return self.first_code

    def get_entry_count(self) -> int:
        """Mirror ``getEntryCount()`` (CmapSubtable.java L734-737)."""
        return self.entry_count

    def get_id_delta(self) -> int:
        """Mirror ``getIdDelta()`` (CmapSubtable.java L742-745).

        ``id_delta`` is an int16 in upstream — values in the
        ``[-32768, 32767]`` range. Callers using this for glyph-id
        arithmetic should mod by 65536 (matching upstream's
        ``(p + idDelta) % 65536``).
        """
        return self.id_delta

    def get_id_range_offset(self) -> int:
        """Mirror ``getIdRangeOffset()`` (CmapSubtable.java L750-753)."""
        return self.id_range_offset


__all__ = ["SubHeader"]
