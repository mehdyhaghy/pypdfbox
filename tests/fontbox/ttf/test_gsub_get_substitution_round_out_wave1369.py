"""Wave 1369 round-out tests for :meth:`GlyphSubstitutionTable.get_substitution`.

Existing waves cover the substitution surface through a real Liberation
Sans font. This file targets the *behavioural* edges around upstream's
single-substitution lookup that are easier to exercise via lightweight
fakes than via a real font:

* The ``gid == -1`` sentinel short-circuit (upstream uses ``-1`` to mean
  "no glyph"; the table must return it unchanged without consulting the
  GSUB).
* Bare table with no ``_gsub_table`` populated — every GID passes
  through unchanged.
* The substitution cache: a second call for the same GID returns the
  cached result without re-walking the lookup list.
* ``get_unsubstitution`` is identity when called with a GID that wasn't
  produced by a prior ``get_substitution`` call.
* Lookup-type filter: lookups whose type is not 1 (single substitution)
  are skipped silently, matching upstream's ``LookupType != 1`` guard.
* Out-of-range feature index / lookup index entries don't crash.
* Empty enabled-features list = run every default feature; ``None``
  also runs every default feature; an empty list of *enabled* features
  with no matches yields no substitution.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable


def _gsub_with_single_substitution(
    glyph_order: tuple[str, ...],
    mapping: dict[str, str],
    lookup_type: int = 1,
    feature_tag: str = "liga",
    script_tag: str = "latn",
) -> GlyphSubstitutionTable:
    """Build a :class:`GlyphSubstitutionTable` whose fontTools-equivalent
    state has one script with one feature, one lookup of ``lookup_type``,
    and a single-substitution ``mapping``."""
    table = GlyphSubstitutionTable()
    table._glyph_order = list(glyph_order)  # noqa: SLF001
    table._glyph_name_to_gid = {n: i for i, n in enumerate(glyph_order)}  # noqa: SLF001
    table._script_tags = [script_tag]  # noqa: SLF001
    table._feature_tags = [feature_tag]  # noqa: SLF001
    table._gsub_table = SimpleNamespace(  # noqa: SLF001
        ScriptList=SimpleNamespace(
            ScriptRecord=[
                SimpleNamespace(
                    ScriptTag=script_tag,
                    Script=SimpleNamespace(
                        DefaultLangSys=SimpleNamespace(
                            ReqFeatureIndex=0xFFFF,
                            FeatureIndex=[0],
                        ),
                        LangSysRecord=[],
                    ),
                )
            ]
        ),
        FeatureList=SimpleNamespace(
            FeatureRecord=[
                SimpleNamespace(
                    FeatureTag=feature_tag,
                    Feature=SimpleNamespace(LookupListIndex=[0]),
                )
            ]
        ),
        LookupList=SimpleNamespace(
            Lookup=[
                SimpleNamespace(
                    LookupType=lookup_type,
                    SubTable=[SimpleNamespace(mapping=mapping)],
                )
            ]
        ),
    )
    return table


# ---------- gid sentinel ----------------------------------------------------


def test_get_substitution_minus_one_short_circuits() -> None:
    """``gid == -1`` must short-circuit and return ``-1`` regardless of
    whether a GSUB is populated."""
    table = GlyphSubstitutionTable()  # no GSUB at all
    assert table.get_substitution(-1) == -1
    table2 = _gsub_with_single_substitution(("a", "a.alt"), {"a": "a.alt"})
    assert table2.get_substitution(-1) == -1


# ---------- no GSUB populated ----------------------------------------------


def test_get_substitution_passes_through_when_no_gsub() -> None:
    """A bare :class:`GlyphSubstitutionTable` instance (no
    ``populate_from_fonttools`` call) should pass every GID through
    unchanged."""
    table = GlyphSubstitutionTable()
    for gid in (0, 1, 99, 65535):
        assert table.get_substitution(gid) == gid


# ---------- single substitution lookup -------------------------------------


def test_get_substitution_applies_single_lookup() -> None:
    table = _gsub_with_single_substitution(("a", "a.alt"), {"a": "a.alt"})
    assert table.get_substitution(0, ["latn"], ["liga"]) == 1


def test_get_substitution_caches_result() -> None:
    """Upstream uses the lookup cache to keep substitution deterministic
    across repeated calls with the same input. Verify the cache is
    populated after the first call and the second call observes the
    cached value (the underlying lookup mapping is poisoned mid-flight
    so a real second walk would yield a different result)."""
    table = _gsub_with_single_substitution(("a", "a.alt"), {"a": "a.alt"})
    first = table.get_substitution(0, ["latn"], ["liga"])
    assert first == 1
    # Cache is populated.
    assert table._lookup_cache[0] == 1  # noqa: SLF001
    # Poison the underlying single-sub mapping. If the second call
    # re-ran the lookup walk it would now resolve "a" -> "a.alt2",
    # which doesn't exist in the glyph order and would return 0.
    table._gsub_table.LookupList.Lookup[0].SubTable[0].mapping = {  # noqa: SLF001
        "a": "ghost",
    }
    second = table.get_substitution(0, ["latn"], ["liga"])
    assert second == 1  # cache hit returns the original substitution


def test_get_unsubstitution_reverses_a_previous_substitution() -> None:
    """The reverse cache lets callers undo a substitution they have
    actually requested. Bare GIDs the table has never seen come back
    unchanged."""
    table = _gsub_with_single_substitution(("a", "a.alt"), {"a": "a.alt"})
    sgid = table.get_substitution(0, ["latn"], ["liga"])
    assert sgid == 1
    assert table.get_unsubstitution(sgid) == 0
    # A GID the table never produced as a substitution comes back as-is.
    assert table.get_unsubstitution(42) == 42


# ---------- lookup-type filter ---------------------------------------------


@pytest.mark.parametrize(
    ("lookup_type", "expected_gid"),
    [
        (1, 1),  # single substitution: lookup applied → gid 1
        (2, 0),  # multiple substitution: skipped → gid unchanged
        (4, 0),  # ligature substitution: skipped → gid unchanged
        (7, 0),  # extension substitution: skipped → gid unchanged
    ],
    ids=["single", "multiple", "ligature", "extension"],
)
def test_get_substitution_only_applies_single_lookup_type(
    lookup_type: int, expected_gid: int
) -> None:
    """Only ``LookupType == 1`` (single substitution) plugs into the
    ``gid -> gid`` surface. Other lookup types skip silently to match
    upstream's ``getLookupType() != 1`` guard."""
    table = _gsub_with_single_substitution(
        ("a", "a.alt"), {"a": "a.alt"}, lookup_type=lookup_type
    )
    assert table.get_substitution(0, ["latn"], ["liga"]) == expected_gid


# ---------- out-of-range indices -------------------------------------------


def test_get_substitution_invalid_feature_index_skipped() -> None:
    """A feature index past the end of ``FeatureRecord`` must be
    silently skipped — mirrors upstream's bounds check."""
    table = _gsub_with_single_substitution(("a", "a.alt"), {"a": "a.alt"})
    # Replace the DefaultLangSys to reference a non-existent feature.
    table._gsub_table.ScriptList.ScriptRecord[0].Script.DefaultLangSys.FeatureIndex = [  # noqa: SLF001
        99,
        0,
    ]
    assert table.get_substitution(0, ["latn"], ["liga"]) == 1


def test_get_substitution_invalid_lookup_index_skipped() -> None:
    """A lookup index past the end of ``Lookup`` must be silently skipped."""
    table = _gsub_with_single_substitution(("a", "a.alt"), {"a": "a.alt"})
    # Reference a non-existent lookup *before* the valid one — the
    # invalid one is skipped, the valid one still fires.
    table._gsub_table.FeatureList.FeatureRecord[  # noqa: SLF001
        0
    ].Feature.LookupListIndex = [99, 0]
    assert table.get_substitution(0, ["latn"], ["liga"]) == 1


# ---------- empty enabled-features list --------------------------------


def test_get_substitution_enabled_features_none_runs_every_feature() -> None:
    """``enabled_features=None`` means "every default feature applies"."""
    table = _gsub_with_single_substitution(("a", "a.alt"), {"a": "a.alt"})
    assert table.get_substitution(0, ["latn"], None) == 1


def test_get_substitution_no_matching_enabled_feature_returns_input() -> None:
    """When the enabled-features list misses every feature in the
    script, no lookup fires and the input GID is returned as-is."""
    table = _gsub_with_single_substitution(("a", "a.alt"), {"a": "a.alt"})
    assert table.get_substitution(0, ["latn"], ["dlig"]) == 0  # 'liga' not enabled


def test_get_substitution_empty_script_tags_falls_back_to_first_script() -> None:
    """An empty / ``None`` script-tags list falls back to the first
    available script in the GSUB."""
    table = _gsub_with_single_substitution(("a", "a.alt"), {"a": "a.alt"})
    # Both [] and None should work the same way.
    assert table.get_substitution(0, [], ["liga"]) == 1
    # Reset the cache so the second call really re-runs the lookup.
    table._lookup_cache.clear()  # noqa: SLF001
    table._reverse_lookup.clear()  # noqa: SLF001
    assert table.get_substitution(0, None, ["liga"]) == 1


# ---------- get_gsub_data is None per project deviation --------------------


def test_get_gsub_data_projects_active_script() -> None:
    """Wave 1375: :meth:`get_gsub_data` projects a real
    :class:`GsubData` view; the default call picks the first preferred
    supported script (``latn`` here), the explicit-tag call returns
    that script and ``None`` for an unknown one."""
    table = _gsub_with_single_substitution(("a", "a.alt"), {"a": "a.alt"})
    default_data = table.get_gsub_data()
    assert default_data is not None
    assert default_data.get_active_script_name() == "latn"
    explicit_data = table.get_gsub_data("latn")
    assert explicit_data is not None
    assert explicit_data.get_active_script_name() == "latn"
    assert table.get_gsub_data("non_existent_tag") is None


# ---------- get_supported_script_tags ---------------------------------------


def test_get_supported_script_tags_returns_set_copy() -> None:
    """Upstream returns an unmodifiable view; we return a fresh ``set``
    on each call. Mutating the returned set must not perturb the table."""
    table = _gsub_with_single_substitution(("a", "a.alt"), {"a": "a.alt"})
    tags = table.get_supported_script_tags()
    tags.add("intruder")
    assert "intruder" not in table.get_supported_script_tags()
