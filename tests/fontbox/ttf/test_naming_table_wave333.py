from __future__ import annotations

import struct
from typing import cast

from pypdfbox.fontbox.ttf.name_record import NameRecord
from pypdfbox.fontbox.ttf.naming_table import NamingTable
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def _read_windows_family(raw: bytes) -> NamingTable:
    blob = (
        struct.pack(">HHH", 0, 1, 6 + 12)
        + struct.pack(
            ">HHHHHH",
            NameRecord.PLATFORM_WINDOWS,
            NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
            NameRecord.LANGUAGE_WINDOWS_EN_US,
            NameRecord.NAME_FONT_FAMILY_NAME,
            len(raw),
            0,
        )
        + raw
    )
    table = NamingTable()
    table.set_offset(0)
    table.set_length(len(blob))
    table.read(cast(TrueTypeFont, object()), MemoryTTFDataStream(blob))
    return table


def test_wave333_windows_utf16be_name_consumes_bom() -> None:
    table = _read_windows_family(b"\xfe\xff" + "BOM Sans".encode("utf-16-be"))

    assert table.get_name_records()[0].get_string() == "BOM Sans"
    assert table.get_font_family() == "BOM Sans"


def test_wave333_windows_utf16le_bom_name_decodes_little_endian() -> None:
    table = _read_windows_family(b"\xff\xfe" + "Little Sans".encode("utf-16-le"))

    assert table.get_name_records()[0].get_string() == "Little Sans"
    assert table.get_font_family() == "Little Sans"
