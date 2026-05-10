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
