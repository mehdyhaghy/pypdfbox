"""PDFBOX-6297: format 8 / 12 / 13 cmap subtables skip groups that are not
sorted by end code, formats 12 / 13 reject an nbGroups above 0x10FFFF, and
format 13 rejects a glyph id equal to numGlyphs."""

import logging
import struct

import pytest

from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


class _CmapStub:
    def get_offset(self) -> int:
        return 0


def _subtable(fmt: int, groups: list[tuple[int, int, int]], n_groups: int | None = None) -> bytes:
    body = b"\x00" * 8192 if fmt == 8 else b""
    body += struct.pack(">I", len(groups) if n_groups is None else n_groups)
    for group in groups:
        body += struct.pack(">III", *group)
    return struct.pack(">HHII", fmt, 0, 0, 0) + body


def _parse(blob: bytes, num_glyphs: int = 50) -> CmapSubtable:
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=num_glyphs, data=MemoryTTFDataStream(blob))
    return sub


@pytest.mark.parametrize("fmt", [8, 12, 13])
def test_unsorted_group_is_skipped(fmt: int, caplog: pytest.LogCaptureFixture) -> None:
    groups = [(0x50, 0x52, 1), (0x41, 0x42, 10), (0x60, 0x60, 20)]
    with caplog.at_level(logging.WARNING, logger="pypdfbox.fontbox.ttf.cmap_subtable"):
        sub = _parse(_subtable(fmt, groups))
    assert f"Format {fmt} cmap unsorted mapping group was skipped" in caplog.text
    assert sub.get_glyph_id(0x41) == 0
    assert sub.get_glyph_id(0x42) == 0
    assert sub.get_glyph_id(0x50) == 1
    assert sub.get_glyph_id(0x60) == 20


@pytest.mark.parametrize("fmt", [8, 12, 13])
def test_overlapping_group_with_same_end_is_skipped(fmt: int) -> None:
    sub = _parse(_subtable(fmt, [(0x41, 0x45, 1), (0x44, 0x45, 30)]))
    assert sub.get_glyph_id(0x44) == (1 if fmt == 13 else 4)


@pytest.mark.parametrize("fmt", [8, 12, 13])
def test_group_ending_at_code_zero_is_skipped(fmt: int) -> None:
    # upstream starts lastEndCode at 0, so a group ending at 0 is "unsorted"
    sub = _parse(_subtable(fmt, [(0, 0, 3), (0x41, 0x41, 4)]))
    assert sub.get_glyph_id(0) == 0
    assert sub.get_glyph_id(0x41) == 4


@pytest.mark.parametrize("fmt", [12, 13])
def test_huge_nb_groups_is_rejected_without_reading(fmt: int) -> None:
    with pytest.raises(OSError, match=f"Format {fmt} cmap is invalid"):
        _parse(_subtable(fmt, [], n_groups=0x110000))


def test_format8_huge_nb_groups_is_rejected() -> None:
    with pytest.raises(OSError, match=r"Subtype8"):
        _parse(_subtable(8, [], n_groups=65537))


def test_format13_glyph_id_equal_to_num_glyphs_stops(caplog: pytest.LogCaptureFixture) -> None:
    groups = [(0x41, 0x41, 5), (0x42, 0x42, 10), (0x43, 0x43, 6)]
    with caplog.at_level(logging.WARNING, logger="pypdfbox.fontbox.ttf.cmap_subtable"):
        sub = _parse(_subtable(13, groups), num_glyphs=10)
    assert "Format 13 cmap contains an invalid glyph index" in caplog.text
    assert sub.get_glyph_id(0x41) == 5
    assert sub.get_glyph_id(0x42) == 0
    assert sub.get_glyph_id(0x43) == 0
