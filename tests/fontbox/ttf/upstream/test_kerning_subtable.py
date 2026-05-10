"""Upstream parity tests for ``KerningSubtable``.

Apache PDFBox 3.0.x does not ship a standalone ``KerningSubtableTest.java``;
the kern table is exercised indirectly through ``TrueTypeFontTest`` (which
invokes ``getKerning`` against a real font). We provide a small parity
surface here covering the public method contract documented in upstream
``KerningSubtable``:

* ``isHorizontalKerning()`` / ``isHorizontalKerning(boolean)`` — coverage
  flag interpretation.
* ``getKerning(int, int)`` — pair lookup, 0 when absent.
* ``getKerning(int[])`` — sequence variant returning per-glyph adjustments.
* ``read(TTFDataStream, int)`` — entry-point for both OpenType (version=0)
  and Apple (version=1) parent kern tables.
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf.kerning_subtable import KerningSubtable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def _make_format_0(pairs: list[tuple[int, int, int]], coverage: int = 0x0001) -> bytes:
    """Build a valid OpenType Format 0 kern subtable for the stream-based
    ``read(data, 0)`` parity tests."""
    n_pairs = len(pairs)
    body = struct.pack(">HHHH", n_pairs, 0, 0, 0)
    for left, right, value in pairs:
        body += struct.pack(">HHh", left, right, value)
    length = 6 + len(body)
    header = struct.pack(">HHH", 0, length, coverage & 0xFFFF)
    return header + body


def test_is_horizontal_kerning_no_arg_excludes_cross_stream() -> None:
    """Upstream ``isHorizontalKerning()`` is equivalent to
    ``isHorizontalKerning(false)`` — horizontal subtables that *aren't*
    cross-stream and aren't minimums."""
    blob = _make_format_0([(1, 2, -10)], coverage=0x0001)  # horizontal only
    sub = KerningSubtable()
    sub.read(MemoryTTFDataStream(blob), 0)
    assert sub.is_horizontal_kerning() is True
    assert sub.is_horizontal_kerning(False) is True
    assert sub.is_horizontal_kerning(True) is False


def test_get_kerning_int_int_returns_zero_for_absent_pair() -> None:
    """Upstream contract: ``getKerning(l, r)`` returns 0 if the pair is
    absent from the sorted pair list (binary search miss)."""
    blob = _make_format_0([(1, 2, -100)])
    sub = KerningSubtable()
    sub.read(MemoryTTFDataStream(blob), 0)
    assert sub.get_kerning(1, 2) == -100
    assert sub.get_kerning(2, 1) == 0


def test_get_kerning_int_array_per_glyph_pairs_with_next_non_negative() -> None:
    """Upstream ``getKerning(int[])`` semantics: for each position N,
    pair glyph N with the next non-negative glyph in the sequence."""
    blob = _make_format_0([(1, 2, -100), (2, 3, -50)])
    sub = KerningSubtable()
    sub.read(MemoryTTFDataStream(blob), 0)
    out = sub.get_kerning([1, 2, 3])
    # 1 → 2 = -100, 2 → 3 = -50, 3 → (none) = 0.
    assert out == [-100, -50, 0]


def test_read_dispatches_on_version() -> None:
    """``read(data, version)`` dispatches: 0 = OpenType, 1 = Apple,
    anything else raises (upstream throws ``IllegalStateException``)."""
    sub = KerningSubtable()
    # version=1 (Apple) is logged and skipped — pair data stays unset.
    sub.read(MemoryTTFDataStream(b""), 1)
    assert sub.get_kerning(0, 0) == 0
    # Unknown version → ValueError (Pythonic equivalent of
    # IllegalStateException).
    with pytest.raises(ValueError):
        sub.read(MemoryTTFDataStream(b""), 42)


def test_unsupported_subtable_returns_zero_per_upstream_contract() -> None:
    """When pair data is unavailable (no read or unsupported format),
    upstream's ``getKerning(l, r)`` logs a warning and returns 0."""
    sub = KerningSubtable()
    assert sub.get_kerning(1, 2) == 0


def test_is_bits_set_matches_upstream_helper() -> None:
    """Upstream ``isBitsSet(int bits, int mask, int shift)`` returns true
    when the masked & shifted value is non-zero."""
    # Coverage = 0x0005 → horizontal (bit 0) + cross-stream (bit 2) set,
    # minimums (bit 1) clear.
    coverage = 0x0005
    assert KerningSubtable.is_bits_set(
        coverage,
        KerningSubtable.COVERAGE_HORIZONTAL,
        KerningSubtable.COVERAGE_HORIZONTAL_SHIFT,
    ) is True
    assert KerningSubtable.is_bits_set(
        coverage,
        KerningSubtable.COVERAGE_MINIMUMS,
        KerningSubtable.COVERAGE_MINIMUMS_SHIFT,
    ) is False
    assert KerningSubtable.is_bits_set(
        coverage,
        KerningSubtable.COVERAGE_CROSS_STREAM,
        KerningSubtable.COVERAGE_CROSS_STREAM_SHIFT,
    ) is True


def test_get_bits_extracts_field_per_upstream_helper() -> None:
    """Upstream ``getBits(int bits, int mask, int shift)`` masks then
    right-shifts to recover the bit-field's low-order representation."""
    # Coverage 0x0201 → format byte (high) = 2, flag byte (low) = 1.
    coverage = 0x0201
    assert KerningSubtable.get_bits(
        coverage,
        KerningSubtable.COVERAGE_FORMAT,
        KerningSubtable.COVERAGE_FORMAT_SHIFT,
    ) == 2
    assert KerningSubtable.get_bits(
        coverage,
        KerningSubtable.COVERAGE_HORIZONTAL,
        KerningSubtable.COVERAGE_HORIZONTAL_SHIFT,
    ) == 1


def test_read_subtable0_dispatches_to_format_0_body() -> None:
    """Upstream ``readSubtable0`` reads the OpenType header (version,
    length, coverage) and dispatches on the format byte. Format 0 ends
    up populating the pair table."""
    blob = _make_format_0([(10, 20, -42)], coverage=0x0001)
    sub = KerningSubtable()
    sub.read_subtable0(MemoryTTFDataStream(blob))
    assert sub.get_kerning(10, 20) == -42
    assert sub.get_kerning(20, 10) == 0


def test_read_subtable1_is_unsupported_no_pair_data() -> None:
    """Upstream ``readSubtable1`` logs "not yet supported" and leaves
    pair data unset; subsequent ``getKerning`` returns 0."""
    sub = KerningSubtable()
    sub.read_subtable1(MemoryTTFDataStream(b""))
    assert sub.get_kerning(1, 2) == 0


def test_read_subtable0_format0_reads_pair_body() -> None:
    """Upstream ``readSubtable0Format0`` body reader: nPairs (uint16),
    searchRange (uint16), entrySelector (uint16), rangeShift (uint16),
    then nPairs * (left, right, value) entries."""
    body = struct.pack(">HHHH", 1, 0, 0, 0) + struct.pack(">HHh", 7, 8, -33)
    sub = KerningSubtable()
    sub.read_subtable0_format0(MemoryTTFDataStream(body))
    assert sub.get_kerning(7, 8) == -33


def test_read_subtable0_format2_is_log_only_helper() -> None:
    """Upstream ``readSubtable0Format2`` is a no-op log helper; the
    real Format 2 decoder runs from the buffered length-aware path."""
    sub = KerningSubtable()
    # Stream content is irrelevant — the helper logs and returns.
    sub.read_subtable0_format2(MemoryTTFDataStream(b"\x00\x00\x00\x00"))
    assert sub.get_kerning(1, 2) == 0
