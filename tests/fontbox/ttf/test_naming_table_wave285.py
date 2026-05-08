from __future__ import annotations

import struct
from typing import cast

from pypdfbox.fontbox.ttf.name_record import NameRecord
from pypdfbox.fontbox.ttf.naming_table import NamingTable
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def _read(blob: bytes, *, table_length: int | None = None) -> NamingTable:
    table = NamingTable()
    table.set_offset(0)
    table.set_length(len(blob) if table_length is None else table_length)
    table.read(cast(TrueTypeFont, object()), MemoryTTFDataStream(blob))
    return table


def test_read_honors_declared_string_storage_offset_with_padding() -> None:
    raw = "Offset Sans".encode("utf-16-be")
    storage_offset = 6 + 12 + 4
    blob = (
        struct.pack(">HHH", 0, 1, storage_offset)
        + struct.pack(
            ">HHHHHH",
            NameRecord.PLATFORM_WINDOWS,
            NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
            NameRecord.LANGUAGE_WINDOWS_EN_US,
            NameRecord.NAME_FONT_FAMILY_NAME,
            len(raw),
            0,
        )
        + b"xxxx"
        + raw
    )

    table = _read(blob)

    assert table.get_font_family() == "Offset Sans"
    assert table.get_name_records()[0].get_string() == "Offset Sans"


def test_record_extending_past_table_length_is_left_unread() -> None:
    blob = (
        struct.pack(">HHH", 0, 1, 6 + 12)
        + struct.pack(
            ">HHHHHH",
            NameRecord.PLATFORM_WINDOWS,
            NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
            NameRecord.LANGUAGE_WINDOWS_EN_US,
            NameRecord.NAME_FONT_FAMILY_NAME,
            10,
            0,
        )
        + b"\x00A"
    )

    table = _read(blob)

    assert table.get_name_records()[0].get_string() is None
    assert table.get_font_family() is None


def test_record_extending_past_underlying_stream_is_left_unread() -> None:
    raw = "Short".encode("utf-16-be")
    blob = (
        struct.pack(">HHH", 0, 1, 6 + 12)
        + struct.pack(
            ">HHHHHH",
            NameRecord.PLATFORM_WINDOWS,
            NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
            NameRecord.LANGUAGE_WINDOWS_EN_US,
            NameRecord.NAME_FONT_FAMILY_NAME,
            len(raw) + 2,
            0,
        )
        + raw
    )

    table = _read(blob, table_length=len(blob) + 2)

    assert table.get_name_records()[0].get_string() is None
    assert table.get_font_family() is None
