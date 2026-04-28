"""Direct binary parsing tests for ``KerningSubtable.from_bytes``.

Exercises the upstream Format 0 (sorted pair list) and Format 2 (class-based)
on-disk layouts. Hand-crafts minimal valid byte sequences so the parser
runs without a real font, mirroring upstream's
``KerningSubtableFormat0Test`` / ``KerningSubtableFormat2Test`` style.
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf.kerning_subtable import KerningSubtable


# ---------- Format 0 -------------------------------------------------------


def _make_format_0(pairs: list[tuple[int, int, int]], coverage: int = 0x0001) -> bytes:
    """Build a valid OpenType Format 0 kern subtable.

    Header: version (uint16), length (uint16), coverage (uint16). Coverage
    high byte = format (0 here), low byte = flags. Body: nPairs (uint16),
    searchRange (uint16), entrySelector (uint16), rangeShift (uint16),
    then nPairs * (left, right, value) triples.
    """
    n_pairs = len(pairs)
    # search constants — values aren't validated by the parser, but we set
    # them for upstream-fidelity.
    if n_pairs == 0:
        entry_selector = 0
        search_range = 0
        range_shift = 0
    else:
        entry_selector = 0
        while (1 << (entry_selector + 1)) <= n_pairs:
            entry_selector += 1
        search_range = (1 << entry_selector) * 6
        range_shift = n_pairs * 6 - search_range
    body = struct.pack(">HHHH", n_pairs, search_range, entry_selector, range_shift)
    for left, right, value in pairs:
        body += struct.pack(">HHh", left, right, value)
    length = 6 + len(body)
    # coverage: format (0) in high byte, flags in low byte.
    header = struct.pack(">HHH", 0, length, coverage & 0xFFFF)
    return header + body


def test_format_0_parses_pairs_into_gid_keyed_lookup() -> None:
    blob = _make_format_0(
        [(1, 2, -100), (1, 3, -50), (4, 5, 25)],
        coverage=0x0001,  # horizontal
    )
    sub = KerningSubtable.from_bytes(blob)
    assert sub.get_format() == 0
    assert sub.is_horizontal() is True
    assert sub.is_minimum() is False
    assert sub.is_cross_stream() is False
    assert sub.get_kerning(1, 2) == -100
    assert sub.get_kerning(1, 3) == -50
    assert sub.get_kerning(4, 5) == 25
    # Missing pair → 0.
    assert sub.get_kerning(2, 1) == 0


def test_format_0_horizontal_kerning_default_excludes_cross_stream() -> None:
    blob = _make_format_0([(1, 2, -1)], coverage=0x0005)  # horizontal + cross
    sub = KerningSubtable.from_bytes(blob)
    assert sub.is_horizontal() is True
    assert sub.is_cross_stream() is True
    assert sub.is_horizontal_kerning(False) is False
    assert sub.is_horizontal_kerning(True) is True


def test_format_0_minimum_subtable_disqualified() -> None:
    blob = _make_format_0([(1, 2, -1)], coverage=0x0003)  # horizontal + minimums
    sub = KerningSubtable.from_bytes(blob)
    assert sub.is_minimum() is True
    assert sub.is_horizontal_kerning(False) is False
    assert sub.is_horizontal_kerning(True) is False


def test_format_0_negative_gid_returns_zero() -> None:
    blob = _make_format_0([(1, 2, -100)])
    sub = KerningSubtable.from_bytes(blob)
    assert sub.get_kerning(-1, 2) == 0
    assert sub.get_kerning(1, -1) == 0


def test_format_0_sequence_lookup() -> None:
    blob = _make_format_0([(1, 2, -100), (2, 1, -80)])
    sub = KerningSubtable.from_bytes(blob)
    assert sub.get_kerning([1, 2, 1]) == [-100, -80, 0]


def test_format_0_zero_pairs() -> None:
    blob = _make_format_0([])
    sub = KerningSubtable.from_bytes(blob)
    assert sub.get_kerning(1, 2) == 0


def test_format_0_int16_range_handled() -> None:
    blob = _make_format_0([(1, 2, -32768), (3, 4, 32767)])
    sub = KerningSubtable.from_bytes(blob)
    assert sub.get_kerning(1, 2) == -32768
    assert sub.get_kerning(3, 4) == 32767


# ---------- Format 2 -------------------------------------------------------


def _make_format_2(
    left_first: int,
    left_classes: list[int],
    right_first: int,
    right_classes: list[int],
    row_width: int,
    array_values: list[int],
    coverage_flags: int = 0x0001,
) -> bytes:
    """Build a Format 2 (class-based) subtable.

    Layout (after the OpenType subtable header):
      rowWidth (uint16) = row width in bytes
      leftClassTableOffset (uint16) — from start of subtable header
      rightClassTableOffset (uint16) — from start of subtable header
      arrayOffset (uint16) — from start of subtable header
      kerning value array (int16[])
      left class table: firstGlyph (uint16), nGlyphs (uint16), values uint16[]
      right class table: same shape

    We lay them out in a fixed order: header(6) + format2-header(8) + array
    + leftClass + rightClass.
    """
    header_size = 6
    fmt2_header_size = 8
    array_offset = header_size + fmt2_header_size
    array_bytes = b"".join(struct.pack(">h", v) for v in array_values)

    left_offset = array_offset + len(array_bytes)
    left_table = struct.pack(">HH", left_first, len(left_classes))
    left_table += b"".join(struct.pack(">H", c) for c in left_classes)

    right_offset = left_offset + len(left_table)
    right_table = struct.pack(">HH", right_first, len(right_classes))
    right_table += b"".join(struct.pack(">H", c) for c in right_classes)

    # Format 2 in coverage high byte (0x02), flags in low byte.
    coverage = (2 << 8) | (coverage_flags & 0xFF)
    body = struct.pack(
        ">HHHH", row_width, left_offset, right_offset, array_offset
    )
    body += array_bytes + left_table + right_table
    length = header_size + len(body)
    header = struct.pack(">HHH", 0, length, coverage)
    return header + body


def test_format_2_parses_class_based_lookup() -> None:
    # Two left classes (A, B) and two right classes (X, Y). Class values
    # are byte offsets within a row. Row width = 4 bytes (= 2 int16 entries).
    # Class layout: left class 0 → row offset 0; left class 1 → row offset 4.
    # Right class 0 → col offset 0; right class 1 → col offset 2.
    # Array (4 int16 values, 8 bytes):
    #   index 0 (l=0,r=0) = 100
    #   index 1 (l=0,r=1) = -50
    #   index 2 (l=1,r=0) = 0
    #   index 3 (l=1,r=1) = 25
    blob = _make_format_2(
        left_first=10,
        left_classes=[0, 4],  # gid 10 -> class 0, gid 11 -> class 4 (row 4)
        right_first=20,
        right_classes=[0, 2],  # gid 20 -> col 0, gid 21 -> col 2
        row_width=4,
        array_values=[100, -50, 0, 25],
    )
    sub = KerningSubtable.from_bytes(blob)
    assert sub.get_format() == 2
    assert sub.get_kerning(10, 20) == 100
    assert sub.get_kerning(10, 21) == -50
    assert sub.get_kerning(11, 20) == 0
    assert sub.get_kerning(11, 21) == 25


def test_format_2_unmapped_glyph_uses_default_class_zero() -> None:
    blob = _make_format_2(
        left_first=10,
        left_classes=[0, 4],
        right_first=20,
        right_classes=[0, 2],
        row_width=4,
        array_values=[111, 222, 333, 444],
    )
    sub = KerningSubtable.from_bytes(blob)
    # gid 99 not in either class table → class 0 / 0 → first array entry.
    assert sub.get_kerning(99, 99) == 111


def test_format_2_horizontal_flag_preserved() -> None:
    blob = _make_format_2(
        left_first=10, left_classes=[0],
        right_first=20, right_classes=[0],
        row_width=2, array_values=[42],
        coverage_flags=0x01,
    )
    sub = KerningSubtable.from_bytes(blob)
    assert sub.is_horizontal() is True
    assert sub.get_format() == 2


def test_format_2_negative_gid_returns_zero() -> None:
    blob = _make_format_2(
        left_first=10, left_classes=[0],
        right_first=20, right_classes=[0],
        row_width=2, array_values=[42],
    )
    sub = KerningSubtable.from_bytes(blob)
    assert sub.get_kerning(-1, 20) == 0
    assert sub.get_kerning(10, -1) == 0


# ---------- Format header guards -------------------------------------------


def test_from_bytes_unknown_format_returns_zero_lookup() -> None:
    # Format = 1 in high byte (Apple state-machine — unsupported).
    coverage = (1 << 8) | 0x01
    body = b"\x00" * 16
    blob = struct.pack(">HHH", 0, 6 + len(body), coverage) + body
    sub = KerningSubtable.from_bytes(blob)
    assert sub.get_format() == 1
    assert sub.get_kerning(0, 1) == 0


def test_from_bytes_truncated_header_raises() -> None:
    with pytest.raises(ValueError):
        KerningSubtable.from_bytes(b"\x00\x00")


def test_from_bytes_truncated_format_0_body_raises() -> None:
    # Header valid, body truncated.
    blob = struct.pack(">HHH", 0, 9, 0x0001) + b"\x00\x00\x00"
    with pytest.raises(ValueError):
        KerningSubtable.from_bytes(blob)


def test_from_bytes_apple_version_consumes_8_byte_header() -> None:
    # length(uint32) + coverage(uint16) + tupleIndex(uint16). Format = 0.
    body = struct.pack(">HHHH", 0, 0, 0, 0)  # zero pairs
    blob = struct.pack(">IHH", 8 + len(body), 0x0000, 0) + body
    sub = KerningSubtable.from_bytes(blob, version=1)
    assert sub.get_format() == 0
    assert sub.get_kerning(0, 1) == 0


# ---------- KerningSubtable#read(stream, version) parity ------------------

from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def test_read_stream_version_0_format_0() -> None:
    """Upstream ``read(data, 0)`` parity: parses an OpenType subtable from
    a stream and populates pair data. Mirrors ``readSubtable0`` →
    ``readSubtable0Format0``."""
    blob = _make_format_0([(1, 2, -100), (3, 4, 50)], coverage=0x0001)
    stream = MemoryTTFDataStream(blob)
    sub = KerningSubtable()
    sub.read(stream, 0)
    assert sub.get_format() == 0
    assert sub.is_horizontal() is True
    assert sub.get_kerning(1, 2) == -100
    assert sub.get_kerning(3, 4) == 50


def test_read_stream_version_0_format_2() -> None:
    """Upstream ``readSubtable0`` falls through to a no-op for format 2;
    we go further and actually parse it. Verify the dispatch through the
    stream-based ``read`` path."""
    blob = _make_format_2(
        left_first=10, left_classes=[0, 4],
        right_first=20, right_classes=[0, 2],
        row_width=4,
        array_values=[100, -50, 0, 25],
    )
    stream = MemoryTTFDataStream(blob)
    sub = KerningSubtable()
    sub.read(stream, 0)
    assert sub.get_format() == 2
    assert sub.get_kerning(10, 20) == 100
    assert sub.get_kerning(11, 21) == 25


def test_read_stream_version_1_apple_logged_and_skipped() -> None:
    """Upstream ``readSubtable1`` logs and skips. We mirror that — pair
    data stays unset → 0 lookup."""
    sub = KerningSubtable()
    sub.read(MemoryTTFDataStream(b""), 1)
    assert sub.get_kerning(1, 2) == 0


def test_read_stream_unknown_version_raises() -> None:
    """Upstream throws ``IllegalStateException`` for unknown versions —
    we surface ``ValueError`` per Python convention."""
    sub = KerningSubtable()
    with pytest.raises(ValueError):
        sub.read(MemoryTTFDataStream(b""), 99)


def test_read_stream_version_0_bad_inner_version_skipped() -> None:
    """If the inner subtable version field is non-zero, upstream logs
    and bails out without populating pairs."""
    # Inner version = 99 (invalid) → readSubtable0 returns early.
    blob = struct.pack(">HHH", 99, 6, 0x0001)
    stream = MemoryTTFDataStream(blob)
    sub = KerningSubtable()
    sub.read(stream, 0)
    assert sub.get_kerning(0, 1) == 0


def test_read_stream_version_0_short_length_skipped() -> None:
    """Upstream rejects subtables shorter than the 6-byte header."""
    blob = struct.pack(">HHH", 0, 4, 0x0001)
    stream = MemoryTTFDataStream(blob)
    sub = KerningSubtable()
    sub.read(stream, 0)
    assert sub.get_kerning(0, 1) == 0


# ---------- binary search parity helper ------------------------------------


def test_binary_search_pair_matches_dict_lookup() -> None:
    """``binary_search_pair`` mirrors upstream's ``Arrays.binarySearch``
    over the sorted (left, right) pair list. Must agree with the dict
    path for every pair."""
    blob = _make_format_0([(1, 2, -100), (1, 5, 7), (3, 4, 50), (10, 20, -3)])
    sub = KerningSubtable.from_bytes(blob)
    for left, right, expected in [(1, 2, -100), (1, 5, 7), (3, 4, 50), (10, 20, -3)]:
        assert sub.binary_search_pair(left, right) == expected
        assert sub.get_kerning(left, right) == expected


def test_binary_search_pair_missing_returns_zero() -> None:
    blob = _make_format_0([(1, 2, -100)])
    sub = KerningSubtable.from_bytes(blob)
    assert sub.binary_search_pair(99, 99) == 0
    assert sub.binary_search_pair(-1, 2) == 0


def test_binary_search_pair_no_pair_data_returns_zero() -> None:
    sub = KerningSubtable()
    assert sub.binary_search_pair(1, 2) == 0
