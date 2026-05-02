from __future__ import annotations

import struct
from datetime import UTC, datetime

from pypdfbox.fontbox.ttf.header_table import HeaderTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

# Two LONGDATETIME values with known meaning.
# 2020-01-01 00:00:00 UTC = 3,660,681,600 seconds since 1904-01-01.
_CREATED_SECS = 3_660_681_600
# 2021-06-15 12:34:56 UTC, computed once and frozen here:
_MODIFIED_SECS = 3_706_605_296


def _build_head(
    *,
    version: tuple[int, int] = (1, 0),
    font_revision: tuple[int, int] = (2, 0),
    check_sum_adjustment: int = 0xDEADBEEF,
    magic_number: int = 0x5F0F3CF5,
    flags: int = 0x000B,
    units_per_em: int = 2048,
    created_secs: int = _CREATED_SECS,
    modified_secs: int = _MODIFIED_SECS,
    x_min: int = -100,
    y_min: int = -200,
    x_max: int = 1500,
    y_max: int = 1800,
    mac_style: int = HeaderTable.MAC_STYLE_BOLD | HeaderTable.MAC_STYLE_ITALIC,
    lowest_rec_ppem: int = 9,
    font_direction_hint: int = 2,
    index_to_loc_format: int = 1,
    glyph_data_format: int = 0,
) -> bytes:
    return struct.pack(
        ">hHhHIIHHqqhhhhHHhhh",
        version[0],
        version[1],
        font_revision[0],
        font_revision[1],
        check_sum_adjustment,
        magic_number,
        flags,
        units_per_em,
        created_secs,
        modified_secs,
        x_min,
        y_min,
        x_max,
        y_max,
        mac_style,
        lowest_rec_ppem,
        font_direction_hint,
        index_to_loc_format,
        glyph_data_format,
    )


def test_payload_is_exactly_54_bytes() -> None:
    assert len(_build_head()) == 54


def test_read_full_record() -> None:
    table = HeaderTable()
    table.read(None, MemoryTTFDataStream(_build_head()))  # type: ignore[arg-type]

    assert table.get_initialized() is True
    assert table.get_version() == 1.0
    assert table.get_font_revision() == 2.0
    assert table.get_check_sum_adjustment() == 0xDEADBEEF
    assert table.get_magic_number() == 0x5F0F3CF5
    assert table.get_flags() == 0x000B
    assert table.get_units_per_em() == 2048
    assert table.get_created() == datetime(2020, 1, 1, tzinfo=UTC)
    assert table.get_modified() == datetime(2021, 6, 15, 12, 34, 56, tzinfo=UTC)
    assert table.get_x_min() == -100
    assert table.get_y_min() == -200
    assert table.get_x_max() == 1500
    assert table.get_y_max() == 1800
    assert table.get_mac_style() == 3
    assert table.get_lowest_rec_ppem() == 9
    assert table.get_font_direction_hint() == 2
    assert table.get_index_to_loc_format() == 1
    assert table.get_glyph_data_format() == 0


def test_tag_class_constants() -> None:
    assert HeaderTable.TAG == "head"
    assert HeaderTable.MAC_STYLE_BOLD == 1
    assert HeaderTable.MAC_STYLE_ITALIC == 2


def test_fixed_point_fractional_version() -> None:
    # version 1.5 → whole=1, frac=0x8000 (== 0.5)
    raw = _build_head(version=(1, 0x8000))
    table = HeaderTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_version() == 1.5


def test_long_date_time_epoch_zero() -> None:
    raw = _build_head(created_secs=0, modified_secs=0)
    table = HeaderTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_created() == datetime(1904, 1, 1, tzinfo=UTC)
    assert table.get_modified() == datetime(1904, 1, 1, tzinfo=UTC)


def test_defaults_before_read() -> None:
    table = HeaderTable()
    assert table.get_initialized() is False
    assert table.get_version() == 0.0
    assert table.get_units_per_em() == 0
    assert table.get_created() is None
    assert table.get_modified() is None


def test_upstream_header_setters_round_trip() -> None:
    table = HeaderTable()
    created = datetime(2022, 2, 3, 4, 5, 6, tzinfo=UTC)
    modified = datetime(2023, 3, 4, 5, 6, 7, tzinfo=UTC)

    table.set_version(1.5)
    table.set_font_revision(2.25)
    table.set_check_sum_adjustment(0x01020304)
    table.set_magic_number(0x5F0F3CF5)
    table.set_flags(0x001B)
    table.set_units_per_em(1000)
    table.set_created(created)
    table.set_modified(modified)
    table.set_x_min(-10)
    table.set_y_min(-20)
    table.set_x_max(900)
    table.set_y_max(1100)
    table.set_mac_style(HeaderTable.MAC_STYLE_BOLD)
    table.set_lowest_rec_ppem(8)
    table.set_font_direction_hint(2)
    table.set_index_to_loc_format(1)
    table.set_glyph_data_format(0)

    assert table.get_version() == 1.5
    assert table.get_font_revision() == 2.25
    assert table.get_check_sum_adjustment() == 0x01020304
    assert table.get_magic_number() == 0x5F0F3CF5
    assert table.get_flags() == 0x001B
    assert table.get_units_per_em() == 1000
    assert table.get_created() == created
    assert table.get_modified() == modified
    assert table.get_x_min() == -10
    assert table.get_y_min() == -20
    assert table.get_x_max() == 900
    assert table.get_y_max() == 1100
    assert table.get_mac_style() == HeaderTable.MAC_STYLE_BOLD
    assert table.get_lowest_rec_ppem() == 8
    assert table.get_font_direction_hint() == 2
    assert table.get_index_to_loc_format() == 1
    assert table.get_glyph_data_format() == 0


def test_signed_bbox_handles_negatives() -> None:
    raw = _build_head(x_min=-32768, y_min=-32768, x_max=32767, y_max=32767)
    table = HeaderTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_x_min() == -32768
    assert table.get_y_min() == -32768
    assert table.get_x_max() == 32767
    assert table.get_y_max() == 32767


def test_is_bold_predicate() -> None:
    table = HeaderTable()
    assert table.is_bold() is False  # default
    table.set_mac_style(HeaderTable.MAC_STYLE_BOLD)
    assert table.is_bold() is True
    assert table.is_italic() is False
    # Bold + Italic both set.
    table.set_mac_style(HeaderTable.MAC_STYLE_BOLD | HeaderTable.MAC_STYLE_ITALIC)
    assert table.is_bold() is True
    assert table.is_italic() is True


def test_is_italic_predicate() -> None:
    table = HeaderTable()
    assert table.is_italic() is False  # default
    table.set_mac_style(HeaderTable.MAC_STYLE_ITALIC)
    assert table.is_italic() is True
    assert table.is_bold() is False


def test_mac_style_predicates_ignore_extra_bits() -> None:
    # Bits beyond Bold/Italic should not perturb the predicates.
    table = HeaderTable()
    table.set_mac_style(0xFFFC)  # Bold/Italic both clear, all others set
    assert table.is_bold() is False
    assert table.is_italic() is False


def test_get_bbox_tuple() -> None:
    raw = _build_head(x_min=-100, y_min=-200, x_max=1500, y_max=1800)
    table = HeaderTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_bbox() == (-100, -200, 1500, 1800)


def test_get_bbox_default_zeros() -> None:
    table = HeaderTable()
    assert table.get_bbox() == (0, 0, 0, 0)
