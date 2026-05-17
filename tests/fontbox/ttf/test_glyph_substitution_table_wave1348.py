"""Coverage-boost tests for the structural None-guard branches and the
byte-level read helpers that the existing
``test_glyph_substitution_table*`` suites don't exercise.

Targets:
* lines 208 / 217 / 237 / 252 / 383 / 389 / 396-398 / 433 / 436 / 448 /
  461 / 549 / 598-600 / 613 / 636 / 650 / 672 / 702 / 746 / 749:
  None / out-of-range / missing-attribute guards on the structural
  accessors when ``_gsub_table`` is bound to a stub that lacks the
  expected sub-tables.
* lines 905-911 / 920 / 969 / 1039 / 1071 / 1073 / 1075:
  byte-level error paths in ``read_script_table`` / ``read_feature_list``
  / ``read_lookup_list`` / ``read_lookup_subtable``.

We avoid building a real font; instead we fabricate stub objects mirroring
the fontTools attribute graph (ScriptList, FeatureList, LookupList, etc.).
"""

from __future__ import annotations

import struct
from types import SimpleNamespace
from typing import Any

import pytest

from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def _u16(v: int) -> bytes:
    return struct.pack(">H", v)


def _s16(v: int) -> bytes:
    return struct.pack(">h", v)


def _tag(t: str) -> bytes:
    assert len(t) == 4
    return t.encode("iso-8859-1")


# ----------------------------------------------------------------------
# stub builders
# ----------------------------------------------------------------------


def _bind(table: GlyphSubstitutionTable, stub: Any) -> None:
    """Attach a fake gsub_table without going through fontTools."""
    table._gsub_table = stub


def _stub(**kwargs: Any) -> Any:
    return SimpleNamespace(**kwargs)


# ----------------------------------------------------------------------
# Structural None / missing branches
# ----------------------------------------------------------------------


def test_get_lookup_indices_for_feature_no_feature_list() -> None:
    """Line 208: ``_gsub_table`` is set but ``FeatureList`` is ``None``."""
    t = GlyphSubstitutionTable()
    _bind(t, _stub(FeatureList=None))
    assert t.get_lookup_indices_for_feature("liga") == []


def test_get_lookup_indices_for_feature_record_with_none_feature() -> None:
    """Line 217: a matching ``FeatureRecord`` whose ``.Feature`` is
    ``None`` is skipped."""
    record = _stub(FeatureTag="liga", Feature=None)
    fl = _stub(FeatureRecord=[record])
    t = GlyphSubstitutionTable()
    _bind(t, _stub(FeatureList=fl))
    assert t.get_lookup_indices_for_feature("liga") == []


def test_get_lookup_indices_for_feature_deduplicates() -> None:
    """Cover the dedup branch (``lookup_index_i in seen``) — two
    feature records share the same lookup index."""
    feat = _stub(LookupListIndex=[3, 3, 5])
    record_a = _stub(FeatureTag="liga", Feature=feat)
    record_b = _stub(FeatureTag="liga", Feature=feat)
    fl = _stub(FeatureRecord=[record_a, record_b])
    t = GlyphSubstitutionTable()
    _bind(t, _stub(FeatureList=fl))
    assert t.get_lookup_indices_for_feature("liga") == [3, 5]


def test_get_lookup_count_no_lookup_list() -> None:
    """Line 237: ``LookupList`` is ``None`` returns 0."""
    t = GlyphSubstitutionTable()
    _bind(t, _stub(LookupList=None))
    assert t.get_lookup_count() == 0


def test_get_lookup_types_no_lookup_list() -> None:
    """Line 252: same shape but for ``get_lookup_types``."""
    t = GlyphSubstitutionTable()
    _bind(t, _stub(LookupList=None))
    assert t.get_lookup_types() == []


def test_get_lang_sys_tables_no_script_list() -> None:
    """Line 383: ``_gsub_table`` is set but ``ScriptList`` is ``None``."""
    t = GlyphSubstitutionTable()
    _bind(t, _stub(ScriptList=None))
    assert t.get_lang_sys_tables("latn") == []


def test_get_lang_sys_tables_script_record_with_none_script() -> None:
    """Line 389: the matching ScriptRecord's ``.Script`` is ``None``."""
    sr = _stub(ScriptTag="latn", Script=None)
    sl = _stub(ScriptRecord=[sr])
    t = GlyphSubstitutionTable()
    _bind(t, _stub(ScriptList=sl))
    assert t.get_lang_sys_tables("latn") == []


def test_get_lang_sys_tables_collects_lang_sys_records() -> None:
    """Lines 396-398: iterate ``LangSysRecord`` entries; ``None`` LangSys
    is skipped, non-None is appended."""
    ls1 = _stub(name="dflt-lang-sys")
    lsr_present = _stub(LangSys=ls1)
    lsr_none = _stub(LangSys=None)
    default_ls = _stub(name="default")
    script = _stub(
        LangSysRecord=[lsr_present, lsr_none],
        DefaultLangSys=default_ls,
    )
    sr = _stub(ScriptTag="latn", Script=script)
    sl = _stub(ScriptRecord=[sr])
    t = GlyphSubstitutionTable()
    _bind(t, _stub(ScriptList=sl))
    result = t.get_lang_sys_tables("latn")
    # Per-language entries first, default appended last.
    assert result == [ls1, default_ls]


def test_get_feature_records_no_feature_list() -> None:
    """Line 433: ``FeatureList`` is ``None``."""
    t = GlyphSubstitutionTable()
    _bind(t, _stub(FeatureList=None))
    assert t.get_feature_records([_stub()]) == []


def test_get_feature_records_empty_feature_records() -> None:
    """Line 436: ``FeatureRecord`` is empty."""
    t = GlyphSubstitutionTable()
    _bind(t, _stub(FeatureList=_stub(FeatureRecord=[])))
    assert t.get_feature_records([_stub()]) == []


def test_get_feature_records_out_of_range_index_skipped() -> None:
    """Line 448: a ``FeatureIndex`` >= ``len(feature_records)`` is
    silently skipped."""
    record0 = _stub(FeatureTag="liga", Feature=_stub())
    fl = _stub(FeatureRecord=[record0])
    ls = _stub(ReqFeatureIndex=0xFFFF, FeatureIndex=[0, 5, 9])
    t = GlyphSubstitutionTable()
    _bind(t, _stub(FeatureList=fl))
    result = t.get_feature_records([ls])
    assert result == [record0]


def test_get_feature_records_sorts_by_enabled_features_order() -> None:
    """Line 461: when ``enabled_features`` is supplied and ``len(result)
    > 1`` the result is reordered to match the enabled-features index."""
    rec_a = _stub(FeatureTag="sups", Feature=_stub())
    rec_b = _stub(FeatureTag="liga", Feature=_stub())
    fl = _stub(FeatureRecord=[rec_a, rec_b])
    ls = _stub(ReqFeatureIndex=0xFFFF, FeatureIndex=[0, 1])
    t = GlyphSubstitutionTable()
    _bind(t, _stub(FeatureList=fl))
    # Request liga before sups → result must be [liga, sups], not the
    # FeatureList directory order.
    out = t.get_feature_records([ls], enabled_features=["liga", "sups"])
    assert [str(r.FeatureTag) for r in out] == ["liga", "sups"]


def test_get_feature_records_unfiltered_returns_all() -> None:
    """``enabled_features=None`` skips the filter sort."""
    rec_a = _stub(FeatureTag="liga", Feature=_stub())
    fl = _stub(FeatureRecord=[rec_a])
    ls = _stub(ReqFeatureIndex=0xFFFF, FeatureIndex=[0])
    t = GlyphSubstitutionTable()
    _bind(t, _stub(FeatureList=fl))
    assert t.get_feature_records([ls]) == [rec_a]


# ----------------------------------------------------------------------
# _select_script_tag / _collect_feature_indices branches — 598-600, 613,
# 636, 650, 672
# ----------------------------------------------------------------------


def test_select_script_tag_returns_first_script_when_no_tags() -> None:
    """Line 600: empty tags + no cached script returns the first
    available script tag."""
    t = GlyphSubstitutionTable()
    t._script_tags = ["grek", "latn"]
    assert t._select_script_tag(()) == "grek"


def test_select_script_tag_returns_none_when_no_tags_and_no_scripts() -> None:
    """Line 600: empty tags AND no script tags returns ``None``."""
    t = GlyphSubstitutionTable()
    t._script_tags = []
    assert t._select_script_tag(()) is None


def test_select_script_tag_returns_cached_when_no_tags() -> None:
    """Line 598-599: empty tags returns the cached
    ``_last_used_supported_script``."""
    t = GlyphSubstitutionTable()
    t._script_tags = ["latn"]
    t._last_used_supported_script = "grek"
    assert t._select_script_tag(()) == "grek"


def test_select_script_tag_dflt_returns_unknown_when_no_scripts() -> None:
    """Line 613: single ``DFLT`` tag with no script tags and no cache
    returns the input tag as-is."""
    t = GlyphSubstitutionTable()
    t._script_tags = []
    t._last_used_supported_script = None
    assert t._select_script_tag(("DFLT",)) == "DFLT"


def test_collect_feature_indices_no_script_tag() -> None:
    """Line 636: ``script_tag is None`` returns empty list."""
    t = GlyphSubstitutionTable()
    _bind(t, _stub(ScriptList=_stub(ScriptRecord=[])))
    assert t._collect_feature_indices(None, None) == []


def test_collect_feature_indices_absorb_skips_none_lang_sys() -> None:
    """Line 650: ``absorb(None)`` is a no-op (covered by passing a
    script whose DefaultLangSys is None)."""
    script = _stub(DefaultLangSys=None, LangSysRecord=[])
    sr = _stub(ScriptTag="latn", Script=script)
    sl = _stub(ScriptRecord=[sr])
    fl = _stub(FeatureRecord=[])
    t = GlyphSubstitutionTable()
    _bind(t, _stub(ScriptList=sl, FeatureList=fl))
    # No DefaultLangSys, no per-language records → empty list.
    assert t._collect_feature_indices("latn", None) == []


def test_collect_feature_indices_drops_out_of_range_tag() -> None:
    """Line 672: ``tag_for(fi)`` returns ``None`` for fi out of range,
    so the entry is filtered out of ``filtered``."""
    # FeatureList has only one record at index 0.
    feature_records = [_stub(FeatureTag="liga", Feature=_stub())]
    fl = _stub(FeatureRecord=feature_records)
    # LangSys references an out-of-range index 99 plus index 0.
    ls = _stub(ReqFeatureIndex=0xFFFF, FeatureIndex=[99, 0])
    script = _stub(DefaultLangSys=ls, LangSysRecord=[])
    sl = _stub(ScriptRecord=[_stub(ScriptTag="latn", Script=script)])
    t = GlyphSubstitutionTable()
    _bind(t, _stub(ScriptList=sl, FeatureList=fl))
    # Enabled set includes 'liga' → only the valid index 0 stays.
    assert t._collect_feature_indices("latn", ["liga"]) == [0]


# ----------------------------------------------------------------------
# _apply_single_lookup_in_gid_space — line 702
# ----------------------------------------------------------------------


def test_apply_single_lookup_skips_subtable_without_mapping() -> None:
    """Line 702: a subtable whose ``.mapping`` is falsy is skipped, the
    loop continues, and ``gid`` is returned unchanged."""
    t = GlyphSubstitutionTable()
    t._glyph_order = ["A", "B"]
    t._glyph_name_to_gid = {"A": 0, "B": 1}
    subtable_no_mapping = _stub(mapping=None)
    subtable_empty_mapping = _stub(mapping={})
    lookup = _stub(SubTable=[subtable_no_mapping, subtable_empty_mapping])
    assert t._apply_single_lookup_in_gid_space(lookup, 0) == 0


def test_apply_single_lookup_returns_input_on_mapping_miss() -> None:
    """The branch where mapping exists but doesn't cover the glyph name."""
    t = GlyphSubstitutionTable()
    t._glyph_order = ["A"]
    t._glyph_name_to_gid = {"A": 0}
    lookup = _stub(SubTable=[_stub(mapping={"Z": "Y"})])
    assert t._apply_single_lookup_in_gid_space(lookup, 0) == 0


# ----------------------------------------------------------------------
# apply_feature — lines 746, 749
# ----------------------------------------------------------------------


def test_apply_feature_skips_out_of_range_lookup_index() -> None:
    """Line 746: lookup_index out of range is silently skipped."""
    t = GlyphSubstitutionTable()
    ll = _stub(Lookup=[_stub(LookupType=1, SubTable=[])])
    _bind(t, _stub(LookupList=ll))
    feature = _stub(LookupListIndex=[99])  # out of range
    record = _stub(Feature=feature)
    # Returns gid unchanged.
    assert t.apply_feature(record, 5) == 5


def test_apply_feature_skips_non_single_lookup_type() -> None:
    """Line 749: a lookup with LookupType != 1 is skipped."""
    t = GlyphSubstitutionTable()
    t._glyph_order = ["A"]
    t._glyph_name_to_gid = {"A": 0}
    ll = _stub(Lookup=[_stub(LookupType=2, SubTable=[])])
    _bind(t, _stub(LookupList=ll))
    feature = _stub(LookupListIndex=[0])
    assert t.apply_feature(_stub(Feature=feature), 0) == 0


def test_apply_feature_with_none_feature_returns_gid() -> None:
    """The early-out branch when the record's Feature is None."""
    t = GlyphSubstitutionTable()
    _bind(t, _stub(LookupList=_stub(Lookup=[])))
    assert t.apply_feature(_stub(Feature=None), 7) == 7


def test_apply_feature_returns_input_when_table_absent() -> None:
    t = GlyphSubstitutionTable()
    assert t.apply_feature(_stub(Feature=_stub(LookupListIndex=[0])), 9) == 9


def test_apply_feature_with_none_lookup_list_returns_gid() -> None:
    t = GlyphSubstitutionTable()
    _bind(t, _stub(LookupList=None))
    assert t.apply_feature(_stub(Feature=_stub(LookupListIndex=[0])), 9) == 9


# ----------------------------------------------------------------------
# get_substitution — line 549 (skip out-of-range feature index)
# ----------------------------------------------------------------------


def test_get_substitution_skips_out_of_range_feature_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 549: a feature index outside ``feature_records`` is silently
    skipped during the main substitution loop."""
    t = GlyphSubstitutionTable()
    # Stub a gsub table with a valid FeatureList + LookupList shape, but
    # have _collect_feature_indices return an out-of-range index.
    fr = _stub(
        FeatureTag="liga",
        Feature=_stub(LookupListIndex=[0]),
    )
    fl = _stub(FeatureRecord=[fr])
    lookup = _stub(LookupType=1, SubTable=[])
    ll = _stub(Lookup=[lookup])
    _bind(t, _stub(FeatureList=fl, LookupList=ll))
    monkeypatch.setattr(
        t,
        "_collect_feature_indices",
        lambda script, enabled: [99, 0],
    )
    monkeypatch.setattr(t, "_select_script_tag", lambda tags: "latn")
    # gid stays unchanged because the only valid lookup has no mapping.
    assert t.get_substitution(7, ["latn"], None) == 7


# ----------------------------------------------------------------------
# read_script_table — lines 905-911 (sort error) and 920 (lang sys
# offset valid path)
# ----------------------------------------------------------------------


def test_read_script_table_returns_empty_when_lang_sys_unsorted() -> None:
    """Lines 905-911: when ``langSysTags`` are not alphabetically sorted
    the parser bails out and returns the empty result."""
    # Payload: defaultLangSysOffset=0, langSysCount=2,
    #          tag="ARA " offset=12, tag="AAA " offset=20  (AAA < ARA → sort error)
    # tag2 < tag1 triggers the sort error path.
    payload = (
        _u16(0)            # defaultLangSysOffset
        + _u16(2)          # langSysCount
        + _tag("ARA ") + _u16(12)  # langSysTags[0] / langSysOffsets[0]
        + _tag("AAA ") + _u16(20)  # langSysTags[1] (< ARA — error)
        + b"\x00" * 32              # padding (won't be read after error)
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    result = table.read_script_table(stream, 0)
    assert result == {"default_lang_sys": None, "lang_sys_tables": {}}


def test_read_script_table_with_valid_lang_sys_records() -> None:
    """Line 920: the happy-path iteration that builds ``lang_sys_tables``.

    Use sorted tags + valid offsets so the parser walks to completion."""
    # langSysRecord layout: tag(4) + offset(2). LangSysTable layout per
    # read_lang_sys_table: lookupOrder(2) + reqFeatureIndex(2) +
    # featureIndexCount(2) [+ featureIndices(2*n)].
    # Place a single LangSysTable at offset 12 (after header bytes 0..11).
    # defaultLangSysOffset=0 (no default), langSysCount=1, tag="ENG ",
    # offset=10 (relative to script-table start).
    payload = (
        _u16(0)               # defaultLangSysOffset
        + _u16(1)             # langSysCount
        + _tag("ENG ") + _u16(10)
        # LangSysTable at offset 10:
        + _u16(0xFFFF)        # lookupOrder
        + _u16(0xFFFF)        # reqFeatureIndex (none)
        + _u16(0)             # featureIndexCount
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    result = table.read_script_table(stream, 0)
    assert result["default_lang_sys"] is None
    assert "ENG " in result["lang_sys_tables"]


# ----------------------------------------------------------------------
# read_feature_list — line 969 (warning sort + return for non-alnum tags)
# ----------------------------------------------------------------------


def test_read_feature_list_returns_empty_when_tags_unsorted_non_alnum() -> None:
    """Line 982 (the ``else`` warning branch + early return): two feature
    tags out of alphabetic order where at least one is non-alphanumeric
    triggers the warning + empty-result path."""
    # featureCount=2, tag1="zz1 " offset=12, tag2="!!a "  (non-alnum & < zz1)
    payload = (
        _u16(2)
        + _tag("zz1 ") + _u16(12)
        + _tag("!!a ") + _u16(20)  # non-alphanumeric and out of order
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    result = table.read_feature_list(stream, 0)
    assert result == {"feature_count": 0, "feature_records": []}


def test_read_feature_list_logs_debug_when_alnum_tags_unsorted() -> None:
    """Lines 969-974 (the debug branch): two alphanumeric tags out of
    alphabetic order log a debug message but still proceed to build
    feature records — non-returning branch."""
    # featureCount=2, both alnum but out of sorted order: "zzz0" then
    # "aaa0". The else (warning + return) branch only fires when at
    # least one is non-alphanumeric; here both pass ``isalnum``, so we
    # hit the debug log and keep parsing. Each feature table needs a
    # featureParams(2) + lookupIndexCount(2) header — point both offsets
    # to a shared trailing feature-table block at the end of the buffer.
    feature_table_offset = 12
    payload = (
        _u16(2)                                   # featureCount
        + _tag("zzz0") + _u16(feature_table_offset)  # tag 0
        + _tag("aaa0") + _u16(feature_table_offset)  # tag 1 (debug-only)
        + _u16(0) + _u16(0)                       # featureTable: no params, no lookups
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    result = table.read_feature_list(stream, 0)
    # Both records produced — the debug-only branch did not return early.
    assert result["feature_count"] == 2
    assert len(result["feature_records"]) == 2


# ----------------------------------------------------------------------
# read_lookup_list — line 1039 (lookup offset overruns data)
# ----------------------------------------------------------------------


def test_read_lookup_list_logs_error_on_out_of_bounds_offset() -> None:
    """Line 1039: a lookup offset that points past the end of the data
    triggers the error log; the parser continues and produces a
    best-effort result."""
    # lookupCount=1, lookups[0]=9999 (way past end). The single lookup
    # offset is well-formed (non-zero) so we hit the "out of bounds"
    # branch rather than the "is 0" branch.
    payload = (
        _u16(1)        # lookupCount
        + _u16(9999)   # lookups[0] — far past end of buffer
        # Provide enough padding so read_lookup_table can seek to offset
        # 9999 without an OSError — we will reach the table-shape-read
        # try block, which simply returns an empty-shaped dict in that
        # branch. To keep the test small we monkey-patch read_lookup_table.
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    # Stub read_lookup_table to avoid the out-of-bounds seek raising.
    table.read_lookup_table = lambda data, offset: {  # type: ignore[method-assign]
        "lookup_type": 0,
        "lookup_flag": 0,
        "mark_filtering_set": 0,
        "sub_tables": [],
    }
    result = table.read_lookup_list(stream, 0)
    assert result["lookup_count"] == 1


# ----------------------------------------------------------------------
# read_lookup_subtable dispatch — lines 1071, 1073, 1075
# ----------------------------------------------------------------------


def test_read_lookup_subtable_dispatches_type_2_to_multiple() -> None:
    """Line 1071: lookup_type=2 -> read_multiple_substitution_subtable."""
    # Header layout (multiple subst format 1):
    #   substFormat(2) + coverageOffset(2) + sequenceCount(2) +
    #   sequenceOffsets[0](2) = 8 bytes total.
    # Coverage block (format 1, 1 glyph): format(2) + glyphCount(2) +
    # glyph(2) = 6 bytes -> place at offset 8.
    # Sequence block (1 entry, 1 sub glyph): glyphCount(2) + glyph(2) =
    # 4 bytes -> place at offset 14.
    coverage_offset = 8
    sequence_offset = 14
    payload = (
        _u16(1)                    # substFormat
        + _u16(coverage_offset)    # coverageOffset
        + _u16(1)                  # sequenceCount
        + _u16(sequence_offset)    # sequenceOffsets[0]
        + _u16(1) + _u16(1) + _u16(42)   # coverage: format 1, 1 glyph (42)
        + _u16(1) + _u16(100)            # sequence: 1 sub glyph
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    sub = table.read_lookup_subtable(stream, 0, 2)
    assert sub is not None
    assert sub["subst_format"] == 1
    assert len(sub["sequence_tables"]) == 1


def test_read_lookup_subtable_dispatches_type_3_to_alternate() -> None:
    """Line 1073: lookup_type=3 -> read_alternate_substitution_subtable."""
    # Same layout as the type-2 case.
    coverage_offset = 8
    alt_offset = 14
    payload = (
        _u16(1)                    # substFormat
        + _u16(coverage_offset)    # coverageOffset
        + _u16(1)                  # altSetCount
        + _u16(alt_offset)         # alternateOffsets[0]
        + _u16(1) + _u16(1) + _u16(50)   # coverage: format 1, 1 glyph
        + _u16(1) + _u16(70)             # alt set: 1 glyph
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    sub = table.read_lookup_subtable(stream, 0, 3)
    assert sub is not None
    assert len(sub["alternate_set_tables"]) == 1


def _u32(v: int) -> bytes:
    return struct.pack(">I", v)


def test_read_lookup_table_extension_type_mismatch_logs_and_skips() -> None:
    """Lines 1147-1155: in the type-7 (extension) branch, after the
    first subtable reassigns ``lookup_type`` to its
    ``extension_lookup_type``, a subsequent subtable whose own
    ``extension_lookup_type`` differs trips the
    ``extensionLookupType changed`` error log and is skipped.

    Build a 2-subtable extension lookup where subtable 0 wraps type 1
    (single substitution) and subtable 1 wraps type 2 (multiple
    substitution). On the second iteration ``lookup_type == 1`` (from
    the first reassignment) and ``extension_lookup_type == 2`` — the
    inequality holds, so the error branch fires and the subtable is
    skipped.
    """
    # LookupTable header layout:
    #   lookupType(2) + lookupFlag(2) + subTableCount(2) +
    #   subTableOffsets[0](2) + subTableOffsets[1](2) = 10 bytes
    # Each extension subtable is exactly substFormat(2) +
    # extensionLookupType(2) + extensionOffset(4) = 8 bytes.
    #
    # We place extension subtable 0 at offset 10, subtable 1 at offset
    # 18. The single-format-1 ``read_single_lookup_sub_table`` callout
    # for subtable 0 needs an extension_offset pointing at a valid
    # Single-substitution Format 1 block; subtable 1 never gets there
    # (it's the one we want skipped).
    #
    # Single subst format 1 block: substFormat(2) + coverageOffset(2) +
    # deltaGlyphID(2) + coverage(format 1: format(2) + glyphCount(2) +
    # glyphArray(2*glyphCount)). 12 bytes minimum.
    #
    # Place single-subst block at offset 26 (right after the two extension
    # subtables). extension_offset for subtable 0 = 26 - 10 = 16.
    single_subst_offset = 26
    coverage_in_subst_offset = 6  # right after substFormat+coverageOffset+delta
    payload = (
        # Lookup header (offset 0..9)
        _u16(7)                # lookupType
        + _u16(0)              # lookupFlag (mark filtering not set)
        + _u16(2)              # subTableCount = 2
        + _u16(10)             # subTableOffsets[0] = 10
        + _u16(18)             # subTableOffsets[1] = 18
        # Extension subtable 0 at offset 10 (wraps type 1)
        + _u16(1)              # substFormat = 1
        + _u16(1)              # extensionLookupType = 1
        + _u32(single_subst_offset - 10)  # extensionOffset = 16
        # Extension subtable 1 at offset 18 (wraps type 2 — mismatch!)
        + _u16(1)              # substFormat = 1
        + _u16(2)              # extensionLookupType = 2 (DIFFERS from 1)
        + _u32(0)              # extensionOffset (ignored due to mismatch)
        # Single-subst Format 1 block at offset 26
        + _u16(1)              # substFormat
        + _u16(coverage_in_subst_offset)  # coverageOffset (within block)
        + _s16(0)              # deltaGlyphID
        + _u16(1) + _u16(1) + _u16(99)   # coverage: format 1, 1 glyph
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    result = table.read_lookup_table(stream, 0)
    # First subtable parsed; second skipped (left at None).
    assert result["lookup_type"] == 1  # reassigned after subtable 0
    assert result["sub_tables"][1] is None


def test_read_lookup_subtable_dispatches_type_4_to_ligature() -> None:
    """Line 1075: lookup_type=4 -> read_ligature_substitution_subtable."""
    # Layout: substFormat(2) + coverageOffset(2) + ligSetCount(2) +
    # ligatureOffsets[0](2) + coverage block + ligature set block.
    coverage_offset = 8
    lig_set_offset = coverage_offset + 6
    # LigatureSet: ligatureCount(2) + ligatureOffsets[0](2) +
    # Ligature: ligGlyph(2) + componentCount(2) + components(2*n-1)
    lig_offset = 4  # within the ligature set, point to the ligature table
    payload = (
        _u16(1)                          # substFormat
        + _u16(coverage_offset)          # coverageOffset
        + _u16(1)                        # ligSetCount
        + _u16(lig_set_offset)           # ligatureOffsets[0]
        + _u16(1) + _u16(1) + _u16(60)   # coverage: format 1, 1 glyph
        + _u16(1) + _u16(lig_offset)     # ligature set: 1 ligature
        + _u16(200) + _u16(2) + _u16(61)  # ligature: glyph 200, 2 comp, comp[1]=61
    )
    stream = MemoryTTFDataStream(payload)
    table = GlyphSubstitutionTable()
    sub = table.read_lookup_subtable(stream, 0, 4)
    assert sub is not None
    assert sub["ligature_set_tables"]
