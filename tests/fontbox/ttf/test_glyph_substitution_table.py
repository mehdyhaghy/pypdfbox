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


def test_get_gsub_data_returns_none_by_design() -> None:
    """Documented deviation — see CHANGES.md."""
    t = GlyphSubstitutionTable()
    assert t.get_gsub_data() is None
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
