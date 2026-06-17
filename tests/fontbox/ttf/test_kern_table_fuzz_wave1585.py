"""Fuzz / parity tests for the legacy TrueType ``kern`` table parser.

Hammers ``KerningSubtable`` Format 0 pair lookup, coverage-byte parsing
(horizontal / minimums / cross-stream flags + the format in the high byte),
the binary-search over the sorted pair array, the ``KerningTable`` horizontal
non-cross-stream subtable selection, and edge cases (empty table, numTables=0).

Behaviour is checked against upstream Apache PDFBox
``org.apache.fontbox.ttf.KerningSubtable`` (3.0.7):

* Coverage masks ``COVERAGE_HORIZONTAL=0x0001``, ``COVERAGE_MINIMUMS=0x0002``,
  ``COVERAGE_CROSS_STREAM=0x0004``, ``COVERAGE_FORMAT=0xFF00`` with shifts
  ``0/1/2/8`` (``KerningSubtable.java`` L36-44).
* ``isHorizontalKerning(cross)`` short-circuit logic (L103-121).
* ``PairData0Format0`` binary-search lookup over sorted ``(left,right,value)``
  rows; miss returns 0 (L279-289). Value column is a signed int16 (L272).
* ``getKerning(int[])`` returns ``null`` when ``pairs == null`` (L133-160).
* ``readSubtable0`` reads version/length/coverage then dispatches on the
  format high byte (L180-220); ``length < 6`` aborts (L189-193).
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf.kerning_subtable import KerningSubtable
from pypdfbox.fontbox.ttf.kerning_table import KerningTable
from pypdfbox.fontbox.ttf.pair_data0_format0 import PairData0Format0
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

# ---------------------------------------------------------------------------
# Synthetic kern subtable builders (OpenType layout PDFBox parses).
# ---------------------------------------------------------------------------


def _search_header(n_pairs: int) -> bytes:
    """The 8-byte binary-search header upstream emits for Format 0.

    ``searchRange = 2^floor(log2(n)) * 6``, ``entrySelector = floor(log2(n))``,
    ``rangeShift = n*6 - searchRange``. The parser does not validate these,
    but real fonts set them so we keep upstream fidelity.
    """
    if n_pairs == 0:
        return struct.pack(">HHHH", 0, 0, 0, 0)
    entry_selector = 0
    while (1 << (entry_selector + 1)) <= n_pairs:
        entry_selector += 1
    search_range = (1 << entry_selector) * 6
    range_shift = n_pairs * 6 - search_range
    return struct.pack(">HHHH", n_pairs, search_range, entry_selector, range_shift)


def _format_0_subtable(
    pairs: list[tuple[int, int, int]],
    coverage_flags: int = 0x0001,
) -> bytes:
    """Build a full OpenType Format-0 subtable (header + body).

    ``coverage_flags`` is the low byte (horizontal / minimums / cross-stream).
    Format 0 lives in the high byte, so the coverage word is just the flags.
    """
    body = _search_header(len(pairs))
    # Pairs must be sorted by (left, right) for upstream binary search.
    for left, right, value in sorted(pairs, key=lambda p: (p[0], p[1])):
        body += struct.pack(">HHh", left, right, value)
    length = 6 + len(body)
    coverage = (0x00 << 8) | (coverage_flags & 0xFF)
    return struct.pack(">HHH", 0, length, coverage) + body


def _subtable_with_format(
    fmt: int, coverage_flags: int = 0x0001, body: bytes = b""
) -> bytes:
    """Build a subtable whose coverage high byte selects ``fmt``."""
    payload = body if body else struct.pack(">HHHH", 0, 0, 0, 0)
    length = 6 + len(payload)
    coverage = ((fmt & 0xFF) << 8) | (coverage_flags & 0xFF)
    return struct.pack(">HHH", 0, length, coverage) + payload


def _kern_table_bytes(subtables: list[bytes], version: int = 0) -> bytes:
    """Wrap subtables in the OpenType ``kern`` table header.

    Layout: version (uint16), nTables (uint16), then each subtable.
    """
    header = struct.pack(">HH", version, len(subtables))
    return header + b"".join(subtables)


def _read_via_stream(subtable_bytes: bytes) -> KerningSubtable:
    """Parse a single subtable through the ``TTFDataStream`` read path
    (mirrors upstream ``KerningSubtable#read(data, version=0)``)."""
    sub = KerningSubtable()
    sub.read(MemoryTTFDataStream(subtable_bytes), 0)
    return sub


# ---------------------------------------------------------------------------
# Format 0 pair lookup — present / absent / signed value.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pairs,probe,expected",
    [
        ([(1, 2, -100)], (1, 2), -100),
        ([(1, 2, -100)], (2, 1), 0),  # reversed pair absent
        ([(3, 7, 40), (3, 8, -40)], (3, 8), -40),
        ([(10, 20, 0)], (10, 20), 0),  # present but zero value
        ([(1, 2, 32767)], (1, 2), 32767),  # int16 max
        ([(1, 2, -32768)], (1, 2), -32768),  # int16 min
        ([(0, 0, 11)], (0, 0), 11),  # zero GIDs
        ([(65535, 65534, -7)], (65535, 65534), -7),  # max uint16 GIDs
    ],
    ids=[
        "present",
        "reversed_absent",
        "second_of_two",
        "zero_value_present",
        "int16_max",
        "int16_min",
        "zero_gids",
        "max_gids",
    ],
)
def test_format_0_pair_lookup(
    pairs: list[tuple[int, int, int]], probe: tuple[int, int], expected: int
) -> None:
    sub = KerningSubtable.from_bytes(_format_0_subtable(pairs))
    assert sub.get_kerning(probe[0], probe[1]) == expected


def test_format_0_absent_pair_returns_zero() -> None:
    sub = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 5), (3, 4, 6)]))
    assert sub.get_kerning(9, 9) == 0
    assert sub.get_kerning(1, 4) == 0
    assert sub.get_kerning(3, 2) == 0


def test_format_0_signed_value_preserved() -> None:
    # Raw bytes 0x8000 must decode as -32768, not 32768 (upstream readSignedShort).
    sub = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, -1), (5, 6, -300)]))
    assert sub.get_kerning(1, 2) == -1
    assert sub.get_kerning(5, 6) == -300


# ---------------------------------------------------------------------------
# Coverage-byte parsing — flags + format high byte.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "flags,horizontal,minimums,cross",
    [
        (0x0000, False, False, False),
        (0x0001, True, False, False),  # horizontal
        (0x0002, False, True, False),  # minimums
        (0x0004, False, False, True),  # cross-stream
        (0x0005, True, False, True),  # horizontal + cross
        (0x0003, True, True, False),  # horizontal + minimums
        (0x0007, True, True, True),  # all three
    ],
    ids=[
        "none",
        "horizontal",
        "minimums",
        "cross",
        "horiz_cross",
        "horiz_min",
        "all",
    ],
)
def test_coverage_flag_bit_positions(
    flags: int, horizontal: bool, minimums: bool, cross: bool
) -> None:
    sub = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 1)], flags))
    assert sub.is_horizontal() is horizontal
    assert sub.is_minimum() is minimums
    assert sub.is_cross_stream() is cross


@pytest.mark.parametrize("fmt", [0, 1, 2, 3, 255])
def test_format_extracted_from_high_byte(fmt: int) -> None:
    sub = KerningSubtable.from_bytes(_subtable_with_format(fmt, 0x0001))
    assert sub.get_format() == fmt


def test_coverage_word_reconstructed_high_byte_format() -> None:
    # Format 2 + horizontal flag => coverage word 0x0201.
    sub = KerningSubtable.from_bytes(
        _subtable_with_format(2, 0x0001, struct.pack(">HHHH", 0, 6, 8, 10))
    )
    assert sub.get_coverage() == 0x0201
    assert sub.get_format() == 2
    assert sub.is_horizontal() is True


def test_high_byte_flags_do_not_leak_into_low_flags() -> None:
    # A format byte of 0x07 (all low bits set) must NOT turn on horizontal/
    # minimum/cross — those are read from the LOW byte only.
    sub = KerningSubtable.from_bytes(_subtable_with_format(0x07, 0x0000))
    assert sub.get_format() == 7
    assert sub.is_horizontal() is False
    assert sub.is_minimum() is False
    assert sub.is_cross_stream() is False


# ---------------------------------------------------------------------------
# isHorizontalKerning(cross) short-circuit logic.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "flags,cross_arg,expected",
    [
        (0x0001, False, True),  # horizontal, inline -> True
        (0x0001, True, False),  # horizontal but not cross -> cross asks False
        (0x0005, False, False),  # horizontal+cross, inline -> False
        (0x0005, True, True),  # horizontal+cross, cross -> True
        (0x0003, False, False),  # minimums disqualifies
        (0x0003, True, False),  # minimums disqualifies even cross
        (0x0000, False, False),  # not horizontal
        (0x0004, False, False),  # cross only, not horizontal
    ],
    ids=[
        "horiz_inline",
        "horiz_cross_query",
        "horizcross_inline",
        "horizcross_cross",
        "min_inline",
        "min_cross",
        "nonhoriz",
        "crossonly",
    ],
)
def test_is_horizontal_kerning_logic(
    flags: int, cross_arg: bool, expected: bool
) -> None:
    sub = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 1)], flags))
    assert sub.is_horizontal_kerning(cross_arg) is expected


# ---------------------------------------------------------------------------
# Subtable selection on KerningTable.
# ---------------------------------------------------------------------------


def _wrap_table(*subtables: KerningSubtable) -> KerningTable:
    table = KerningTable()
    table._subtables = list(subtables)  # noqa: SLF001
    return table


def test_selection_skips_cross_stream_and_picks_horizontal() -> None:
    cross = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 9)], 0x0005))
    horiz = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 9)], 0x0001))
    table = _wrap_table(cross, horiz)
    assert table.get_horizontal_kerning_subtable(False) is horiz
    assert table.get_horizontal_kerning_subtable(True) is cross


def test_selection_skips_vertical_subtables() -> None:
    vertical = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 9)], 0x0000))
    horiz = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 9)], 0x0001))
    table = _wrap_table(vertical, horiz)
    assert table.get_horizontal_kerning_subtable() is horiz


def test_selection_skips_minimum_subtables() -> None:
    minimum = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 9)], 0x0003))
    horiz = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 9)], 0x0001))
    table = _wrap_table(minimum, horiz)
    assert table.get_horizontal_kerning_subtable() is horiz


def test_selection_returns_first_matching() -> None:
    h1 = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 1)], 0x0001))
    h2 = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 2)], 0x0001))
    table = _wrap_table(h1, h2)
    assert table.get_horizontal_kerning_subtable() is h1


def test_selection_none_when_no_horizontal() -> None:
    cross = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 1)], 0x0005))
    minimum = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 1)], 0x0003))
    table = _wrap_table(cross, minimum)
    assert table.get_horizontal_kerning_subtable(False) is None


def test_empty_table_no_subtables_returns_none() -> None:
    table = _wrap_table()
    assert table.get_horizontal_kerning_subtable() is None
    assert table.get_horizontal_kerning_subtable(True) is None
    assert table.get_subtables() == []


# ---------------------------------------------------------------------------
# Binary search over the sorted pair array (PairData0Format0).
# ---------------------------------------------------------------------------


def _pair_data(rows: list[tuple[int, int, int]]) -> PairData0Format0:
    body = _search_header(len(rows))
    for left, right, value in rows:
        body += struct.pack(">HHh", left, right, value)
    pd = PairData0Format0()
    pd.read(MemoryTTFDataStream(body))
    return pd


def test_binary_search_finds_middle_and_ends() -> None:
    rows = [(1, 1, 10), (1, 5, 20), (3, 2, 30), (3, 9, 40), (8, 1, 50)]
    pd = _pair_data(rows)
    assert pd.get_kerning(1, 1) == 10  # first
    assert pd.get_kerning(3, 2) == 30  # middle
    assert pd.get_kerning(8, 1) == 50  # last
    assert pd.get_kerning(3, 9) == 40


def test_binary_search_miss_between_keys_returns_zero() -> None:
    pd = _pair_data([(1, 1, 10), (3, 2, 30), (8, 1, 50)])
    assert pd.get_kerning(2, 0) == 0  # left between 1 and 3
    assert pd.get_kerning(1, 2) == 0  # same left, missing right
    assert pd.get_kerning(0, 0) == 0  # below all
    assert pd.get_kerning(99, 99) == 0  # above all


def test_binary_search_empty_pairs_returns_zero() -> None:
    pd = _pair_data([])
    assert pd.get_kerning(1, 2) == 0


def test_binary_search_subtable_view_matches_dict_lookup() -> None:
    pairs = [(1, 2, -5), (1, 9, 7), (4, 4, 13), (4, 5, -2)]
    sub = KerningSubtable.from_bytes(_format_0_subtable(pairs))
    for left, right, value in pairs:
        assert sub.get_kerning(left, right) == value
        assert sub.binary_search_pair(left, right) == value
    assert sub.binary_search_pair(2, 2) == 0


def test_pair_data_compare_orders_left_then_right() -> None:
    assert PairData0Format0.compare((1, 2, 0), (1, 3, 0)) < 0
    assert PairData0Format0.compare((2, 0, 0), (1, 9, 0)) > 0
    assert PairData0Format0.compare((5, 5, 0), (5, 5, 99)) == 0
    assert PairData0Format0.compare((1, 9, 0), (1, 2, 0)) > 0


# ---------------------------------------------------------------------------
# (left << 16 | right) key packing: left/right are NOT swapped.
# ---------------------------------------------------------------------------


def test_key_packing_left_right_not_swapped() -> None:
    sub = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 100), (2, 1, -100)]))
    assert sub.get_kerning(1, 2) == 100
    assert sub.get_kerning(2, 1) == -100  # distinct ordered key


def test_key_packing_distinguishes_swapped_high_low() -> None:
    # (0, 256) and (256, 0) would collide if packed as a single int with a
    # wrong shift. They must stay distinct.
    sub = KerningSubtable.from_bytes(
        _format_0_subtable([(0, 256, 11), (256, 0, 22)])
    )
    assert sub.get_kerning(0, 256) == 11
    assert sub.get_kerning(256, 0) == 22


# ---------------------------------------------------------------------------
# getKerning(int[]) sequence — present vs unsupported (pairs == null).
# ---------------------------------------------------------------------------


def test_sequence_lookup_present_pairs() -> None:
    sub = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, -100), (2, 1, -80)]))
    assert sub.get_kerning([1, 2, 1]) == [-100, -80, 0]


def test_sequence_lookup_skips_negative_sentinel() -> None:
    sub = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, -50)]))
    # index 0 (gid 1) pairs with next non-negative gid (2), skipping the -1.
    assert sub.get_kerning([1, -1, 2]) == [-50, 0, 0]


def test_sequence_lookup_returns_none_when_pairs_unsupported() -> None:
    # Format 1 leaves pairs unset; upstream getKerning(int[]) returns null.
    sub = KerningSubtable.from_bytes(_subtable_with_format(1, 0x0001))
    assert sub.get_kerning([1, 2, 3]) is None


# ---------------------------------------------------------------------------
# Whole-table parsing via stream + numTables=0 / empty body.
# ---------------------------------------------------------------------------


def test_stream_read_format_0_pairs() -> None:
    sub = _read_via_stream(_format_0_subtable([(1, 2, -100), (3, 4, 25)], 0x0001))
    assert sub.get_format() == 0
    assert sub.is_horizontal() is True
    assert sub.get_kerning(1, 2) == -100
    assert sub.get_kerning(3, 4) == 25
    assert sub.get_kerning(5, 6) == 0


def test_stream_read_too_short_length_aborts() -> None:
    # length < 6 => upstream warns and leaves pairs unset (lookup -> 0).
    blob = struct.pack(">HHH", 0, 4, 0x0001)
    sub = _read_via_stream(blob)
    assert sub.get_kerning(1, 2) == 0


def test_stream_read_unsupported_subtable_version_aborts() -> None:
    # subtable version != 0 => upstream bails out before reading coverage.
    blob = struct.pack(">HHH", 1, 100, 0x0001) + _search_header(0)
    sub = _read_via_stream(blob)
    assert sub.get_kerning(1, 2) == 0


def test_kern_table_zero_subtables_builds_empty() -> None:
    raw = _kern_table_bytes([], version=0)
    version, n_tables = struct.unpack_from(">HH", raw, 0)
    assert version == 0
    assert n_tables == 0
    # An empty KerningTable selects nothing.
    table = _wrap_table()
    assert table.get_horizontal_kerning_subtable() is None


def test_kern_table_multiple_subtables_roundtrip() -> None:
    s0 = _format_0_subtable([(1, 2, 5)], 0x0001)
    s1 = _format_0_subtable([(3, 4, -5)], 0x0005)
    raw = _kern_table_bytes([s0, s1], version=0)
    version, n_tables = struct.unpack_from(">HH", raw, 0)
    assert version == 0
    assert n_tables == 2
    # Parse each subtable region back individually.
    sub0 = KerningSubtable.from_bytes(s0)
    sub1 = KerningSubtable.from_bytes(s1)
    table = _wrap_table(sub0, sub1)
    assert table.get_horizontal_kerning_subtable(False) is sub0
    assert table.get_horizontal_kerning_subtable(True) is sub1


def test_read_subtable_version_dispatch_rejects_unknown() -> None:
    sub = KerningSubtable()
    with pytest.raises(ValueError, match="unknown kern table version"):
        sub.read(MemoryTTFDataStream(_format_0_subtable([(1, 2, 1)])), 2)
