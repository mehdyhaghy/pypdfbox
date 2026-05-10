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


def test_get_charset_matches_upstream_dispatch() -> None:
    """Mirrors upstream ``NamingTable#getCharset`` (NamingTable.java line 110).

    Each platform / encoding pair must select the same codec upstream picks.
    """
    def _nr(plat: int, enc: int) -> NameRecord:
        nr = NameRecord()
        nr.set_platform_id(plat)
        nr.set_platform_encoding_id(enc)
        return nr

    # Windows symbol + unicode BMP → utf-16-be (Java StandardCharsets.UTF_16,
    # but the table is big-endian and our pypdfbox decoder strips the BOM).
    assert NamingTable.get_charset(
        _nr(NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_SYMBOL)
    ) == "utf-16-be"
    assert NamingTable.get_charset(
        _nr(NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP)
    ) == "utf-16-be"
    # Unicode platform → utf-16-be regardless of encoding.
    assert NamingTable.get_charset(_nr(NameRecord.PLATFORM_UNICODE, 0)) == "utf-16-be"
    assert NamingTable.get_charset(_nr(NameRecord.PLATFORM_UNICODE, 4)) == "utf-16-be"
    # ISO encoding 0 → US-ASCII, encoding 1 → UTF-16BE.
    assert NamingTable.get_charset(_nr(NameRecord.PLATFORM_ISO, 0)) == "us-ascii"
    assert NamingTable.get_charset(_nr(NameRecord.PLATFORM_ISO, 1)) == "utf-16-be"
    # Default → ISO-8859-1 (matches StandardCharsets.ISO_8859_1).
    assert NamingTable.get_charset(_nr(NameRecord.PLATFORM_ISO, 99)) == "iso-8859-1"


def test_is_useful_for_only_headers_filter() -> None:
    """Mirrors upstream ``NamingTable#isUsefulForOnlyHeaders``
    (NamingTable.java line 181)."""
    def _nr(name_id: int, lang: int) -> NameRecord:
        nr = NameRecord()
        nr.set_name_id(name_id)
        nr.set_language_id(lang)
        return nr

    # Useful: ps name / family / sub family + (Unicode lang or Windows en-US).
    for nid in (
        NameRecord.NAME_POSTSCRIPT_NAME,
        NameRecord.NAME_FONT_FAMILY_NAME,
        NameRecord.NAME_FONT_SUB_FAMILY_NAME,
    ):
        assert NamingTable.is_useful_for_only_headers(
            _nr(nid, NameRecord.LANGUAGE_UNICODE)
        )
        assert NamingTable.is_useful_for_only_headers(
            _nr(nid, NameRecord.LANGUAGE_WINDOWS_EN_US)
        )
        # Other languages → not useful.
        assert not NamingTable.is_useful_for_only_headers(_nr(nid, 0x0407))
    # Other name ids → never useful.
    for nid in (
        NameRecord.NAME_COPYRIGHT,
        NameRecord.NAME_UNIQUE_FONT_ID,
        NameRecord.NAME_FULL_FONT_NAME,
        NameRecord.NAME_VERSION,
        NameRecord.NAME_TRADEMARK,
    ):
        assert not NamingTable.is_useful_for_only_headers(
            _nr(nid, NameRecord.LANGUAGE_WINDOWS_EN_US)
        )


def test_read_headers_populates_font_headers() -> None:
    """Mirrors upstream ``NamingTable#readHeaders`` (NamingTable.java line 67):
    populates ``FontHeaders`` with PostScript name + family / sub-family,
    skipping records the fast path doesn't need."""
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
    from pypdfbox.fontbox.ttf.ttf_parser import FontHeaders

    records = [
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_FAMILY_NAME,
         "Liberation Sans".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_SUB_FAMILY_NAME,
         "Bold".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_POSTSCRIPT_NAME,
         "LiberationSans-Bold".encode("utf-16-be")),
        # Records that aren't useful for headers — should be filtered out.
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_COPYRIGHT,
         "(c) 2020".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         0x0407,  # de-DE — not Windows en-US, not Unicode lang.
         NameRecord.NAME_FONT_FAMILY_NAME, "Liberation".encode("utf-16-be")),
    ]
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
    headers = FontHeaders()
    table.read_headers(_StubTTF(), MemoryTTFDataStream(blob), headers)  # type: ignore[arg-type]

    assert headers.get_name() == "LiberationSans-Bold"
    assert headers.get_font_family() == "Liberation Sans"
    assert headers.get_font_sub_family() == "Bold"
    # Headers fast path drops records that aren't useful — copyright and the
    # de-DE family are filtered out, leaving exactly the three useful ones.
    assert len(table.get_name_records()) == 3


def test_fill_lookup_table_is_idempotent_and_public() -> None:
    """The public ``fill_lookup_table`` overload mirrors upstream
    ``NamingTable#fillLookupTable`` (NamingTable.java line 141) — it can
    be called repeatedly and the lookup remains consistent."""
    t = _build([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_FAMILY_NAME,
         "Roboto".encode("utf-16-be")),
    ])
    # Re-running fill_lookup_table over the existing records reproduces the
    # same lookup state — upstream relies on this for test injection.
    before = t.get_name(
        NameRecord.NAME_FONT_FAMILY_NAME,
        NameRecord.PLATFORM_WINDOWS,
        NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
        NameRecord.LANGUAGE_WINDOWS_EN_US,
    )
    t.fill_lookup_table()
    t.read_interesting_strings()
    after = t.get_name(
        NameRecord.NAME_FONT_FAMILY_NAME,
        NameRecord.PLATFORM_WINDOWS,
        NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
        NameRecord.LANGUAGE_WINDOWS_EN_US,
    )
    assert before == after == "Roboto"
    assert t.get_font_family() == "Roboto"
