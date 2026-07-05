from __future__ import annotations

import struct
from typing import cast

import pytest

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


def test_read_ignores_declared_string_storage_offset() -> None:
    # Upstream NamingTable#read (3.0.7, line 99) computes the string-storage
    # base as 6 + 12*numRecords past the table start and IGNORES the header's
    # declared storage offset. A table whose declared offset points past four
    # bytes of padding therefore decodes the padding, not the intended string.
    # Oracle-verified (wave 1598, NamingTableFuzzProbe).
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

    # The 22-byte read starts at the computed base (18): the four padding
    # bytes decode as UTF-16BE chars and the string is truncated 4 bytes
    # early — exactly what Apache FontBox produces.
    expected = (b"xxxx" + raw)[: len(raw)].decode("utf-16-be")
    assert table.get_name_records()[0].get_string() == expected
    assert table.get_font_family() == expected


def test_record_extending_past_stream_end_raises() -> None:
    # Upstream's PDFBOX-2608 guard only checks the raw string offset against
    # the table length; a record whose LENGTH runs past the end of the data
    # is read anyway and the short read throws IOException out of read()
    # (TTFDataStream.read: "Unexpected end of TTF stream reached").
    # Oracle-verified (wave 1598, NamingTableFuzzProbe).
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

    with pytest.raises(OSError, match="Unexpected end of TTF stream"):
        _read(blob)


def test_record_extending_past_declared_length_reads_following_bytes() -> None:
    # A string that starts inside the table but crosses the DECLARED table
    # length is still read from the stream when the bytes exist (upstream
    # reads straight into whatever follows the table in the file).
    raw = "Short".encode("utf-16-be")
    trailing = "!?".encode("utf-16-be")
    blob = (
        struct.pack(">HHH", 0, 1, 6 + 12)
        + struct.pack(
            ">HHHHHH",
            NameRecord.PLATFORM_WINDOWS,
            NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
            NameRecord.LANGUAGE_WINDOWS_EN_US,
            NameRecord.NAME_FONT_FAMILY_NAME,
            len(raw) + len(trailing),
            0,
        )
        + raw
        + trailing
    )

    # Declared table length stops before the trailing bytes; the read does not.
    table = _read(blob, table_length=len(blob) - len(trailing))

    assert table.get_name_records()[0].get_string() == "Short!?"
    assert table.get_font_family() == "Short!?"


def test_string_offset_beyond_table_length_leaves_record_with_none_string() -> None:
    # The one guard upstream DOES apply (PDFBOX-2608): a raw string offset
    # greater than the table length skips the read and leaves the record in
    # place with a null string — the record is NOT dropped from the list.
    blob = (
        struct.pack(">HHH", 0, 1, 6 + 12)
        + struct.pack(
            ">HHHHHH",
            NameRecord.PLATFORM_WINDOWS,
            NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
            NameRecord.LANGUAGE_WINDOWS_EN_US,
            NameRecord.NAME_FONT_FAMILY_NAME,
            4,
            500,
        )
        + b"\x00A\x00B"
    )

    table = _read(blob)

    records = table.get_name_records()
    assert len(records) == 1
    assert records[0].get_string() is None
    assert table.get_font_family() is None
