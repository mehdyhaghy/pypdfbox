from __future__ import annotations

import struct

from pypdfbox.fontbox.ttf.os2_windows_metrics_table import OS2WindowsMetricsTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

# Layout (counts in bytes):
#   header (uint16 + 15 * int16/uint16) = 32 bytes
#   panose (10 bytes)
#   unicode range 1..4 (4 * uint32) = 16 bytes
#   achVendID (4 chars) = 4 bytes
#   fsSelection + firstCharIndex + lastCharIndex (3 * uint16) = 6 bytes
#   typo asc/desc/lineGap + winAsc/Desc (5 * int16/uint16) = 10 bytes
# v0 grand total = 78 bytes
# v1 adds 2 * uint32 (code page ranges) = +8 → 86 bytes
# v2..v4 adds 5 more shorts = +10 → 96 bytes


def _build_v0(
    *,
    version: int = 0,
    average_char_width: int = 500,
    weight_class: int = OS2WindowsMetricsTable.WEIGHT_CLASS_NORMAL,
    width_class: int = OS2WindowsMetricsTable.WIDTH_CLASS_MEDIUM,
    fs_type: int = 0,
    panose: bytes = b"\x02\x0b\x06\x03\x05\x04\x05\x02\x02\x04",
    unicode_range1: int = 0xE00002FF,
    unicode_range2: int = 0x500000FF,
    unicode_range3: int = 0,
    unicode_range4: int = 0,
    ach_vend_id: str = "ADBE",
    fs_selection: int = 0x0040,
    first_char_index: int = 32,
    last_char_index: int = 0xFFFD,
    typo_ascender: int = 800,
    typo_descender: int = -200,
    typo_line_gap: int = 90,
    win_ascent: int = 1000,
    win_descent: int = 250,
) -> bytes:
    assert len(panose) == 10
    assert len(ach_vend_id) == 4
    return (
        struct.pack(
            ">HhHHhhhhhhhhhhhh",
            version,
            average_char_width,
            weight_class,
            width_class,
            fs_type,
            10,  # subscript_x_size
            12,  # subscript_y_size
            0,  # subscript_x_offset
            -50,  # subscript_y_offset
            10,  # superscript_x_size
            12,  # superscript_y_size
            0,  # superscript_x_offset
            500,  # superscript_y_offset
            50,  # strikeout_size
            260,  # strikeout_position
            8,  # family_class
        )
        + panose
        + struct.pack(
            ">IIII",
            unicode_range1,
            unicode_range2,
            unicode_range3,
            unicode_range4,
        )
        + ach_vend_id.encode("iso-8859-1")
        + struct.pack(
            ">HHHhhhHH",
            fs_selection,
            first_char_index,
            last_char_index,
            typo_ascender,
            typo_descender,
            typo_line_gap,
            win_ascent,
            win_descent,
        )
    )


def _build_v1(
    *, code_page_range1: int = 0x0000019F, code_page_range2: int = 0, **kwargs: int
) -> bytes:
    kwargs.setdefault("version", 1)
    return _build_v0(**kwargs) + struct.pack(  # type: ignore[arg-type]
        ">II", code_page_range1, code_page_range2
    )


def _build_v2(
    *,
    sx_height: int = 500,
    s_cap_height: int = 700,
    us_default_char: int = 0,
    us_break_char: int = 32,
    us_max_context: int = 1,
    code_page_range1: int = 0x0000019F,
    code_page_range2: int = 0,
    **kwargs: int,
) -> bytes:
    kwargs.setdefault("version", 2)
    return (
        _build_v0(**kwargs)  # type: ignore[arg-type]
        + struct.pack(">II", code_page_range1, code_page_range2)
        + struct.pack(
            ">hhHHH",
            sx_height,
            s_cap_height,
            us_default_char,
            us_break_char,
            us_max_context,
        )
    )


def test_payload_sizes_match_spec() -> None:
    assert len(_build_v0()) == 78
    assert len(_build_v1()) == 86
    assert len(_build_v2()) == 96


def test_tag_and_class_constants() -> None:
    assert OS2WindowsMetricsTable.TAG == "OS/2"
    assert OS2WindowsMetricsTable.WEIGHT_CLASS_NORMAL == 400
    assert OS2WindowsMetricsTable.WEIGHT_CLASS_BOLD == 700
    assert OS2WindowsMetricsTable.WIDTH_CLASS_MEDIUM == 5
    assert OS2WindowsMetricsTable.FAMILY_CLASS_SANS_SERIF == 8
    assert OS2WindowsMetricsTable.FSTYPE_NO_SUBSETTING == 0x0100


def test_defaults_before_read() -> None:
    table = OS2WindowsMetricsTable()
    assert table.get_initialized() is False
    assert table.get_version() == 0
    assert table.get_panose() == b"\x00" * 10
    assert table.get_ach_vend_id() == "XXXX"


def test_v0_round_trip() -> None:
    raw = _build_v0()
    table = OS2WindowsMetricsTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_initialized() is True
    assert table.get_version() == 0
    assert table.get_average_char_width() == 500
    assert table.get_weight_class() == OS2WindowsMetricsTable.WEIGHT_CLASS_NORMAL
    assert table.get_width_class() == OS2WindowsMetricsTable.WIDTH_CLASS_MEDIUM
    assert table.get_fs_type() == 0
    assert table.get_subscript_x_size() == 10
    assert table.get_subscript_y_size() == 12
    assert table.get_subscript_x_offset() == 0
    assert table.get_subscript_y_offset() == -50
    assert table.get_superscript_x_size() == 10
    assert table.get_superscript_y_size() == 12
    assert table.get_superscript_x_offset() == 0
    assert table.get_superscript_y_offset() == 500
    assert table.get_strikeout_size() == 50
    assert table.get_strikeout_position() == 260
    assert table.get_family_class() == 8
    assert table.get_panose() == b"\x02\x0b\x06\x03\x05\x04\x05\x02\x02\x04"
    assert table.get_unicode_range1() == 0xE00002FF
    assert table.get_unicode_range2() == 0x500000FF
    assert table.get_unicode_range3() == 0
    assert table.get_unicode_range4() == 0
    assert table.get_ach_vend_id() == "ADBE"
    assert table.get_fs_selection() == 0x0040
    assert table.get_first_char_index() == 32
    assert table.get_last_char_index() == 0xFFFD
    assert table.get_typo_ascender() == 800
    assert table.get_typo_descender() == -200
    assert table.get_typo_line_gap() == 90
    assert table.get_win_ascent() == 1000
    assert table.get_win_descent() == 250
    # v0 leaves these zeroed.
    assert table.get_code_page_range1() == 0
    assert table.get_code_page_range2() == 0
    assert table.get_height() == 0
    assert table.get_cap_height() == 0


def test_v1_includes_codepage_ranges() -> None:
    raw = _build_v1(code_page_range1=0x0000019F, code_page_range2=0xDEAD0000)
    table = OS2WindowsMetricsTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_version() == 1
    assert table.get_code_page_range1() == 0x0000019F
    assert table.get_code_page_range2() == 0xDEAD0000
    # v1 still doesn't have x-height etc.
    assert table.get_height() == 0
    assert table.get_cap_height() == 0


def test_v2_includes_x_height_and_friends() -> None:
    raw = _build_v2(
        sx_height=480,
        s_cap_height=720,
        us_default_char=0,
        us_break_char=32,
        us_max_context=3,
    )
    table = OS2WindowsMetricsTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_version() == 2
    assert table.get_height() == 480
    assert table.get_cap_height() == 720
    assert table.get_default_char() == 0
    assert table.get_break_char() == 32
    assert table.get_max_context() == 3


def test_v3_v4_v5_parse_with_v2_layout() -> None:
    # The parser only branches on >= 1 and >= 2; v3/4/5 use the v2 byte layout
    # without adding new fields the parser knows about.
    for version in (3, 4, 5):
        raw = _build_v2(version=version)
        table = OS2WindowsMetricsTable()
        table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
        assert table.get_version() == version
        assert table.get_initialized() is True
        assert table.get_height() == 500


def test_truncated_legacy_table_below_typo_section() -> None:
    # Drop the trailing typo/win block (10 bytes) → only 68 bytes available.
    raw = _build_v0()[:68]
    table = OS2WindowsMetricsTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    # Parser must swallow the EOF and still mark itself initialized.
    assert table.get_initialized() is True
    # Fields that were available are populated.
    assert table.get_first_char_index() == 32
    # Fields that weren't available stay at their defaults.
    assert table.get_typo_ascender() == 0
    assert table.get_win_ascent() == 0


def test_truncated_v1_downgrades_to_v0() -> None:
    # Claim v1 in the header but provide only the v0-sized payload.
    raw = _build_v0(version=1)
    assert len(raw) == 78
    table = OS2WindowsMetricsTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    # Per the source: failure to read the v1 codepage ranges resets version to 0.
    assert table.get_version() == 0
    assert table.get_initialized() is True
    assert table.get_code_page_range1() == 0
    assert table.get_code_page_range2() == 0


def test_truncated_v2_downgrades_to_v1() -> None:
    # Claim v2 in the header but provide only the v1-sized payload.
    raw = _build_v1(version=2)
    assert len(raw) == 86
    table = OS2WindowsMetricsTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    # Per the source: failure to read the v2 metrics block resets version to 1.
    assert table.get_version() == 1
    assert table.get_initialized() is True
    # v1 fields should still be populated from before the EOF.
    assert table.get_code_page_range1() == 0x0000019F
    # v2 fields stay at their defaults.
    assert table.get_height() == 0
    assert table.get_cap_height() == 0


def test_panose_length_is_ten() -> None:
    table = OS2WindowsMetricsTable()
    table.read(None, MemoryTTFDataStream(_build_v0()))  # type: ignore[arg-type]
    assert len(table.get_panose()) == 10


def test_ach_vend_id_decoded_as_iso_8859_1() -> None:
    raw = _build_v0(ach_vend_id="ABCD")
    table = OS2WindowsMetricsTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_ach_vend_id() == "ABCD"


def test_upstream_metric_setters_round_trip() -> None:
    table = OS2WindowsMetricsTable()
    panose = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a"

    table.set_version(2)
    table.set_average_char_width(511)
    table.set_weight_class(OS2WindowsMetricsTable.WEIGHT_CLASS_BOLD)
    table.set_width_class(OS2WindowsMetricsTable.WIDTH_CLASS_EXPANDED)
    table.set_fs_type(OS2WindowsMetricsTable.FSTYPE_PREVIEW_AND_PRINT)
    table.set_subscript_x_size(10)
    table.set_subscript_y_size(11)
    table.set_subscript_x_offset(-12)
    table.set_subscript_y_offset(-13)
    table.set_superscript_x_size(14)
    table.set_superscript_y_size(15)
    table.set_superscript_x_offset(16)
    table.set_superscript_y_offset(17)
    table.set_strikeout_size(18)
    table.set_strikeout_position(19)
    table.set_family_class(OS2WindowsMetricsTable.FAMILY_CLASS_SANS_SERIF)
    table.set_panose(panose)
    table.set_unicode_range1(0x01020304)
    table.set_unicode_range2(0x05060708)
    table.set_unicode_range3(0x090A0B0C)
    table.set_unicode_range4(0x0D0E0F10)
    table.set_ach_vend_id("TEST")
    table.set_fs_selection(0x0040)
    table.set_first_char_index(32)
    table.set_last_char_index(0xFFFD)
    table.set_typo_ascender(800)
    table.set_typo_descender(-200)
    table.set_typo_line_gap(90)
    table.set_win_ascent(1000)
    table.set_win_descent(250)
    table.set_code_page_range1(0x0000019F)
    table.set_code_page_range2(0x80000000)

    assert table.get_version() == 2
    assert table.get_average_char_width() == 511
    assert table.get_weight_class() == OS2WindowsMetricsTable.WEIGHT_CLASS_BOLD
    assert table.get_width_class() == OS2WindowsMetricsTable.WIDTH_CLASS_EXPANDED
    assert table.get_fs_type() == OS2WindowsMetricsTable.FSTYPE_PREVIEW_AND_PRINT
    assert table.get_subscript_x_size() == 10
    assert table.get_subscript_y_size() == 11
    assert table.get_subscript_x_offset() == -12
    assert table.get_subscript_y_offset() == -13
    assert table.get_superscript_x_size() == 14
    assert table.get_superscript_y_size() == 15
    assert table.get_superscript_x_offset() == 16
    assert table.get_superscript_y_offset() == 17
    assert table.get_strikeout_size() == 18
    assert table.get_strikeout_position() == 19
    assert table.get_family_class() == OS2WindowsMetricsTable.FAMILY_CLASS_SANS_SERIF
    assert table.get_panose() == panose
    assert table.get_unicode_range1() == 0x01020304
    assert table.get_unicode_range2() == 0x05060708
    assert table.get_unicode_range3() == 0x090A0B0C
    assert table.get_unicode_range4() == 0x0D0E0F10
    assert table.get_ach_vend_id() == "TEST"
    assert table.get_fs_selection() == 0x0040
    assert table.get_first_char_index() == 32
    assert table.get_last_char_index() == 0xFFFD
    assert table.get_typo_ascender() == 800
    assert table.get_typo_descender() == -200
    assert table.get_typo_line_gap() == 90
    assert table.get_win_ascent() == 1000
    assert table.get_win_descent() == 250
    assert table.get_code_page_range1() == 0x0000019F
    assert table.get_code_page_range2() == 0x80000000
