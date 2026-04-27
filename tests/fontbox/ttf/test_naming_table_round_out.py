"""Round-out coverage for ``NamingTable`` accessors and ``getName(int)`` overload.

These tests exercise the upstream-style API additions:

* ``get_name(name_id)`` — Microsoft Unicode BMP English-US preferred, with
  fallback to other Microsoft languages, the Unicode platform, and finally
  Macintosh Roman English.
* ``get_unique_id()``, ``get_full_name()``, ``get_version()``,
  ``get_copyright()``, ``get_trademark()``.
* Decoding the four supported Macintosh script codes (Roman, best-effort
  Japanese) plus the ``ENCODING_WINDOWS_UNICODE_UCS4`` Windows surrogate path.
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf.name_record import NameRecord
from pypdfbox.fontbox.ttf.naming_table import NamingTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


class _StubTTF:
    """Minimal duck-typed TrueTypeFont — never inspected by ``NamingTable.read``."""


def _build_name_table(records: list[tuple[int, int, int, int, bytes]]) -> bytes:
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


# ---- get_name(int) overload -----------------------------------------------


def test_get_name_int_prefers_microsoft_unicode_en_us() -> None:
    blob = _build_name_table([
        (NameRecord.PLATFORM_MACINTOSH, NameRecord.ENCODING_MACINTOSH_ROMAN,
         NameRecord.LANGUAGE_MACINTOSH_ENGLISH, NameRecord.NAME_FULL_FONT_NAME,
         b"MacFull"),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FULL_FONT_NAME,
         "WinFull".encode("utf-16-be")),
    ])
    t = _read(blob)
    assert t.get_name(NameRecord.NAME_FULL_FONT_NAME) == "WinFull"


def test_get_name_int_falls_back_to_other_ms_language() -> None:
    blob = _build_name_table([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         0x0407, NameRecord.NAME_FULL_FONT_NAME,  # de-DE
         "Vollname".encode("utf-16-be")),
    ])
    t = _read(blob)
    assert t.get_name(NameRecord.NAME_FULL_FONT_NAME) == "Vollname"


def test_get_name_int_falls_back_to_unicode_platform() -> None:
    blob = _build_name_table([
        (NameRecord.PLATFORM_UNICODE, NameRecord.ENCODING_UNICODE_2_0_BMP,
         NameRecord.LANGUAGE_UNICODE, NameRecord.NAME_FULL_FONT_NAME,
         "U-Full".encode("utf-16-be")),
    ])
    t = _read(blob)
    assert t.get_name(NameRecord.NAME_FULL_FONT_NAME) == "U-Full"


def test_get_name_int_falls_back_to_mac_roman() -> None:
    blob = _build_name_table([
        (NameRecord.PLATFORM_MACINTOSH, NameRecord.ENCODING_MACINTOSH_ROMAN,
         NameRecord.LANGUAGE_MACINTOSH_ENGLISH, NameRecord.NAME_FULL_FONT_NAME,
         b"MacFull"),
    ])
    t = _read(blob)
    assert t.get_name(NameRecord.NAME_FULL_FONT_NAME) == "MacFull"


def test_get_name_int_returns_none_when_missing() -> None:
    blob = _build_name_table([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_FAMILY_NAME,
         "X".encode("utf-16-be")),
    ])
    t = _read(blob)
    assert t.get_name(NameRecord.NAME_TRADEMARK) is None


def test_get_name_partial_kwargs_raises_type_error() -> None:
    t = _read(_build_name_table([]))
    with pytest.raises(TypeError):
        t.get_name(NameRecord.NAME_FULL_FONT_NAME, NameRecord.PLATFORM_WINDOWS)


# ---- decoded accessors ----------------------------------------------------


def test_unique_id_full_name_version_copyright_trademark() -> None:
    blob = _build_name_table([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_UNIQUE_FONT_ID,
         "UniqueId-1".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FULL_FONT_NAME,
         "Arial Bold".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_VERSION,
         "Version 1.0".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_COPYRIGHT,
         "(c) ACME".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_TRADEMARK,
         "ACME (TM)".encode("utf-16-be")),
    ])
    t = _read(blob)
    assert t.get_unique_id() == "UniqueId-1"
    assert t.get_full_name() == "Arial Bold"
    assert t.get_version() == "Version 1.0"
    assert t.get_copyright() == "(c) ACME"
    assert t.get_trademark() == "ACME (TM)"


def test_accessors_default_to_none_when_records_absent() -> None:
    blob = _build_name_table([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_FAMILY_NAME,
         "Helv".encode("utf-16-be")),
    ])
    t = _read(blob)
    assert t.get_unique_id() is None
    assert t.get_full_name() is None
    assert t.get_version() is None
    assert t.get_copyright() is None
    assert t.get_trademark() is None


# ---- charset coverage -----------------------------------------------------


def test_macintosh_roman_decodes_high_bytes_with_mac_roman() -> None:
    # Mac Roman 0xA8 = ®, 0xA9 = ©, 0xAA = ™
    raw = bytes([0xA8, 0xA9, 0xAA])
    blob = _build_name_table([
        (NameRecord.PLATFORM_MACINTOSH, NameRecord.ENCODING_MACINTOSH_ROMAN,
         NameRecord.LANGUAGE_MACINTOSH_ENGLISH, NameRecord.NAME_COPYRIGHT,
         raw),
    ])
    t = _read(blob)
    decoded = t.get_name(
        NameRecord.NAME_COPYRIGHT,
        NameRecord.PLATFORM_MACINTOSH,
        NameRecord.ENCODING_MACINTOSH_ROMAN,
        NameRecord.LANGUAGE_MACINTOSH_ENGLISH,
    )
    assert decoded == "®©™"


def test_macintosh_japanese_decodes_with_shift_jis_best_effort() -> None:
    # ASCII subset of Shift-JIS — round-trips identically.
    raw = b"NIPPON"
    blob = _build_name_table([
        (NameRecord.PLATFORM_MACINTOSH, 1,  # encoding 1 = Japanese
         11, NameRecord.NAME_FONT_FAMILY_NAME, raw),
    ])
    t = _read(blob)
    decoded = t.get_name(NameRecord.NAME_FONT_FAMILY_NAME,
                         NameRecord.PLATFORM_MACINTOSH, 1, 11)
    assert decoded == "NIPPON"


def test_unknown_macintosh_encoding_falls_back_to_latin1() -> None:
    # Unknown Mac script code 99 — charset_for returns iso-8859-1 already, so
    # bytes round-trip as latin-1.
    raw = bytes([0xC0, 0xC1, 0xC2])
    blob = _build_name_table([
        (NameRecord.PLATFORM_MACINTOSH, 99, 0,
         NameRecord.NAME_FONT_FAMILY_NAME, raw),
    ])
    t = _read(blob)
    decoded = t.get_name(NameRecord.NAME_FONT_FAMILY_NAME,
                         NameRecord.PLATFORM_MACINTOSH, 99, 0)
    assert decoded == raw.decode("latin-1")


def test_windows_unicode_ucs4_treated_as_utf16be() -> None:
    raw = "Roboto".encode("utf-16-be")
    blob = _build_name_table([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_UCS4,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_FAMILY_NAME,
         raw),
    ])
    t = _read(blob)
    decoded = t.get_name(NameRecord.NAME_FONT_FAMILY_NAME,
                         NameRecord.PLATFORM_WINDOWS,
                         NameRecord.ENCODING_WINDOWS_UNICODE_UCS4,
                         NameRecord.LANGUAGE_WINDOWS_EN_US)
    assert decoded == "Roboto"


# ---- get_name_records returns the underlying list -------------------------


def test_get_name_records_returns_list_in_read_order() -> None:
    blob = _build_name_table([
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_FAMILY_NAME,
         "A".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FONT_SUB_FAMILY_NAME,
         "B".encode("utf-16-be")),
        (NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
         NameRecord.LANGUAGE_WINDOWS_EN_US, NameRecord.NAME_FULL_FONT_NAME,
         "AB".encode("utf-16-be")),
    ])
    t = _read(blob)
    records = t.get_name_records()
    assert isinstance(records, list)
    assert [nr.get_name_id() for nr in records] == [
        NameRecord.NAME_FONT_FAMILY_NAME,
        NameRecord.NAME_FONT_SUB_FAMILY_NAME,
        NameRecord.NAME_FULL_FONT_NAME,
    ]
