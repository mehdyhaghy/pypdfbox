"""Tests for :class:`VerticalOriginTable`."""

from __future__ import annotations

import struct

from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from pypdfbox.fontbox.ttf.vertical_origin_table import VerticalOriginTable


def _vorg_bytes(version: float, default_y: int, origins: list[tuple[int, int]]) -> bytes:
    """Build a synthetic ``VORG`` table body."""
    integer = int(version)
    fractional = int(round((version - integer) * 65536)) & 0xFFFF
    version_word = ((integer & 0xFFFF) << 16) | fractional
    buf = struct.pack(">IhH", version_word, default_y, len(origins))
    for gid, y in origins:
        buf += struct.pack(">Hh", gid, y)
    return buf


def test_tag_is_vorg() -> None:
    assert VerticalOriginTable.TAG == "VORG"


def test_uninitialized_has_zero_defaults() -> None:
    table = VerticalOriginTable()
    assert table.get_version() == 0.0
    assert table.get_origin_y(0) == 0
    assert table.initialized is False


def test_read_populates_state() -> None:
    table = VerticalOriginTable()
    raw = _vorg_bytes(1.0, 880, [(1, 900), (2, 850), (3, -100)])
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_version() == 1.0
    assert table.get_origin_y(1) == 900
    assert table.get_origin_y(2) == 850
    assert table.get_origin_y(3) == -100
    # Unlisted gid falls back to defaultVertOriginY.
    assert table.get_origin_y(99) == 880
    assert table.initialized is True


def test_default_only_table() -> None:
    table = VerticalOriginTable()
    table.read(None, MemoryTTFDataStream(_vorg_bytes(1.0, 700, [])))  # type: ignore[arg-type]
    # Every gid hits the default.
    assert table.get_origin_y(0) == 700
    assert table.get_origin_y(12345) == 700


def test_negative_default_y_round_trips() -> None:
    table = VerticalOriginTable()
    table.read(None, MemoryTTFDataStream(_vorg_bytes(1.0, -50, [])))  # type: ignore[arg-type]
    assert table.get_origin_y(0) == -50
