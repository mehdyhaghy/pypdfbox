from __future__ import annotations

from types import SimpleNamespace

from pypdfbox.fontbox.ttf import TrueTypeFont, TTFTable


class _FakeTTFont:
    def __init__(
        self,
        tables: dict[str, object] | None = None,
        glyph_order: list[str] | None = None,
    ) -> None:
        self._tables = tables or {}
        self._glyph_order = glyph_order or []

    def __contains__(self, tag: object) -> bool:
        return tag in self._tables

    def __getitem__(self, tag: str) -> object:
        return self._tables[tag]

    def getGlyphOrder(self) -> list[str]:  # noqa: N802 - fontTools API
        return list(self._glyph_order)


def _font(
    tt: _FakeTTFont | None = None,
    *,
    table_map: dict[str, TTFTable] | None = None,
    raw: bytes = b"abcdef",
) -> TrueTypeFont:
    font = object.__new__(TrueTypeFont)
    font._tt = tt or _FakeTTFont()  # noqa: SLF001
    font._raw_bytes = raw  # noqa: SLF001
    font._table_map = table_map if table_map is not None else {}  # noqa: SLF001
    font._head = None  # noqa: SLF001
    font._hhea = None  # noqa: SLF001
    font._maxp = None  # noqa: SLF001
    font._hmtx = None  # noqa: SLF001
    font._vhea = None  # noqa: SLF001
    font._vmtx = None  # noqa: SLF001
    font._cmap_subtable = None  # noqa: SLF001
    font._cmap_resolved = False  # noqa: SLF001
    font._advance_widths = None  # noqa: SLF001
    font._glyph_table = None  # noqa: SLF001
    font._dsig = None  # noqa: SLF001
    font._dsig_resolved = False  # noqa: SLF001
    font._kern = None  # noqa: SLF001
    font._kern_resolved = False  # noqa: SLF001
    font._gsub = None  # noqa: SLF001
    font._gsub_resolved = False  # noqa: SLF001
    font._gpos = None  # noqa: SLF001
    font._gpos_resolved = False  # noqa: SLF001
    font._naming = None  # noqa: SLF001
    font._naming_resolved = False  # noqa: SLF001
    font._post = None  # noqa: SLF001
    font._post_resolved = False  # noqa: SLF001
    font._os2 = None  # noqa: SLF001
    font._os2_resolved = False  # noqa: SLF001
    font._loca = None  # noqa: SLF001
    font._loca_resolved = False  # noqa: SLF001
    font._closed = False  # noqa: SLF001
    return font


def _bad_entry(offset: int, length: int) -> TTFTable:
    table = TTFTable()
    table.set_tag("bad")
    table.set_offset(offset)
    table.set_length(length)
    return table


def test_wave389_missing_sfnt_tables_use_pdfbox_fallbacks_and_cache_none() -> None:
    font = _font()

    assert font.get_header() is None
    assert font.get_horizontal_header() is None
    assert font.get_maximum_profile() is None
    assert font.get_horizontal_metrics() is None
    assert font.get_vertical_header() is None
    assert font.get_vertical_metrics() is None
    assert font.get_glyph_table() is None
    assert font.get_glyph(0) is None

    assert font.get_advance_width(123) == 250
    assert font.get_advance_height(123) == 250
    assert font.get_name() is None
    assert font.get_family_name() is None
    assert font.get_full_name() is None
    assert font.get_version() is None
    assert font.get_font_bbox() == (0, 0, 0, 0)
    assert font.get_italic_angle() == 0.0
    assert font.get_underline_position() == 0
    assert font.get_underline_thickness() == 0
    assert font.is_fixed_pitch() is False
    assert font.get_weight() == 400
    assert font.get_width() == 5
    assert font.get_width("A") == 0.0
    assert font.get_capabilities() == {}
    assert font.has_table("head") is False
    assert font.is_supported() is False

    for accessor, attr in (
        (font.get_unicode_cmap_subtable, "_cmap_resolved"),
        (font.get_dsig, "_dsig_resolved"),
        (font.get_kerning_table, "_kern_resolved"),
        (font.get_gsub, "_gsub_resolved"),
        (font.get_gpos, "_gpos_resolved"),
        (font.get_naming, "_naming_resolved"),
        (font.get_post_script, "_post_resolved"),
        (font.get_os2_windows, "_os2_resolved"),
        (font.get_index_to_location, "_loca_resolved"),
    ):
        assert accessor() is None
        assert getattr(font, attr) is True
        assert accessor() is None


def test_wave389_table_byte_helpers_reject_malformed_directory_entries() -> None:
    negative = _bad_entry(-1, 2)
    overflow = _bad_entry(4, 20)
    font = _font(table_map={"negative": negative, "overflow": overflow})

    assert font.get_table_bytes(negative) is None
    assert font.get_table_n_bytes(negative, 1) is None
    assert font.get_table_bytes("overflow") is None
    assert font.get_table_n_bytes("overflow", 1) is None


def test_wave389_empty_hmtx_metrics_fall_back_to_default_width() -> None:
    font = _font(
        _FakeTTFont({"hmtx": SimpleNamespace(metrics={})}, glyph_order=[]),
        table_map={"hmtx": TTFTable()},
    )

    assert font.advance_widths == []
    assert font.get_advance_width(0) == 250


def test_wave389_horizontal_header_and_metrics_populate_from_fonttools_shape() -> None:
    hhea = SimpleNamespace(
        tableVersion=0x00010000,
        ascent=700,
        descent=-200,
        lineGap=0,
        advanceWidthMax=1000,
        minLeftSideBearing=-2,
        minRightSideBearing=-3,
        xMaxExtent=900,
        caretSlopeRise=1,
        caretSlopeRun=0,
        metricDataFormat=0,
        numberOfHMetrics=2,
    )
    hmtx = SimpleNamespace(metrics={".notdef": (500, 0), "A": (600, 10), "B": (700, 20)})
    font = _font(
        _FakeTTFont({"hhea": hhea, "hmtx": hmtx}, glyph_order=[".notdef", "A", "B"])
    )

    header = font.get_horizontal_header()
    metrics = font.get_horizontal_metrics()

    assert header is not None
    assert header.get_number_of_h_metrics() == 2
    assert metrics is not None
    assert metrics.get_advance_width(2) == 600
    assert metrics.get_left_side_bearing(2) == 20
    assert font.get_advance_width(99) == 700
    assert font.get_horizontal_header() is header
    assert font.get_horizontal_metrics() is metrics


def test_wave389_maximum_profile_clamps_zero_component_depth_and_caches() -> None:
    maxp = SimpleNamespace(tableVersion=0x00010000, numGlyphs=4, maxComponentDepth=0)
    font = _font(_FakeTTFont({"maxp": maxp}))

    table = font.get_maximum_profile()

    assert table is not None
    assert table.get_version() == 1.0
    assert table.get_num_glyphs() == 4
    assert table.get_max_component_depth() == 1
    assert font.get_maximum_profile() is table


def test_wave389_vertical_metrics_populate_and_drive_advance_height() -> None:
    vhea = SimpleNamespace(
        tableVersion=0x00010000,
        ascent=880,
        descent=-120,
        lineGap=20,
        advanceHeightMax=1000,
        minTopSideBearing=-4,
        minBottomSideBearing=-5,
        yMaxExtent=900,
        caretSlopeRise=1,
        caretSlopeRun=0,
        caretOffset=0,
        metricDataFormat=0,
        numberOfVMetrics=2,
    )
    vmtx = SimpleNamespace(metrics={".notdef": (1000, 10), "A": (980, 12), "B": (970, 14)})
    font = _font(
        _FakeTTFont({"vhea": vhea, "vmtx": vmtx}, glyph_order=[".notdef", "A", "B"])
    )

    header = font.get_vertical_header()
    metrics = font.get_vertical_metrics()

    assert header is not None
    assert header.get_number_of_v_metrics() == 2
    assert metrics is not None
    assert metrics.get_advance_height(0) == 1000
    assert metrics.get_advance_height(2) == 980
    assert font.get_advance_height(2) == 980
    assert font.get_vertical_header() is header
    assert font.get_vertical_metrics() is metrics


def test_wave389_vmtx_without_vhea_returns_none() -> None:
    font = _font(_FakeTTFont({"vmtx": SimpleNamespace(metrics={})}))

    assert font.get_vertical_metrics() is None


def test_wave389_cmap_with_no_pdfbox_compatible_subtable_caches_none() -> None:
    cmap = SimpleNamespace(getcmap=lambda _platform_id, _encoding_id: None)
    font = _font(_FakeTTFont({"cmap": cmap}))

    assert font.get_unicode_cmap_subtable() is None
    assert font.get_unicode_cmap_subtable() is None


def test_wave389_naming_skips_records_that_do_not_decode() -> None:
    class BadNameRecord:
        platformID = 3
        platEncID = 1
        langID = 0x409
        nameID = 6

        def toUnicode(self) -> str:  # noqa: N802 - fontTools API
            raise ValueError("bad name record")

    font = _font(_FakeTTFont({"name": SimpleNamespace(names=[BadNameRecord()])}))

    naming = font.get_naming()

    assert naming is not None
    assert naming.get_post_script_name() is None


def test_wave389_fixed_point_and_font_matrix_zero_units_branch() -> None:
    font = _font()
    font.get_units_per_em = lambda: 0  # type: ignore[method-assign]

    assert TrueTypeFont._fixed_16_16(0x00018000) == 1.5  # noqa: SLF001
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
