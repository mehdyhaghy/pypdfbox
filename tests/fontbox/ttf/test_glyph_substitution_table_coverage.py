"""Coverage-boost tests for :mod:`pypdfbox.fontbox.ttf.glyph_substitution_table`.

Targets the SFNT byte-level ``read_*`` parser surface the existing
``test_glyph_substitution_table*`` suites don't exercise (those rely on
fontTools to populate the structures). Crafting tiny GSUB sub-blocks in
memory hits ``read_script_list``, ``read_script_table``,
``read_lang_sys_table``, ``read_feature_list``, ``read_feature_table``,
``read_lookup_list``, ``read_lookup_table``, ``read_lookup_subtable``,
``read_single_lookup_sub_table`` (formats 1 & 2),
``read_multiple_substitution_subtable``,
``read_alternate_substitution_subtable``,
``read_ligature_substitution_subtable`` (including
``read_ligature_set_table`` and ``read_ligature_table``), and
``read_coverage_table`` (both formats + the unknown-format error).
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable
from pypdfbox.fontbox.ttf.table.common.coverage_table_format1 import (
    CoverageTableFormat1,
)
from pypdfbox.fontbox.ttf.table.common.coverage_table_format2 import (
    CoverageTableFormat2,
)
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def _u16(v: int) -> bytes:
    return struct.pack(">H", v)


def _s16(v: int) -> bytes:
    return struct.pack(">h", v)


def _u32(v: int) -> bytes:
    return struct.pack(">I", v)


def _tag(t: str) -> bytes:
    assert len(t) == 4
    return t.encode("iso-8859-1")


# ---------- read_coverage_table -------------------------------------------


def test_read_coverage_table_format1() -> None:
    """Format 1: ``[format(1)][glyphCount][glyph...]`` round-trips to a
    :class:`CoverageTableFormat1` with the same glyph array."""
    payload = _u16(1) + _u16(3) + _u16(10) + _u16(20) + _u16(30)
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    cov = table.read_coverage_table(stream, 0)
    assert isinstance(cov, CoverageTableFormat1)
    assert cov.get_size() == 3
    assert cov.get_glyph_id(1) == 20


def test_read_coverage_table_format2() -> None:
    """Format 2: ``[format(2)][rangeCount][range...]`` where each
    range is ``(start, end, startCoverageIndex)``."""
    payload = (
        _u16(2)        # format
        + _u16(2)      # rangeCount
        + _u16(10) + _u16(15) + _u16(0)
        + _u16(20) + _u16(25) + _u16(6)
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    cov = table.read_coverage_table(stream, 0)
    assert isinstance(cov, CoverageTableFormat2)
    assert cov.get_size() == 12  # 6 + 6 glyphs


def test_read_coverage_table_unknown_format_raises() -> None:
    payload = _u16(99)  # unknown format
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    with pytest.raises(OSError, match="Unknown coverage format"):
        table.read_coverage_table(stream, 0)


# ---------- read_single_lookup_sub_table ----------------------------------


def test_read_single_lookup_subtable_format1() -> None:
    """Format 1 single subst: ``[format(1)][coverageOffset][deltaGlyphID]``
    plus a coverage block at ``coverageOffset``."""
    # Layout: subst block at offset 0, coverage block at offset 6.
    payload = (
        _u16(1)          # subst_format
        + _u16(6)        # coverage_offset (relative to subtable start)
        + _s16(-3)       # delta_glyph_id
        # coverage starts here at offset 6
        + _u16(1) + _u16(2) + _u16(5) + _u16(8)
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    result = table.read_single_lookup_sub_table(stream, 0)
    assert result is not None
    assert result["subst_format"] == 1
    assert result["delta_glyph_id"] == -3
    assert isinstance(result["coverage_table"], CoverageTableFormat1)


def test_read_single_lookup_subtable_format2() -> None:
    """Format 2: ``[format(2)][coverageOffset][glyphCount][glyphID...]``."""
    payload = (
        _u16(2)          # subst_format
        + _u16(10)       # coverage_offset
        + _u16(2)        # glyph_count
        + _u16(100) + _u16(200)
        # coverage at offset 10
        + _u16(1) + _u16(2) + _u16(7) + _u16(9)
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    result = table.read_single_lookup_sub_table(stream, 0)
    assert result is not None
    assert result["subst_format"] == 2
    assert result["substitute_glyph_ids"] == [100, 200]


def test_read_single_lookup_subtable_unknown_format() -> None:
    payload = _u16(7) + _u16(0)  # bogus subst_format
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    assert table.read_single_lookup_sub_table(stream, 0) is None


# ---------- read_multiple_substitution_subtable ---------------------------


def test_read_multiple_substitution_subtable() -> None:
    # subst_format(1), coverage_offset, sequence_count, sequence_offset...
    # then coverage block, then sequence tables (each: glyph_count + glyph_ids).
    # We'll place coverage at the end and sequences right after the header.
    # Header is 2 + 2 + 2 + 2*1 = 8 bytes for one sequence.
    # Sequence at offset 8: glyph_count + glyph_ids = 2 + 2*2 = 6 bytes.
    # Coverage at offset 14.
    payload = (
        _u16(1)          # subst_format
        + _u16(14)       # coverage_offset
        + _u16(1)        # sequence_count
        + _u16(8)        # sequence_offset[0]
        + _u16(2) + _u16(50) + _u16(60)  # sequence: 2 glyphs
        # coverage at offset 14: format 1, count 1, glyph 5
        + _u16(1) + _u16(1) + _u16(5)
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    result = table.read_multiple_substitution_subtable(stream, 0)
    assert result["subst_format"] == 1
    seqs = result["sequence_tables"]
    assert len(seqs) == 1
    assert seqs[0]["substitute_glyph_ids"] == [50, 60]


def test_read_multiple_substitution_subtable_wrong_format_raises() -> None:
    payload = _u16(99)
    with pytest.raises(OSError, match="LigatureSubstitutionTable"):
        GlyphSubstitutionTable().read_multiple_substitution_subtable(
            MemoryTTFDataStream(payload), 0,
        )


def test_read_multiple_substitution_subtable_size_mismatch_raises() -> None:
    """sequence_count (2) vs coverage size (1) — must raise."""
    # Header: subst_format + coverage_offset + sequence_count + 2*offset = 10 bytes
    payload = (
        _u16(1)          # subst_format
        + _u16(10)       # coverage_offset
        + _u16(2)        # sequence_count -- mismatch
        + _u16(99)       # sequence_offset[0] (doesn't matter, never reached)
        + _u16(99)       # sequence_offset[1]
        # coverage at offset 10: format 1, count 1, glyph 5
        + _u16(1) + _u16(1) + _u16(5)
    )
    with pytest.raises(OSError, match="coverage count"):
        GlyphSubstitutionTable().read_multiple_substitution_subtable(
            MemoryTTFDataStream(payload), 0,
        )


# ---------- read_alternate_substitution_subtable --------------------------


def test_read_alternate_substitution_subtable() -> None:
    payload = (
        _u16(1)          # subst_format
        + _u16(14)       # coverage_offset
        + _u16(1)        # alt_set_count
        + _u16(8)        # alternate_offset[0]
        + _u16(2) + _u16(70) + _u16(80)  # alt set: 2 glyphs
        # coverage at offset 14
        + _u16(1) + _u16(1) + _u16(6)
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    result = table.read_alternate_substitution_subtable(stream, 0)
    assert result["subst_format"] == 1
    alt = result["alternate_set_tables"]
    assert alt[0]["alternate_glyph_ids"] == [70, 80]


def test_read_alternate_substitution_subtable_wrong_format_raises() -> None:
    payload = _u16(99)
    with pytest.raises(OSError, match="AlternateSubstitutionTable"):
        GlyphSubstitutionTable().read_alternate_substitution_subtable(
            MemoryTTFDataStream(payload), 0,
        )


def test_read_alternate_substitution_subtable_size_mismatch_raises() -> None:
    payload = (
        _u16(1)          # subst_format
        + _u16(10)       # coverage_offset
        + _u16(2)        # alt_set_count -- mismatch
        + _u16(99) + _u16(99)
        # coverage at offset 10
        + _u16(1) + _u16(1) + _u16(6)
    )
    with pytest.raises(OSError, match="coverage count"):
        GlyphSubstitutionTable().read_alternate_substitution_subtable(
            MemoryTTFDataStream(payload), 0,
        )


# ---------- read_ligature_substitution_subtable ---------------------------


def test_read_ligature_substitution_subtable() -> None:
    """One ligature set with one ligature ``f + i -> fi``."""
    # Header: subst_format + coverage_offset + lig_set_count + lig_offset[0]
    #         = 2 + 2 + 2 + 2 = 8 bytes
    # Ligature set at offset 8: lig_count + lig_offset = 2 + 2 = 4 bytes
    # Ligature table at offset 8 + 4 = 12: lig_glyph + comp_count + comp[1..]
    #   = 2 + 2 + 2 = 6 bytes
    # Coverage at offset 18.
    payload = (
        _u16(1)          # subst_format
        + _u16(18)       # coverage_offset
        + _u16(1)        # lig_set_count
        + _u16(8)        # ligature_offset[0]
        # ligature set at offset 8
        + _u16(1)        # ligature_count
        + _u16(4)        # ligature_offset[0] (relative to lig-set start)
        # ligature table at offset 12
        + _u16(900)      # ligature_glyph (fi GID)
        + _u16(2)        # component_count
        + _u16(105)      # second component GID (first is implied coverage glyph)
        # coverage at offset 18: format 1, count 1, glyph 102 (= f)
        + _u16(1) + _u16(1) + _u16(102)
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    result = table.read_ligature_substitution_subtable(stream, 0)
    assert result["subst_format"] == 1
    lig_sets = result["ligature_set_tables"]
    assert len(lig_sets) == 1
    lig_tables = lig_sets[0]["ligature_tables"]
    assert lig_tables[0]["ligature_glyph"] == 900
    assert lig_tables[0]["component_count"] == 2
    # First component is coverage glyph (102), second from the table (105).
    assert lig_tables[0]["component_glyph_ids"] == [102, 105]


def test_read_ligature_substitution_subtable_wrong_format_raises() -> None:
    payload = _u16(99)
    with pytest.raises(OSError, match="LigatureSubstitutionTable"):
        GlyphSubstitutionTable().read_ligature_substitution_subtable(
            MemoryTTFDataStream(payload), 0,
        )


def test_read_ligature_substitution_subtable_size_mismatch_raises() -> None:
    payload = (
        _u16(1)          # subst_format
        + _u16(10)       # coverage_offset
        + _u16(2)        # lig_set_count -- mismatch
        + _u16(99) + _u16(99)
        # coverage at offset 10
        + _u16(1) + _u16(1) + _u16(102)
    )
    with pytest.raises(OSError, match="coverage count"):
        GlyphSubstitutionTable().read_ligature_substitution_subtable(
            MemoryTTFDataStream(payload), 0,
        )


def test_read_ligature_table_corrupt_component_count_raises() -> None:
    """A ligature with > 100 components is treated as corrupt."""
    payload = _u16(900) + _u16(101)  # ligature_glyph, component_count=101
    with pytest.raises(OSError, match="font likely corrupt"):
        GlyphSubstitutionTable().read_ligature_table(
            MemoryTTFDataStream(payload), 0, 5,
        )


def test_read_ligature_table_zero_components() -> None:
    """component_count == 0 returns an empty component list (the
    coverage-glyph slot doesn't exist)."""
    payload = _u16(900) + _u16(0)
    result = GlyphSubstitutionTable().read_ligature_table(
        MemoryTTFDataStream(payload), 0, 5,
    )
    assert result["component_count"] == 0
    assert result["component_glyph_ids"] == []


# ---------- read_lookup_subtable dispatch ----------------------------------


def test_read_lookup_subtable_type_1_dispatches() -> None:
    payload = (
        _u16(1) + _u16(6) + _s16(2)
        + _u16(1) + _u16(1) + _u16(10)
    )
    result = GlyphSubstitutionTable().read_lookup_subtable(
        MemoryTTFDataStream(payload), 0, 1,
    )
    assert result is not None and result["subst_format"] == 1


def test_read_lookup_subtable_type_5_unsupported() -> None:
    """Lookup types 5/6/8 hit the default ``None`` branch."""
    result = GlyphSubstitutionTable().read_lookup_subtable(
        MemoryTTFDataStream(b""), 0, 5,
    )
    assert result is None


def test_read_lookup_subtable_type_8_unsupported() -> None:
    result = GlyphSubstitutionTable().read_lookup_subtable(
        MemoryTTFDataStream(b""), 0, 8,
    )
    assert result is None


# ---------- read_lookup_table ---------------------------------------------


def test_read_lookup_table_type_1_no_mark_filter() -> None:
    # Header: lookup_type + lookup_flag + sub_table_count + sub_offset
    #         = 2 + 2 + 2 + 2 = 8 bytes
    # Sub at offset 8: format 1 single subst (size 12)
    payload = (
        _u16(1)          # lookup_type
        + _u16(0)        # lookup_flag (no mark-filter)
        + _u16(1)        # sub_table_count
        + _u16(8)        # sub_offset[0]
        # subtable at offset 8: format1, coverage_offset=6, delta=1
        + _u16(1) + _u16(6) + _s16(1)
        # coverage at offset 14
        + _u16(1) + _u16(1) + _u16(50)
    )
    result = GlyphSubstitutionTable().read_lookup_table(
        MemoryTTFDataStream(payload), 0,
    )
    assert result["lookup_type"] == 1
    assert result["lookup_flag"] == 0
    assert result["mark_filtering_set"] == 0
    assert len(result["sub_tables"]) == 1
    assert result["sub_tables"][0]["subst_format"] == 1


def test_read_lookup_table_with_mark_filter_set() -> None:
    """lookup_flag bit 0x0010 set means a trailing mark_filtering_set."""
    payload = (
        _u16(1)
        + _u16(0x0010)
        + _u16(1)
        + _u16(10)       # sub_offset (after the 2-byte mark-filter slot)
        + _u16(42)       # mark_filtering_set
        # subtable at offset 10
        + _u16(1) + _u16(6) + _s16(1)
        + _u16(1) + _u16(1) + _u16(50)
    )
    result = GlyphSubstitutionTable().read_lookup_table(
        MemoryTTFDataStream(payload), 0,
    )
    assert result["mark_filtering_set"] == 42


def test_read_lookup_table_unsupported_type_returns_none_subtables() -> None:
    """Types 5/6/8 — the parser emits a debug log and returns subtables
    populated as ``None``."""
    payload = (
        _u16(5)          # lookup_type 5 (context — unsupported)
        + _u16(0)
        + _u16(1)
        + _u16(8)
        # filler bytes for "subtable"
        + b"\x00" * 8
    )
    result = GlyphSubstitutionTable().read_lookup_table(
        MemoryTTFDataStream(payload), 0,
    )
    assert result["lookup_type"] == 5
    # Unsupported type: sub_tables list is allocated but never filled.
    assert result["sub_tables"] == [None]


def test_read_lookup_table_zero_offset_short_circuits() -> None:
    """When a sub_table_offset is 0 we get an error + early-return empty."""
    payload = (
        _u16(1)          # lookup_type
        + _u16(0)        # lookup_flag
        + _u16(1)        # sub_table_count
        + _u16(0)        # sub_offset[0] is zero — invalid
    )
    result = GlyphSubstitutionTable().read_lookup_table(
        MemoryTTFDataStream(payload), 0,
    )
    assert result["sub_tables"] == []


def test_read_lookup_table_offset_past_eof_short_circuits() -> None:
    """sub_offset that lands past end of stream triggers the error
    branch returning empty sub_tables."""
    payload = (
        _u16(1)
        + _u16(0)
        + _u16(1)
        + _u16(65000)    # absurd offset (well past end of stream)
        + b"\x00" * 4
    )
    result = GlyphSubstitutionTable().read_lookup_table(
        MemoryTTFDataStream(payload), 0,
    )
    assert result["sub_tables"] == []


def test_read_lookup_table_type_7_extension_unwraps() -> None:
    """LookupType 7 = ExtensionSubst — the inner lookup_type promotes to
    the outer ``lookup_type`` field (mirrors upstream's transparent
    unwrap)."""
    # Outer header: lookup_type + flag + sub_count + sub_offset = 8 bytes
    # Subtable at offset 8 (8 bytes: subst_format + ext_type + ext_offset_u32)
    # ends at offset 16. Inner subtable immediately follows at offset 16.
    # ext_offset is *relative to subtable start (8)*, so to point at 16 use 8.
    payload = (
        _u16(7)          # lookup_type=7
        + _u16(0)        # lookup_flag
        + _u16(1)        # sub_table_count
        + _u16(8)        # sub_offset[0]
        # extension subtable at offset 8 (size 8 bytes)
        + _u16(1)        # subst_format=1
        + _u16(1)        # extension_lookup_type=1
        + _u32(8)        # extension_offset (u32!), 8 + 8 = 16
        # inner type-1 subtable at offset 16: format1, coverage_offset=6, delta=2
        + _u16(1) + _u16(6) + _s16(2)
        # coverage at offset 16 + 6 = 22
        + _u16(1) + _u16(1) + _u16(99)
    )
    result = GlyphSubstitutionTable().read_lookup_table(
        MemoryTTFDataStream(payload), 0,
    )
    # The unwrap rewrites the outer lookup_type to the extension type.
    assert result["lookup_type"] == 1
    assert result["sub_tables"][0] is not None
    assert result["sub_tables"][0]["delta_glyph_id"] == 2


def test_read_lookup_table_type_7_bad_subst_format_skipped() -> None:
    """When an ExtensionSubst subtable carries the wrong SubstFormat,
    the parser logs and skips it, leaving the sub_tables slot ``None``."""
    payload = (
        _u16(7)          # lookup_type=7
        + _u16(0)
        + _u16(1)
        + _u16(8)
        # extension subtable at offset 8 — wrong SubstFormat
        + _u16(99)       # subst_format != 1
        + _u16(1)
        + _u32(0)
    )
    result = GlyphSubstitutionTable().read_lookup_table(
        MemoryTTFDataStream(payload), 0,
    )
    assert result["sub_tables"] == [None]


# ---------- read_lookup_list ----------------------------------------------


def test_read_lookup_list_basic() -> None:
    # Header: lookup_count + lookup_offset[0..n-1]
    # 1 lookup => 2 + 2 = 4 header bytes
    # Lookup table at offset 4: 8 + 6 = 14 bytes for type-1 / 1 sub
    payload = (
        _u16(1)          # lookup_count
        + _u16(4)        # lookup_offset[0]
        # lookup at offset 4
        + _u16(1)        # lookup_type
        + _u16(0)        # lookup_flag
        + _u16(1)        # sub_table_count
        + _u16(8)        # sub_offset[0] relative to lookup
        # subtable at offset 4 + 8 = 12
        + _u16(1) + _u16(6) + _s16(1)
        # coverage at offset 12 + 6 = 18
        + _u16(1) + _u16(1) + _u16(11)
    )
    result = GlyphSubstitutionTable().read_lookup_list(
        MemoryTTFDataStream(payload), 0,
    )
    assert result["lookup_count"] == 1
    assert len(result["lookup_tables"]) == 1
    assert result["lookup_tables"][0]["lookup_type"] == 1


def test_read_lookup_list_logs_zero_offset() -> None:
    """An entry whose lookup offset is 0 still parses (the inner
    read_lookup_table call seeks to ``offset + 0``, which gets a header
    out of whatever's there). What matters here is the error-logging
    branch (line 1033-1037) is exercised — and the function still
    returns a dict with ``lookup_count`` matching the input."""
    # Lookup_count=1, lookup_offset=0, then a lookup body.
    payload = (
        _u16(1)          # lookup_count
        + _u16(0)        # lookup_offset[0] -- triggers warn branch
        + _u16(1) + _u16(0) + _u16(1) + _u16(8)
        + _u16(1) + _u16(6) + _s16(0)
        + _u16(1) + _u16(1) + _u16(0)
    )
    # Wrap so original_data_size returns > offset+0.
    # offset=2 means the actual lookup body starts after lookup_count.
    # Easier: use offset=2 so lookup_count is at byte 2.
    stream = MemoryTTFDataStream(_u16(99) + payload)
    result = GlyphSubstitutionTable().read_lookup_list(stream, 2)
    assert result["lookup_count"] == 1


def test_read_lookup_list_dedupes_duplicate_offsets() -> None:
    """Upstream caches lookup_table by offset — duplicates resolve to the
    same dict (mirrors PDFBOX-6146)."""
    # 2 lookups sharing the same offset.
    payload = (
        _u16(2)          # lookup_count
        + _u16(6)        # lookup_offset[0]
        + _u16(6)        # lookup_offset[1] -- duplicate
        # lookup at offset 6
        + _u16(1) + _u16(0) + _u16(1) + _u16(8)
        # subtable at offset 6 + 8 = 14
        + _u16(1) + _u16(6) + _s16(0)
        # coverage at offset 14 + 6 = 20
        + _u16(1) + _u16(1) + _u16(0)
    )
    result = GlyphSubstitutionTable().read_lookup_list(
        MemoryTTFDataStream(payload), 0,
    )
    assert result["lookup_count"] == 2
    # Both entries point to the *same* dict instance (cache hit).
    assert result["lookup_tables"][0] is result["lookup_tables"][1]


# ---------- read_feature_table + read_feature_list ------------------------


def test_read_feature_table() -> None:
    payload = (
        _u16(0)          # feature_params
        + _u16(2)        # lookup_index_count
        + _u16(5) + _u16(7)
    )
    result = GlyphSubstitutionTable().read_feature_table(
        MemoryTTFDataStream(payload), 0,
    )
    assert result["feature_params"] == 0
    assert result["lookup_index_count"] == 2
    assert result["lookup_list_indices"] == [5, 7]


def test_read_feature_list_sorted() -> None:
    # 2 features, sorted: 'aalt' < 'liga'
    # Header: feature_count + per-feature (tag + offset) = 2 + 2*(4+2) = 14
    payload = (
        _u16(2)          # feature_count
        + _tag("aalt") + _u16(14)
        + _tag("liga") + _u16(18)
        # feature_table 'aalt' at offset 14: feature_params + lookup_index_count + 0 lookups
        + _u16(0) + _u16(0)
        # 'liga' at offset 18
        + _u16(0) + _u16(1) + _u16(3)
    )
    result = GlyphSubstitutionTable().read_feature_list(
        MemoryTTFDataStream(payload), 0,
    )
    assert result["feature_count"] == 2
    tags = [t for t, _ in result["feature_records"]]
    assert tags == ["aalt", "liga"]


def test_read_feature_list_unsorted_non_alnum_returns_empty() -> None:
    """An out-of-order non-alnum tag pair triggers the warn-and-return
    branch (returns empty feature_records)."""
    # tag order: 'liga' then '!!!!' — '!!!!' < 'liga' and is not alnum.
    payload = (
        _u16(2)
        + _tag("liga") + _u16(14)
        + _tag("!!!!") + _u16(14)
        + _u16(0) + _u16(0)
    )
    result = GlyphSubstitutionTable().read_feature_list(
        MemoryTTFDataStream(payload), 0,
    )
    assert result == {"feature_count": 0, "feature_records": []}


# ---------- read_lang_sys_table ------------------------------------------


def test_read_lang_sys_table() -> None:
    payload = (
        _u16(0)          # lookup_order
        + _u16(0xFFFF)   # required_feature_index
        + _u16(3)        # feature_index_count
        + _u16(1) + _u16(2) + _u16(3)
    )
    result = GlyphSubstitutionTable().read_lang_sys_table(
        MemoryTTFDataStream(payload), 0,
    )
    assert result["lookup_order"] == 0
    assert result["required_feature_index"] == 0xFFFF
    assert result["feature_index_count"] == 3
    assert result["feature_indices"] == [1, 2, 3]


# ---------- read_script_table --------------------------------------------


def test_read_script_table_no_default_no_langsys() -> None:
    payload = (
        _u16(0)          # default_lang_sys_offset (0 = absent)
        + _u16(0)        # lang_sys_count
    )
    result = GlyphSubstitutionTable().read_script_table(
        MemoryTTFDataStream(payload), 0,
    )
    assert result["default_lang_sys"] is None
    assert result["lang_sys_tables"] == {}


def test_read_script_table_with_default_lang_sys() -> None:
    # default_lang_sys_offset=4, lang_sys_count=0
    # default_lang_sys at offset 4: lookup_order=0, req=0xFFFF, count=0
    payload = (
        _u16(4)          # default_lang_sys_offset
        + _u16(0)        # lang_sys_count
        + _u16(0) + _u16(0xFFFF) + _u16(0)
    )
    result = GlyphSubstitutionTable().read_script_table(
        MemoryTTFDataStream(payload), 0,
    )
    assert result["default_lang_sys"] is not None
    assert result["default_lang_sys"]["required_feature_index"] == 0xFFFF


def test_read_script_table_unsorted_lang_sys_returns_empty() -> None:
    """Out-of-order LangSysRecord tags (per spec they must be sorted)
    returns the empty placeholder."""
    payload = (
        _u16(0)          # default_lang_sys_offset
        + _u16(2)        # lang_sys_count
        + _tag("ZZZZ") + _u16(14)
        + _tag("AAAA") + _u16(14)
        # placeholder bytes
        + _u16(0) + _u16(0xFFFF) + _u16(0)
    )
    result = GlyphSubstitutionTable().read_script_table(
        MemoryTTFDataStream(payload), 0,
    )
    assert result == {"default_lang_sys": None, "lang_sys_tables": {}}


def test_read_script_table_implausible_offset_returns_empty() -> None:
    """A LangSys offset pointing *backwards* into already-consumed data
    is implausible — the parser short-circuits."""
    # default_lang_sys_offset=0, lang_sys_count=1, lang_sys_offset=2 which is
    # < data.get_current_position() - offset (= 4 + 6 = 10).
    payload = (
        _u16(0)
        + _u16(1)
        + _tag("DFLT") + _u16(2)  # offset 2 -- before our current position
    )
    result = GlyphSubstitutionTable().read_script_table(
        MemoryTTFDataStream(payload), 0,
    )
    assert result == {"default_lang_sys": None, "lang_sys_tables": {}}


# ---------- read_script_list ---------------------------------------------


def test_read_script_list_basic() -> None:
    # script_count=1, then (tag, offset)*1 = 4+2 = 6 header bytes (after the 2-byte count)
    # total header = 2 + 6 = 8. Script table at offset 8.
    payload = (
        _u16(1)
        + _tag("latn") + _u16(8)
        # script_table at offset 8: no default, no langsys
        + _u16(0) + _u16(0)
    )
    result = GlyphSubstitutionTable().read_script_list(
        MemoryTTFDataStream(payload), 0,
    )
    assert "latn" in result


def test_read_script_list_dedupes_duplicate_tags() -> None:
    """PDFBOX-6146: duplicate script tags are skipped on second
    occurrence (the first wins)."""
    payload = (
        _u16(2)
        + _tag("latn") + _u16(14)
        + _tag("latn") + _u16(14)   # duplicate
        + _u16(0) + _u16(0)
    )
    result = GlyphSubstitutionTable().read_script_list(
        MemoryTTFDataStream(payload), 0,
    )
    # Only one entry survives.
    assert list(result.keys()) == ["latn"]


def test_read_script_list_implausible_offset_short_circuits() -> None:
    """An offset that points backwards triggers the error-and-return path."""
    payload = (
        _u16(1)
        + _tag("latn") + _u16(2)   # offset 2 is implausibly small
    )
    result = GlyphSubstitutionTable().read_script_list(
        MemoryTTFDataStream(payload), 0,
    )
    assert result == {}


# ---------- minor coverage holes in the structural-accessor surface -------


def test_get_lookup_with_none_lookup_list() -> None:
    """``get_lookup`` returns ``None`` when the underlying LookupList is
    absent — line 322."""
    table = GlyphSubstitutionTable()
    assert table.get_lookup(0) is None


def test_get_feature_record_unpopulated() -> None:
    """``get_feature_record`` returns ``None`` when FeatureList is absent
    — line 363."""
    table = GlyphSubstitutionTable()
    assert table.get_feature_record(0) is None


def test_get_feature_records_with_none_entries_skipped() -> None:
    """The ``if ls is None: continue`` branch is reached when a caller
    passes a list containing ``None`` entries."""

    # Need a populated table to get past the early-empty short-circuit.
    # Build a minimal fake gsub_table the helper accepts.
    class _FakeFeatureList:
        FeatureRecord = []

    class _FakeGsub:
        FeatureList = _FakeFeatureList()

    table = GlyphSubstitutionTable()
    table._gsub_table = _FakeGsub()  # type: ignore[assignment]
    # Empty feature_records list -> early return [] before the loop.
    # Pump a non-empty feature_records by giving the fake a record.
    class _FR:
        FeatureTag = "liga"

    _FakeFeatureList.FeatureRecord = [_FR()]  # type: ignore[attr-defined]
    # Now pass [None] as lang_sys_tables: should hit the ``if ls is None``
    # continue branch and return [].
    assert table.get_feature_records([None], None) == []


def test_get_feature_records_required_feature() -> None:
    """A required feature (``ReqFeatureIndex != 0xFFFF``) is always
    included."""

    class _Feat:
        LookupListIndex = []

    class _FR:
        FeatureTag = "liga"
        Feature = _Feat()

    class _FakeFeatureList:
        FeatureRecord = [_FR()]

    class _FakeGsub:
        FeatureList = _FakeFeatureList()

    class _LS:
        ReqFeatureIndex = 0
        FeatureIndex = []

    table = GlyphSubstitutionTable()
    table._gsub_table = _FakeGsub()  # type: ignore[assignment]
    result = table.get_feature_records([_LS()], None)
    assert len(result) == 1
    assert result[0] is _FakeFeatureList.FeatureRecord[0]


def test_get_feature_records_vrt2_supersedes_vert() -> None:
    class _F:
        LookupListIndex = []

    class _FR_vert:
        FeatureTag = "vert"
        Feature = _F()

    class _FR_vrt2:
        FeatureTag = "vrt2"
        Feature = _F()

    class _FakeFeatureList:
        FeatureRecord = [_FR_vert(), _FR_vrt2()]

    class _FakeGsub:
        FeatureList = _FakeFeatureList()

    class _LS:
        ReqFeatureIndex = 0xFFFF
        FeatureIndex = [0, 1]

    table = GlyphSubstitutionTable()
    table._gsub_table = _FakeGsub()  # type: ignore[assignment]
    result = table.get_feature_records([_LS()], None)
    tags = [str(fr.FeatureTag) for fr in result]
    assert "vrt2" in tags
    assert "vert" not in tags


def test_get_lookup_subtables_zero_count() -> None:
    """A lookup that has an empty SubTable list — empty result."""

    class _L:
        SubTable = []

    table = GlyphSubstitutionTable()
    # Patch _gsub_table so get_lookup_list returns a faux LookupList.
    class _LL:
        Lookup = [_L()]

    class _Gsub:
        LookupList = _LL()

    table._gsub_table = _Gsub()  # type: ignore[assignment]
    assert table.get_lookup_subtables(0) == []


def test_apply_feature_with_no_lookup_list() -> None:
    """``apply_feature`` returns input when LookupList is absent."""

    class _Feat:
        LookupListIndex = [0]

    class _FR:
        Feature = _Feat()

    class _Gsub:
        # No LookupList attribute -> branch (line 737)
        pass

    table = GlyphSubstitutionTable()
    table._gsub_table = _Gsub()  # type: ignore[assignment]
    assert table.apply_feature(_FR(), 5) == 5


def test_apply_feature_with_no_feature_attr() -> None:
    """``apply_feature`` returns input when ``feature_record.Feature`` is
    ``None``."""

    class _LL:
        Lookup = []

    class _Gsub:
        LookupList = _LL()

    class _FR:
        Feature = None

    table = GlyphSubstitutionTable()
    table._gsub_table = _Gsub()  # type: ignore[assignment]
    assert table.apply_feature(_FR(), 7) == 7


def test_do_lookup_with_none_table() -> None:
    """Explicit ``None`` lookup_table passthrough."""
    table = GlyphSubstitutionTable()
    assert table.do_lookup(None, 11) == 11


def test_contains_and_remove_feature_helpers() -> None:
    class _FR:
        def __init__(self, tag: str) -> None:
            self.FeatureTag = tag

    records = [_FR("liga"), _FR("sups"), _FR("liga"), _FR("vert")]
    assert GlyphSubstitutionTable.contains_feature(records, "sups") is True
    assert GlyphSubstitutionTable.contains_feature(records, "zzzz") is False
    GlyphSubstitutionTable.remove_feature(records, "liga")
    tags = [r.FeatureTag for r in records]
    assert "liga" not in tags
    assert tags == ["sups", "vert"]
