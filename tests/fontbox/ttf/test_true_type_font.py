"""Hand-written tests for the round-out accessors on
:class:`pypdfbox.fontbox.ttf.TrueTypeFont`.

Exercises the ``get_table`` / ``get_table_bytes`` / ``get_naming`` /
``get_post_script`` / ``get_os2_windows`` / ``get_index_to_location`` /
``get_cmap`` / ``name_to_gid`` / ``get_path`` / ``close`` /
``is_post_script`` / ``is_supported`` / ``get_original_data`` /
``get_bounding_box`` accessors against the bundled LiberationSans
fixture (a real TTF — synthesising one in-memory would require
re-implementing every table writer fontTools already ships).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pypdfbox.fontbox.font_box_font import FontBoxFont
from pypdfbox.fontbox.ttf import (
    DigitalSignatureTable,
    IndexToLocationTable,
    KerningTable,
    NamingTable,
    OS2WindowsMetricsTable,
    PostScriptTable,
    TrueTypeFont,
    TTFTable,
)
from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_sans() -> TrueTypeFont:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return TrueTypeFont.from_bytes(FIXTURE.read_bytes())


# ---------- raw table accessors ------------------------------------------


def test_get_table_returns_directory_entry(liberation_sans: TrueTypeFont) -> None:
    head = liberation_sans.get_table("head")
    assert head is not None
    assert isinstance(head, TTFTable)
    assert head.get_tag() == "head"
    # head is a fixed-size 54-byte table.
    assert head.get_length() == 54


def test_get_table_unknown_tag_returns_none(liberation_sans: TrueTypeFont) -> None:
    assert liberation_sans.get_table("ZZZZ") is None


def test_get_tables_returns_directory_entries(liberation_sans: TrueTypeFont) -> None:
    tables = liberation_sans.get_tables()
    table_map = liberation_sans.get_table_map()
    assert tables
    assert len(tables) == len(table_map)
    assert {table.get_tag() for table in tables} == set(table_map)


def test_pdfbox_camelcase_table_aliases(liberation_sans: TrueTypeFont) -> None:
    head = liberation_sans.getTable("head")

    assert head is liberation_sans.get_table("head")
    assert liberation_sans.getTables() == liberation_sans.get_tables()
    assert head is not None


def test_get_table_bytes_matches_directory_length(
    liberation_sans: TrueTypeFont,
) -> None:
    raw = liberation_sans.get_table_bytes("head")
    assert raw is not None
    assert isinstance(raw, bytes)
    assert len(raw) == 54
    # head magic number (offset 12, uint32 BE = 0x5F0F3CF5).
    assert raw[12:16] == b"\x5F\x0F\x3C\xF5"


def test_get_table_bytes_accepts_table_entry(liberation_sans: TrueTypeFont) -> None:
    head = liberation_sans.get_table("head")
    assert head is not None
    raw_from_entry = liberation_sans.get_table_bytes(head)
    raw_from_tag = liberation_sans.get_table_bytes("head")
    assert raw_from_entry == raw_from_tag


def test_get_table_bytes_unknown_returns_none(liberation_sans: TrueTypeFont) -> None:
    assert liberation_sans.get_table_bytes("ZZZZ") is None


# ---------- typed table accessors ----------------------------------------


def test_get_header_preserves_long_datetime_metadata(
    liberation_sans: TrueTypeFont,
) -> None:
    header = liberation_sans.get_header()
    assert header is not None
    assert header.get_created() == datetime(2010, 6, 18, 10, 23, 22, tzinfo=UTC)
    assert header.get_modified() == datetime(2021, 9, 30, 9, 4, 22, tzinfo=UTC)


def test_get_naming_returns_populated_table(liberation_sans: TrueTypeFont) -> None:
    nt = liberation_sans.get_naming()
    assert nt is not None
    assert isinstance(nt, NamingTable)
    assert nt.get_post_script_name() == "LiberationSans"
    assert nt.get_font_family() == "Liberation Sans"
    # Plenty of records in a real font (Latin / metadata / vendor).
    assert len(nt.get_name_records()) > 5


def test_get_naming_is_cached(liberation_sans: TrueTypeFont) -> None:
    a = liberation_sans.get_naming()
    b = liberation_sans.get_naming()
    assert a is b


def test_pdfbox_camelcase_scalar_name_aliases(liberation_sans: TrueTypeFont) -> None:
    assert liberation_sans.getUnitsPerEm() == liberation_sans.get_units_per_em()
    assert liberation_sans.getNumberOfGlyphs() == liberation_sans.get_number_of_glyphs()
    assert liberation_sans.getName() == liberation_sans.get_name()
    assert liberation_sans.getFamilyName() == liberation_sans.get_family_name()
    assert liberation_sans.getFullName() == liberation_sans.get_full_name()
    assert liberation_sans.getVersion() == liberation_sans.get_version()


def test_get_post_script(liberation_sans: TrueTypeFont) -> None:
    post = liberation_sans.get_post_script()
    assert post is not None
    assert isinstance(post, PostScriptTable)
    assert post.get_italic_angle() == 0.0
    # Liberation Sans uses post format 2.0 (per-glyph names).
    assert post.get_format_type() == 2.0
    assert post.get_underline_thickness() > 0
    glyph_names = post.get_glyph_names()
    assert glyph_names is not None
    assert len(glyph_names) > 0
    # gid 0 is .notdef in every conforming font.
    assert glyph_names[0] == ".notdef"


def test_get_os2_windows(liberation_sans: TrueTypeFont) -> None:
    os2 = liberation_sans.get_os2_windows()
    assert os2 is not None
    assert isinstance(os2, OS2WindowsMetricsTable)
    assert os2.get_weight_class() == 400
    assert os2.get_width_class() == 5
    panose = os2.get_panose()
    assert isinstance(panose, bytes)
    assert len(panose) == 10


def test_get_index_to_location(liberation_sans: TrueTypeFont) -> None:
    loca = liberation_sans.get_index_to_location()
    assert loca is not None
    assert isinstance(loca, IndexToLocationTable)
    offsets = loca.get_offsets()
    # loca holds num_glyphs + 1 entries.
    assert len(offsets) == liberation_sans.get_number_of_glyphs() + 1
    # Offsets are monotonically non-decreasing.
    for prev, curr in zip(offsets, offsets[1:], strict=False):
        assert curr >= prev


def test_get_cmap_alias(liberation_sans: TrueTypeFont) -> None:
    a = liberation_sans.get_cmap()
    b = liberation_sans.get_unicode_cmap_subtable()
    assert a is b
    assert isinstance(a, CmapSubtable)


# ---------- name-to-gid lookup -------------------------------------------


def test_name_to_gid_known_glyph(liberation_sans: TrueTypeFont) -> None:
    # ``A`` is present in every conforming Latin font.
    gid = liberation_sans.name_to_gid("A")
    assert gid > 0


def test_name_to_gid_unknown_returns_zero(liberation_sans: TrueTypeFont) -> None:
    assert liberation_sans.name_to_gid("definitelyNotAGlyphName") == 0


def test_name_to_gid_empty_returns_zero(liberation_sans: TrueTypeFont) -> None:
    assert liberation_sans.name_to_gid("") == 0


# ---------- glyph helpers ------------------------------------------------


def test_get_path_for_known_gid(liberation_sans: TrueTypeFont) -> None:
    gid = liberation_sans.name_to_gid("A")
    pen = liberation_sans.get_path(gid)
    assert pen is not None
    # RecordingPen.value is a list of (op, args) tuples.
    assert hasattr(pen, "value")
    assert isinstance(pen.value, list)
    # ``A`` has at least one moveTo — i.e. its outline is non-empty.
    assert any(op == "moveTo" for op, _args in pen.value)


def test_get_path_out_of_range_returns_none(liberation_sans: TrueTypeFont) -> None:
    n = liberation_sans.get_number_of_glyphs()
    assert liberation_sans.get_path(n + 100) is None


def test_get_path_accepts_glyph_name(liberation_sans: TrueTypeFont) -> None:
    by_gid = liberation_sans.get_path(liberation_sans.name_to_gid("A"))
    by_name = liberation_sans.get_path("A")
    assert by_name is not None
    assert by_gid is not None
    assert by_name.value == by_gid.value


def test_get_path_unknown_name_returns_none(liberation_sans: TrueTypeFont) -> None:
    assert liberation_sans.get_path("definitelyNotAGlyphName") is None


def test_has_glyph_uses_real_glyph_names(liberation_sans: TrueTypeFont) -> None:
    assert liberation_sans.has_glyph("A") is True
    assert liberation_sans.has_glyph(".notdef") is False
    assert liberation_sans.has_glyph("definitelyNotAGlyphName") is False


def test_get_width_with_name_returns_advance_width(
    liberation_sans: TrueTypeFont,
) -> None:
    gid = liberation_sans.name_to_gid("A")
    assert liberation_sans.get_width("A") == float(liberation_sans.get_advance_width(gid))
    assert liberation_sans.get_width("definitelyNotAGlyphName") == 0.0


def test_get_bounding_box_alias(liberation_sans: TrueTypeFont) -> None:
    bbox = liberation_sans.get_bounding_box()
    assert bbox == liberation_sans.get_font_bbox()


def test_get_font_matrix_scales_by_units_per_em(
    liberation_sans: TrueTypeFont,
) -> None:
    scale = 1.0 / liberation_sans.get_units_per_em()
    assert liberation_sans.get_font_matrix() == [scale, 0.0, 0.0, scale, 0.0, 0.0]


def test_truetype_font_satisfies_fontbox_protocol(
    liberation_sans: TrueTypeFont,
) -> None:
    assert isinstance(liberation_sans, FontBoxFont)


# ---------- font-level metadata ------------------------------------------


def test_get_original_data_round_trips(liberation_sans: TrueTypeFont) -> None:
    raw = liberation_sans.get_original_data()
    assert isinstance(raw, bytes)
    assert raw == FIXTURE.read_bytes()
    assert liberation_sans.get_original_data_size() == len(raw)


def test_is_post_script_false_for_truetype(liberation_sans: TrueTypeFont) -> None:
    assert liberation_sans.is_post_script() is False


def test_is_supported_for_complete_font(liberation_sans: TrueTypeFont) -> None:
    assert liberation_sans.is_supported() is True


# ---------- aliases for kerning / DSIG -----------------------------------


def test_get_kerning_alias(liberation_sans: TrueTypeFont) -> None:
    a = liberation_sans.get_kerning()
    b = liberation_sans.get_kerning_table()
    # Both calls share the cached state — they're either both ``None``
    # (no kern table) or the same wrapper instance.
    assert a is b
    if a is not None:
        assert isinstance(a, KerningTable)


def test_get_digital_signature_alias(liberation_sans: TrueTypeFont) -> None:
    a = liberation_sans.get_digital_signature()
    b = liberation_sans.get_dsig()
    assert a is b
    if a is not None:
        assert isinstance(a, DigitalSignatureTable)


# ---------- close / context manager --------------------------------------


def test_close_is_idempotent() -> None:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    font = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    font.close()
    # Calling close() twice must not raise.
    font.close()


def test_context_manager_closes() -> None:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    with TrueTypeFont.from_bytes(FIXTURE.read_bytes()) as font:
        assert font.get_units_per_em() > 0
    # ``__exit__`` invokes ``close``.
    assert font._closed is True  # noqa: SLF001


# ---------- get_advance_height ------------------------------------------


def test_get_advance_height_falls_back_when_no_vmtx(
    liberation_sans: TrueTypeFont,
) -> None:
    # LiberationSans has no ``vmtx`` table — upstream returns 250 in this
    # case (matches ``VerticalMetricsTable`` default fallback).
    assert liberation_sans.get_vertical_metrics() is None
    assert liberation_sans.get_advance_height(0) == 250
    assert liberation_sans.get_advance_height(123) == 250


# ---------- get_table_n_bytes -------------------------------------------


def test_get_table_n_bytes_caps_at_table_length(
    liberation_sans: TrueTypeFont,
) -> None:
    full = liberation_sans.get_table_bytes("head")
    assert full is not None
    # limit larger than the table -> entire table.
    larger = liberation_sans.get_table_n_bytes("head", 1024)
    assert larger == full
    # limit smaller than the table -> truncated prefix.
    head_prefix = liberation_sans.get_table_n_bytes("head", 16)
    assert head_prefix is not None
    assert head_prefix == full[:16]
    assert len(head_prefix) == 16


def test_get_table_n_bytes_negative_limit_yields_empty(
    liberation_sans: TrueTypeFont,
) -> None:
    assert liberation_sans.get_table_n_bytes("head", -5) == b""


def test_get_table_n_bytes_unknown_table(liberation_sans: TrueTypeFont) -> None:
    assert liberation_sans.get_table_n_bytes("ZZZZ", 16) is None


def test_get_table_n_bytes_accepts_table_entry(
    liberation_sans: TrueTypeFont,
) -> None:
    head = liberation_sans.get_table("head")
    assert head is not None
    by_entry = liberation_sans.get_table_n_bytes(head, 8)
    by_tag = liberation_sans.get_table_n_bytes("head", 8)
    assert by_entry == by_tag
    assert by_entry is not None
    assert len(by_entry) == 8


# ---------- GSUB feature toggles ----------------------------------------


def test_enable_gsub_default(liberation_sans: TrueTypeFont) -> None:
    # Each access mints a wrapper — instantiate one to confirm default.
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    f = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    assert f.is_enable_gsub() is True
    f.set_enable_gsub(False)
    assert f.is_enable_gsub() is False
    f.set_enable_gsub(True)
    assert f.is_enable_gsub() is True


def test_enable_disable_gsub_feature() -> None:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    f = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    assert f.get_enabled_gsub_features() == []
    f.enable_gsub_feature("liga")
    f.enable_gsub_feature("kern")
    assert f.get_enabled_gsub_features() == ["liga", "kern"]
    f.disable_gsub_feature("liga")
    assert f.get_enabled_gsub_features() == ["kern"]
    # Disabling an absent tag is a silent no-op (matches upstream).
    f.disable_gsub_feature("never-added")
    assert f.get_enabled_gsub_features() == ["kern"]


def test_enable_vertical_substitutions_registers_vrt2_and_vert() -> None:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    f = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    f.enable_vertical_substitutions()
    assert f.get_enabled_gsub_features() == ["vrt2", "vert"]


def test_enabled_features_isolated_per_font() -> None:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    f1 = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    f2 = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    f1.enable_gsub_feature("liga")
    assert f1.get_enabled_gsub_features() == ["liga"]
    # The second font must not see ``liga`` — features are per-instance.
    assert f2.get_enabled_gsub_features() == []
