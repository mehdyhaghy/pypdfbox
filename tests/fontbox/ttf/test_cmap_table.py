from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.ttf.cmap_table import CmapTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from pypdfbox.fontbox.ttf.ttf_table import TTFTable


# ---------------------------------------------------------------------------
# Class-level basics
# ---------------------------------------------------------------------------


def test_cmap_table_tag_constant() -> None:
    assert CmapTable.TAG == "cmap"


def test_cmap_table_is_a_ttf_table() -> None:
    table = CmapTable()
    assert isinstance(table, TTFTable)


def test_cmap_table_platform_constants() -> None:
    assert CmapTable.PLATFORM_UNICODE == 0
    assert CmapTable.PLATFORM_MACINTOSH == 1
    assert CmapTable.PLATFORM_WINDOWS == 3


def test_cmap_table_mac_encoding_constants() -> None:
    assert CmapTable.ENCODING_MAC_ROMAN == 0


def test_cmap_table_windows_encoding_constants() -> None:
    assert CmapTable.ENCODING_WIN_SYMBOL == 0
    assert CmapTable.ENCODING_WIN_UNICODE_BMP == 1
    assert CmapTable.ENCODING_WIN_SHIFT_JIS == 2
    assert CmapTable.ENCODING_WIN_BIG5 == 3
    assert CmapTable.ENCODING_WIN_PRC == 4
    assert CmapTable.ENCODING_WIN_WANSUNG == 5
    assert CmapTable.ENCODING_WIN_JOHAB == 6
    assert CmapTable.ENCODING_WIN_UNICODE_FULL == 10


def test_cmap_table_unicode_encoding_constants() -> None:
    assert CmapTable.ENCODING_UNICODE_1_0 == 0
    assert CmapTable.ENCODING_UNICODE_1_1 == 1
    assert CmapTable.ENCODING_UNICODE_2_0_BMP == 3
    assert CmapTable.ENCODING_UNICODE_2_0_FULL == 4


def test_cmap_table_default_state() -> None:
    table = CmapTable()
    assert table.get_cmaps() == []
    assert table.get_subtable(3, 1) is None
    # Inherited from TTFTable.
    assert table.get_tag() == ""
    assert table.get_offset() == 0


# ---------------------------------------------------------------------------
# get_cmaps / set_cmaps
# ---------------------------------------------------------------------------


def _stub_subtable(platform_id: int, encoding_id: int) -> CmapSubtable:
    sub = CmapSubtable()
    sub.set_platform_id(platform_id)
    sub.set_platform_encoding_id(encoding_id)
    return sub


def test_set_cmaps_replaces_storage_and_get_cmaps_round_trips() -> None:
    table = CmapTable()
    a = _stub_subtable(3, 1)
    b = _stub_subtable(0, 4)
    table.set_cmaps([a, b])
    assert table.get_cmaps() == [a, b]


def test_get_cmaps_returns_live_storage() -> None:
    # Mutating the returned list mutates the table — upstream returns
    # the underlying array, so we mirror that aliasing behavior.
    table = CmapTable()
    a = _stub_subtable(3, 1)
    table.set_cmaps([a])
    table.get_cmaps().append(_stub_subtable(0, 4))
    assert len(table.get_cmaps()) == 2


# ---------------------------------------------------------------------------
# get_subtable
# ---------------------------------------------------------------------------


def test_get_subtable_returns_first_match() -> None:
    table = CmapTable()
    table.set_cmaps(
        [
            _stub_subtable(0, 3),
            _stub_subtable(3, 1),
            _stub_subtable(3, 10),
        ]
    )
    assert table.get_subtable(3, 1) is table.get_cmaps()[1]
    assert table.get_subtable(3, 10) is table.get_cmaps()[2]
    assert table.get_subtable(0, 3) is table.get_cmaps()[0]


def test_get_subtable_with_no_match_returns_none() -> None:
    table = CmapTable()
    table.set_cmaps([_stub_subtable(3, 1)])
    assert table.get_subtable(1, 0) is None
    assert table.get_subtable(3, 10) is None


def test_get_subtable_when_uses_constants() -> None:
    table = CmapTable()
    table.set_cmaps(
        [_stub_subtable(CmapTable.PLATFORM_WINDOWS, CmapTable.ENCODING_WIN_UNICODE_BMP)]
    )
    sub = table.get_subtable(
        CmapTable.PLATFORM_WINDOWS, CmapTable.ENCODING_WIN_UNICODE_BMP
    )
    assert sub is not None
    assert sub.get_platform_id() == 3
    assert sub.get_platform_encoding_id() == 1


def test_get_subtable_first_match_wins_when_duplicates() -> None:
    table = CmapTable()
    first = _stub_subtable(3, 1)
    second = _stub_subtable(3, 1)
    table.set_cmaps([first, second])
    assert table.get_subtable(3, 1) is first


# ---------------------------------------------------------------------------
# read() — full directory + format-0 subtable
# ---------------------------------------------------------------------------


class _FakeTTF:
    def __init__(self, num_glyphs: int) -> None:
        self._num_glyphs = num_glyphs

    def get_number_of_glyphs(self) -> int:
        return self._num_glyphs


def _build_cmap_with_one_format0_subtable(platform_id: int, encoding_id: int) -> bytes:
    """Return a minimal ``cmap`` table containing a single format-0 subtable.

    Layout:
        version(uint16) numberOfTables(uint16)
        directory: platformId(uint16) platformEncodingId(uint16) subtableOffset(uint32)
        subtable: format(uint16=0) length(uint16) version(uint16) bytes[256]
    """
    glyph_mapping = bytes(range(256))
    # Directory header is 4 bytes; one entry is 8 bytes -> subtable starts at 12.
    subtable_offset = 12
    header = struct.pack(">HH", 0, 1)  # version, numberOfTables
    directory = struct.pack(">HHI", platform_id, encoding_id, subtable_offset)
    subtable = struct.pack(">HHH", 0, 262, 0) + glyph_mapping
    return header + directory + subtable


def test_read_populates_subtables_and_initialized_flag() -> None:
    blob = _build_cmap_with_one_format0_subtable(3, 0)
    data = MemoryTTFDataStream(blob)
    table = CmapTable()
    # Offset of the cmap table within ``data`` is 0 here — init_subtable will
    # use ``cmap.get_offset() + sub_table_offset`` to seek the format word.
    table.read(_FakeTTF(num_glyphs=256), data)

    assert table.initialized is True
    cmaps = table.get_cmaps()
    assert len(cmaps) == 1
    sub = cmaps[0]
    assert sub.get_platform_id() == 3
    assert sub.get_platform_encoding_id() == 0
    # Identity format-0 mapping survived: 'A' -> glyph 0x41.
    assert sub.get_glyph_id(0x41) == 0x41


def test_read_zero_subtables_leaves_empty_list() -> None:
    # version=0, numberOfTables=0, no directory, no subtables.
    blob = struct.pack(">HH", 0, 0)
    data = MemoryTTFDataStream(blob)
    table = CmapTable()
    table.read(_FakeTTF(num_glyphs=10), data)
    assert table.get_cmaps() == []
    assert table.initialized is True


def test_read_then_get_subtable_finds_loaded_table() -> None:
    blob = _build_cmap_with_one_format0_subtable(3, 0)
    data = MemoryTTFDataStream(blob)
    table = CmapTable()
    table.read(_FakeTTF(num_glyphs=256), data)
    assert table.get_subtable(3, 0) is table.get_cmaps()[0]
    assert table.get_subtable(3, 1) is None


# ---------------------------------------------------------------------------
# Type / inheritance checks
# ---------------------------------------------------------------------------


def test_cmap_table_inherits_offset_length_setters() -> None:
    table = CmapTable()
    table.set_offset(123)
    table.set_length(456)
    assert table.get_offset() == 123
    assert table.get_length() == 456
