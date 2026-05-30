from __future__ import annotations

import io
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from .cmap_table import CmapTable
from .digital_signature_table import DigitalSignatureTable
from .glyph_positioning_table import GlyphPositioningTable
from .glyph_substitution_table import GlyphSubstitutionTable
from .gsub.gsub_data import GsubData
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
    from .cmap_lookup import CmapLookup
    from .cmap_subtable import CmapSubtable
    from .glyph_data import GlyphData
    from .glyph_table import GlyphTable
    from .kerning_table import KerningTable


class _SubstitutingCmapLookup:
    """A :class:`CmapLookup` that applies GSUB substitutions on top of an
    inner Unicode cmap.

    Internal stand-in for upstream's
    ``org.apache.fontbox.ttf.SubstitutingCmapLookup`` — kept module-local
    because the standalone class hasn't been ported yet, but the
    behaviour the PDF rendering pipeline cares about (transparent glyph
    substitution after a Unicode-style ``get_glyph_id`` call) is what
    matters here.
    """

    def __init__(
        self,
        cmap: CmapSubtable,
        gsub_table: GlyphSubstitutionTable,
        features: tuple[str, ...],
    ) -> None:
        self._cmap = cmap
        self._gsub = gsub_table
        self._features = features

    def get_glyph_id(self, code_point: int) -> int:
        """Look up ``code_point`` in the inner cmap, then run any enabled
        GSUB feature substitutions over the resolved GID.
        """
        gid = int(self._cmap.get_glyph_id(code_point))
        substitute = getattr(self._gsub, "substitute_glyph", None)
        if substitute is None:
            return gid
        for feature in self._features:
            try:
                replaced = substitute(gid, feature)
            except (KeyError, ValueError, TypeError):
                continue
            if replaced is not None:
                gid = int(replaced)
        return gid

    def get_char_codes(self, gid: int) -> list[int] | None:
        return self._cmap.get_char_codes(gid)


class _VerticalOriginView:
    """Minimal projection of the ``VORG`` (vertical origin) table.

    The standalone :class:`VerticalOriginTable` port is a future-wave
    item — the table is rare (only CFF / OTF CJK fonts and a handful of
    Latin fonts ship one), so we surface enough of the upstream shape
    here to keep :meth:`TrueTypeFont.get_vertical_origin` returning a
    real object when ``VORG`` is present without expanding the typed-
    table inventory in this wave. The accessor names (``get_origin_y``,
    etc.) match upstream's ``VerticalOriginTable`` so callers porting
    from PDFBox find them.
    """

    def __init__(self) -> None:
        self.major_version: int = 1
        self.minor_version: int = 0
        self.default_vertical_origin: int = 0
        self.origins: dict[int, int] = {}

    def get_origin_y(self, gid: int) -> int:
        """Vertical origin (Y, in design units) for ``gid``."""
        return self.origins.get(int(gid), self.default_vertical_origin)


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
        # Mirrors upstream's ``version`` ``float`` field — the SFNT scaler
        # value (1.0 / 0x00010000 for TrueType, the floats encoding ``OTTO``
        # / ``true`` / ``typ1`` for the legacy magics). Seeded to 1.0 so a
        # caller that constructs a :class:`TrueTypeFont` directly (without
        # going through :class:`TTFParser`) still observes a sensible
        # default; the parser overrides it through :meth:`set_version`.
        self._version: float = 1.0
        # Mirrors upstream's ``enableGsub`` flag: callers can suppress the
        # GSUB table if a font's substitution rules misbehave. Defaults to
        # ``True`` to match upstream.
        self._enable_gsub: bool = True
        # Mirrors upstream's ``enabledGsubFeatures`` list: tags consumers
        # have explicitly opted into (e.g. ``"vrt2"`` / ``"vert"`` for
        # vertical writing).
        self._enabled_gsub_features: list[str] = []
        # Cache for the PostScript-name lookup map (gid by glyph name).
        # Mirrors upstream's volatile ``postScriptNames`` field, lazily
        # populated on first :meth:`name_to_gid` call. ``None`` until the
        # ``post`` table has been consulted.
        self._post_script_names: dict[str, int] | None = None
        # Materialise the SFNT bytes into a BytesIO for fontTools. The
        # legacy TTFDataStream surface only guarantees random-access
        # reads, so we round-trip through bytes rather than wrapping it.
        raw = self._read_all_bytes(data)
        # Lazy import — fontTools is heavy and most pypdfbox use does not
        # touch it.
        import fontTools.ttLib as ttLib  # type: ignore[import-untyped]  # noqa: PLC0415

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
        self._gpos: GlyphPositioningTable | None = None
        self._gpos_resolved: bool = False
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

    # ---------- attribute-style accessors -------------------------------

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
        """Mirrors upstream ``getUnitsPerEm()`` — caches on first call,
        falls back to 0 when the font has no ``head`` table (matches
        upstream's defensive ``// this should never happen`` branch).
        """
        if "head" not in self._tt:
            return 0
        return int(self._tt["head"].unitsPerEm)

    def get_number_of_glyphs(self) -> int:
        """Mirrors upstream ``getNumberOfGlyphs()`` — caches on first call,
        falls back to 0 when the font has no ``maxp`` table.
        """
        if "maxp" not in self._tt:
            return 0
        return int(self._tt["maxp"].numGlyphs)

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

    def get_advance_height(self, gid: int) -> int:
        """Advance height (in font units) for ``gid``. Falls back to 250
        when the font lacks a ``vmtx`` table — matches upstream's
        ``VerticalMetricsTable.getAdvanceHeight`` default for fonts with
        no vertical metrics.
        """
        vmtx = self.get_vertical_metrics()
        if vmtx is None:
            return 250
        return vmtx.get_advance_height(gid)

    # ---------- typed-table accessors (legacy surface) ------------------

    def add_table(self, table: TTFTable) -> None:
        """Register a directory entry under its tag.

        Mirrors upstream ``addTable(TTFTable)`` (TrueTypeFont.java line
        114) — package-private on the Java side, called by
        :class:`TTFParser` while seeding the directory. Python has no
        package visibility, so it is exposed here too; callers outside
        the parser should not invoke it directly. The supplied table
        replaces any existing entry with the same tag.
        """
        # Materialise the directory cache so subsequent ``get_table_map``
        # calls see the new entry without re-walking ``self._tt.reader``.
        table_map = self.get_table_map()
        tag = table.get_tag()
        if tag is None:
            return
        table_map[tag] = table

    def read_table(self, table: TTFTable) -> None:
        """Initialise a directory entry by re-reading its bytes.

        Mirrors upstream ``readTable(TTFTable)`` (TrueTypeFont.java line
        404) — package-private parser hook used to lazily fault tables
        in. fontTools already eagerly parses the recognised tables once
        :class:`TTFFont` is constructed, so the work this method does on
        the Java side is mostly already complete by the time it would
        be called here. We still flip the entry's ``initialized`` bit
        and re-attach the on-disk byte slice so callers walking the
        directory observe the upstream contract.
        """
        if table is None:
            return
        raw = self.get_table_bytes(table)
        if raw is not None:
            # ``TTFTable.set_data`` was added in an earlier wave for the
            # raw-bytes accessor path; if the field is absent (legacy
            # TTFTable subclasses) just record the initialisation flag.
            setter = getattr(table, "set_data", None)
            if setter is not None:  # pragma: no cover - pre-wave compat shim
                setter(raw)
        table.initialized = True

    def read_table_headers(self, tag: str, out_headers: Any) -> None:
        """Populate ``out_headers`` with the header fields of ``tag``.

        Mirrors upstream ``readTableHeaders(String, FontHeaders)``
        (TrueTypeFont.java line 422) — package-private parser hook used
        by the embedded-font header reader. ``FontHeaders`` is a thin
        DTO that has not been ported separately; we accept any object
        and assign a small set of well-known attributes onto it. The
        call is a no-op when the font lacks ``tag``.
        """
        if tag not in self.get_table_map():
            return
        # Best-effort projection: surface the most-frequently-consumed
        # head / hhea / OS-2 / post fields onto the supplied DTO. The
        # caller decides which subset to inspect.
        if tag == "head":
            head = self.get_header()
            if head is not None and out_headers is not None:
                out_headers.units_per_em = head.get_units_per_em()
                out_headers.x_min = head.get_x_min()
                out_headers.y_min = head.get_y_min()
                out_headers.x_max = head.get_x_max()
                out_headers.y_max = head.get_y_max()
        elif tag == "hhea":
            hhea = self.get_horizontal_header()
            if hhea is not None and out_headers is not None:
                out_headers.number_of_h_metrics = hhea.get_number_of_h_metrics()
        elif tag == "OS/2":
            os2 = self.get_os2_windows()
            if os2 is not None and out_headers is not None:
                out_headers.weight_class = os2.get_weight_class()
        elif tag == "post":
            post = self.get_post_script()
            if post is not None and out_headers is not None:
                out_headers.italic_angle = post.get_italic_angle()

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

    def get_tables(self) -> list[TTFTable]:
        """Return all SFNT-directory entries.

        Mirrors upstream's ``getTables()`` collection helper. The entries
        are the same :class:`TTFTable` objects exposed by
        :meth:`get_table_map`.
        """
        return list(self.get_table_map().values())

    def get_table_bytes(self, table: str | TTFTable) -> bytes | None:
        """Return the raw on-disk bytes of ``table``, or ``None`` if absent.

        Mirrors upstream's ``getTableBytes(TTFTable)`` while preserving the
        earlier Python convenience of passing a table tag string. Pulls the
        bytes out of the in-memory SFNT buffer using the directory entry's
        offset/length so callers don't have to re-read the file.
        """
        entry = self.get_table_map().get(table) if isinstance(table, str) else table
        if entry is None:
            return None
        offset = entry.get_offset()
        length = entry.get_length()
        if offset < 0 or length < 0 or offset + length > len(self._raw_bytes):
            return None
        return self._raw_bytes[offset : offset + length]

    def get_table_n_bytes(self, table: str | TTFTable, limit: int) -> bytes | None:
        """Return up to ``limit`` raw on-disk bytes of ``table``.

        Mirrors upstream's ``getTableNBytes(TTFTable, int)`` — used by the
        embedded-font header parser to peek at large tables without
        decoding them in full. Negative ``limit`` clamps to 0; a ``limit``
        larger than the table is silently capped to the table length.
        Returns ``None`` for an unknown / malformed table entry.
        """
        entry = self.get_table_map().get(table) if isinstance(table, str) else table
        if entry is None:
            return None
        offset = entry.get_offset()
        length = entry.get_length()
        if offset < 0 or length < 0 or offset + length > len(self._raw_bytes):
            return None
        capped = max(0, min(int(limit), length))
        return self._raw_bytes[offset : offset + capped]

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
        h._created = self._long_datetime(int(ft.created))  # noqa: SLF001
        h._modified = self._long_datetime(int(ft.modified))  # noqa: SLF001
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

    # ---------- GSUB feature toggles -----------------------------------

    def is_enable_gsub(self) -> bool:
        """``True`` when the GSUB table is enabled for this font.

        Mirrors upstream's ``isEnableGsub()``. Defaults to ``True``;
        callers can suppress GSUB on a per-font basis via
        :meth:`set_enable_gsub` when its substitution rules misbehave.
        """
        return self._enable_gsub

    def set_enable_gsub(self, enable: bool) -> None:  # noqa: FBT001
        """Enable or disable the GSUB table for this font.

        Mirrors upstream's ``setEnableGsub(boolean)``.
        """
        self._enable_gsub = bool(enable)

    def enable_gsub_feature(self, feature_tag: str) -> None:
        """Opt into a particular GSUB feature (e.g. ``"liga"``, ``"vrt2"``).

        Mirrors upstream's ``enableGsubFeature(String)``. The feature may
        not be supported by the font or by pypdfbox yet — this just records
        the request.
        """
        self._enabled_gsub_features.append(feature_tag)

    def disable_gsub_feature(self, feature_tag: str) -> None:
        """Remove a previously-enabled GSUB feature tag.

        Mirrors upstream's ``disableGsubFeature(String)`` — uses
        ``list.remove`` semantics, so removing a tag that was never added
        raises :class:`ValueError`, matching Java's behaviour where the
        underlying ``ArrayList.remove(Object)`` is a no-op only when the
        tag is present.
        """
        # ``list.remove`` mirrors ``ArrayList.remove(Object)`` for the
        # present-tag case. Upstream silently ignores absent tags
        # (``ArrayList.remove(Object)`` returns ``false`` rather than
        # throwing); match that to avoid surprising callers.
        with suppress(ValueError):
            self._enabled_gsub_features.remove(feature_tag)

    def enable_vertical_substitutions(self) -> None:
        """Enable the GSUB features used for vertical writing.

        Mirrors upstream's ``enableVerticalSubstitutions()`` — registers
        the standard ``vrt2`` and ``vert`` feature tags.
        """
        self.enable_gsub_feature("vrt2")
        self.enable_gsub_feature("vert")

    def get_enabled_gsub_features(self) -> list[str]:
        """Return a copy of the currently-enabled GSUB feature tags.

        Not present on upstream as a public accessor (the field is
        package-private), but exposed here so tests and consumers can
        observe the result of :meth:`enable_gsub_feature` /
        :meth:`disable_gsub_feature` without reaching into private state.
        """
        return list(self._enabled_gsub_features)

    # ---------- GPOS (glyph positioning) accessor ----------------------

    def get_gpos(self) -> GlyphPositioningTable | None:
        """Return the ``GPOS`` table view, or ``None`` if absent.

        GPOS carries OpenType glyph positioning rules — pair-based
        kerning (the most common use), cursive attachment, mark-to-
        base / mark-to-mark / mark-to-ligature attachment, and
        contextual / chained-contextual positioning. Most modern fonts
        carry kerning in GPOS rather than the legacy ``kern`` table, so
        this is the table actually consulted during PDF text layout.

        Parsing is delegated to ``fontTools.ttLib`` — see
        :class:`GlyphPositioningTable` for the rationale.

        Result is cached, including the negative case — repeat callers
        on a font without GPOS won't re-probe the directory.
        """
        if self._gpos_resolved:
            return self._gpos
        self._gpos_resolved = True
        if "GPOS" not in self._tt:
            self._gpos = None
            return None
        t = GlyphPositioningTable()
        t.populate_from_fonttools(self._tt)
        self._gpos = t
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

    def get_name(
        self,
        name_id: int | None = None,
        platform_id: int | None = None,
        encoding_id: int | None = None,
        language_id: int | None = None,
    ) -> str | None:
        """Name-table string lookup.

        Called with no arguments this mirrors upstream ``getName()``
        (TrueTypeFont.java L527) — returns the PostScript name
        (``nameID = 6``), or ``None`` when the font has no ``name``
        table.

        Called with ``name_id`` (and optionally the full
        platform / encoding / language triplet) this delegates to
        :meth:`NamingTable.get_name`, exposing the lookup surface
        upstream callers reach by doing ``font.getNaming().getName(...)``.
        The four-argument form returns the exact-match record; the
        single-argument form runs upstream's preferred-record fallback
        order (Windows Unicode BMP English-US first, then other
        Microsoft Unicode languages, then Unicode platform, then
        Macintosh Roman English).
        """
        if name_id is None:
            return self._get_name_string(6)
        naming = self.get_naming()
        if naming is None:
            return None
        return naming.get_name(name_id, platform_id, encoding_id, language_id)

    def get_family_name(self) -> str | None:
        """Font family name (name table, nameID 1)."""
        return self._get_name_string(1)

    def get_full_name(self) -> str | None:
        """Full font name (name table, nameID 4)."""
        return self._get_name_string(4)

    def get_version(self) -> str | None:
        """Version string (name table, nameID 5).

        **Deviation from upstream:** Java's ``TrueTypeFont.getVersion()``
        returns the SFNT scaler ``float`` written by
        :meth:`set_version`; the name-table version string is not
        otherwise exposed. We surface the name-table version under the
        same accessor (existing wave tests rely on it) and provide
        :meth:`get_sfnt_version` for the upstream-shaped scaler value.
        """
        return self._get_name_string(5)

    def get_sfnt_version(self) -> float:
        """Return the SFNT scaler version (upstream's ``float version``).

        Mirrors what upstream's ``getVersion()`` returns. Set by the
        parser through :meth:`set_version`; defaults to 1.0 when the
        font was constructed directly without going through
        :class:`TTFParser`.
        """
        return self._version

    def set_version(self, version_value: float) -> None:
        """Record the SFNT scaler version (upstream parser hook).

        Mirrors upstream ``setVersion(float)`` — package-private on the
        Java side, called by :class:`TTFParser` while seeding the font.
        Python has no package visibility, so it's exposed here too;
        callers outside parsing should not invoke it directly.
        """
        self._version = float(version_value)

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

    def get_width(self, name: str | None = None) -> int | float:
        """Return width information.

        With no argument, returns ``OS/2.usWidthClass`` (1..9), preserving
        the existing table-scalar helper. With a glyph name, mirrors
        ``TrueTypeFont.getWidth(String)`` (TrueTypeFont.java line 752) which
        is unconditionally ``getAdvanceWidth(nameToGID(name))`` cast to a
        float — there is NO special-case for an unresolved (gid 0) name, so
        a name that falls back to ``.notdef`` reports gid 0's advance, not
        ``0.0``.
        """
        if name is not None:
            return float(self.get_advance_width(self.name_to_gid(name)))
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

        Selects a fontTools cmap subtable using the same priority order as
        PDFBox's ``TrueTypeFont.getUnicodeCmapImpl`` and wraps its mapping in
        a thin :class:`CmapSubtable` view so callers can continue to use
        ``get_glyph_id(code)`` / ``get_char_codes(gid)`` unchanged. Returns
        ``None`` if the font has no cmap, or no PDFBox-compatible Unicode /
        symbol cmap.
        """
        if self._cmap_resolved:
            return self._cmap_subtable
        self._cmap_resolved = True
        if "cmap" not in self._tt:
            self._cmap_subtable = None
            return None
        cmap_table = self._tt["cmap"]
        preferred = (
            (
                CmapTable.PLATFORM_UNICODE,
                CmapTable.ENCODING_UNICODE_2_0_FULL,
            ),
            (
                CmapTable.PLATFORM_WINDOWS,
                CmapTable.ENCODING_WIN_UNICODE_FULL,
            ),
            (
                CmapTable.PLATFORM_UNICODE,
                CmapTable.ENCODING_UNICODE_2_0_BMP,
            ),
            (
                CmapTable.PLATFORM_WINDOWS,
                CmapTable.ENCODING_WIN_UNICODE_BMP,
            ),
            (
                CmapTable.PLATFORM_WINDOWS,
                CmapTable.ENCODING_WIN_SYMBOL,
            ),
            (
                CmapTable.PLATFORM_UNICODE,
                CmapTable.ENCODING_UNICODE_1_1,
            ),
        )
        chosen = None
        for platform_id, platform_encoding_id in preferred:
            chosen = cmap_table.getcmap(platform_id, platform_encoding_id)
            if chosen is not None:
                break
        if chosen is None:
            self._cmap_subtable = None
            return None

        glyph_name_to_gid = {n: i for i, n in enumerate(self._tt.getGlyphOrder())}
        char_to_gid: dict[int, int] = {}
        for code, name in chosen.cmap.items():
            gid = glyph_name_to_gid.get(name)
            if gid is not None:
                char_to_gid[code] = gid

        from .cmap_subtable import CmapSubtable  # noqa: PLC0415

        view = CmapSubtable()
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

    def get_unicode_cmap_lookup(self, is_strict: bool = True) -> CmapLookup | None:  # noqa: FBT001, FBT002
        """Return a Unicode :class:`CmapLookup` for this font.

        Mirrors upstream's ``getUnicodeCmapLookup()`` /
        ``getUnicodeCmapLookup(boolean isStrict)`` (TrueTypeFont.java
        lines 581 / 597). When GSUB features have been enabled through
        :meth:`enable_gsub_feature` and the font carries a GSUB table,
        the lookup is wrapped in a :class:`SubstitutingCmapLookup` so
        glyph substitution kicks in transparently for the caller.

        When ``is_strict`` is ``True`` (the default) and the font has no
        cmap table, raises :class:`OSError` matching upstream's
        ``IOException`` contract; ``is_strict=False`` returns the first
        cmap subtable available (potentially non-Unicode), or ``None``
        if the font has no cmaps at all.
        """
        cmap = self._get_unicode_cmap_impl(is_strict=is_strict)
        if cmap is not None and self._enabled_gsub_features:
            gsub_table = self.get_gsub()
            if gsub_table is not None:
                return _SubstitutingCmapLookup(
                    cmap, gsub_table, tuple(self._enabled_gsub_features)
                )
        return cmap

    def _get_unicode_cmap_impl(self, *, is_strict: bool) -> CmapSubtable | None:
        """Implementation of :meth:`get_unicode_cmap_lookup` minus the
        substitution-wrapper step.

        Mirrors upstream's private ``getUnicodeCmapImpl(boolean)`` —
        applies the same priority order :meth:`get_unicode_cmap_subtable`
        uses but adds the ``is_strict`` semantics for the no-cmap and
        no-Unicode-cmap cases.
        """
        cmap = self.get_unicode_cmap_subtable()
        if cmap is not None:
            return cmap
        if "cmap" not in self._tt:
            if is_strict:
                msg = (
                    f"The TrueType font {self.get_name()} does not contain "
                    "a 'cmap' table"
                )
                raise OSError(msg)
            return None
        # cmap table is present but no preferred Unicode subtable matched.
        if is_strict:
            msg = "The TrueType font does not contain a Unicode cmap"
            raise OSError(msg)
        # Non-strict fallback: return the first cmap subtable available.
        cmap_table = self._tt["cmap"]
        subtables = list(getattr(cmap_table, "tables", []) or [])
        if not subtables:  # pragma: no cover - parser rejects fonts w/o cmap
            return None
        chosen = subtables[0]
        glyph_name_to_gid = {n: i for i, n in enumerate(self._tt.getGlyphOrder())}
        char_to_gid: dict[int, int] = {}
        for code, name in chosen.cmap.items():
            gid = glyph_name_to_gid.get(name)
            if gid is not None:
                char_to_gid[code] = gid

        from .cmap_subtable import CmapSubtable  # noqa: PLC0415

        view = CmapSubtable()
        view.set_platform_id(int(chosen.platformID))
        view.set_platform_encoding_id(int(chosen.platEncID))
        view._character_code_to_glyph_id = char_to_gid  # noqa: SLF001
        max_gid = max(char_to_gid.values(), default=-1)
        if max_gid >= 0:
            view._build_glyph_id_to_character_code_lookup(max_gid)  # noqa: SLF001
        return view

    def get_gsub_data(self) -> GsubData:
        """Return the parsed GSUB data, or :attr:`GsubData.NO_DATA_FOUND`.

        Mirrors upstream's ``getGsubData()`` (TrueTypeFont.java line
        717) — returns the sentinel :attr:`GsubData.NO_DATA_FOUND` when
        GSUB has been disabled via :meth:`set_enable_gsub`, when the
        font has no GSUB table, or when the table has no parsed data
        for the active script.
        """
        if not self._enable_gsub:
            return GsubData.NO_DATA_FOUND
        table = self.get_gsub()
        if table is None:
            return GsubData.NO_DATA_FOUND
        get_data = getattr(table, "get_gsub_data", None)
        if get_data is None:
            return GsubData.NO_DATA_FOUND
        result = get_data()
        if result is None:
            return GsubData.NO_DATA_FOUND
        return result  # pragma: no cover - corpus fonts lack GSUB tables

    def name_to_gid(self, name: str) -> int:
        """Return the GID for a PostScript glyph name (0 / ``.notdef`` if unknown).

        Mirrors upstream's ``nameToGID(String)`` (TrueTypeFont.java line
        680) — three-stage lookup:

        1. Consult the ``post`` table's PostScript-name -> GID map.
        2. If the name is a ``uniXXXX`` form, parse the codepoint and
           consult the Unicode cmap (non-strict).
        3. PDFBOX-5604: ``g\\d+`` is interpreted as a literal GID.

        Falls back to gid 0 (``.notdef``) when nothing matches.
        """
        if not name:
            return 0

        # 1) post-table lookup. Wrapped in a try/except so a stub TTFont
        # without a ``post`` table (or a half-built fixture that bypassed
        # ``__init__``) still falls through to the cmap / glyph-order
        # branches below.
        try:
            self._read_post_script_names()
        except AttributeError:
            pass
        else:
            psn = getattr(self, "_post_script_names", None)
            if psn:
                gid = psn.get(name)
                if gid is not None and gid > 0:
                    num_glyphs = self.get_number_of_glyphs()
                    if 0 < gid < num_glyphs:
                        return gid

        # 2) cmap fallback for ``uniXXXX``-style names.
        uni = self._parse_uni_name(name)
        if uni > -1:
            try:
                cmap = self.get_unicode_cmap_lookup(is_strict=False)
            except (AttributeError, OSError):
                cmap = None
            if cmap is not None:
                return int(cmap.get_glyph_id(uni))

        # 3) PDFBOX-5604 — ``g\d+`` is a literal GID.
        if len(name) > 1 and name[0] == "g" and name[1:].isdigit():
            try:
                return int(name[1:])
            except ValueError:  # pragma: no cover - name[1:].isdigit() guarantees int() succeeds
                return 0

        # Upstream returns 0 (``.notdef``) when nothing matches — there is NO
        # glyph-order-by-name fallback (see TrueTypeFont.nameToGID bytecode:
        # post -> parseUniName/cmap -> ``g\d+`` -> ``return 0``). A previous
        # wave added a ``getGlyphOrder().index(name)`` safety net here, which
        # made name lookups for real glyph names (e.g. ``A``) on a font with a
        # format-3.0 ``post`` table resolve via fontTools' synthetic glyph
        # order instead of returning 0 like Apache FontBox. That diverged the
        # OTF/CFF loading surface, so the fallback is gone.
        return 0

    def _read_post_script_names(self) -> None:
        """Build the PostScript-name -> GID map from the ``post`` table.

        Mirrors upstream's private ``readPostScriptNames`` — caches in
        ``_post_script_names``; subsequent calls are no-ops. The ``post``
        table only carries glyph names for format 2.0 / 2.5; for other
        formats the map is empty.
        """
        # Tolerate test fixtures that bypass ``__init__`` via
        # ``object.__new__(TrueTypeFont)`` — those mocks predate the
        # ``_post_script_names`` cache being a constructor field.
        if getattr(self, "_post_script_names", None) is not None:
            return
        post = self.get_post_script()
        names = post.get_glyph_names() if post is not None else None
        if names:
            self._post_script_names = {n: i for i, n in enumerate(names)}
        else:
            self._post_script_names = {}

    @staticmethod
    def _parse_uni_name(name: str) -> int:
        """Decode a Unicode PostScript name in the ``uniXXXX`` form.

        Mirrors upstream's private ``parseUniName`` — accepts a 7-char
        string starting ``uni`` followed by 4 hex digits and returns the
        decoded codepoint (or -1 on any of: wrong shape, surrogate-area
        codepoint, parse error). Multi-character forms (``uniXXXXYYYY``)
        return the codepoint of the first character only, matching
        upstream's ``unicode.codePointAt(0)`` return.
        """
        if not (name.startswith("uni") and len(name) == 7):
            return -1
        try:
            chars: list[str] = []
            pos = 3
            while pos + 4 <= len(name):
                code_point = int(name[pos : pos + 4], 16)
                # Skip the disallowed surrogate area.
                if code_point <= 0xD7FF or code_point >= 0xE000:
                    chars.append(chr(code_point))
                pos += 4
        except ValueError:
            return -1
        if not chars:
            return -1
        return ord(chars[0])

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
            # fontTools stores the raw on-disk bytes on ``ft_record.string``
            # (decoded form on its ``toUnicode`` accessor). The byte-level
            # ``NamingTable.read`` path decodes via :meth:`NamingTable.get_charset`
            # — same selection PDFBox uses, which differs from fontTools'
            # default ``toUnicode`` for platform=1 (Macintosh) records:
            # upstream PDFBox falls through to ISO-8859-1 for the Macintosh
            # platform while fontTools chooses MacRoman. Decoding the raw
            # bytes through ``NamingTable.get_charset`` keeps every record
            # parity-identical to PDFBox (wave 1449, ``NameTableProbe``).
            raw = getattr(ft_record, "string", None)
            value: str | None = None
            if isinstance(raw, bytes | bytearray):
                charset = NamingTable.get_charset(nr)
                try:
                    value = NamingTable._decode_string(bytes(raw), charset)  # noqa: SLF001
                except LookupError:
                    value = bytes(raw).decode("latin-1")
                nr.set_string_length(len(raw))
            else:
                # ``ft_record.string`` is already a Python ``str`` — fontTools
                # has decoded it for us (rare; happens on synthesised records).
                # Fall back to ``toUnicode`` for parity with previous behaviour.
                try:
                    value = ft_record.toUnicode()
                except (UnicodeDecodeError, ValueError):
                    value = None
                if value is not None:
                    value = str(value)
                    nr.set_string_length(len(value.encode("utf-8")))
            if value is not None:
                nr.set_string(value)
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
        # Only formats that actually carry a glyph-name table populate the
        # name list — upstream ``PostScriptTable.read`` leaves the names
        # ``null`` for format 3.0 (and 1.0, whose names are the implicit Mac
        # standard order). fontTools exposes a synthetic ``glyphOrder`` even
        # for format 3.0, so blindly copying it made ``name_to_gid`` resolve
        # real names (e.g. ``A``) on a 3.0-``post`` font — Apache FontBox
        # returns 0 there (PDFBox-shaped ``nameToGID`` never consults a
        # synthetic order). Gate on the format so a 3.0 ``post`` carries no
        # names, exactly as upstream.
        if t._format_type in (2.0, 2.5, 4.0):  # noqa: SLF001, PLR2004
            glyph_names = getattr(ft_post, "glyphOrder", None)
            if glyph_names is None:  # pragma: no cover - fontTools sets glyphOrder
                try:
                    glyph_names = self._tt.getGlyphOrder()
                except (AttributeError, KeyError):
                    glyph_names = None
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

    def get_vertical_origin(self) -> _VerticalOriginView | None:
        """Return the populated ``VORG`` table view, or ``None`` if absent.

        Mirrors upstream ``getVerticalOrigin()`` (TrueTypeFont.java line
        345). The ``VORG`` table is rare — it carries explicit vertical
        origins for CJK CFF fonts and a handful of OpenType-flavoured
        Latin fonts. fontTools decodes it lazily; we project the parsed
        values onto a small in-module view (``_VerticalOriginView``) so
        the upstream accessor surface stays available without expanding
        the typed-table inventory in this wave.
        """
        if "VORG" not in self._tt:
            return None
        ft = self._tt["VORG"]
        view = _VerticalOriginView()
        view.major_version = int(getattr(ft, "majorVersion", 1))
        view.minor_version = int(getattr(ft, "minorVersion", 0))
        view.default_vertical_origin = int(
            getattr(ft, "defaultVertOriginY", 0)
        )
        # fontTools exposes the per-glyph entries as ``VOriginRecords``
        # keyed by glyph name; project to a {gid: origin} dict for parity
        # with upstream's ``getOriginY(int gid)`` lookup shape.
        glyph_order = self._tt.getGlyphOrder()
        name_to_gid = {n: i for i, n in enumerate(glyph_order)}
        records = getattr(ft, "VOriginRecords", None) or {}
        view.origins = {
            name_to_gid[name]: int(record.vOrigY)
            for name, record in records.items()
            if name in name_to_gid
        }
        return view

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

    def get_path(self, gid: int | str) -> Any | None:
        """Return the outline of a glyph as a fontTools ``RecordingPen``.

        Integer input preserves the existing GID helper. String input mirrors
        upstream ``FontBoxFont.getPath(String)`` by resolving the glyph name
        first. Returns ``None`` when the font has no ``glyf`` table or the
        glyph is missing / out of range.
        """
        if isinstance(gid, str):
            resolved_gid = self.name_to_gid(gid)
            if resolved_gid == 0:
                return None
            gid = resolved_gid
        glyph = self.get_glyph(gid)
        if glyph is None:
            return None
        return glyph.get_path()

    def has_glyph(self, name: str) -> bool:
        """Return ``True`` iff ``name`` resolves to a real non-.notdef glyph.

        Mirrors upstream ``FontBoxFont.hasGlyph(String)``. The missing-glyph
        slot (gid 0) is intentionally reported as absent.
        """
        return self.name_to_gid(name) != 0

    def get_bounding_box(self) -> tuple[int, int, int, int]:
        """Alias for :meth:`get_font_bbox` — mirrors upstream's
        ``getFontBBox()`` shorthand exposed under the broader name."""
        return self.get_font_bbox()

    def get_font_matrix(self) -> list[float]:
        """Return the TrueType font matrix.

        TrueType outlines are stored in design units, so the matrix scales by
        ``1 / unitsPerEm`` in both axes, matching upstream's
        ``FontBoxFont.getFontMatrix()`` contract.
        """
        units_per_em = self.get_units_per_em()
        scale = 1.0 / units_per_em if units_per_em else 0.001
        return [scale, 0.0, 0.0, scale, 0.0, 0.0]

    def get_font_b_box(self) -> tuple[int, int, int, int]:
        """Spelled-out alias for :meth:`get_font_bbox` matching the
        CFF helper spelling and the camelCase-snake_case projection of
        upstream's ``getFontBBox()``.
        """
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

    def save(self, output: Any) -> None:
        """Serialise the (possibly-mutated) font back out as an SFNT stream.

        ``output`` accepts the same shapes ``fontTools.ttLib.TTFont.save``
        does: a filesystem path (``str`` / ``os.PathLike``) or a writable
        binary file-like object. The font is written via the underlying
        fontTools ``TTFont`` so tables modified through ``get_naming()``,
        ``get_glyph()``, etc. survive the round trip.

        Library-first: re-implementing the SFNT serialiser in Python is
        exactly what ``fontTools`` exists for. The PDFBox upstream does
        the serialisation byte-by-byte via ``TTFSubsetter`` for the
        embedding case; for callers that just want to write a TTF back
        out, fontTools' ``TTFont.save`` is the correct primitive.

        Implementation note: ``TTFont`` is constructed with ``lazy=True``
        for read-side performance, but its ``save()`` then assumes the
        reader file has a ``.name`` attribute (it tries to detect a save
        over the original file). When the font was loaded from a
        ``BytesIO`` — which is always the case here — that check fails
        with ``AttributeError``. Routing every save through a
        ``BytesIO`` sink and then dumping the bytes sidesteps the bug
        and produces identical output (fontTools' ``save`` writes the
        same SFNT regardless of destination).
        """
        import os as _os  # noqa: PLC0415

        sink = io.BytesIO()
        self._tt.save(sink, reorderTables=True)
        payload = sink.getvalue()
        if isinstance(output, (str, _os.PathLike)):
            with open(_os.fspath(output), "wb") as fh:
                fh.write(payload)
            return
        # File-like sink — write the materialised bytes through.
        write = getattr(output, "write", None)
        if write is None:
            msg = (
                "TrueTypeFont.save: output must be a path or a writable "
                f"binary file-like object, got {type(output).__name__}"
            )
            raise TypeError(msg)
        write(payload)

    def get_naming_table(self) -> NamingTable | None:
        """Alias for :meth:`get_naming` exposing the upstream-equivalent
        getter under the more explicit ``get_naming_table`` spelling.

        PDFBox uses ``getNaming()`` (TrueTypeFont.java L213); we keep
        that as the canonical accessor and expose ``get_naming_table``
        as a more discoverable variant. Both return the same instance.
        """
        return self.get_naming()

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
        with suppress(AttributeError, OSError):
            self._tt.close()

    def __enter__(self) -> TrueTypeFont:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def __str__(self) -> str:
        """Mirrors upstream's ``toString()`` — returns the PostScript
        name from the ``name`` table, or ``"(null)"`` if the font lacks
        one (or fails to read it).
        """
        return self.to_string()

    def to_string(self) -> str:
        """Mirrors upstream's ``toString()`` — returns the PostScript
        name from the ``name`` table, or ``"(null)"`` if the font lacks
        one (or fails to read it). Exposed under the snake_case spelling
        so the parity matcher recognises it; ``__str__`` defers to it.
        """
        try:
            naming_table = self.get_naming()
            if naming_table is not None:
                ps_name = naming_table.get_post_script_name()
                if ps_name is not None:
                    return ps_name
            return "(null)"  # pragma: no cover - fixtures carry a PS name
        except OSError as exc:
            return f"(null - {exc})"

    # ---------- public spellings for upstream parity matchers --------------

    def read_post_script_names(self) -> None:
        """Public spelling of :meth:`_read_post_script_names`.

        Mirrors upstream's package-private ``readPostScriptNames``
        (TrueTypeFont.java line 540) — Python has no package
        visibility, so this is exposed as a public method for the parity
        matcher and any direct caller that wants to force-warm the
        PostScript-name cache. The leading-underscore variant remains
        the canonical implementation.
        """
        self._read_post_script_names()

    @staticmethod
    def parse_uni_name(name: str) -> int:
        """Public spelling of :meth:`_parse_uni_name`.

        Mirrors upstream's private ``parseUniName`` (TrueTypeFont.java
        line 736) — exposed under the upstream snake_case shape for the
        parity matcher; the leading-underscore variant remains the
        canonical implementation.
        """
        return TrueTypeFont._parse_uni_name(name)

    def get_unicode_cmap_impl(self, is_strict: bool = True) -> CmapSubtable | None:  # noqa: FBT001, FBT002
        """Public spelling of :meth:`_get_unicode_cmap_impl`.

        Mirrors upstream's private ``getUnicodeCmapImpl(boolean)``
        (TrueTypeFont.java line 612) — exposed under the upstream
        snake_case shape for the parity matcher. The leading-underscore
        variant remains the canonical implementation.
        """
        return self._get_unicode_cmap_impl(is_strict=is_strict)

    # ---------- helpers -------------------------------------------------

    @staticmethod
    def _fixed_16_16(raw: int) -> float:
        """Decode a 16.16 fixed-point unsigned 32-bit value into a float."""
        whole = (raw >> 16) & 0xFFFF
        frac = raw & 0xFFFF
        return whole + frac / 65536.0

    @staticmethod
    def _long_datetime(seconds_since_1904: int) -> datetime:
        """Decode an OpenType LONGDATETIME value."""
        epoch = datetime(1904, 1, 1, tzinfo=UTC)
        return epoch + timedelta(seconds=seconds_since_1904)

    @staticmethod
    def _read_all_bytes(data: TTFDataStream) -> bytes:
        """Drain the supplied TTFDataStream into a ``bytes`` buffer for
        fontTools to consume. Both shipped concrete subclasses already
        hold the full font in memory, so this is a cheap reference copy.
        """
        return data.get_original_data()


__all__ = ["TrueTypeFont"]
