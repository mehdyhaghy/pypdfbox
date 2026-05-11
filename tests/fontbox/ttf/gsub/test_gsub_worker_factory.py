"""Tests for :class:`GsubWorkerFactory`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.cmap_lookup import CmapLookup
from pypdfbox.fontbox.ttf.gsub import (
    DefaultGsubWorker,
    GsubData,
    GsubWorkerFactory,
    GsubWorkerForBengali,
    GsubWorkerForDevanagari,
    GsubWorkerForDflt,
    GsubWorkerForGujarati,
    GsubWorkerForLatin,
)
from pypdfbox.fontbox.ttf.model.language import Language


class _NullCmap(CmapLookup):
    def get_glyph_id(self, code_point_at: int) -> int:
        return 0

    def get_char_codes(self, gid: int) -> list[int] | None:
        return None


def _factory() -> GsubWorkerFactory:
    return GsubWorkerFactory()


def test_returns_default_worker_for_unknown_language() -> None:
    gd = GsubData(language="HEBREW")
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, DefaultGsubWorker)


def test_returns_dflt_worker_for_dflt_language() -> None:
    gd = GsubData(language="DFLT")
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, GsubWorkerForDflt)


def test_returns_latin_worker_for_latin_language() -> None:
    gd = GsubData(language="LATIN")
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, GsubWorkerForLatin)


def test_returns_bengali_worker_for_bengali_language() -> None:
    gd = GsubData(language="BENGALI")
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, GsubWorkerForBengali)


def test_returns_devanagari_worker_for_devanagari_language() -> None:
    gd = GsubData(language="DEVANAGARI")
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, GsubWorkerForDevanagari)


def test_returns_gujarati_worker_for_gujarati_language() -> None:
    gd = GsubData(language="GUJARATI")
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, GsubWorkerForGujarati)


def test_accepts_language_enum_value_for_latin() -> None:
    # ``GsubData.language`` is typed as ``str`` but the dispatch must
    # tolerate a real ``Language`` enum too — upstream branches on
    # the enum itself.
    gd = GsubData()
    gd.language = Language.LATIN  # type: ignore[assignment]
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, GsubWorkerForLatin)


def test_case_insensitive_language_match() -> None:
    gd = GsubData(language="latin")
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, GsubWorkerForLatin)


def test_empty_language_returns_default_worker() -> None:
    gd = GsubData(language="")
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, DefaultGsubWorker)


# ---------- Wave 1286: script-list-aware resolution ----------


def _gsub_data_with_scripts(language: str, *script_tags: str) -> GsubData:
    """Build a :class:`GsubData` whose ``script_list`` carries ``script_tags``."""
    gd = GsubData(language=language)
    # ``ScriptTable`` carries no fields relevant to dispatch — empty
    # instances are enough to make ``script_list`` keys present.
    from pypdfbox.fontbox.ttf.gsub.script_table import ScriptTable

    for tag in script_tags:
        gd.script_list[tag] = ScriptTable()
    return gd


def test_resolve_from_script_list_when_language_unspecified() -> None:
    """``UNSPECIFIED`` language must still route a font that carries
    ``deva`` to the Devanagari worker."""
    gd = _gsub_data_with_scripts("UNSPECIFIED", "deva")
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, GsubWorkerForDevanagari)


def test_resolve_from_script_list_prefers_modern_tag() -> None:
    """``bng2`` (modern) beats ``beng`` when both are present."""
    gd = _gsub_data_with_scripts("UNSPECIFIED", "beng", "bng2")
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, GsubWorkerForBengali)


def test_resolve_from_script_list_falls_back_to_legacy_tag() -> None:
    """Without ``gjr2`` the secondary ``gujr`` tag still resolves Gujarati."""
    gd = _gsub_data_with_scripts("UNSPECIFIED", "gujr")
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, GsubWorkerForGujarati)


def test_explicit_hint_wins_over_other_scripts_when_present() -> None:
    """A font carrying both ``latn`` and ``deva`` whose hint is
    ``LATIN`` must route to Latin (the hint matches a present script)."""
    gd = _gsub_data_with_scripts("LATIN", "latn", "deva")
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, GsubWorkerForLatin)


def test_unknown_hint_falls_through_to_script_resolution() -> None:
    """A font whose hint is ``"HEBREW"`` (unknown) but whose script
    list carries ``latn`` must still route to Latin via script
    resolution rather than the default worker."""
    gd = _gsub_data_with_scripts("HEBREW", "latn")
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, GsubWorkerForLatin)


def test_empty_script_list_and_unknown_hint_returns_default() -> None:
    gd = GsubData(language="HEBREW")
    worker = _factory().get_gsub_worker(_NullCmap(), gd)
    assert isinstance(worker, DefaultGsubWorker)
