"""Wave 1392 — close the ``GsubData`` projection + ``OpenTypeScript``
constants gap previously tracked in DEFERRED.md.

The DEFERRED.md entry called out two latent gaps in
``pypdfbox/fontbox/ttf/glyph_substitution_table.py``:

1. ``get_gsub_data`` / ``get_gsub_data(scriptTag)`` returned ``None``
   (now ports the per-script ``GsubData`` projection — pre-existing).
2. ``selectScriptTag`` did not depend on ``OpenTypeScript.INHERITED`` /
   ``OpenTypeScript.TAG_DEFAULT`` (now uses both constants and adds the
   missing ``INHERITED`` branch — closed in wave 1392).

These tests pin the upstream-parity behaviour of the constants-driven
path so future refactors cannot silently drop either branch.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable
from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData
from pypdfbox.fontbox.ttf.open_type_script import OpenTypeScript

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _make_table_with_scripts(script_tags: list[str]) -> GlyphSubstitutionTable:
    """Build a minimal ``GlyphSubstitutionTable`` with ``_script_tags``
    populated. Used to exercise ``_select_script_tag`` without going
    through the full ``populate_from_fonttools`` ceremony."""
    t = GlyphSubstitutionTable()
    t._script_tags = list(script_tags)
    return t


# ----------------------------------------------------------------------
# INHERITED handling (wave 1392 — newly closed)
# ----------------------------------------------------------------------


def test_select_script_tag_inherited_returns_first_when_no_cache() -> None:
    """Per upstream L720-728: a lone ``Inherited`` tag with no cached
    ``lastUsedSupportedScript`` falls back to the first script in the
    table (``scriptList.keySet().iterator().next()`` upstream)."""
    t = _make_table_with_scripts(["latn", "grek"])
    assert t._select_script_tag((OpenTypeScript.INHERITED,)) == "latn"
    # Cache is populated as a side effect.
    assert t._last_used_supported_script == "latn"


def test_select_script_tag_inherited_returns_cached_when_present() -> None:
    """Per upstream L729: a lone ``Inherited`` tag returns the cached
    script when one is present (most common path during a paragraph)."""
    t = _make_table_with_scripts(["latn", "grek"])
    t._last_used_supported_script = "grek"
    assert t._select_script_tag((OpenTypeScript.INHERITED,)) == "grek"


def test_select_script_tag_inherited_returns_input_when_no_scripts() -> None:
    """Edge case not tested upstream (upstream would NPE on the
    ``iterator().next()`` call): an empty scriptList + no cache returns
    the input tag as-is so the caller can detect the unresolved state."""
    t = _make_table_with_scripts([])
    assert t._select_script_tag((OpenTypeScript.INHERITED,)) == OpenTypeScript.INHERITED


def test_select_script_tag_inherited_uppercase_distinct_from_lowercase() -> None:
    """``OpenTypeScript.INHERITED`` is the literal ``"Inherited"`` —
    NOT ``"inherited"``. Lowercase variant must fall through to the
    normal scriptList membership check (and fail to find a match)."""
    t = _make_table_with_scripts(["latn"])
    # Lowercase ``inherited`` is not in scriptList → falls through to
    # the iterate-tags-for-membership loop, finds no match, returns
    # the input tag as-is (per upstream L744).
    assert t._select_script_tag(("inherited",)) == "inherited"
    # Cache must NOT be populated by the failed lookup.
    assert t._last_used_supported_script is None


# ----------------------------------------------------------------------
# TAG_DEFAULT handling (now uses OpenTypeScript.TAG_DEFAULT constant)
# ----------------------------------------------------------------------


def test_select_script_tag_default_present_returns_default_via_membership() -> None:
    """When ``DFLT`` IS in scriptList, upstream L721 takes the false
    branch (``!scriptList.containsKey(tag)``) — falls through to the
    membership loop which returns ``DFLT`` directly."""
    t = _make_table_with_scripts([OpenTypeScript.TAG_DEFAULT, "latn"])
    assert t._select_script_tag((OpenTypeScript.TAG_DEFAULT,)) == OpenTypeScript.TAG_DEFAULT
    assert t._last_used_supported_script == OpenTypeScript.TAG_DEFAULT


def test_select_script_tag_default_missing_returns_first_when_no_cache() -> None:
    """When ``DFLT`` is NOT in scriptList (which is the common case —
    most fonts don't carry a literal DFLT entry), the
    ``!scriptList.containsKey(tag)`` branch fires and we fall back to
    the first script."""
    t = _make_table_with_scripts(["latn", "grek"])
    assert t._select_script_tag((OpenTypeScript.TAG_DEFAULT,)) == "latn"
    assert t._last_used_supported_script == "latn"


def test_select_script_tag_default_missing_returns_cached() -> None:
    """When ``DFLT`` is not in scriptList AND cache is populated, the
    cache wins."""
    t = _make_table_with_scripts(["latn"])
    t._last_used_supported_script = "grek"  # script not even in table
    assert t._select_script_tag((OpenTypeScript.TAG_DEFAULT,)) == "grek"


def test_select_script_tag_lowercase_dflt_treated_as_default() -> None:
    """pypdfbox-side tolerance: lowercase ``"dflt"`` is treated as
    equivalent to upstream's uppercase ``"DFLT"``."""
    t = _make_table_with_scripts(["latn"])
    assert t._select_script_tag(("dflt",)) == "latn"


# ----------------------------------------------------------------------
# Constant identity — ``OpenTypeScript`` constants must be the literal
# strings upstream uses, so direct file-data comparisons keep working.
# ----------------------------------------------------------------------


def test_select_script_tag_uses_real_constants() -> None:
    """The constants must be the literal upstream strings — a refactor
    that imports a different OT-script module by mistake would silently
    break the script-tag identity comparisons."""
    assert OpenTypeScript.INHERITED == "Inherited"
    assert OpenTypeScript.TAG_DEFAULT == "DFLT"


def test_select_script_tag_inherited_multi_tag_no_special_case() -> None:
    """The special-case branches only fire when ``len(tags) == 1``.
    A multi-tag input including ``Inherited`` falls through to the
    normal membership loop (mirrors upstream L717)."""
    t = _make_table_with_scripts(["latn"])
    # Both tags present in the call; INHERITED is the first but
    # length != 1, so we just iterate and return the first match.
    result = t._select_script_tag((OpenTypeScript.INHERITED, "latn"))
    assert result == "latn"
    assert t._last_used_supported_script == "latn"


# ----------------------------------------------------------------------
# get_gsub_data projection — pin the wave-1392 docstring promise that
# this method returns a populated GsubData (not None).
# ----------------------------------------------------------------------


class _StubLangSys:
    def __init__(self, feature_indices: list[int]) -> None:
        self.ReqFeatureIndex = 0xFFFF
        self.FeatureIndex = feature_indices
        self.LangSysTag = "dflt"


class _StubScriptTable:
    def __init__(self, default_lang_sys: _StubLangSys) -> None:
        self.DefaultLangSys = default_lang_sys
        self.LangSysRecord = []


class _StubScriptRecord:
    def __init__(self, tag: str, default_feature_indices: list[int]) -> None:
        self.ScriptTag = tag
        self.Script = _StubScriptTable(_StubLangSys(default_feature_indices))


class _StubScriptList:
    def __init__(self, records: list[_StubScriptRecord]) -> None:
        self.ScriptRecord = records


class _StubFeature:
    def __init__(self, lookup_indices: list[int]) -> None:
        self.LookupListIndex = lookup_indices


class _StubFeatureRecord:
    def __init__(self, tag: str, lookup_indices: list[int]) -> None:
        self.FeatureTag = tag
        self.Feature = _StubFeature(lookup_indices)


class _StubFeatureList:
    def __init__(self, records: list[_StubFeatureRecord]) -> None:
        self.FeatureRecord = records


class _StubLookupList:
    def __init__(self) -> None:
        self.Lookup: list[Any] = []


class _StubGsubTable:
    def __init__(
        self, script_tag: str, feature_tags: list[str]
    ) -> None:
        # Each declared feature lands at its own index (0..N-1).
        self.ScriptList = _StubScriptList(
            [
                _StubScriptRecord(
                    script_tag,
                    default_feature_indices=list(range(len(feature_tags))),
                )
            ]
        )
        self.FeatureList = _StubFeatureList(
            [_StubFeatureRecord(tag, [0]) for tag in feature_tags]
        )
        self.LookupList = _StubLookupList()


def _bind_stub(t: GlyphSubstitutionTable, gsub: _StubGsubTable) -> None:
    """Bind a stub ``GSUB`` graph onto the table so the projection
    helpers can walk it."""
    t._gsub_table = gsub
    t._script_tags = [r.ScriptTag for r in gsub.ScriptList.ScriptRecord]


def test_get_gsub_data_returns_populated_data_when_script_supported() -> None:
    """``get_gsub_data(scriptTag)`` must return a populated GsubData
    with the script's feature tags exposed in ``feature_list``."""
    t = GlyphSubstitutionTable()
    _bind_stub(t, _StubGsubTable("latn", ["liga", "kern", "sups"]))
    data = t.get_gsub_data("latn")
    assert data is not None
    assert isinstance(data, GsubData)
    assert data.active_script_name == "latn"
    assert set(data.feature_list.keys()) == {"liga", "kern", "sups"}


def test_get_gsub_data_unknown_script_returns_none() -> None:
    """``get_gsub_data(scriptTag)`` must return ``None`` when the script
    tag is not in the table's script list (parity with upstream's
    ``null`` return)."""
    t = GlyphSubstitutionTable()
    _bind_stub(t, _StubGsubTable("latn", ["liga"]))
    assert t.get_gsub_data("grek") is None


def test_get_gsub_data_no_args_picks_default_script() -> None:
    """``get_gsub_data()`` (no args) selects the most-preferred
    supported script via the ``Language`` preference order; for a
    Latin-only stub that's ``latn``."""
    t = GlyphSubstitutionTable()
    _bind_stub(t, _StubGsubTable("latn", ["liga"]))
    data = t.get_gsub_data()
    assert data is not None
    assert data.active_script_name == "latn"
    assert "liga" in data.feature_list


def test_get_gsub_data_no_table_returns_no_data_found_sentinel() -> None:
    """``get_gsub_data()`` on an unbound table returns the
    ``GsubData.NO_DATA_FOUND`` sentinel (not a fresh empty instance)."""
    t = GlyphSubstitutionTable()
    # _gsub_table left as None (default).
    data = t.get_gsub_data()
    assert data is GsubData.NO_DATA_FOUND


def test_get_gsub_data_no_table_with_script_arg_returns_none() -> None:
    """``get_gsub_data(scriptTag)`` on an unbound table returns
    ``None`` (parity with upstream — no projection possible at all)."""
    t = GlyphSubstitutionTable()
    assert t.get_gsub_data("latn") is None
