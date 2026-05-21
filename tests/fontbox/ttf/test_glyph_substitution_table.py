"""Tests for :class:`pypdfbox.fontbox.ttf.GlyphSubstitutionTable`.

Uses the bundled ``LiberationSans-Regular.ttf`` fixture, which carries a
real GSUB table with seven scripts (``DFLT bopo copt cyrl grek hebr latn``)
and five features (``ccmp dlig subs sups``).

The ``sups`` feature points to a single-substitution lookup that maps
``four -> four.sups`` etc. — those are the GIDs we exercise to prove
``get_substitution`` actually walks the GSUB graph rather than returning
the input unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import GlyphSubstitutionTable, TrueTypeFont
from pypdfbox.fontbox.ttf.ttf_table import TTFTable

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_sans() -> TrueTypeFont:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return TrueTypeFont.from_bytes(FIXTURE.read_bytes())


@pytest.fixture(scope="module")
def gsub(liberation_sans: TrueTypeFont) -> GlyphSubstitutionTable:
    table = liberation_sans.get_gsub()
    assert table is not None
    return table


# ---------- basic shape ----------------------------------------------------


def test_tag_constant() -> None:
    assert GlyphSubstitutionTable.TAG == "GSUB"


def test_inherits_ttf_table() -> None:
    assert issubclass(GlyphSubstitutionTable, TTFTable)


def test_default_state_before_population() -> None:
    t = GlyphSubstitutionTable()
    assert t.get_tag() == "GSUB"
    assert t.get_supported_script_tags() == set()
    assert t.get_supported_feature_tags() == []
    assert t.get_raw_table() is None
    assert t.get_lookup_indices_for_feature("sups") == []
    assert t.get_initialized() is False


def test_get_substitution_no_table_returns_input() -> None:
    """Without a backing GSUB the wrapper must be a passthrough — that
    matches upstream's behaviour when the font has no GSUB at all."""
    t = GlyphSubstitutionTable()
    assert t.get_substitution(42, ["latn"], None) == 42
    # Sentinel ``-1`` always short-circuits.
    assert t.get_substitution(-1, ["latn"], ["sups"]) == -1


def test_get_unsubstitution_unknown_passthrough() -> None:
    t = GlyphSubstitutionTable()
    assert t.get_unsubstitution(99) == 99


def test_get_gsub_data_returns_no_data_when_table_not_populated() -> None:
    """Wave 1375: ``get_gsub_data()`` projects against the underlying
    fontTools GSUB structures; an empty table returns
    :attr:`GsubData.NO_DATA_FOUND` for the default case and ``None`` for
    an explicit unsupported tag."""
    from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData

    t = GlyphSubstitutionTable()
    assert t.get_gsub_data() is GsubData.NO_DATA_FOUND
    assert t.get_gsub_data("latn") is None


# ---------- accessor accessor wired into TrueTypeFont ----------------------


def test_get_gsub_returns_none_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """A font without a GSUB table must yield ``None`` (and the negative
    result must be cached so we don't re-probe on every call)."""
    if not FIXTURE.exists():
        pytest.skip("Fixture not present")
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    # Swap the underlying fontTools dict to omit GSUB.
    inner = ttf._tt
    original_contains = inner.__contains__

    def fake_contains(self: object, key: str) -> bool:  # noqa: ARG001
        if key == "GSUB":
            return False
        return original_contains(key)

    monkeypatch.setattr(type(inner), "__contains__", fake_contains)
    assert ttf.get_gsub() is None
    # cached
    assert ttf.get_gsub() is None


def test_get_gsub_is_cached(liberation_sans: TrueTypeFont) -> None:
    a = liberation_sans.get_gsub()
    b = liberation_sans.get_gsub()
    assert a is b


# ---------- script + feature inventory -------------------------------------


def test_supported_script_tags(gsub: GlyphSubstitutionTable) -> None:
    expected = {"DFLT", "bopo", "copt", "cyrl", "grek", "hebr", "latn"}
    assert gsub.get_supported_script_tags() == expected


def test_supported_feature_tags_present(gsub: GlyphSubstitutionTable) -> None:
    tags = gsub.get_supported_feature_tags()
    # ccmp appears twice in this font (once for latin/grek, once for hebr);
    # populate-time dedup keeps the first occurrence only.
    for tag in ("ccmp", "dlig", "subs", "sups"):
        assert tag in tags


def test_initialized_flag_set_after_population(
    gsub: GlyphSubstitutionTable,
) -> None:
    assert gsub.get_initialized() is True


def test_raw_table_exposes_fonttools_object(gsub: GlyphSubstitutionTable) -> None:
    raw = gsub.get_raw_table()
    assert raw is not None
    assert hasattr(raw, "ScriptList")
    assert hasattr(raw, "FeatureList")
    assert hasattr(raw, "LookupList")


def test_lookup_indices_for_feature(gsub: GlyphSubstitutionTable) -> None:
    assert gsub.get_lookup_indices_for_feature("sups") == [5]
    assert gsub.get_lookup_indices_for_feature("subs") == [6]
    # Liberation Sans has two ccmp FeatureRecords; the helper walks both
    # and preserves first-seen lookup order.
    assert gsub.get_lookup_indices_for_feature("ccmp") == [3, 1, 2]
    assert gsub.get_lookup_indices_for_feature("zzzz") == []


# ---------- get_substitution: real lookup walks ----------------------------


def _gid(ttf: TrueTypeFont, name: str) -> int:
    order = ttf._tt.getGlyphOrder()
    return order.index(name)


def test_substitution_applies_sups_feature(
    liberation_sans: TrueTypeFont, gsub: GlyphSubstitutionTable,
) -> None:
    """``sups`` is a type-1 single-subst lookup: ``four -> four.sups``.
    Enabling the feature must rewrite GIDs covered by the lookup."""
    src = _gid(liberation_sans, "four")
    expected = _gid(liberation_sans, "four.sups")
    assert gsub.get_substitution(src, ["latn"], ["sups"]) == expected


def test_substitution_applies_subs_feature(
    liberation_sans: TrueTypeFont,
) -> None:
    """Use a fresh table per test — ``get_substitution`` caches its
    answer for a given GID, so cross-feature reuse must use a fresh
    instance to avoid bleed-through from earlier ``sups`` calls."""
    table = GlyphSubstitutionTable()
    table.populate_from_fonttools(liberation_sans._tt)
    src = _gid(liberation_sans, "zero")
    expected = _gid(liberation_sans, "zero.subs")
    assert table.get_substitution(src, ["latn"], ["subs"]) == expected


def test_substitution_no_enabled_features_means_passthrough(
    liberation_sans: TrueTypeFont,
) -> None:
    """When ``enabled_features`` is an empty list, no rule fires."""
    table = GlyphSubstitutionTable()
    table.populate_from_fonttools(liberation_sans._tt)
    src = _gid(liberation_sans, "four")
    assert table.get_substitution(src, ["latn"], []) == src


def test_substitution_uncovered_glyph_returns_input(
    liberation_sans: TrueTypeFont,
) -> None:
    """A glyph not covered by the ``sups`` lookup must come back
    unchanged even when ``sups`` is enabled."""
    table = GlyphSubstitutionTable()
    table.populate_from_fonttools(liberation_sans._tt)
    src = _gid(liberation_sans, "A")  # not in the sups mapping
    assert table.get_substitution(src, ["latn"], ["sups"]) == src


def test_substitution_caches_first_result(
    liberation_sans: TrueTypeFont,
) -> None:
    """Upstream guarantees a single GID always substitutes to the same
    output, regardless of script / enabled-features context. We honour
    that by caching the first result."""
    table = GlyphSubstitutionTable()
    table.populate_from_fonttools(liberation_sans._tt)
    src = _gid(liberation_sans, "four")
    first = table.get_substitution(src, ["latn"], ["sups"])
    # Second call without enabled_features must still return the cached
    # substitution (otherwise the cache contract is broken).
    second = table.get_substitution(src, ["latn"], [])
    assert second == first


def test_substitution_unsubstitution_round_trip(
    liberation_sans: TrueTypeFont,
) -> None:
    table = GlyphSubstitutionTable()
    table.populate_from_fonttools(liberation_sans._tt)
    src = _gid(liberation_sans, "four")
    sgid = table.get_substitution(src, ["latn"], ["sups"])
    assert sgid != src
    assert table.get_unsubstitution(sgid) == src


def test_substitution_negative_one_sentinel(
    gsub: GlyphSubstitutionTable,
) -> None:
    assert gsub.get_substitution(-1, ["latn"], ["sups"]) == -1


def test_substitution_unknown_script_passthrough(
    liberation_sans: TrueTypeFont,
) -> None:
    """An unsupported script tag with no fallback resolves to the input."""
    table = GlyphSubstitutionTable()
    table.populate_from_fonttools(liberation_sans._tt)
    src = _gid(liberation_sans, "four")
    # ``zzzz`` is not present; with no recognized tags we still go
    # through ``selectScriptTag``'s "first tag in list wins" path,
    # which here picks ``zzzz`` — and ``zzzz`` has no script record,
    # so no features apply and the GID is unchanged.
    assert table.get_substitution(src, ["zzzz"], ["sups"]) == src


def test_read_method_is_noop(liberation_sans: TrueTypeFont) -> None:
    """The ``read`` slot is a placeholder — fontTools does the parsing."""
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

    table = GlyphSubstitutionTable()
    # Should not raise even with an empty stream — read is intentionally a no-op.
    table.read(liberation_sans, MemoryTTFDataStream(b""))
    assert table.get_initialized() is False


# ---------- structural accessor coverage -----------------------------------


def test_lookup_type_constants_match_ot_spec() -> None:
    """Class-level ``LOOKUP_TYPE_*`` constants must match the OT spec
    GSUB Header lookup-type taxonomy."""
    assert GlyphSubstitutionTable.LOOKUP_TYPE_SINGLE == 1
    assert GlyphSubstitutionTable.LOOKUP_TYPE_MULTIPLE == 2
    assert GlyphSubstitutionTable.LOOKUP_TYPE_ALTERNATE == 3
    assert GlyphSubstitutionTable.LOOKUP_TYPE_LIGATURE == 4
    assert GlyphSubstitutionTable.LOOKUP_TYPE_CONTEXT == 5
    assert GlyphSubstitutionTable.LOOKUP_TYPE_CHAINING_CONTEXT == 6
    assert GlyphSubstitutionTable.LOOKUP_TYPE_EXTENSION_SUBSTITUTION == 7
    assert (
        GlyphSubstitutionTable.LOOKUP_TYPE_REVERSE_CHAINING_CONTEXTUAL_SINGLE
        == 8
    )


def test_get_lookup_count_unpopulated() -> None:
    t = GlyphSubstitutionTable()
    assert t.get_lookup_count() == 0


def test_get_lookup_count_populated(gsub: GlyphSubstitutionTable) -> None:
    """Liberation Sans's GSUB has a non-empty LookupList."""
    assert gsub.get_lookup_count() > 0


def test_get_lookup_types_unpopulated() -> None:
    t = GlyphSubstitutionTable()
    assert t.get_lookup_types() == []


def test_get_lookup_types_all_legal(gsub: GlyphSubstitutionTable) -> None:
    """Every lookup type must fall in the OT spec range 1..8."""
    types = gsub.get_lookup_types()
    assert types
    for lt in types:
        assert 1 <= lt <= 8


def test_get_script_list_unpopulated() -> None:
    assert GlyphSubstitutionTable().get_script_list() is None


def test_get_script_list_populated(gsub: GlyphSubstitutionTable) -> None:
    sl = gsub.get_script_list()
    assert sl is not None
    assert hasattr(sl, "ScriptRecord")


def test_get_feature_list_unpopulated() -> None:
    assert GlyphSubstitutionTable().get_feature_list() is None


def test_get_feature_list_populated(gsub: GlyphSubstitutionTable) -> None:
    fl = gsub.get_feature_list()
    assert fl is not None
    assert hasattr(fl, "FeatureRecord")


def test_get_lookup_list_unpopulated() -> None:
    assert GlyphSubstitutionTable().get_lookup_list() is None


def test_get_lookup_list_populated(gsub: GlyphSubstitutionTable) -> None:
    ll = gsub.get_lookup_list()
    assert ll is not None
    assert hasattr(ll, "Lookup")


def test_get_lookup_out_of_range(gsub: GlyphSubstitutionTable) -> None:
    assert gsub.get_lookup(-1) is None
    assert gsub.get_lookup(99999) is None


def test_get_lookup_in_range(gsub: GlyphSubstitutionTable) -> None:
    lookup = gsub.get_lookup(0)
    assert lookup is not None
    assert hasattr(lookup, "LookupType")


def test_get_lookup_subtables_out_of_range(gsub: GlyphSubstitutionTable) -> None:
    assert gsub.get_lookup_subtables(-1) == []
    assert gsub.get_lookup_subtables(99999) == []


def test_get_lookup_subtables_in_range(gsub: GlyphSubstitutionTable) -> None:
    subs = gsub.get_lookup_subtables(0)
    assert isinstance(subs, list)
    # Lookup 0 must have at least one subtable in a real font.
    assert subs


def test_get_feature_record_out_of_range(gsub: GlyphSubstitutionTable) -> None:
    assert gsub.get_feature_record(-1) is None
    assert gsub.get_feature_record(99999) is None


def test_get_feature_record_in_range(gsub: GlyphSubstitutionTable) -> None:
    fr = gsub.get_feature_record(0)
    assert fr is not None
    assert hasattr(fr, "FeatureTag")


def test_get_lang_sys_tables_unknown_script(gsub: GlyphSubstitutionTable) -> None:
    assert gsub.get_lang_sys_tables("zzzz") == []


def test_get_lang_sys_tables_known_script(gsub: GlyphSubstitutionTable) -> None:
    """A populated script must yield at least one LangSys (default or
    per-language)."""
    tables = gsub.get_lang_sys_tables("latn")
    assert tables  # non-empty


def test_get_lang_sys_tables_unpopulated() -> None:
    assert GlyphSubstitutionTable().get_lang_sys_tables("latn") == []


def test_get_feature_records_empty_lang_sys() -> None:
    t = GlyphSubstitutionTable()
    assert t.get_feature_records([], None) == []


def test_get_feature_records_filtered(gsub: GlyphSubstitutionTable) -> None:
    """Filtering by feature tag must drop records whose tag isn't
    enabled."""
    lang_sys = gsub.get_lang_sys_tables("latn")
    assert lang_sys
    only_sups = gsub.get_feature_records(lang_sys, ["sups"])
    for fr in only_sups:
        assert str(fr.FeatureTag).strip() == "sups"


def test_get_feature_records_no_filter_returns_all(
    gsub: GlyphSubstitutionTable,
) -> None:
    lang_sys = gsub.get_lang_sys_tables("latn")
    assert lang_sys
    everything = gsub.get_feature_records(lang_sys, None)
    # Liberation Sans's latn LangSys references multiple feature
    # records; expect at least one.
    assert everything


def test_select_script_tag_public_mirror(gsub: GlyphSubstitutionTable) -> None:
    """The public mirror must resolve a real script tag and update the
    last-used hint."""
    chosen = gsub.select_script_tag(["latn"])
    assert chosen == "latn"
    assert gsub.get_last_used_supported_script() == "latn"


def test_select_script_tag_unknown_returns_first(
    gsub: GlyphSubstitutionTable,
) -> None:
    assert gsub.select_script_tag(["zzzz"]) == "zzzz"


def test_get_last_used_supported_script_initial() -> None:
    assert GlyphSubstitutionTable().get_last_used_supported_script() is None


def test_apply_feature_unpopulated_passthrough() -> None:
    """Unpopulated table — apply_feature must return input unchanged."""
    t = GlyphSubstitutionTable()
    assert t.apply_feature(None, 7) == 7


def test_apply_feature_with_real_record(
    liberation_sans: TrueTypeFont,
) -> None:
    """Plumb a real FeatureRecord through and verify substitution
    matches what get_substitution returns."""
    table = GlyphSubstitutionTable()
    table.populate_from_fonttools(liberation_sans._tt)
    src = _gid(liberation_sans, "four")
    expected = _gid(liberation_sans, "four.sups")
    # Find the sups feature record — there's only one in this font.
    fl = table.get_feature_list()
    assert fl is not None
    sups_fr = next(
        fr
        for fr in fl.FeatureRecord
        if str(fr.FeatureTag).strip() == "sups"
    )
    assert table.apply_feature(sups_fr, src) == expected


def test_do_lookup_unpopulated_passthrough() -> None:
    t = GlyphSubstitutionTable()
    assert t.do_lookup(None, 5) == 5


def test_do_lookup_skips_non_type_1(
    liberation_sans: TrueTypeFont,
) -> None:
    """do_lookup must short-circuit when the LookupType isn't 1."""

    class FakeLookup:
        LookupType = 4  # ligature
        SubTable: list[object] = []

    table = GlyphSubstitutionTable()
    table.populate_from_fonttools(liberation_sans._tt)
    assert table.do_lookup(FakeLookup(), 42) == 42


def test_do_lookup_with_real_type_1(liberation_sans: TrueTypeFont) -> None:
    table = GlyphSubstitutionTable()
    table.populate_from_fonttools(liberation_sans._tt)
    src = _gid(liberation_sans, "four")
    expected = _gid(liberation_sans, "four.sups")
    # Lookup index 5 is the sups single-substitution lookup
    # (asserted by the existing wave548 test).
    sups_lookup = table.get_lookup(5)
    assert sups_lookup is not None
    assert table.do_lookup(sups_lookup, src) == expected


# ---------- contains_feature / remove_feature ------------------------------


class _FakeFR:
    """Stand-in for fontTools ``FeatureRecord`` in pure-data tests."""

    def __init__(self, tag: str) -> None:
        self.FeatureTag = tag


def test_contains_feature_true_and_false() -> None:
    records = [_FakeFR("liga"), _FakeFR("sups"), _FakeFR("vert")]
    assert GlyphSubstitutionTable.contains_feature(records, "sups") is True
    assert GlyphSubstitutionTable.contains_feature(records, "zzzz") is False
    assert GlyphSubstitutionTable.contains_feature([], "anything") is False


def test_contains_feature_strips_whitespace() -> None:
    """fontTools tags are 4-byte strings — sometimes carry trailing
    space ('vert' vs 'vert '). The helper must normalise."""
    records = [_FakeFR("vert ")]
    assert GlyphSubstitutionTable.contains_feature(records, "vert") is True


def test_remove_feature_drops_matching_entries() -> None:
    records = [_FakeFR("liga"), _FakeFR("vert"), _FakeFR("sups"), _FakeFR("vert")]
    GlyphSubstitutionTable.remove_feature(records, "vert")
    assert [str(r.FeatureTag) for r in records] == ["liga", "sups"]


def test_remove_feature_no_match_is_noop() -> None:
    records = [_FakeFR("liga"), _FakeFR("sups")]
    GlyphSubstitutionTable.remove_feature(records, "zzzz")
    assert [str(r.FeatureTag) for r in records] == ["liga", "sups"]


def test_remove_feature_empty_list() -> None:
    records: list[object] = []
    GlyphSubstitutionTable.remove_feature(records, "vert")
    assert records == []


# ---------- read_* upstream-private parsers (byte-stream decoders) --------


def _pack_uint16(value: int) -> bytes:
    return value.to_bytes(2, "big", signed=False)


def _pack_int16(value: int) -> bytes:
    return value.to_bytes(2, "big", signed=True)


def test_read_lang_sys_table_decodes_required_feature_and_indices() -> None:
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

    table = GlyphSubstitutionTable()
    blob = (
        _pack_uint16(0)
        + _pack_uint16(0xFFFF)
        + _pack_uint16(3)
        + _pack_uint16(0)
        + _pack_uint16(1)
        + _pack_uint16(4)
    )
    out = table.read_lang_sys_table(MemoryTTFDataStream(blob), 0)
    assert out["lookup_order"] == 0
    assert out["required_feature_index"] == 0xFFFF
    assert out["feature_index_count"] == 3
    assert out["feature_indices"] == [0, 1, 4]


def test_read_feature_table_decodes_lookup_indices() -> None:
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

    table = GlyphSubstitutionTable()
    blob = (
        _pack_uint16(0)
        + _pack_uint16(2)
        + _pack_uint16(2)
        + _pack_uint16(5)
    )
    out = table.read_feature_table(MemoryTTFDataStream(blob), 0)
    assert out["feature_params"] == 0
    assert out["lookup_index_count"] == 2
    assert out["lookup_list_indices"] == [2, 5]


def test_read_coverage_table_format1() -> None:
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

    table = GlyphSubstitutionTable()
    blob = (
        _pack_uint16(1)
        + _pack_uint16(3)
        + _pack_uint16(10)
        + _pack_uint16(20)
        + _pack_uint16(30)
    )
    out = table.read_coverage_table(MemoryTTFDataStream(blob), 0)
    assert out.get_coverage_format() == 1
    assert out.get_size() == 3
    assert out.get_glyph_id(0) == 10
    assert out.get_glyph_id(2) == 30


def test_read_coverage_table_format2_and_range_record() -> None:
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

    table = GlyphSubstitutionTable()
    blob = (
        _pack_uint16(2)
        + _pack_uint16(1)
        + _pack_uint16(10)
        + _pack_uint16(12)
        + _pack_uint16(0)
    )
    out = table.read_coverage_table(MemoryTTFDataStream(blob), 0)
    assert out.get_coverage_format() == 2
    records = out.get_range_records()
    assert len(records) == 1
    assert records[0].start_glyph_id == 10
    assert records[0].end_glyph_id == 12


def test_read_range_record_round_trip() -> None:
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

    table = GlyphSubstitutionTable()
    blob = _pack_uint16(5) + _pack_uint16(9) + _pack_uint16(1)
    out = table.read_range_record(MemoryTTFDataStream(blob))
    assert out.start_glyph_id == 5
    assert out.end_glyph_id == 9
    assert out.start_coverage_index == 1


def test_read_single_lookup_sub_table_format1() -> None:
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

    table = GlyphSubstitutionTable()
    blob = (
        _pack_uint16(1)
        + _pack_uint16(6)
        + _pack_int16(3)
        + _pack_uint16(1)
        + _pack_uint16(1)
        + _pack_uint16(7)
    )
    out = table.read_single_lookup_sub_table(MemoryTTFDataStream(blob), 0)
    assert out["subst_format"] == 1
    assert out["delta_glyph_id"] == 3
    assert out["coverage_table"].get_glyph_id(0) == 7


def test_read_single_lookup_sub_table_format2() -> None:
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

    table = GlyphSubstitutionTable()
    blob = (
        _pack_uint16(2)
        + _pack_uint16(8)
        + _pack_uint16(1)
        + _pack_uint16(99)
        + _pack_uint16(1)
        + _pack_uint16(1)
        + _pack_uint16(50)
    )
    out = table.read_single_lookup_sub_table(MemoryTTFDataStream(blob), 0)
    assert out["subst_format"] == 2
    assert out["substitute_glyph_ids"] == [99]
    assert out["coverage_table"].get_glyph_id(0) == 50


def test_read_ligature_table_uses_coverage_glyph_id_as_first_component() -> None:
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

    table = GlyphSubstitutionTable()
    blob = (
        _pack_uint16(42)
        + _pack_uint16(3)
        + _pack_uint16(101)
        + _pack_uint16(102)
    )
    out = table.read_ligature_table(MemoryTTFDataStream(blob), 0, 100)
    assert out["ligature_glyph"] == 42
    assert out["component_count"] == 3
    assert out["component_glyph_ids"] == [100, 101, 102]


def test_read_script_table_with_default_only() -> None:
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

    table = GlyphSubstitutionTable()
    # ScriptTable at offset 0: defaultLangSysOffset (4), langSysCount (0).
    # LangSysTable at offset 4: lookupOrder (0), requiredFeatureIndex (1),
    # featureIndexCount (0).
    blob = (
        _pack_uint16(4)
        + _pack_uint16(0)
        + _pack_uint16(0)
        + _pack_uint16(1)
        + _pack_uint16(0)
    )
    out = table.read_script_table(MemoryTTFDataStream(blob), 0)
    assert out["lang_sys_tables"] == {}
    assert out["default_lang_sys"] is not None
    assert out["default_lang_sys"]["required_feature_index"] == 1


def test_read_lookup_subtable_unsupported_type_returns_none() -> None:
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

    table = GlyphSubstitutionTable()
    out = table.read_lookup_subtable(MemoryTTFDataStream(b""), 0, 5)
    assert out is None


def test_read_coverage_table_unknown_format_raises() -> None:
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

    table = GlyphSubstitutionTable()
    blob = _pack_uint16(99)
    with pytest.raises(OSError, match="Unknown coverage format"):
        table.read_coverage_table(MemoryTTFDataStream(blob), 0)
