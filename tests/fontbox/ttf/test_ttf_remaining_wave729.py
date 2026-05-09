from __future__ import annotations

import struct
from types import SimpleNamespace
from typing import Any

import pytest

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.ttf.cmap_table import CmapTable
from pypdfbox.fontbox.ttf.name_record import NameRecord
from pypdfbox.fontbox.ttf.naming_table import NamingTable
from pypdfbox.fontbox.ttf.open_type_font import OpenTypeFont
from pypdfbox.fontbox.ttf.ttf_data_stream import (
    MemoryTTFDataStream,
    RandomAccessReadDataStream,
    TTFDataStream,
)


class _StubTTF:
    pass


class _CmapStub(CmapTable):
    def __init__(self) -> None:
        super().__init__()
        self.set_offset(0)


class _ShortRandomAccessSource:
    def length(self) -> int:
        return 3

    def seek(self, _position: int) -> None:
        pass

    def read_into(self, _buf: bytearray, _offset: int, _length: int) -> int:
        return 0


class _BytesRandomAccessSource:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._position = 0

    def length(self) -> int:
        return len(self._data)

    def seek(self, position: int) -> None:
        self._position = position

    def read_into(self, buf: bytearray, offset: int, length: int) -> int:
        available = len(self._data) - self._position
        if available <= 0:
            return -1
        count = min(length, available)
        buf[offset : offset + count] = self._data[self._position : self._position + count]
        self._position += count
        return count


def _build_name_table(records: list[tuple[int, int, int, int, bytes]]) -> bytes:
    header = struct.pack(">HHH", 0, len(records), 6 + len(records) * 12)
    string_pool = b""
    record_blobs: list[bytes] = []
    for platform, encoding, language, name_id, raw in records:
        record_blobs.append(
            struct.pack(
                ">HHHHHH",
                platform,
                encoding,
                language,
                name_id,
                len(raw),
                len(string_pool),
            )
        )
        string_pool += raw
    return header + b"".join(record_blobs) + string_pool


def _read_name_table(blob: bytes) -> NamingTable:
    table = NamingTable()
    table.set_offset(0)
    table.set_length(len(blob))
    table.read(_StubTTF(), MemoryTTFDataStream(blob))  # type: ignore[arg-type]
    return table


def _build_format2(glyphs: list[int], first_code: int = 0x30) -> bytes:
    sub_header_keys = struct.pack(">256H", *([0] * 256))
    sub_header = struct.pack(">HHhH", first_code, len(glyphs), 0, 2)
    glyph_array = struct.pack(f">{len(glyphs)}H", *glyphs)
    return struct.pack(">HHH", 2, 0, 0) + sub_header_keys + sub_header + glyph_array


def _build_format12(groups: list[tuple[int, int, int]]) -> bytes:
    payload = struct.pack(">I", len(groups))
    for first, end, start_glyph in groups:
        payload += struct.pack(">III", first, end, start_glyph)
    return struct.pack(">HHII", 12, 0, 0, 0) + payload


def test_read_bounds_helper_rejects_too_long_range() -> None:
    with pytest.raises(IndexError, match="out of bounds"):
        TTFDataStream._check_read_bounds(bytearray(2), 1, 2)


def test_random_access_constructor_rejects_short_source() -> None:
    with pytest.raises(OSError, match="Unexpected end"):
        RandomAccessReadDataStream(_ShortRandomAccessSource())  # type: ignore[arg-type]


def test_random_access_read_long_short_raises() -> None:
    stream = RandomAccessReadDataStream(_BytesRandomAccessSource(b"\x00\x01"))  # type: ignore[arg-type]
    with pytest.raises(EOFError, match="premature EOF"):
        stream.read_long()


def test_open_type_get_cff_uses_raw_data_when_compile_fails_empty() -> None:
    class _BrokenCFFTable:
        data = b""

        def compile(self, _tt: Any) -> bytes:
            raise ValueError("cannot compile")

    font = object.__new__(OpenTypeFont)
    font._cff = object()  # noqa: SLF001
    font._cff_resolved = False  # noqa: SLF001
    font._tt = {"CFF ": _BrokenCFFTable()}  # noqa: SLF001

    assert font.get_cff() is None
    assert font.get_cff() is None


def test_open_type_get_cff_uses_cid_wrapper_for_ros_top_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()

    monkeypatch.setattr(CFFCIDFont, "from_bytes", staticmethod(lambda data: sentinel))

    class _FontSet:
        fontNames = ["CIDFont"]

        def __getitem__(self, _name: str) -> Any:
            return SimpleNamespace(ROS=("Adobe", "Identity", 0), rawDict={})

    class _CFFTable:
        cff = _FontSet()

        def compile(self, _tt: Any) -> bytes:
            return b"nonempty"

    font = object.__new__(OpenTypeFont)
    font._cff = None  # noqa: SLF001
    font._cff_resolved = False  # noqa: SLF001
    font._tt = {"CFF ": _CFFTable()}  # noqa: SLF001

    assert font.get_cff() is sentinel


def test_naming_table_decode_falls_back_to_latin1_for_unknown_codec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        NamingTable,
        "_charset_for",
        staticmethod(lambda _record: "not-a-real-python-codec"),
    )
    blob = _build_name_table(
        [
            (
                NameRecord.PLATFORM_MACINTOSH,
                99,
                NameRecord.LANGUAGE_MACINTOSH_ENGLISH,
                NameRecord.NAME_FONT_FAMILY_NAME,
                b"\xe9Name",
            )
        ]
    )

    table = _read_name_table(blob)

    assert (
        table.get_name(
            NameRecord.NAME_FONT_FAMILY_NAME,
            NameRecord.PLATFORM_MACINTOSH,
            99,
            NameRecord.LANGUAGE_MACINTOSH_ENGLISH,
        )
        == "éName"
    )


def test_naming_table_english_names_and_language_helpers() -> None:
    german = 0x0407
    blob = _build_name_table(
        [
            (
                NameRecord.PLATFORM_WINDOWS,
                NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
                NameRecord.LANGUAGE_WINDOWS_EN_US,
                NameRecord.NAME_FONT_FAMILY_NAME,
                "Primary".encode("utf-16-be"),
            ),
            (
                NameRecord.PLATFORM_WINDOWS,
                NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
                german,
                NameRecord.NAME_FONT_FAMILY_NAME,
                "Deutsch".encode("utf-16-be"),
            ),
            (
                NameRecord.PLATFORM_WINDOWS,
                NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
                german,
                NameRecord.NAME_FULL_FONT_NAME,
                "Full Deutsch".encode("utf-16-be"),
            ),
        ]
    )
    table = _read_name_table(blob)

    assert table.get_english_name(NameRecord.NAME_FONT_FAMILY_NAME) == "Primary"
    assert len(table.get_names_by_id(NameRecord.NAME_FONT_FAMILY_NAME)) == 2
    assert table.language_ids(NameRecord.NAME_FONT_FAMILY_NAME) == [
        NameRecord.LANGUAGE_WINDOWS_EN_US,
        german,
    ]
    assert table.get_version(german) is None


def test_format_12_invalid_glyph_index_logs_and_skips(
    caplog: pytest.LogCaptureFixture,
) -> None:
    blob = _build_format12([(0x41, 0x42, 3)])
    subtable = CmapSubtable()

    subtable.init_subtable(_CmapStub(), num_glyphs=4, data=MemoryTTFDataStream(blob))

    assert subtable.get_glyph_id(0x41) == 3
    assert subtable.get_glyph_id(0x42) == 0
    assert "Format 12 cmap contains an invalid glyph index" in caplog.text


def test_format_2_stops_repeated_invalid_glyph_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    blob = _build_format2(list(range(20, 32)))
    subtable = CmapSubtable()

    subtable.init_subtable(_CmapStub(), num_glyphs=1, data=MemoryTTFDataStream(blob))

    assert subtable.get_glyph_id(0x30) == 0
    assert caplog.text.count("ignored, numGlyphs is 1") == 11


def test_get_char_codes_returns_none_for_missing_multi_map() -> None:
    subtable = CmapSubtable()
    subtable._glyph_id_to_character_code = [-2_147_483_648]  # noqa: SLF001

    assert subtable.get_char_codes(0) is None
