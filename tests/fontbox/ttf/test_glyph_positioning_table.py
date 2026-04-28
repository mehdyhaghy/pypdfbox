"""Tests for :class:`pypdfbox.fontbox.ttf.GlyphPositioningTable`.

Uses the bundled ``LiberationSans-Regular.ttf`` fixture, whose GPOS
table carries:

* 7 scripts (``DFLT bopo copt cyrl grek hebr latn``)
* 4 distinct features (``kern mark mkmk`` plus a duplicate ``kern``)
* 37 lookups spread across types 1, 2, 4, 6, and 8

The well-known kerning pair ``(A, V) -> -152`` makes a good lookup-type-2
oracle without inventing fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import GlyphPositioningTable, TrueTypeFont
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
def gpos(liberation_sans: TrueTypeFont) -> GlyphPositioningTable:
    table = liberation_sans.get_gpos()
    assert table is not None
    return table


# ---------- basic shape ----------------------------------------------------


def test_tag_constant() -> None:
    assert GlyphPositioningTable.TAG == "GPOS"


def test_inherits_ttf_table() -> None:
    assert issubclass(GlyphPositioningTable, TTFTable)


def test_lookup_type_constants_match_spec() -> None:
    """OT § GPOS Header — lookup type identifiers are positional 1..9."""
    assert GlyphPositioningTable.LOOKUP_TYPE_SINGLE_ADJUSTMENT == 1
    assert GlyphPositioningTable.LOOKUP_TYPE_PAIR_ADJUSTMENT == 2
    assert GlyphPositioningTable.LOOKUP_TYPE_CURSIVE_ATTACHMENT == 3
    assert GlyphPositioningTable.LOOKUP_TYPE_MARK_TO_BASE == 4
    assert GlyphPositioningTable.LOOKUP_TYPE_MARK_TO_LIGATURE == 5
    assert GlyphPositioningTable.LOOKUP_TYPE_MARK_TO_MARK == 6
    assert GlyphPositioningTable.LOOKUP_TYPE_CONTEXTUAL == 7
    assert GlyphPositioningTable.LOOKUP_TYPE_CHAINED_CONTEXTUAL == 8
    assert GlyphPositioningTable.LOOKUP_TYPE_EXTENSION == 9


def test_default_state_before_population() -> None:
    t = GlyphPositioningTable()
    assert t.get_tag() == "GPOS"
    assert t.get_supported_script_tags() == set()
    assert t.get_supported_feature_tags() == []
    assert t.get_raw_table() is None
    assert t.get_lookup_count() == 0
    assert t.get_lookup_types() == []
    assert t.get_initialized() is False


def test_get_kerning_no_table_returns_zero() -> None:
    """Without a backing GPOS the wrapper must return 0 — no kerning info."""
    t = GlyphPositioningTable()
    assert t.get_kerning(36, 57) == 0
    # Sentinel ``-1`` always short-circuits.
    assert t.get_kerning(-1, 57) == 0
    assert t.get_kerning(36, -1) == 0


def test_has_kerning_returns_false_when_unpopulated() -> None:
    t = GlyphPositioningTable()
    assert t.has_kerning() is False


# ---------- accessor wired into TrueTypeFont -------------------------------


def test_get_gpos_returns_none_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """A font without a GPOS table must yield ``None`` (cached)."""
    if not FIXTURE.exists():
        pytest.skip("Fixture not present")
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    inner = ttf._tt
    original_contains = inner.__contains__

    def fake_contains(self: object, key: str) -> bool:  # noqa: ARG001
        if key == "GPOS":
            return False
        return original_contains(key)

    monkeypatch.setattr(type(inner), "__contains__", fake_contains)
    assert ttf.get_gpos() is None
    # cached negative — second call must still be None.
    assert ttf.get_gpos() is None


def test_get_gpos_is_cached(liberation_sans: TrueTypeFont) -> None:
    a = liberation_sans.get_gpos()
    b = liberation_sans.get_gpos()
    assert a is b


# ---------- script + feature inventory -------------------------------------


def test_supported_script_tags(gpos: GlyphPositioningTable) -> None:
    expected = {"DFLT", "bopo", "copt", "cyrl", "grek", "hebr", "latn"}
    assert gpos.get_supported_script_tags() == expected


def test_supported_feature_tags_present(gpos: GlyphPositioningTable) -> None:
    tags = gpos.get_supported_feature_tags()
    # Duplicate ``kern`` (latin + hebrew variants) is deduped at populate time.
    for tag in ("kern", "mark", "mkmk"):
        assert tag in tags


def test_initialized_flag_set_after_population(
    gpos: GlyphPositioningTable,
) -> None:
    assert gpos.get_initialized() is True


def test_raw_table_exposes_fonttools_object(gpos: GlyphPositioningTable) -> None:
    raw = gpos.get_raw_table()
    assert raw is not None
    assert hasattr(raw, "ScriptList")
    assert hasattr(raw, "FeatureList")
    assert hasattr(raw, "LookupList")


def test_lookup_count_matches_fonttools(
    liberation_sans: TrueTypeFont, gpos: GlyphPositioningTable,
) -> None:
    expected = len(liberation_sans._tt["GPOS"].table.LookupList.Lookup)
    assert gpos.get_lookup_count() == expected
    assert gpos.get_lookup_count() == 37  # fixture-specific oracle


def test_lookup_types_inventory(gpos: GlyphPositioningTable) -> None:
    types = gpos.get_lookup_types()
    assert len(types) == gpos.get_lookup_count()
    # Fixture sanity — pair-adjustment, mark-to-base, mark-to-mark and
    # chained-contextual lookups are all advertised in this font.
    assert 1 in types
    assert 2 in types
    assert 4 in types
    assert 6 in types
    assert 8 in types


# ---------- kerning lookup walking -----------------------------------------


def _gid(ttf: TrueTypeFont, name: str) -> int:
    order = ttf._tt.getGlyphOrder()
    return order.index(name)


def test_kerning_known_pair_a_v(
    liberation_sans: TrueTypeFont, gpos: GlyphPositioningTable,
) -> None:
    """``A`` + ``V`` carries a -152 X-advance adjustment in this font.
    Anything other than -152 means the GPOS pair-adjustment walk is
    broken."""
    a = _gid(liberation_sans, "A")
    v = _gid(liberation_sans, "V")
    assert gpos.get_kerning(a, v) == -152


def test_kerning_known_pair_a_t(
    liberation_sans: TrueTypeFont, gpos: GlyphPositioningTable,
) -> None:
    a = _gid(liberation_sans, "A")
    t = _gid(liberation_sans, "T")
    assert gpos.get_kerning(a, t) == -152


def test_kerning_known_pair_a_w(
    liberation_sans: TrueTypeFont, gpos: GlyphPositioningTable,
) -> None:
    a = _gid(liberation_sans, "A")
    w = _gid(liberation_sans, "W")
    assert gpos.get_kerning(a, w) == -76


def test_kerning_uncovered_pair_returns_zero(
    liberation_sans: TrueTypeFont, gpos: GlyphPositioningTable,
) -> None:
    """A pair the kerning lookup doesn't cover must yield 0."""
    a = _gid(liberation_sans, "A")
    b = _gid(liberation_sans, "B")
    assert gpos.get_kerning(a, b) == 0


def test_kerning_sentinels_short_circuit(gpos: GlyphPositioningTable) -> None:
    assert gpos.get_kerning(-1, 100) == 0
    assert gpos.get_kerning(100, -1) == 0
    assert gpos.get_kerning(-1, -1) == 0


def test_has_kerning_true_for_liberation_sans(
    gpos: GlyphPositioningTable,
) -> None:
    assert gpos.has_kerning() is True


def test_kerning_pairs_cached_across_calls(
    liberation_sans: TrueTypeFont,
) -> None:
    """Building the kerning map is the most expensive thing this class
    does. It must be built exactly once and reused — pin that by
    poking at the private cache."""
    table = GlyphPositioningTable()
    table.populate_from_fonttools(liberation_sans._tt)
    assert table._kerning_pairs is None
    a = _gid(liberation_sans, "A")
    v = _gid(liberation_sans, "V")
    table.get_kerning(a, v)
    built = table._kerning_pairs
    assert built is not None
    table.get_kerning(a, v)
    assert table._kerning_pairs is built  # same dict instance


# ---------- read() is a no-op ----------------------------------------------


def test_read_method_is_noop(liberation_sans: TrueTypeFont) -> None:
    """The ``read`` slot is a placeholder — fontTools does the parsing."""
    from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

    table = GlyphPositioningTable()
    table.read(liberation_sans, MemoryTTFDataStream(b""))
    assert table.get_initialized() is False


# ---------- structural accessors (script / feature / lookup lists) ----------


def test_get_script_list_returns_fonttools_object(
    gpos: GlyphPositioningTable,
) -> None:
    sl = gpos.get_script_list()
    assert sl is not None
    # Carries one ScriptRecord per supported script tag.
    records = sl.ScriptRecord
    assert len(records) == 7
    tags = {str(sr.ScriptTag) for sr in records}
    assert tags == {"DFLT", "bopo", "copt", "cyrl", "grek", "hebr", "latn"}


def test_get_script_list_none_when_unpopulated() -> None:
    t = GlyphPositioningTable()
    assert t.get_script_list() is None


def test_get_feature_list_returns_fonttools_object(
    gpos: GlyphPositioningTable,
) -> None:
    fl = gpos.get_feature_list()
    assert fl is not None
    records = fl.FeatureRecord
    # ``kern`` appears twice in this font (latin + hebrew variants).
    tags = [str(fr.FeatureTag).strip() for fr in records]
    assert "kern" in tags
    assert "mark" in tags
    assert "mkmk" in tags
    assert tags.count("kern") >= 1


def test_get_feature_list_none_when_unpopulated() -> None:
    t = GlyphPositioningTable()
    assert t.get_feature_list() is None


def test_get_lookup_list_returns_fonttools_object(
    gpos: GlyphPositioningTable,
) -> None:
    ll = gpos.get_lookup_list()
    assert ll is not None
    assert len(ll.Lookup) == 37


def test_get_lookup_list_none_when_unpopulated() -> None:
    t = GlyphPositioningTable()
    assert t.get_lookup_list() is None


def test_get_lookup_returns_indexed_entry(
    gpos: GlyphPositioningTable,
) -> None:
    """Each entry exposes ``LookupType`` / ``SubTable`` per OT spec."""
    lookup = gpos.get_lookup(0)
    assert lookup is not None
    assert hasattr(lookup, "LookupType")
    assert hasattr(lookup, "SubTable")


def test_get_lookup_out_of_range_returns_none(
    gpos: GlyphPositioningTable,
) -> None:
    assert gpos.get_lookup(-1) is None
    assert gpos.get_lookup(9999) is None


def test_get_lookup_unpopulated_returns_none() -> None:
    t = GlyphPositioningTable()
    assert t.get_lookup(0) is None


def test_get_lookup_subtables_for_pair_adjustment(
    gpos: GlyphPositioningTable,
) -> None:
    """Walk every type-2 (pair-adjustment) lookup and confirm
    ``get_lookup_subtables`` returns at least one subtable for each."""
    types = gpos.get_lookup_types()
    pair_indices = [i for i, t in enumerate(types) if t == 2]
    assert pair_indices, "fixture should carry at least one pair-adjustment lookup"
    for li in pair_indices:
        subtables = gpos.get_lookup_subtables(li)
        assert subtables  # non-empty
        # At least one subtable should expose Format 1 or 2 PairPos shape.
        fmts = {int(getattr(s, "Format", 0)) for s in subtables}
        assert fmts & {1, 2}


def test_get_lookup_subtables_out_of_range_returns_empty(
    gpos: GlyphPositioningTable,
) -> None:
    assert gpos.get_lookup_subtables(-1) == []
    assert gpos.get_lookup_subtables(9999) == []


def test_get_lookup_subtables_unpopulated_returns_empty() -> None:
    t = GlyphPositioningTable()
    assert t.get_lookup_subtables(0) == []


def test_get_feature_record_indexed_access(
    gpos: GlyphPositioningTable,
) -> None:
    fr = gpos.get_feature_record(0)
    assert fr is not None
    assert hasattr(fr, "FeatureTag")
    assert hasattr(fr, "Feature")


def test_get_feature_record_out_of_range_returns_none(
    gpos: GlyphPositioningTable,
) -> None:
    assert gpos.get_feature_record(-1) is None
    assert gpos.get_feature_record(9999) is None


def test_get_feature_record_unpopulated_returns_none() -> None:
    t = GlyphPositioningTable()
    assert t.get_feature_record(0) is None


def test_get_lookup_indices_for_feature_kern(
    gpos: GlyphPositioningTable,
) -> None:
    """``kern`` appears for both Latin and Hebrew in this font; the
    union of their LookupListIndex entries should land at least one
    type-2 (pair-adjustment) lookup."""
    indices = gpos.get_lookup_indices_for_feature("kern")
    assert indices, "kern feature should reference at least one lookup"
    # Every returned index must point at a real lookup; at least one
    # of them must be type-2 (pair adjustment) for kern to make sense.
    types = gpos.get_lookup_types()
    referenced_types = {types[i] for i in indices}
    assert 2 in referenced_types


def test_get_lookup_indices_for_feature_unknown_returns_empty(
    gpos: GlyphPositioningTable,
) -> None:
    assert gpos.get_lookup_indices_for_feature("zzzz") == []


def test_get_lookup_indices_for_feature_dedup(
    gpos: GlyphPositioningTable,
) -> None:
    """Duplicate lookup indices across multiple ``kern`` records must
    be deduplicated; the result must preserve first-appearance order."""
    indices = gpos.get_lookup_indices_for_feature("kern")
    assert len(indices) == len(set(indices))


def test_get_lookup_indices_for_feature_unpopulated_returns_empty() -> None:
    t = GlyphPositioningTable()
    assert t.get_lookup_indices_for_feature("kern") == []
