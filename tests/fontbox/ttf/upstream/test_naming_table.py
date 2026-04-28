"""Upstream parity tests for ``NamingTable``.

Apache PDFBox 3.0.x does not ship a standalone ``NamingTableTest.java`` —
the ``name`` table is exercised indirectly through ``TrueTypeFontTest``
and ``TTFParserTest``. We provide a small parity surface here for the
public accessors callers depend on, modelled after the assertions made in
``TrueTypeFontTest#testGetNumberOfGlyphs`` (which reads a real Liberation
Sans TTF and asserts family/full name).

These tests use synthetic ``name`` table bytes — sufficient to exercise
the upstream API contract without bundling Liberation Sans.
"""

from __future__ import annotations

import struct

from pypdfbox.fontbox.ttf.name_record import NameRecord
from pypdfbox.fontbox.ttf.naming_table import NamingTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


class _StubTTF:
    pass


def _build(records: list[tuple[int, int, int, int, bytes]]) -> NamingTable:
    n = len(records)
    header = struct.pack(">HHH", 0, n, 6 + n * 12)
    pool = b""
    blobs: list[bytes] = []
    for plat, enc, lang, name_id, raw in records:
        offset = len(pool)
        blobs.append(struct.pack(
            ">HHHHHH", plat, enc, lang, name_id, len(raw), offset,
        ))
        pool += raw
    blob = header + b"".join(blobs) + pool
    table = NamingTable()
    table.set_offset(0)
    table.set_length(len(blob))
    table.read(_StubTTF(), MemoryTTFDataStream(blob))  # type: ignore[arg-type]
    return table


def test_get_name_overload_round_trip() -> None:
    """Mirror upstream ``getName(int)`` vs ``getName(int, int, int, int)``."""
    raw = "Liberation Sans".encode("utf-16-be")
    t = _build([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_FAMILY_NAME,
         raw),
    ])
    by_id = t.get_name(NameRecord.NAME_FONT_FAMILY_NAME)
    by_quadruple = t.get_name(
        NameRecord.NAME_FONT_FAMILY_NAME,
        NameRecord.PLATFORM_WINDOWS,
        NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
        NameRecord.LANGUAGE_WINDOWS_EN_US,
    )
    assert by_id == by_quadruple == "Liberation Sans"


def test_full_name_and_family_match_upstream_assertions() -> None:
    t = _build([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_FAMILY_NAME,
         "Liberation Sans".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FULL_FONT_NAME,
         "Liberation Sans Bold".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_SUB_FAMILY_NAME,
         "Bold".encode("utf-16-be")),
    ])
    assert t.get_font_family() == "Liberation Sans"
    assert t.get_font_sub_family() == "Bold"
    assert t.get_full_name() == "Liberation Sans Bold"


def test_post_script_name_strip_matches_upstream() -> None:
    """Upstream trims the PostScript name (java ``String.trim()``)."""
    t = _build([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_POSTSCRIPT_NAME,
         "  LiberationSans-Bold  ".encode("utf-16-be")),
    ])
    assert t.get_post_script_name() == "LiberationSans-Bold"


def test_get_name_records_iteration_matches_upstream() -> None:
    """Upstream callers traverse ``getNameRecords()`` directly. The list
    must contain every record in read order with platform / encoding /
    language / name ids preserved."""
    t = _build([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_COPYRIGHT,
         "(c) 2020".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_FAMILY_NAME,
         "Liberation Sans".encode("utf-16-be")),
    ])
    records = t.get_name_records()
    assert len(records) == 2
    # First record is copyright per insertion order.
    assert records[0].get_name_id() == NameRecord.NAME_COPYRIGHT
    assert records[1].get_name_id() == NameRecord.NAME_FONT_FAMILY_NAME
    # Records expose the upstream-style getters.
    assert records[1].get_platform_id() == NameRecord.PLATFORM_WINDOWS
    assert records[1].get_language_id() == NameRecord.LANGUAGE_WINDOWS_EN_US
    assert records[1].get_string() == "Liberation Sans"


def test_lookup_table_language_records_round_trip() -> None:
    """Multi-language records all decode and remain queryable via the
    quadruple ``getName`` lookup."""
    t = _build([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_FAMILY_NAME,
         "Roboto".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         0x0407, NameRecord.NAME_FONT_FAMILY_NAME,  # de-DE
         "Roboto".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         0x0411, NameRecord.NAME_FONT_FAMILY_NAME,  # ja-JP
         "Roboto".encode("utf-16-be")),
    ])
    for lang in (NameRecord.LANGUAGE_WINDOWS_EN_US, 0x0407, 0x0411):
        assert (
            t.get_name(
                NameRecord.NAME_FONT_FAMILY_NAME,
                NameRecord.PLATFORM_WINDOWS,
                NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
                lang,
            )
            == "Roboto"
        )
