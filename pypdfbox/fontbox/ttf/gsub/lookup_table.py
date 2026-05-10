from __future__ import annotations

from dataclasses import dataclass, field

from .lookup_subtable import LookupSubTable


@dataclass
class LookupTable:
    """OpenType GSUB Lookup table.

    Mirrors ``org.apache.fontbox.ttf.gsub.LookupTable`` from upstream
    Apache PDFBox 3.0.x. A LookupTable groups one or more
    :class:`LookupSubTable` instances that all share the same lookup
    type and processing flags.

    * ``lookup_type`` is the GSUB lookup type (1 = single, 2 = multiple,
      3 = alternate, 4 = ligature, 5 = context, 6 = chaining-context,
      7 = extension, 8 = reverse-chaining).
    * ``lookup_flag`` carries the spec-defined flag bits (RightToLeft,
      IgnoreBaseGlyphs, IgnoreLigatures, IgnoreMarks, UseMarkFilteringSet,
      MarkAttachmentType in the high byte).
    * ``mark_filtering_set`` is meaningful only when the
      ``UseMarkFilteringSet`` bit (0x0010) is set in ``lookup_flag``;
      otherwise it is ``0`` and ignored. Stored unconditionally so
      round-trips don't lose data.
    * ``sub_tables`` is the ordered tuple of subtables to try. Order is
      significant — the first subtable that covers the input glyph wins.
    """

    lookup_type: int = 0
    lookup_flag: int = 0
    mark_filtering_set: int = 0
    sub_tables: tuple[LookupSubTable, ...] = field(default_factory=tuple)

    def get_lookup_type(self) -> int:
        return self.lookup_type

    def get_lookup_flag(self) -> int:
        return self.lookup_flag

    def get_mark_filtering_set(self) -> int:
        return self.mark_filtering_set

    def get_sub_tables(self) -> tuple[LookupSubTable, ...]:
        return self.sub_tables

    def to_string(self) -> str:
        """Mirror upstream ``LookupTable.toString()``.

        Upstream format:
        ``LookupTable[lookupType=<T>,lookupFlag=<F>,markFilteringSet=<M>]``.
        """
        return (
            "LookupTable["
            f"lookupType={self.lookup_type},"
            f"lookupFlag={self.lookup_flag},"
            f"markFilteringSet={self.mark_filtering_set}]"
        )

    def __str__(self) -> str:
        return self.to_string()


__all__ = ["LookupTable"]
