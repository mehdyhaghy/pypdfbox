from __future__ import annotations

import struct
from typing import cast

from pypdfbox.fontbox.ttf.name_record import NameRecord
from pypdfbox.fontbox.ttf.naming_table import NamingTable
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def test_wave311_malformed_utf16_name_uses_replacement_character() -> None:
    raw = b"\x00A\x00"
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

    assert table.get_name_records()[0].get_string() == "A\ufffd"
    assert table.get_font_family() == "A\ufffd"
