from __future__ import annotations

import struct

from pypdfbox.fontbox.ttf.name_record import NameRecord
from pypdfbox.fontbox.ttf.naming_table import NamingTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


class _StubTTF:
    """Minimal duck-typed TrueTypeFont — NamingTable.read() never touches it
    directly, but ``NameRecord.init_data`` accepts the param."""


def _build_name_table(records: list[tuple[int, int, int, int, bytes]]) -> bytes:
    """records: list of (platform_id, encoding_id, language_id, name_id, raw_bytes)."""
    n = len(records)
    header = struct.pack(">HHH", 0, n, 6 + n * 12)
    string_pool = b""
    record_blobs: list[bytes] = []
    for plat, enc, lang, name_id, raw in records:
        offset_in_pool = len(string_pool)
        record_blobs.append(struct.pack(
            ">HHHHHH", plat, enc, lang, name_id, len(raw), offset_in_pool,
        ))
        string_pool += raw
    return header + b"".join(record_blobs) + string_pool


def _read(blob: bytes) -> NamingTable:
    table = NamingTable()
    table.set_offset(0)
    table.set_length(len(blob))
    table.read(_StubTTF(), MemoryTTFDataStream(blob))  # type: ignore[arg-type]
    return table


def test_read_single_windows_unicode_record() -> None:
    name_bytes = "Helvetica".encode("utf-16-be")
    blob = _build_name_table([(
        NameRecord.PLATFORM_WINDOWS,
        NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
        NameRecord.LANGUAGE_WINDOWS_EN_US,
        NameRecord.NAME_FONT_FAMILY_NAME,
        name_bytes,
    )])
    t = _read(blob)
    assert t.get_initialized() is True
    assert len(t.get_name_records()) == 1
    name = t.get_name(
        NameRecord.NAME_FONT_FAMILY_NAME,
        NameRecord.PLATFORM_WINDOWS,
        NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
        NameRecord.LANGUAGE_WINDOWS_EN_US,
    )
    assert name == "Helvetica"
    assert t.get_font_family() == "Helvetica"


def test_get_name_returns_none_for_missing_lookup() -> None:
    blob = _build_name_table([(
        NameRecord.PLATFORM_WINDOWS,
        NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
        NameRecord.LANGUAGE_WINDOWS_EN_US,
        NameRecord.NAME_FONT_FAMILY_NAME,
        "X".encode("utf-16-be"),
    )])
    t = _read(blob)
    assert t.get_name(99, 0, 0, 0) is None
    assert t.get_name(NameRecord.NAME_FONT_FAMILY_NAME, 99, 0, 0) is None
    assert t.get_name(NameRecord.NAME_FONT_FAMILY_NAME,
                      NameRecord.PLATFORM_WINDOWS, 99, 0) is None
    assert t.get_name(NameRecord.NAME_FONT_FAMILY_NAME,
                      NameRecord.PLATFORM_WINDOWS,
                      NameRecord.ENCODING_WINDOWS_UNICODE_BMP, 99) is None


def test_family_subfamily_postscript_name() -> None:
    blob = _build_name_table([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_FAMILY_NAME,
         "Arial".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_SUB_FAMILY_NAME,
         "Bold".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_POSTSCRIPT_NAME,
         "Arial-Bold".encode("utf-16-be")),
    ])
    t = _read(blob)
    assert t.get_font_family() == "Arial"
    assert t.get_font_sub_family() == "Bold"
    assert t.get_post_script_name() == "Arial-Bold"


def test_postscript_name_prefers_macintosh() -> None:
    # Both Mac roman and Windows unicode entries; Mac wins for ps name.
    blob = _build_name_table([
        (NameRecord.PLATFORM_MACINTOSH, NameRecord.ENCODING_MACINTOSH_ROMAN,
         NameRecord.LANGUAGE_MACINTOSH_ENGLISH, NameRecord.NAME_POSTSCRIPT_NAME,
         b"MacName"),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_POSTSCRIPT_NAME,
         "WinName".encode("utf-16-be")),
    ])
    t = _read(blob)
    assert t.get_post_script_name() == "MacName"


def test_postscript_name_strip_whitespace() -> None:
    blob = _build_name_table([(
        NameRecord.PLATFORM_MACINTOSH, NameRecord.ENCODING_MACINTOSH_ROMAN,
        NameRecord.LANGUAGE_MACINTOSH_ENGLISH, NameRecord.NAME_POSTSCRIPT_NAME,
        b"  Padded  ",
    )])
    t = _read(blob)
    assert t.get_post_script_name() == "Padded"


def test_postscript_name_none_when_absent() -> None:
    blob = _build_name_table([(
        NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
        NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_FAMILY_NAME,
        "X".encode("utf-16-be"),
    )])
    t = _read(blob)
    assert t.get_post_script_name() is None


def test_unicode_platform_uses_utf16be_charset() -> None:
    blob = _build_name_table([(
        NameRecord.PLATFORM_UNICODE, NameRecord.ENCODING_UNICODE_2_0_BMP,
        NameRecord.LANGUAGE_UNICODE, NameRecord.NAME_FONT_FAMILY_NAME,
        "Ué".encode("utf-16-be"),
    )])
    t = _read(blob)
    assert t.get_font_family() == "Ué"


def test_iso_platform_ascii_encoding() -> None:
    blob = _build_name_table([(
        NameRecord.PLATFORM_ISO, 0,
        0, NameRecord.NAME_FONT_FAMILY_NAME, b"Foo",
    )])
    t = _read(blob)
    assert t.get_name(NameRecord.NAME_FONT_FAMILY_NAME,
                      NameRecord.PLATFORM_ISO, 0, 0) == "Foo"


def test_iso_platform_utf16_encoding() -> None:
    blob = _build_name_table([(
        NameRecord.PLATFORM_ISO, 1,
        0, NameRecord.NAME_FONT_FAMILY_NAME,
        "Bar".encode("utf-16-be"),
    )])
    t = _read(blob)
    assert t.get_name(NameRecord.NAME_FONT_FAMILY_NAME,
                      NameRecord.PLATFORM_ISO, 1, 0) == "Bar"


def test_macintosh_roman_default_iso_8859_1() -> None:
    blob = _build_name_table([(
        NameRecord.PLATFORM_MACINTOSH, NameRecord.ENCODING_MACINTOSH_ROMAN,
        NameRecord.LANGUAGE_MACINTOSH_ENGLISH, NameRecord.NAME_FONT_FAMILY_NAME,
        b"Times",
    )])
    t = _read(blob)
    assert t.get_font_family() == "Times"


def test_pdfbox_2608_invalid_offset_sets_string_to_none() -> None:
    # Manually craft a record whose stringOffset > table length.
    n = 1
    header = struct.pack(">HHH", 0, n, 6 + n * 12)
    record = struct.pack(
        ">HHHHHH",
        NameRecord.PLATFORM_WINDOWS,
        NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
        NameRecord.LANGUAGE_WINDOWS_EN_US,
        NameRecord.NAME_FONT_FAMILY_NAME,
        4,         # length
        60_000,    # bogus offset, well past the table length we set below
    )
    blob = header + record
    table = NamingTable()
    table.set_offset(0)
    # Pretend the table is small enough that 60_000 > length.
    table.set_length(len(blob))
    table.read(_StubTTF(), MemoryTTFDataStream(blob))  # type: ignore[arg-type]
    assert table.get_name_records()[0].get_string() is None
    assert table.get_font_family() is None


def test_zero_records() -> None:
    blob = struct.pack(">HHH", 0, 0, 6)
    t = _read(blob)
    assert t.get_name_records() == []
    assert t.get_font_family() is None
    assert t.get_font_sub_family() is None
    assert t.get_post_script_name() is None


