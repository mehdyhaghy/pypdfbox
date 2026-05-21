"""Wave 1369 round-out tests for the ``KerningSubtable.read`` /
``read_subtable0`` dispatch path.

The class also exposes a ``from_bytes`` static-style ``classmethod`` —
covered by ``test_kerning_subtable_formats.py``. The ``read(...)`` entry
point that goes through a :class:`TTFDataStream` (mirroring upstream's
``KerningSubtable#read(TTFDataStream, int)`` overload) is less covered
because it consumes the subtable header itself before dispatching by
format. These tests exercise that path end-to-end.

We also exercise the ``binary_search_pair`` parity helper, which mirrors
the upstream ``Arrays.binarySearch`` over the sorted pair list, and the
``is_horizontal_kerning(cross=True/False)`` predicate's interaction with
the ``cross-stream`` coverage flag.
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf.kerning_subtable import KerningSubtable
from pypdfbox.fontbox.ttf.kerning_table import KerningTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def _format_0_subtable(
    pairs: list[tuple[int, int, int]],
    coverage_flags: int = 0x0001,
) -> bytes:
    """Build a Format 0 OpenType ``kern`` subtable starting at the
    subtable header (version, length, coverage)."""
    n_pairs = len(pairs)
    entry_selector = 0
    while (1 << (entry_selector + 1)) <= max(n_pairs, 1):
        entry_selector += 1
    search_range = (1 << entry_selector) * 6
    range_shift = n_pairs * 6 - search_range
    body = struct.pack(">HHHH", n_pairs, search_range, entry_selector, range_shift)
    for left, right, value in pairs:
        body += struct.pack(">HHh", left, right, value)
    length = 6 + len(body)
    # coverage_flags low byte; format 0 in high byte.
    header = struct.pack(">HHH", 0, length, coverage_flags & 0xFFFF)
    return header + body


def _format_2_subtable() -> bytes:
    """Build a minimal Format 2 (class-based) ``kern`` subtable.

    Layout (after the 6-byte OpenType header):
      rowWidth (uint16), leftOffsetTable (uint16), rightOffsetTable (uint16),
      arrayOffset (uint16), then the class tables and the kerning array.
    """
    header_size = 6
    body_header_size = 8
    left_class_size = 4 + 4  # firstGlyph, nGlyphs, then 2 entries
    right_class_size = 4 + 4

    left_off = header_size + body_header_size
    right_off = left_off + left_class_size
    array_off = right_off + right_class_size

    row_width = 4
    body = struct.pack(">HHHH", row_width, left_off, right_off, array_off)
    # Left class table: firstGlyph=10, nGlyphs=2, class values [0, 2]
    body += struct.pack(">HHHH", 10, 2, 0, 2)
    # Right class table: firstGlyph=20, nGlyphs=2, class values [0, 2]
    body += struct.pack(">HHHH", 20, 2, 0, 2)
    # Kerning array — 4 int16 values; index = (leftClass + rightClass) // 2
    body += struct.pack(">hhhh", -5, 7, 11, -13)

    # OpenType header: version=0, length, coverage (format 2 in high byte)
    coverage = (2 << 8) | 0x01  # horizontal, format 2
    length = header_size + len(body)
    return struct.pack(">HHH", 0, length, coverage) + body


# ---------- KerningSubtable.read dispatch ----------------------------------


def test_read_version_0_format_0_dispatches() -> None:
    blob = _format_0_subtable([(10, 20, -50), (15, 25, 100)])
    sub = KerningSubtable()
    sub.read(MemoryTTFDataStream(blob), version=0)
    assert sub.get_format() == 0
    assert sub.is_horizontal() is True
    assert sub.get_kerning(10, 20) == -50
    assert sub.get_kerning(15, 25) == 100
    assert sub.get_kerning(99, 99) == 0


def test_read_version_0_format_2_dispatches() -> None:
    blob = _format_2_subtable()
    sub = KerningSubtable()
    sub.read(MemoryTTFDataStream(blob), version=0)
    assert sub.get_format() == 2
    # leftClass=0, rightClass=0 → idx=0 → -5
    assert sub.get_kerning(10, 20) == -5
    # leftClass=0, rightClass=2 → idx=1 → 7
    assert sub.get_kerning(10, 21) == 7
    # leftClass=2, rightClass=0 → idx=1 → 7
    assert sub.get_kerning(11, 20) == 7
    # leftClass=2, rightClass=2 → idx=2 → 11
    assert sub.get_kerning(11, 21) == 11


def test_read_version_0_unsupported_format_is_silently_skipped() -> None:
    """A format byte the parser doesn't understand leaves pairs unset so
    every lookup returns 0 — matches upstream's "unsupported kerning
    sub-table" log-and-skip behaviour."""
    # Format 3 in high byte, total length 6 (no body needed beyond header).
    blob = struct.pack(">HHH", 0, 6, (3 << 8) | 0x01)
    sub = KerningSubtable()
    sub.read(MemoryTTFDataStream(blob), version=0)
    assert sub.get_format() == 3
    assert sub.get_kerning(0, 1) == 0


def test_read_version_0_bad_sub_version_bails_out() -> None:
    """A non-zero subtable version is a sentinel upstream rejects.
    The subtable should remain in its uninitialized lookup-as-zero state."""
    bad = struct.pack(">HHH", 99, 6, 0x01)
    sub = KerningSubtable()
    sub.read(MemoryTTFDataStream(bad), version=0)
    assert sub.get_kerning(0, 1) == 0


def test_read_version_0_truncated_length_bails_out() -> None:
    """Upstream's "kerning sub-table too short" guard fires when the
    header reports length < 6 — leave the subtable in lookup-as-zero
    state instead of raising."""
    too_short = struct.pack(">HHH", 0, 4, 0x01)
    sub = KerningSubtable()
    sub.read(MemoryTTFDataStream(too_short), version=0)
    assert sub.get_kerning(0, 1) == 0


def test_read_version_1_uses_apple_branch() -> None:
    """Upstream's ``readSubtable1`` logs "not yet supported" and leaves
    pairs unset — observable as a zero lookup for any pair."""
    # version 1 doesn't read from the stream meaningfully in our port;
    # feed an empty stream and confirm no exception.
    sub = KerningSubtable()
    sub.read(MemoryTTFDataStream(b""), version=1)
    assert sub.get_kerning(0, 1) == 0


def test_read_unknown_version_raises() -> None:
    """Versions other than 0 or 1 are illegal."""
    sub = KerningSubtable()
    with pytest.raises(ValueError, match="unknown kern table version"):
        sub.read(MemoryTTFDataStream(b""), version=2)


# ---------- binary_search_pair parity helper -------------------------------


def test_binary_search_pair_finds_existing_pair() -> None:
    sub = KerningSubtable.from_bytes(
        _format_0_subtable([(1, 2, 10), (3, 4, 20), (5, 6, 30)])
    )
    assert sub.binary_search_pair(3, 4) == 20
    assert sub.binary_search_pair(5, 6) == 30


def test_binary_search_pair_returns_zero_for_missing_pair() -> None:
    sub = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 10), (3, 4, 20)]))
    assert sub.binary_search_pair(99, 99) == 0


def test_binary_search_pair_rejects_negative_inputs() -> None:
    sub = KerningSubtable.from_bytes(_format_0_subtable([(1, 2, 10)]))
    assert sub.binary_search_pair(-1, 2) == 0
    assert sub.binary_search_pair(1, -1) == 0


def test_binary_search_pair_matches_dict_lookup() -> None:
    """For every pair the dict-backed ``get_kerning`` returns, the binary
    search must return the same value — upstream parity."""
    sub = KerningSubtable.from_bytes(
        _format_0_subtable([(1, 2, 10), (1, 3, 11), (4, 5, -7)])
    )
    for left, right in ((1, 2), (1, 3), (4, 5), (9, 9)):
        assert sub.binary_search_pair(left, right) == sub.get_kerning(left, right)


# ---------- is_horizontal_kerning predicate --------------------------------


def test_is_horizontal_kerning_default_excludes_cross_stream() -> None:
    """``cross=False`` (default) only matches horizontal subtables whose
    cross-stream flag is unset."""
    sub = KerningSubtable.from_bytes(
        _format_0_subtable([(1, 2, 10)], coverage_flags=0x0001),  # horizontal only
    )
    assert sub.is_horizontal_kerning() is True
    assert sub.is_horizontal_kerning(cross=False) is True
    assert sub.is_horizontal_kerning(cross=True) is False


def test_is_horizontal_kerning_cross_picks_cross_stream() -> None:
    """``cross=True`` matches the cross-stream variant."""
    sub = KerningSubtable.from_bytes(
        # horizontal | cross-stream
        _format_0_subtable([(1, 2, 10)], coverage_flags=0x0005),
    )
    assert sub.is_horizontal_kerning(cross=True) is True
    assert sub.is_horizontal_kerning(cross=False) is False


def test_is_horizontal_kerning_rejects_minimum_subtable() -> None:
    """The minimum-values flag means the subtable reports minimum
    kerning, not adjustments — upstream excludes these from horizontal
    kerning lookup, and so do we."""
    sub = KerningSubtable.from_bytes(
        # horizontal | minimums
        _format_0_subtable([(1, 2, 10)], coverage_flags=0x0003),
    )
    assert sub.is_horizontal_kerning() is False
    assert sub.is_horizontal_kerning(cross=True) is False


def test_is_horizontal_kerning_vertical_subtable_returns_false() -> None:
    """A subtable without the horizontal bit is vertical kerning — never
    selected by ``is_horizontal_kerning``."""
    sub = KerningSubtable.from_bytes(
        _format_0_subtable([(1, 2, 10)], coverage_flags=0x0000),
    )
    assert sub.is_horizontal_kerning() is False
    assert sub.is_horizontal_kerning(cross=True) is False


# ---------- get_bits / is_bits_set static helpers --------------------------


def test_is_bits_set_returns_true_for_masked_bit() -> None:
    assert KerningSubtable.is_bits_set(0b1010, 0b0010, 1) is True


def test_is_bits_set_returns_false_when_bit_cleared() -> None:
    assert KerningSubtable.is_bits_set(0b1000, 0b0010, 1) is False


def test_get_bits_extracts_shifted_field() -> None:
    """Mirrors upstream's ``getBits`` — coverage format byte sits in the
    high byte of the 16-bit coverage word."""
    # Format 3 in the high byte; low byte irrelevant.
    coverage = (3 << 8) | 0xAB
    assert (
        KerningSubtable.get_bits(coverage, KerningSubtable.COVERAGE_FORMAT, 8) == 3
    )


# ---------- KerningTable + KerningSubtable interaction ---------------------


class _FakeFTSubtable:
    """fontTools-shaped subtable used to drive ``KerningTable.from_fonttools``
    without a real font in tree."""

    def __init__(self, coverage: int, format_id: int, kern_table: dict) -> None:
        self.coverage = coverage
        self.format = format_id
        self.kernTable = kern_table  # noqa: N815 — mirrors fontTools attribute
        self.apple = False


class _FakeFTKern:
    def __init__(self, version: float, sub_tables: list[_FakeFTSubtable]) -> None:
        self.version = version
        self.kernTables = sub_tables  # noqa: N815 — mirrors fontTools attribute


def test_kerning_table_from_fonttools_propagates_subtables() -> None:
    sub = _FakeFTSubtable(coverage=0x01, format_id=0, kern_table={})
    ft = _FakeFTKern(version=0, sub_tables=[sub])
    view = KerningTable.from_fonttools(ft, ttf=None)  # type: ignore[arg-type]
    assert view.get_version() == 0
    assert view.get_initialized() is True
    assert len(view.get_subtables()) == 1
    # The high byte of the reconstructed upstream coverage word is the
    # format; the low byte are the flags.
    rebuilt_subtable = view.get_subtables()[0]
    assert rebuilt_subtable.get_format() == 0


def test_kerning_table_from_fonttools_handles_no_subtables() -> None:
    ft = _FakeFTKern(version=0, sub_tables=[])
    view = KerningTable.from_fonttools(ft, ttf=None)  # type: ignore[arg-type]
    assert view.get_subtables() == []
    assert view.get_horizontal_kerning_subtable() is None


def test_kerning_table_get_horizontal_kerning_subtable_returns_first_match() -> None:
    """Pick the first horizontal-inline subtable, skipping minimum / cross
    subtables in the same kerning table."""
    s_min = _FakeFTSubtable(coverage=0x03, format_id=0, kern_table={})
    s_horiz = _FakeFTSubtable(coverage=0x01, format_id=0, kern_table={("a", "b"): 5})
    ft = _FakeFTKern(version=0, sub_tables=[s_min, s_horiz])
    view = KerningTable.from_fonttools(ft, ttf=None)  # type: ignore[arg-type]
    selected = view.get_horizontal_kerning_subtable()
    assert selected is not None
    # The skipped first subtable had the minimum bit; the selected one
    # is the second subtable (horizontal, inline progression).
    assert selected.is_minimum() is False
    assert selected.is_horizontal() is True
