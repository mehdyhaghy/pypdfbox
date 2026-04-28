from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

from .digital_signature_table import DigitalSignatureTable
from .glyph_substitution_table import GlyphSubstitutionTable
from .header_table import HeaderTable
from .horizontal_header_table import HorizontalHeaderTable
from .horizontal_metrics_table import HorizontalMetricsTable
from .index_to_location_table import IndexToLocationTable
from .maximum_profile_table import MaximumProfileTable
from .name_record import NameRecord
from .naming_table import NamingTable
from .os2_windows_metrics_table import OS2WindowsMetricsTable
from .post_script_table import PostScriptTable
from .ttf_data_stream import MemoryTTFDataStream, TTFDataStream
from .ttf_table import TTFTable
from .vertical_header_table import VerticalHeaderTable
from .vertical_metrics_table import VerticalMetricsTable

if TYPE_CHECKING:
    from .cmap_subtable import CmapSubtable
    from .glyph_data import GlyphData
    from .glyph_table import GlyphTable
    from .kerning_table import KerningTable


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
        self._vhea: VerticalHeaderTable | None = None
        self._vmtx: VerticalMetricsTable | None = None
        self._cmap_subtable: CmapSubtable | None = None
        self._cmap_resolved: bool = False
        self._advance_widths: list[int] | None = None
        self._table_map: dict[str, TTFTable] | None = None
        self._glyph_table: GlyphTable | None = None
        self._dsig: DigitalSignatureTable | None = None
        self._dsig_resolved: bool = False
        self._kern: KerningTable | None = None
        self._kern_resolved: bool = False
        self._gsub: GlyphSubstitutionTable | None = None
        self._gsub_resolved: bool = False
        self._naming: NamingTable | None = None
        self._naming_resolved: bool = False
        self._post: PostScriptTable | None = None
        self._post_resolved: bool = False
        self._os2: OS2WindowsMetricsTable | None = None
        self._os2_resolved: bool = False
        self._loca: IndexToLocationTable | None = None
        self._loca_resolved: bool = False
        # Raw bytes kept for embedding round-trips (``get_original_data``).
        self._raw_bytes: bytes = bytes(raw)
        self._closed: bool = False

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

    def get_table(self, tag: str) -> TTFTable | None:
        """Return the SFNT-directory entry for ``tag``, or ``None`` if absent.

        Mirrors upstream's ``getTable(String)`` which yields the raw
        :class:`TTFTable` directory record (tag / offset / length /
        checksum) — *not* the typed table payload. Use the typed
        ``get_header`` / ``get_naming`` / ... helpers for parsed values.
        """
        return self.get_table_map().get(tag)

    def get_table_bytes(self, tag: str) -> bytes | None:
        """Return the raw on-disk bytes of table ``tag``, or ``None`` if absent.

        Mirrors upstream's ``getTableBytes(TTFTable)``. Pulls the bytes
        out of the in-memory SFNT buffer using the directory entry's
        offset/length so callers don't have to re-read the file.
        """
        entry = self.get_table_map().get(tag)
        if entry is None:
            return None
        offset = entry.get_offset()
        length = entry.get_length()
        if offset < 0 or length < 0 or offset + length > len(self._raw_bytes):
            return None
        return self._raw_bytes[offset : offset + length]

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

    # ---------- vertical metrics (vhea / vmtx) -------------------------

    def get_vertical_header(self) -> VerticalHeaderTable | None:
        """Return the populated ``vhea`` table, or ``None`` when the font
        lacks a vertical header (typical of Latin-only fonts).
        """
        if self._vhea is not None:
            return self._vhea
        if "vhea" not in self._tt:
            return None
        ft = self._tt["vhea"]
        t = VerticalHeaderTable()
        # vhea.tableVersion is a raw uint32 ("L") in fontTools — convert
        # back to the 16.16 fixed-point float upstream exposes.
        t._version = self._fixed_16_16(int(ft.tableVersion) & 0xFFFFFFFF)  # noqa: SLF001
        t._ascender = int(ft.ascent)  # noqa: SLF001
        t._descender = int(ft.descent)  # noqa: SLF001
        t._line_gap = int(ft.lineGap)  # noqa: SLF001
        t._advance_height_max = int(ft.advanceHeightMax)  # noqa: SLF001
        t._min_top_side_bearing = int(ft.minTopSideBearing)  # noqa: SLF001
        t._min_bottom_side_bearing = int(ft.minBottomSideBearing)  # noqa: SLF001
        t._y_max_extent = int(ft.yMaxExtent)  # noqa: SLF001
        t._caret_slope_rise = int(ft.caretSlopeRise)  # noqa: SLF001
        t._caret_slope_run = int(ft.caretSlopeRun)  # noqa: SLF001
        t._caret_offset = int(ft.caretOffset)  # noqa: SLF001
        t._metric_data_format = int(ft.metricDataFormat)  # noqa: SLF001
        t._number_of_v_metrics = int(ft.numberOfVMetrics)  # noqa: SLF001
        t.initialized = True
        self._vhea = t
        return t

    def get_vertical_metrics(self) -> VerticalMetricsTable | None:
        """Return the populated ``vmtx`` table, or ``None`` when the font
        lacks a ``vmtx`` (or matching ``vhea``) table.
        """
        if self._vmtx is not None:
            return self._vmtx
        if "vmtx" not in self._tt:
            return None
        vhea = self.get_vertical_header()
        if vhea is None:
            return None
        num_v_metrics = vhea.get_number_of_v_metrics()
        # fontTools resolves vmtx into a {glyph_name: (advance, tsb)} dict
        # keyed by glyph name. Project back to GID order to populate the
        # legacy structure faithfully.
        ft_metrics = self._tt["vmtx"].metrics
        glyph_order = self._tt.getGlyphOrder()
        advances = [int(ft_metrics[n][0]) for n in glyph_order]
        tsbs = [int(ft_metrics[n][1]) for n in glyph_order]

        t = VerticalMetricsTable()
        t._num_v_metrics = num_v_metrics  # noqa: SLF001
        # First num_v_metrics entries carry both advance and TSB; the
        # remaining glyphs share the last advance and have a trailing
        # TSB-only block in the on-disk table.
        t._advance_height = advances[:num_v_metrics]  # noqa: SLF001
        t._top_side_bearing = tsbs[:num_v_metrics]  # noqa: SLF001
        t._additional_top_side_bearing = tsbs[num_v_metrics:]  # noqa: SLF001
        t.initialized = True
        self._vmtx = t
        return t

    # ---------- glyf accessors -----------------------------------------

    def get_glyph_table(self) -> GlyphTable | None:
        """Return the ``glyf`` table view, or ``None`` if absent.

        TrueType-flavoured fonts ship a ``glyf`` table; CFF / OpenType-CFF
        fonts do not (their outlines live in ``CFF ``). The returned
        :class:`GlyphTable` is bound to the same fontTools-parsed font
        instance, so glyph lookups stay zero-copy.
        """
        if self._glyph_table is not None:
            return self._glyph_table
        if "glyf" not in self._tt:
            return None
        from .glyph_table import GlyphTable  # noqa: PLC0415

        gt = GlyphTable()
        gt._bind(self)  # noqa: SLF001
        self._glyph_table = gt
        return gt

    def get_glyph(self, gid: int) -> GlyphData | None:
        """Convenience accessor — :meth:`GlyphTable.get_glyph` for ``gid``.

        Returns ``None`` if the font has no ``glyf`` table or ``gid`` is
        out of range. This mirrors the path most upstream callers take
        (``ttf.getGlyph().getGlyph(gid)``) collapsed into one call, which
        is by far the most common shape in PDFBox glyph rendering code.
        """
        gt = self.get_glyph_table()
        if gt is None:
            return None
        return gt.get_glyph(gid)

    # ---------- DSIG (digital signature) accessor ----------------------

    def get_dsig(self) -> DigitalSignatureTable | None:
        """Return the ``DSIG`` table view, or ``None`` if absent.

        The DSIG table is optional and rare in real-world fonts; most
        production fonts ship without one. When present, it is parsed by
        ``fontTools.ttLib.tables.D_S_I_G_`` and projected onto a
        :class:`DigitalSignatureTable` snapshot so the legacy upstream
        accessor surface stays available.

        Result is cached, including the negative case — repeat callers
        on a font without DSIG won't re-probe the directory.
        """
        if self._dsig_resolved:
            return self._dsig
        self._dsig_resolved = True
        if "DSIG" not in self._tt:
            self._dsig = None
            return None
        ft_dsig = self._tt["DSIG"]
        t = DigitalSignatureTable()
        t.populate_from_fonttools(ft_dsig)
        self._dsig = t
        return t

    # ---------- kern (kerning) accessor --------------------------------

    def get_kerning_table(self) -> KerningTable | None:
        """Return the ``kern`` table view, or ``None`` if absent.

        Most modern fonts carry kerning information in the GPOS table
        instead, so the legacy ``kern`` table is optional. When present,
        fontTools decodes it into ``self._tt["kern"].kernTables`` and we
        wrap that in a :class:`KerningTable` snapshot so the upstream
        ``getSubtables`` / ``getHorizontalKerningSubtable`` API stays
        intact. Result is cached, including the negative case.
        """
        if self._kern_resolved:
            return self._kern
        self._kern_resolved = True
        if "kern" not in self._tt:
            self._kern = None
            return None
        from .kerning_table import KerningTable  # noqa: PLC0415

        ft_kern = self._tt["kern"]
        self._kern = KerningTable.from_fonttools(ft_kern, self)
        return self._kern

    # ---------- GSUB (glyph substitution) accessor ---------------------

    def get_gsub(self) -> GlyphSubstitutionTable | None:
        """Return the ``GSUB`` table view, or ``None`` if absent.

        GSUB carries OpenType glyph substitution rules (ligatures,
        small-caps, super/subscript variants, script-shaping, ...).
        Parsing is delegated to ``fontTools.ttLib`` — see
        :class:`GlyphSubstitutionTable` for the rationale and the
        documented deviation from upstream's ``GsubData`` projection.

        Result is cached, including the negative case — repeat callers
        on a font without GSUB won't re-probe the directory.
        """
        if self._gsub_resolved:
            return self._gsub
        self._gsub_resolved = True
        if "GSUB" not in self._tt:
            self._gsub = None
            return None
        t = GlyphSubstitutionTable()
        t.populate_from_fonttools(self._tt)
        self._gsub = t
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

    def get_cmap(self) -> CmapSubtable | None:
        """Alias for :meth:`get_unicode_cmap_subtable`.

        Mirrors upstream's ``getCmap()`` shorthand. Most callers want the
        Unicode subtable view that PDFBox picks internally, so we reuse
        the existing resolver rather than exposing the full ``cmap``
        directory wrapper.
        """
        return self.get_unicode_cmap_subtable()

    def name_to_gid(self, name: str) -> int:
        """Return the GID for a PostScript glyph name (0 / ``.notdef`` if unknown).

        Mirrors upstream's ``nameToGID(String)``: walks the font's glyph
        order, falling back to gid 0 (``.notdef``) when the name is not
        present. Names like ``glyph123`` (fontTools placeholder for
        unnamed glyphs) are accepted by that path too because they live
        in the glyph order.
        """
        if not name:
            return 0
        order = self._tt.getGlyphOrder()
        try:
            return int(order.index(name))
        except ValueError:
            return 0

    # ---------- naming / post / OS/2 / loca typed-table accessors --------

    def get_naming(self) -> NamingTable | None:
        """Return the populated ``name`` table, or ``None`` if absent.

        fontTools holds the parsed name records on ``TTFont["name"].names``;
        we project each onto a :class:`NameRecord` and rebuild the
        upstream lookup map so ``naming.get_name(name_id)`` and the
        ``get_font_family`` / ``get_post_script_name`` shortcuts work
        without re-reading bytes.
        """
        if self._naming_resolved:
            return self._naming
        self._naming_resolved = True
        if "name" not in self._tt:
            self._naming = None
            return None
        ft_name = self._tt["name"]
        nt = NamingTable()
        records: list[NameRecord] = []
        for ft_record in getattr(ft_name, "names", []) or []:
            nr = NameRecord()
            nr.set_platform_id(int(ft_record.platformID))
            nr.set_platform_encoding_id(int(ft_record.platEncID))
            nr.set_language_id(int(ft_record.langID))
            nr.set_name_id(int(ft_record.nameID))
            try:
                value = ft_record.toUnicode()
            except (UnicodeDecodeError, ValueError):
                value = None
            if value is not None:
                value = str(value)
                nr.set_string(value)
                # ``string_length`` upstream is the on-disk byte length;
                # we don't have it here, so the UTF-8 byte length is the
                # closest meaningful approximation. Tests only assert the
                # round-tripped string.
                nr.set_string_length(len(value.encode("utf-8")))
            records.append(nr)
        nt._name_records = records  # noqa: SLF001
        nt._fill_lookup_table()  # noqa: SLF001
        nt._read_interesting_strings()  # noqa: SLF001
        nt.initialized = True
        self._naming = nt
        return nt

    def get_post_script(self) -> PostScriptTable | None:
        """Return the populated ``post`` table, or ``None`` if absent."""
        if self._post_resolved:
            return self._post
        self._post_resolved = True
        if "post" not in self._tt:
            self._post = None
            return None
        ft_post = self._tt["post"]
        t = PostScriptTable()
        t._format_type = float(ft_post.formatType)  # noqa: SLF001
        t._italic_angle = float(ft_post.italicAngle)  # noqa: SLF001
        t._underline_position = int(ft_post.underlinePosition)  # noqa: SLF001
        t._underline_thickness = int(ft_post.underlineThickness)  # noqa: SLF001
        t._is_fixed_pitch = int(ft_post.isFixedPitch)  # noqa: SLF001
        t._min_mem_type42 = int(ft_post.minMemType42)  # noqa: SLF001
        t._max_mem_type42 = int(ft_post.maxMemType42)  # noqa: SLF001
        t._mim_mem_type1 = int(ft_post.minMemType1)  # noqa: SLF001
        t._max_mem_type1 = int(ft_post.maxMemType1)  # noqa: SLF001
        # fontTools resolves glyph names onto the post table for format 2.0;
        # both formats end up in ``glyphOrder``, indexed by gid.
        glyph_names = getattr(ft_post, "glyphOrder", None)
        if glyph_names is not None:
            t._glyph_names = list(glyph_names)  # noqa: SLF001
        t.initialized = True
        self._post = t
        return t

    def get_os2_windows(self) -> OS2WindowsMetricsTable | None:
        """Return the populated ``OS/2`` table, or ``None`` if absent.

        Optional in pre-Windows fonts but practically required for any
        font shipped on a modern OS — defaults to ``None`` only for
        legacy Mac TrueType files.
        """
        if self._os2_resolved:
            return self._os2
        self._os2_resolved = True
        if "OS/2" not in self._tt:
            self._os2 = None
            return None
        ft = self._tt["OS/2"]
        t = OS2WindowsMetricsTable()
        t._version = int(ft.version)  # noqa: SLF001
        t._average_char_width = int(ft.xAvgCharWidth)  # noqa: SLF001
        t._weight_class = int(ft.usWeightClass)  # noqa: SLF001
        t._width_class = int(ft.usWidthClass)  # noqa: SLF001
        t._fs_type = int(ft.fsType)  # noqa: SLF001
        t._subscript_x_size = int(ft.ySubscriptXSize)  # noqa: SLF001
        t._subscript_y_size = int(ft.ySubscriptYSize)  # noqa: SLF001
        t._subscript_x_offset = int(ft.ySubscriptXOffset)  # noqa: SLF001
        t._subscript_y_offset = int(ft.ySubscriptYOffset)  # noqa: SLF001
        t._superscript_x_size = int(ft.ySuperscriptXSize)  # noqa: SLF001
        t._superscript_y_size = int(ft.ySuperscriptYSize)  # noqa: SLF001
        t._superscript_x_offset = int(ft.ySuperscriptXOffset)  # noqa: SLF001
        t._superscript_y_offset = int(ft.ySuperscriptYOffset)  # noqa: SLF001
        t._strikeout_size = int(ft.yStrikeoutSize)  # noqa: SLF001
        t._strikeout_position = int(ft.yStrikeoutPosition)  # noqa: SLF001
        t._family_class = int(ft.sFamilyClass)  # noqa: SLF001
        # ``panose`` in fontTools is a Panose() object with named fields;
        # serialise back to a 10-byte buffer for upstream parity.
        panose = getattr(ft, "panose", None)
        if panose is not None:
            t._panose = bytes(  # noqa: SLF001
                int(getattr(panose, attr, 0)) & 0xFF
                for attr in (
                    "bFamilyType",
                    "bSerifStyle",
                    "bWeight",
                    "bProportion",
                    "bContrast",
                    "bStrokeVariation",
                    "bArmStyle",
                    "bLetterForm",
                    "bMidline",
                    "bXHeight",
                )
            )
        t._unicode_range1 = int(ft.ulUnicodeRange1)  # noqa: SLF001
        t._unicode_range2 = int(ft.ulUnicodeRange2)  # noqa: SLF001
        t._unicode_range3 = int(ft.ulUnicodeRange3)  # noqa: SLF001
        t._unicode_range4 = int(ft.ulUnicodeRange4)  # noqa: SLF001
        # achVendID may come back as bytes; coerce defensively.
        ach = ft.achVendID
        if isinstance(ach, (bytes, bytearray)):
            ach = ach.decode("ascii", errors="replace")
        t._ach_vend_id = str(ach)  # noqa: SLF001
        t._fs_selection = int(ft.fsSelection)  # noqa: SLF001
        t._first_char_index = int(ft.usFirstCharIndex)  # noqa: SLF001
        t._last_char_index = int(ft.usLastCharIndex)  # noqa: SLF001
        t._typo_ascender = int(ft.sTypoAscender)  # noqa: SLF001
        t._typo_descender = int(ft.sTypoDescender)  # noqa: SLF001
        t._typo_line_gap = int(ft.sTypoLineGap)  # noqa: SLF001
        t._win_ascent = int(ft.usWinAscent)  # noqa: SLF001
        t._win_descent = int(ft.usWinDescent)  # noqa: SLF001
        if t._version >= 1:  # noqa: SLF001
            t._code_page_range1 = int(getattr(ft, "ulCodePageRange1", 0))  # noqa: SLF001
            t._code_page_range2 = int(getattr(ft, "ulCodePageRange2", 0))  # noqa: SLF001
        if t._version >= 2:  # noqa: SLF001
            t._sx_height = int(getattr(ft, "sxHeight", 0))  # noqa: SLF001
            t._s_cap_height = int(getattr(ft, "sCapHeight", 0))  # noqa: SLF001
            t._us_default_char = int(getattr(ft, "usDefaultChar", 0))  # noqa: SLF001
            t._us_break_char = int(getattr(ft, "usBreakChar", 0))  # noqa: SLF001
            t._us_max_context = int(getattr(ft, "usMaxContext", 0))  # noqa: SLF001
        t.initialized = True
        self._os2 = t
        return t

    def get_index_to_location(self) -> IndexToLocationTable | None:
        """Return the populated ``loca`` table, or ``None`` if absent.

        TrueType-only — CFF fonts ship glyph offsets inside the CFF
        block and have no ``loca``. The returned table mirrors upstream's
        offsets-array view; offsets are stored as resolved byte offsets
        regardless of ``head.indexToLocFormat`` (matching what upstream's
        ``read`` produces post-decoding).
        """
        if self._loca_resolved:
            return self._loca
        self._loca_resolved = True
        if "loca" not in self._tt:
            self._loca = None
            return None
        ft_loca = self._tt["loca"]
        offsets = getattr(ft_loca, "locations", None)
        t = IndexToLocationTable()
        if offsets is not None:
            t.set_offsets([int(o) for o in offsets])
        t.initialized = True
        self._loca = t
        return t

    # ---------- aliases for upstream-shaped accessor names ---------------

    def get_kerning(self) -> KerningTable | None:
        """Alias for :meth:`get_kerning_table` matching upstream's
        ``getKerning()`` shorthand."""
        return self.get_kerning_table()

    def get_digital_signature(self) -> DigitalSignatureTable | None:
        """Alias for :meth:`get_dsig` matching upstream's
        ``getDigitalSignature()`` shorthand."""
        return self.get_dsig()

    # ---------- glyph helpers --------------------------------------------

    def get_path(self, gid: int) -> Any | None:
        """Return the outline of glyph ``gid`` as a fontTools ``RecordingPen``.

        Mirrors upstream's ``getPath(int)``. Returns ``None`` when the
        font has no ``glyf`` table (CFF) or ``gid`` is out of range —
        callers that want an empty path can fall back to a blank pen.
        """
        glyph = self.get_glyph(gid)
        if glyph is None:
            return None
        return glyph.get_path()

    def get_bounding_box(self) -> tuple[int, int, int, int]:
        """Alias for :meth:`get_font_bbox` — mirrors upstream's
        ``getFontBBox()`` shorthand exposed under the broader name."""
        return self.get_font_bbox()

    # ---------- font-level metadata --------------------------------------

    def get_original_data(self) -> bytes:
        """Return the raw SFNT bytes the font was constructed from.

        Used by PDF font embedders that need to re-emit the original
        on-disk byte stream (e.g. ``PDTrueTypeFont`` /
        ``PDType0Font`` embedding paths). Mirrors upstream's
        ``getOriginalData()``.
        """
        return self._raw_bytes

    def get_original_data_size(self) -> int:
        """Length of :meth:`get_original_data` in bytes."""
        return len(self._raw_bytes)

    def is_post_script(self) -> bool:
        """``False`` — TrueType-flavoured fonts are not PostScript-flavoured.

        Upstream's ``OpenTypeFont`` subclass overrides this for CFF
        (PostScript-flavoured OpenType) fonts. The base ``TrueTypeFont``
        always returns ``False``.
        """
        return False

    def is_supported(self) -> bool:
        """``True`` iff the font carries the minimum tables PDFBox requires.

        Mirrors upstream's check that ``head``, ``hhea``, ``maxp``,
        ``hmtx``, ``cmap``, ``name`` and ``post`` are all present —
        fonts missing any of these can't be read or embedded reliably.
        """
        required = ("head", "hhea", "maxp", "hmtx", "cmap", "name", "post")
        return all(self.has_table(t) for t in required)

    def close(self) -> None:
        """Release the fontTools-held resources.

        Idempotent. After ``close()``, table accessors will raise on
        re-access against the underlying fontTools object — call sites
        should treat this as "the font handle is no longer usable".
        Mirrors upstream's ``close()``.
        """
        if self._closed:
            return
        self._closed = True
        try:
            self._tt.close()
        except (AttributeError, OSError):
            # Older fontTools releases used a context-manager-only API;
            # nothing to do then.
            pass

    def __enter__(self) -> TrueTypeFont:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

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
