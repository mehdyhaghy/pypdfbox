from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

from .header_table import HeaderTable
from .horizontal_header_table import HorizontalHeaderTable
from .horizontal_metrics_table import HorizontalMetricsTable
from .maximum_profile_table import MaximumProfileTable
from .ttf_data_stream import MemoryTTFDataStream, TTFDataStream
from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .cmap_subtable import CmapSubtable


class TrueTypeFont:
    """TrueType / OpenType font wrapper.

    Mirrors ``org.apache.fontbox.ttf.TrueTypeFont`` at the public-method
    level. Internally the SFNT structure is parsed by ``fontTools.ttLib``
    rather than re-implemented in pure Python — TTF/OTF/CFF parsing is
    exactly what the (MIT-licensed) ``fontTools`` library exists for, so
    we wrap it instead of maintaining a hand-rolled parser. The typed
    table helpers (``HeaderTable``, ``HorizontalHeaderTable``,
    ``HorizontalMetricsTable``, ``MaximumProfileTable``) remain in the
    package and are returned, populated from the fontTools-parsed values,
    so the legacy accessor surface keeps working.

    fontTools is imported lazily inside the constructor so callers that
    never touch a TTF stream don't pay its import cost.
    """

    def __init__(self, data: TTFDataStream) -> None:
        self._data: TTFDataStream = data
        # Materialise the SFNT bytes into a BytesIO for fontTools. The
        # legacy TTFDataStream surface only guarantees random-access
        # reads, so we round-trip through bytes rather than wrapping it.
        raw = self._read_all_bytes(data)
        # Lazy import — fontTools is heavy and most pypdfbox use does not
        # touch it.
        import fontTools.ttLib as ttLib  # noqa: PLC0415

        self._tt: Any = ttLib.TTFont(io.BytesIO(raw), lazy=True)
        # Populated lazily on first access; cached because each call into
        # fontTools re-resolves the underlying table object.
        self._head: HeaderTable | None = None
        self._hhea: HorizontalHeaderTable | None = None
        self._maxp: MaximumProfileTable | None = None
        self._hmtx: HorizontalMetricsTable | None = None
        self._cmap_subtable: CmapSubtable | None = None
        self._cmap_resolved: bool = False
        self._advance_widths: list[int] | None = None
        self._table_map: dict[str, TTFTable] | None = None

    # ---------- factories ----------

    @classmethod
    def from_bytes(cls, data: bytes | bytearray) -> TrueTypeFont:
        """Parse a TTF from an in-memory byte buffer."""
        return cls(MemoryTTFDataStream(data))

    # ---------- attribute-style accessors (PDFBox-equivalent fields) ----

    @property
    def unitsPerEm(self) -> int:  # noqa: N802 — mirror upstream Java field name
        return int(self._tt["head"].unitsPerEm)

    @property
    def numGlyphs(self) -> int:  # noqa: N802 — mirror upstream Java field name
        return int(self._tt["maxp"].numGlyphs)

    @property
    def advance_widths(self) -> list[int]:
        """Per-glyph advance widths in font units, indexed by glyph ID."""
        if self._advance_widths is None:
            metrics = self._tt["hmtx"].metrics
            self._advance_widths = [
                int(metrics[name][0]) for name in self._tt.getGlyphOrder()
            ]
        return self._advance_widths

    # ---------- method-style accessors (camelCase -> snake_case) --------

    def get_units_per_em(self) -> int:
        return self.unitsPerEm

    def get_number_of_glyphs(self) -> int:
        return self.numGlyphs

    def get_advance_width(self, gid: int) -> int:
        """Advance width (in font units) for ``gid``. Falls back to 250
        when the font lacks an ``hmtx`` table — matches upstream's
        ``HorizontalMetricsTable.getAdvanceWidth`` default."""
        if "hmtx" not in self._tt:
            return 250
        widths = self.advance_widths
        if not widths:
            return 250
        if 0 <= gid < len(widths):
            return widths[gid]
        # Monospaced fonts may omit trailing entries — fall back to last.
        return widths[-1]

    # ---------- typed-table accessors (legacy surface) ------------------

    def get_table_map(self) -> dict[str, TTFTable]:
        """Return a {tag: TTFTable} map reflecting the SFNT directory.

        Each entry is a bare :class:`TTFTable` carrying tag / offset /
        length / checksum metadata. The actual table payload is exposed
        through the typed accessors (``get_header``, ``get_horizontal_header``,
        etc.) — this map is preserved only for callers that need to walk
        the directory.
        """
        if self._table_map is None:
            reader = self._tt.reader  # SFNTReader
            tables: dict[str, TTFTable] = {}
            for tag, entry in reader.tables.items():
                t = TTFTable()
                t.set_tag(tag)
                t.set_check_sum(int(entry.checkSum))
                t.set_offset(int(entry.offset))
                t.set_length(int(entry.length))
                tables[tag] = t
            self._table_map = tables
        return self._table_map

    def get_header(self) -> HeaderTable | None:
        if self._head is not None:
            return self._head
        if "head" not in self._tt:
            return None
        ft = self._tt["head"]
        h = HeaderTable()
        h._version = float(ft.tableVersion)  # noqa: SLF001
        h._font_revision = float(ft.fontRevision)  # noqa: SLF001
        h._check_sum_adjustment = int(ft.checkSumAdjustment)  # noqa: SLF001
        h._magic_number = int(ft.magicNumber)  # noqa: SLF001
        h._flags = int(ft.flags)  # noqa: SLF001
        h._units_per_em = int(ft.unitsPerEm)  # noqa: SLF001
        h._x_min = int(ft.xMin)  # noqa: SLF001
        h._y_min = int(ft.yMin)  # noqa: SLF001
        h._x_max = int(ft.xMax)  # noqa: SLF001
        h._y_max = int(ft.yMax)  # noqa: SLF001
        h._mac_style = int(ft.macStyle)  # noqa: SLF001
        h._lowest_rec_ppem = int(ft.lowestRecPPEM)  # noqa: SLF001
        h._font_direction_hint = int(ft.fontDirectionHint)  # noqa: SLF001
        h._index_to_loc_format = int(ft.indexToLocFormat)  # noqa: SLF001
        h._glyph_data_format = int(ft.glyphDataFormat)  # noqa: SLF001
        h.initialized = True
        self._head = h
        return h

    def get_horizontal_header(self) -> HorizontalHeaderTable | None:
        if self._hhea is not None:
            return self._hhea
        if "hhea" not in self._tt:
            return None
        ft = self._tt["hhea"]
        t = HorizontalHeaderTable()
        # fontTools stores hhea.tableVersion as a raw uint32 ("L"), so
        # convert back to the 16.16 fixed-point float upstream exposes.
        t._version = self._fixed_16_16(int(ft.tableVersion))  # noqa: SLF001
        t._ascender = int(ft.ascent)  # noqa: SLF001
        t._descender = int(ft.descent)  # noqa: SLF001
        t._line_gap = int(ft.lineGap)  # noqa: SLF001
        t._advance_width_max = int(ft.advanceWidthMax)  # noqa: SLF001
        t._min_left_side_bearing = int(ft.minLeftSideBearing)  # noqa: SLF001
        t._min_right_side_bearing = int(ft.minRightSideBearing)  # noqa: SLF001
        t._x_max_extent = int(ft.xMaxExtent)  # noqa: SLF001
        t._caret_slope_rise = int(ft.caretSlopeRise)  # noqa: SLF001
        t._caret_slope_run = int(ft.caretSlopeRun)  # noqa: SLF001
        t._metric_data_format = int(ft.metricDataFormat)  # noqa: SLF001
        t._number_of_h_metrics = int(ft.numberOfHMetrics)  # noqa: SLF001
        t.initialized = True
        self._hhea = t
        return t

    def get_maximum_profile(self) -> MaximumProfileTable | None:
        if self._maxp is not None:
            return self._maxp
        if "maxp" not in self._tt:
            return None
        ft = self._tt["maxp"]
        t = MaximumProfileTable()
        # maxp.tableVersion is a signed int32 in fontTools — re-encode to
        # the 16.16 fixed-point float upstream exposes (0x00005000 -> 0.3125,
        # 0x00010000 -> 1.0).
        t._version = self._fixed_16_16(int(ft.tableVersion) & 0xFFFFFFFF)  # noqa: SLF001
        t._num_glyphs = int(ft.numGlyphs)  # noqa: SLF001
        if t._version >= 1.0:  # noqa: SLF001
            t._max_points = int(getattr(ft, "maxPoints", 0))  # noqa: SLF001
            t._max_contours = int(getattr(ft, "maxContours", 0))  # noqa: SLF001
            t._max_composite_points = int(getattr(ft, "maxCompositePoints", 0))  # noqa: SLF001
            t._max_composite_contours = int(getattr(ft, "maxCompositeContours", 0))  # noqa: SLF001
            t._max_zones = int(getattr(ft, "maxZones", 0))  # noqa: SLF001
            t._max_twilight_points = int(getattr(ft, "maxTwilightPoints", 0))  # noqa: SLF001
            t._max_storage = int(getattr(ft, "maxStorage", 0))  # noqa: SLF001
            t._max_function_defs = int(getattr(ft, "maxFunctionDefs", 0))  # noqa: SLF001
            t._max_instruction_defs = int(getattr(ft, "maxInstructionDefs", 0))  # noqa: SLF001
            t._max_stack_elements = int(getattr(ft, "maxStackElements", 0))  # noqa: SLF001
            t._max_size_of_instructions = int(getattr(ft, "maxSizeOfInstructions", 0))  # noqa: SLF001
            t._max_component_elements = int(getattr(ft, "maxComponentElements", 0))  # noqa: SLF001
            depth = int(getattr(ft, "maxComponentDepth", 0))
            # PDFBOX-6105 — clamp 0 to 1.
            t._max_component_depth = depth if depth != 0 else 1  # noqa: SLF001
        t.initialized = True
        self._maxp = t
        return t

    def get_horizontal_metrics(self) -> HorizontalMetricsTable | None:
        if self._hmtx is not None:
            return self._hmtx
        if "hmtx" not in self._tt:
            return None
        hhea = self.get_horizontal_header()
        if hhea is None:
            return None
        num_h_metrics = hhea.get_number_of_h_metrics()
        # fontTools resolves hmtx into a {glyph_name: (advance, lsb)} dict
        # keyed by glyph name. Project back to GID order to populate the
        # legacy structure faithfully.
        ft_metrics = self._tt["hmtx"].metrics
        glyph_order = self._tt.getGlyphOrder()
        advances = [int(ft_metrics[n][0]) for n in glyph_order]
        lsbs = [int(ft_metrics[n][1]) for n in glyph_order]

        t = HorizontalMetricsTable()
        t._num_h_metrics = num_h_metrics  # noqa: SLF001
        # First num_h_metrics entries carry both advance and LSB; the
        # remaining glyphs share the last advance and have a trailing
        # LSB-only block in the on-disk table.
        t._advance_width = advances[:num_h_metrics]  # noqa: SLF001
        t._left_side_bearing = lsbs[:num_h_metrics]  # noqa: SLF001
        t._non_horizontal_left_side_bearing = lsbs[num_h_metrics:]  # noqa: SLF001
        t.initialized = True
        self._hmtx = t
        return t

    # ---------- name-table accessors -----------------------------------

    def _get_name_string(self, name_id: int) -> str | None:
        """Look up a name-table record by ``nameID``.

        Defers to fontTools' ``name.getDebugName``, which walks the
        PDFBox-equivalent priority order (Windows Unicode first, then
        Macintosh Roman) and returns ``None`` when no record matches.
        """
        if "name" not in self._tt:
            return None
        value = self._tt["name"].getDebugName(name_id)
        if value is None:
            return None
        return str(value)

    def get_name(self) -> str | None:
        """PostScript name of the font (name table, nameID 6)."""
        return self._get_name_string(6)

    def get_family_name(self) -> str | None:
        """Font family name (name table, nameID 1)."""
        return self._get_name_string(1)

    def get_full_name(self) -> str | None:
        """Full font name (name table, nameID 4)."""
        return self._get_name_string(4)

    def get_version(self) -> str | None:
        """Version string (name table, nameID 5)."""
        return self._get_name_string(5)

    # ---------- head / post / OS/2 scalar accessors --------------------

    def get_font_bbox(self) -> tuple[int, int, int, int]:
        """Font bounding box (xMin, yMin, xMax, yMax) from the ``head`` table.

        Returns ``(0, 0, 0, 0)`` when the font has no ``head`` table —
        matches upstream's defensive zero-rect fallback.
        """
        if "head" not in self._tt:
            return (0, 0, 0, 0)
        h = self._tt["head"]
        return (int(h.xMin), int(h.yMin), int(h.xMax), int(h.yMax))

    def get_italic_angle(self) -> float:
        """Italic angle in degrees from the ``post`` table (0.0 if absent)."""
        if "post" not in self._tt:
            return 0.0
        return float(self._tt["post"].italicAngle)

    def get_underline_position(self) -> int:
        """Underline position from the ``post`` table (0 if absent)."""
        if "post" not in self._tt:
            return 0
        return int(self._tt["post"].underlinePosition)

    def get_underline_thickness(self) -> int:
        """Underline thickness from the ``post`` table (0 if absent)."""
        if "post" not in self._tt:
            return 0
        return int(self._tt["post"].underlineThickness)

    def is_fixed_pitch(self) -> bool:
        """Whether the font is monospaced (``post.isFixedPitch != 0``)."""
        if "post" not in self._tt:
            return False
        return int(self._tt["post"].isFixedPitch) != 0

    def get_weight(self) -> int:
        """``OS/2.usWeightClass`` (typically 100..900). Defaults to 400
        (Regular) when the font omits the ``OS/2`` table."""
        if "OS/2" not in self._tt:
            return 400
        return int(self._tt["OS/2"].usWeightClass)

    def get_width(self) -> int:
        """``OS/2.usWidthClass`` (1..9). Defaults to 5 (Medium) when the
        font omits the ``OS/2`` table."""
        if "OS/2" not in self._tt:
            return 5
        return int(self._tt["OS/2"].usWidthClass)

    # ---------- table-presence accessors -------------------------------

    def get_capabilities(self) -> dict[str, bool]:
        """Return a ``{tag: True}`` map of every SFNT table present.

        Convenience wrapper over :meth:`get_table_map` for callers that
        only care about which optional tables exist.
        """
        return {tag: True for tag in self.get_table_map()}

    def has_table(self, tag: str) -> bool:
        """``True`` iff the SFNT directory contains a table with ``tag``."""
        return tag in self.get_table_map()

    # ---------- cmap (Unicode subtable) ---------------------------------

    def get_unicode_cmap_subtable(self) -> CmapSubtable | None:
        """Return a Unicode-style cmap subtable view.

        Wraps the dict that ``fontTools`` resolves via
        ``cmap.getBestCmap()`` (which prefers Windows Unicode Full /
        Windows Unicode BMP / Unicode platform tables in the same order
        PDFBox does) inside a thin :class:`CmapSubtable` view so callers
        can continue to use ``get_glyph_id(code)`` / ``get_char_codes(gid)``
        unchanged. Returns ``None`` if the font has no cmap.
        """
        if self._cmap_resolved:
            return self._cmap_subtable
        self._cmap_resolved = True
        if "cmap" not in self._tt:
            self._cmap_subtable = None
            return None
        cmap_table = self._tt["cmap"]
        best = cmap_table.getBestCmap()  # dict[int, str] of unicode -> glyph name
        if not best:
            self._cmap_subtable = None
            return None
        # Find the picked subtable so platform_id / platform_encoding_id
        # stay reportable. fontTools picks a preferred order internally;
        # we mirror it by re-walking the same priority list.
        preferred = (
            (3, 10), (0, 6), (0, 4), (3, 1), (0, 3), (0, 2), (0, 1), (0, 0),
        )
        chosen = None
        for plat, enc in preferred:
            for sub in cmap_table.tables:
                if sub.platformID == plat and sub.platEncID == enc:
                    chosen = sub
                    break
            if chosen is not None:
                break
        if chosen is None:
            chosen = cmap_table.tables[0] if cmap_table.tables else None

        glyph_name_to_gid = {n: i for i, n in enumerate(self._tt.getGlyphOrder())}
        char_to_gid: dict[int, int] = {}
        for code, name in best.items():
            gid = glyph_name_to_gid.get(name)
            if gid is not None:
                char_to_gid[code] = gid

        from .cmap_subtable import CmapSubtable  # noqa: PLC0415

        view = CmapSubtable()
        if chosen is not None:
            view.set_platform_id(int(chosen.platformID))
            view.set_platform_encoding_id(int(chosen.platEncID))
        # Reuse the existing subtable's storage: ``_character_code_to_glyph_id``
        # is what ``get_glyph_id`` reads; ``_glyph_id_to_character_code`` /
        # ``_multiple`` power ``get_char_codes``.
        view._character_code_to_glyph_id = char_to_gid  # noqa: SLF001
        max_gid = max(char_to_gid.values(), default=-1)
        if max_gid >= 0:
            view._build_glyph_id_to_character_code_lookup(max_gid)  # noqa: SLF001
        self._cmap_subtable = view
        return view

    # ---------- helpers -------------------------------------------------

    @staticmethod
    def _fixed_16_16(raw: int) -> float:
        """Decode a 16.16 fixed-point unsigned 32-bit value into a float."""
        whole = (raw >> 16) & 0xFFFF
        frac = raw & 0xFFFF
        return whole + frac / 65536.0

    @staticmethod
    def _read_all_bytes(data: TTFDataStream) -> bytes:
        """Drain the supplied TTFDataStream into a ``bytes`` buffer for
        fontTools to consume. Both shipped concrete subclasses already
        hold the full font in memory, so this is a cheap reference copy.
        """
        return data.get_original_data()


__all__ = ["TrueTypeFont"]
