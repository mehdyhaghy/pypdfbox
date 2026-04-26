from __future__ import annotations

from typing import TYPE_CHECKING

from .header_table import HeaderTable
from .horizontal_header_table import HorizontalHeaderTable
from .horizontal_metrics_table import HorizontalMetricsTable
from .maximum_profile_table import MaximumProfileTable
from .ttf_data_stream import MemoryTTFDataStream, TTFDataStream
from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .cmap_subtable import CmapSubtable


class TrueTypeFont:
    """Minimal TrueType / OpenType font wrapper.

    Mirrors ``org.apache.fontbox.ttf.TrueTypeFont`` but only loads the
    tables required for advance-width lookup in this cluster: ``head``,
    ``hhea``, ``maxp``, ``hmtx``, and (lazily) ``cmap``. A full port —
    glyph outlines, GSUB / GPOS, kerning, name-table accessors — is
    deferred to a later cluster. Construction does *not* eagerly read
    every table; the directory is parsed and tables are read on demand.
    """

    # SFNT directory entry: tag(4) + checksum(4) + offset(4) + length(4)
    _DIR_ENTRY_SIZE: int = 16
    _SFNT_HEADER_SIZE: int = 12  # version(4) + numTables(2) + 3 unused(6)

    def __init__(self, data: TTFDataStream) -> None:
        self._data: TTFDataStream = data
        self._tables: dict[str, TTFTable] = {}
        self._head: HeaderTable | None = None
        self._hhea: HorizontalHeaderTable | None = None
        self._maxp: MaximumProfileTable | None = None
        self._hmtx: HorizontalMetricsTable | None = None
        self._read_directory()

    # ---------- factories ----------

    @classmethod
    def from_bytes(cls, data: bytes | bytearray) -> TrueTypeFont:
        """Parse a TTF from an in-memory byte buffer."""
        return cls(MemoryTTFDataStream(data))

    # ---------- directory ----------

    def _read_directory(self) -> None:
        d = self._data
        d.seek(0)
        d.read_unsigned_int()  # sfnt version (0x00010000 / 'OTTO' / 'true')
        num_tables = d.read_unsigned_short()
        d.read_unsigned_short()  # searchRange
        d.read_unsigned_short()  # entrySelector
        d.read_unsigned_short()  # rangeShift

        for _ in range(num_tables):
            tag = d.read_tag()
            checksum = d.read_unsigned_int()
            offset = d.read_unsigned_int()
            length = d.read_unsigned_int()
            table = TTFTable()
            table.set_tag(tag)
            table.set_check_sum(checksum)
            table.set_offset(offset)
            table.set_length(length)
            self._tables[tag] = table

    # ---------- table access ----------

    def get_table_map(self) -> dict[str, TTFTable]:
        return self._tables

    def get_number_of_glyphs(self) -> int:
        maxp = self.get_maximum_profile()
        return maxp.get_num_glyphs() if maxp is not None else 0

    def get_units_per_em(self) -> int:
        head = self.get_header()
        return head.get_units_per_em() if head is not None else 0

    def get_header(self) -> HeaderTable | None:
        if self._head is None:
            self._head = self._read_table(HeaderTable.TAG, HeaderTable())
        return self._head

    def get_horizontal_header(self) -> HorizontalHeaderTable | None:
        if self._hhea is None:
            self._hhea = self._read_table(
                HorizontalHeaderTable.TAG, HorizontalHeaderTable()
            )
        return self._hhea

    def get_maximum_profile(self) -> MaximumProfileTable | None:
        if self._maxp is None:
            self._maxp = self._read_table(
                MaximumProfileTable.TAG, MaximumProfileTable()
            )
        return self._maxp

    def get_horizontal_metrics(self) -> HorizontalMetricsTable | None:
        if self._hmtx is None:
            # hmtx depends on hhea + maxp (numHMetrics, numGlyphs)
            self.get_horizontal_header()
            self.get_maximum_profile()
            self._hmtx = self._read_table(
                HorizontalMetricsTable.TAG, HorizontalMetricsTable()
            )
        return self._hmtx

    def get_advance_width(self, gid: int) -> int:
        """Advance width (in font units) for ``gid``. Falls back to 250
        when the font lacks an ``hmtx`` table — matches upstream's
        ``HorizontalMetricsTable.getAdvanceWidth`` default."""
        hmtx = self.get_horizontal_metrics()
        if hmtx is None:
            return 250
        return hmtx.get_advance_width(gid)

    # ---------- cmap (minimal) ----------

    def get_unicode_cmap_subtable(self) -> CmapSubtable | None:
        """Return the first usable Unicode-style cmap subtable.

        Walks the ``cmap`` table looking for the platform/encoding
        combinations PDFBox prefers for non-symbolic TrueType fonts:
        (3, 1) Windows Unicode BMP, (0, *) Unicode, (3, 0) Windows
        Symbol. Returns ``None`` if the font has no usable cmap.

        The returned subtable exposes ``get_glyph_id(code)``.
        """
        from .cmap_subtable import CmapSubtable  # noqa: PLC0415

        cmap_dir = self._tables.get("cmap")
        if cmap_dir is None:
            return None

        d = self._data
        d.seek(cmap_dir.get_offset())
        d.read_unsigned_short()  # version
        num_subtables = d.read_unsigned_short()

        subtables: list[CmapSubtable] = []
        for _ in range(num_subtables):
            sub = CmapSubtable()
            sub.init_data(d)
            subtables.append(sub)

        # Sort: prefer (3,1) > (0,*) > (3,0) > anything else.
        def _priority(sub: CmapSubtable) -> int:
            pid = sub.get_platform_id()
            eid = sub.get_platform_encoding_id()
            if pid == 3 and eid == 1:
                return 0
            if pid == 0:
                return 1
            if pid == 3 and eid == 0:
                return 2
            return 3

        num_glyphs = self.get_number_of_glyphs()
        for sub in sorted(subtables, key=_priority):
            try:
                sub.init_subtable(cmap_dir, num_glyphs, d)
                return sub
            except (NotImplementedError, OSError):
                continue
        return None

    # ---------- helpers ----------

    def _read_table(self, tag: str, instance: TTFTable) -> TTFTable | None:
        entry = self._tables.get(tag)
        if entry is None:
            return None
        instance.set_tag(entry.get_tag())
        instance.set_check_sum(entry.get_check_sum())
        instance.set_offset(entry.get_offset())
        instance.set_length(entry.get_length())
        self._data.seek(entry.get_offset())
        instance.read(self, self._data)
        # Replace the placeholder TTFTable with the typed instance.
        self._tables[tag] = instance
        return instance


__all__ = ["TrueTypeFont"]
