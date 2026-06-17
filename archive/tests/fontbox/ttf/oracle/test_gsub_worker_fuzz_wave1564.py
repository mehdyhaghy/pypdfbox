"""Live PDFBox differential parity for the *per-script* ``GsubWorker`` layer
(``oracle/probes/GsubWorkerFuzzProbe.java``, wave 1564).

Wave 1547 (``test_gsub_layout_fuzz_wave1547.py``) fuzzed the substitution-application
*engine* — the splitter plus ``MapBackedScriptFeature`` ``canReplaceGlyphs`` /
``getReplacementForGlyphs`` decision — by re-implementing the worker
``applyGsubFeature`` body by hand, because the concrete worker constructors are
package-private. This wave fuzzes the *worker* layer one level up: the public
``GsubWorkerFactory.getGsubWorker`` dispatch and the chosen worker's
``applyTransforms`` over a built ``MapBackedGsubData`` — i.e. *which* concrete
worker the factory picks per :class:`Language`, and each script worker's
per-script ``FEATURES_IN_ORDER`` application order, end to end.

Angles fuzzed (the wave-1547 engine cases are NOT repeated):
  * factory dispatch by language → concrete worker class chosen;
  * Latin worker (``ccmp``/``liga``/``clig`` order), incl. multi-feature
    ordering where ``ccmp`` feeds ``liga`` (the order is observable);
  * DFLT worker (``ccmp``/``liga``/``clig``/``calt`` — ``calt`` is DFLT-only,
    Latin lacks it);
  * unknown language (``UNSPECIFIED``) → ``DefaultGsubWorker`` (no substitution);
  * Indic workers (Bengali / Devanagari / Gujarati) routed through the factory
    with a stub cmap, applying a ``pres`` ligature;
  * empty run, no-applicable-feature run, repeated glyphs, feature-less data.

Result of the sweep: factory dispatch and per-script worker output are
byte-for-byte faithful to FontBox over every case.

REAL BUG FIXED (wave 1564): ``GsubWorkerFactory.get_gsub_worker`` called
``gsub_data.get_script_list()`` unconditionally while confirming the language
hint. Upstream's ``MapBackedGsubData`` is a first-class ``GsubData`` with **no**
``getScriptList`` method (its factory dispatches purely on ``getLanguage()``), so
handing one to the pypdfbox factory raised ``AttributeError`` instead of
returning the right worker. The factory now resolves the script tags through a
defensive guard (``_get_script_tags``) and degrades to the bare language hint
when no ScriptList is present — matching upstream's pure-language dispatch. The
``unspecified_*`` and every ``MapBackedGsubData``-driven case below pin the fix.

NOTE on scripts pypdfbox ports vs not: pypdfbox additionally ships TAMIL / AALT /
SMCP workers that upstream FontBox 3.0.7 has **no** ``Language`` enum entries for
(its enum is BENGALI/DEVANAGARI/GUJARATI/LATIN/DFLT/UNSPECIFIED only). Those
extra workers cannot be reached through ``MapBackedGsubData`` (whose constructor
takes a ``Language``), so the differential cases here cover only the six
upstream-comparable languages; the pypdfbox-only workers are exercised by the
hand-written worker tests, not the oracle.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.gsub.gsub_worker_factory import GsubWorkerFactory
from pypdfbox.fontbox.ttf.model.language import Language
from pypdfbox.fontbox.ttf.model.map_backed_gsub_data import MapBackedGsubData
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "GsubWorkerFuzzProbe"


class _StubCmap:
    """Trivial ``CmapLookup`` — every char code maps to glyph 0.

    Mirrors the probe's ``STUB_CMAP``; the Indic worker constructors precompute
    reph / before-half glyph ids from the cmap, so a stub is needed to build
    them. Glyph 0 is a sentinel that never appears in the numeric test runs, so
    the reposition passes are inert.
    """

    def get_glyph_id(self, character_code: int) -> int:
        return 0

    def get_char_codes(self, gid: int) -> list[int]:
        return []


# --------------------------------------------------------------------------- #
# Feature maps — identical to the probe's builders.
# --------------------------------------------------------------------------- #
def _liga_map() -> dict[str, dict[tuple[int, ...], int]]:
    return {"liga": {(10, 11): 100, (30,): 400}}


def _ccmp_then_liga_map() -> dict[str, dict[tuple[int, ...], int]]:
    return {"ccmp": {(5,): 10}, "liga": {(10, 11): 100}}


def _clig_only_map() -> dict[str, dict[tuple[int, ...], int]]:
    return {"clig": {(40, 41): 500}}


def _calt_only_map() -> dict[str, dict[tuple[int, ...], int]]:
    return {"calt": {(40, 41): 600}}


def _pres_map() -> dict[str, dict[tuple[int, ...], int]]:
    return {"pres": {(10, 11): 100}}


def _apply(
    language: Language,
    script: str,
    features: dict[str, dict[tuple[int, ...], int]],
    run: list[int],
) -> tuple[str, list[int]]:
    """Drive the factory + worker exactly as the probe does."""
    data = MapBackedGsubData(language, script, features)
    worker = GsubWorkerFactory().get_gsub_worker(_StubCmap(), data)
    return type(worker).__name__, worker.apply_transforms(run)


def _line(worker_class: str, out: list[int]) -> str:
    return f"WORKER\t{worker_class}\tOUT\t" + ",".join(str(g) for g in out) + "\n"


# --------------------------------------------------------------------------- #
# case id -> (language, script, feature-map factory, input run,
#             expected worker class, expected output run).
# Expected values are PDFBox-3.0.7-derived (confirmed against the live oracle).
# --------------------------------------------------------------------------- #
_CASES: dict[
    str,
    tuple[Language, str, callable, list[int], str, list[int]],
] = {
    "latin_empty_run": (Language.LATIN, "latn", _liga_map, [], "GsubWorkerForLatin", []),
    "latin_no_match": (
        Language.LATIN, "latn", _liga_map, [1, 2, 3], "GsubWorkerForLatin", [1, 2, 3],
    ),
    "latin_ligature": (
        Language.LATIN, "latn", _liga_map, [10, 11], "GsubWorkerForLatin", [100],
    ),
    "latin_ligature_in_context": (
        Language.LATIN, "latn", _liga_map, [7, 10, 11, 8],
        "GsubWorkerForLatin", [7, 100, 8],
    ),
    "latin_repeated_glyphs": (
        Language.LATIN, "latn", _liga_map, [30, 30, 30],
        "GsubWorkerForLatin", [400, 400, 400],
    ),
    "latin_no_features": (
        Language.LATIN, "latn", dict, [10, 11, 30],
        "GsubWorkerForLatin", [10, 11, 30],
    ),
    # ccmp ([5]->10) must run before liga ([10,11]->100): [5,11] -> [100].
    "latin_feature_order_ccmp_then_liga": (
        Language.LATIN, "latn", _ccmp_then_liga_map, [5, 11],
        "GsubWorkerForLatin", [100],
    ),
    "latin_only_clig": (
        Language.LATIN, "latn", _clig_only_map, [40, 41],
        "GsubWorkerForLatin", [500],
    ),
    "dflt_ligature": (
        Language.DFLT, "DFLT", _liga_map, [10, 11], "GsubWorkerForDflt", [100],
    ),
    # calt is DFLT-only — Latin's worker would leave [40,41] unchanged.
    "dflt_calt_applies": (
        Language.DFLT, "DFLT", _calt_only_map, [40, 41], "GsubWorkerForDflt", [600],
    ),
    "dflt_empty_run": (
        Language.DFLT, "DFLT", _liga_map, [], "GsubWorkerForDflt", [],
    ),
    # Unknown language -> DefaultGsubWorker, identity output.
    "unspecified_no_substitution": (
        Language.UNSPECIFIED, "zzzz", _liga_map, [10, 11],
        "DefaultGsubWorker", [10, 11],
    ),
    "unspecified_empty_run": (
        Language.UNSPECIFIED, "zzzz", _liga_map, [], "DefaultGsubWorker", [],
    ),
    "bengali_ligature": (
        Language.BENGALI, "bng2", _pres_map, [10, 11], "GsubWorkerForBengali", [100],
    ),
    "bengali_no_match": (
        Language.BENGALI, "bng2", _pres_map, [1, 2, 3],
        "GsubWorkerForBengali", [1, 2, 3],
    ),
    "bengali_empty_run": (
        Language.BENGALI, "bng2", _pres_map, [], "GsubWorkerForBengali", [],
    ),
    "devanagari_ligature": (
        Language.DEVANAGARI, "dev2", _pres_map, [10, 11],
        "GsubWorkerForDevanagari", [100],
    ),
    "devanagari_no_features": (
        Language.DEVANAGARI, "dev2", dict, [10, 11],
        "GsubWorkerForDevanagari", [10, 11],
    ),
    "gujarati_ligature": (
        Language.GUJARATI, "gjr2", _pres_map, [10, 11],
        "GsubWorkerForGujarati", [100],
    ),
}


# --------------------------------------------------------------------------- #
# Differential tests (live oracle): pypdfbox output must equal the probe's.
# --------------------------------------------------------------------------- #
@requires_oracle
@pytest.mark.parametrize("case", list(_CASES), ids=list(_CASES))
def test_gsub_worker_matches_pdfbox(case: str) -> None:
    language, script, feature_factory, run, _wc, _expected = _CASES[case]
    worker_class, out = _apply(language, script, feature_factory(), run)
    java = run_probe_text(_PROBE, case)
    assert _line(worker_class, out) == java, f"GSUB worker divergence ({case})"


# --------------------------------------------------------------------------- #
# Self-contained value tests (run even without the oracle): pin the
# PDFBox-3.0.7-derived expected worker class + substitution output directly.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", list(_CASES), ids=list(_CASES))
def test_gsub_worker_pinned_values(case: str) -> None:
    language, script, feature_factory, run, expected_wc, expected_out = _CASES[case]
    worker_class, out = _apply(language, script, feature_factory(), run)
    assert worker_class == expected_wc
    assert out == expected_out


def test_map_backed_gsub_data_does_not_crash_factory() -> None:
    """Regression pin (wave 1564): the factory must accept an upstream-shaped
    ``MapBackedGsubData`` (which has no ``get_script_list``) without raising
    ``AttributeError`` while confirming the language hint."""
    data = MapBackedGsubData(Language.LATIN, "latn", _liga_map())
    worker = GsubWorkerFactory().get_gsub_worker(_StubCmap(), data)
    assert type(worker).__name__ == "GsubWorkerForLatin"
    assert worker.apply_transforms([10, 11]) == [100]


def test_unspecified_language_falls_back_to_default_worker() -> None:
    """An unknown language with no resolvable ScriptList -> DefaultGsubWorker."""
    data = MapBackedGsubData(Language.UNSPECIFIED, "zzzz", _liga_map())
    worker = GsubWorkerFactory().get_gsub_worker(_StubCmap(), data)
    assert type(worker).__name__ == "DefaultGsubWorker"
    # No substitution: identity output.
    assert worker.apply_transforms([10, 11]) == [10, 11]


def test_latin_feature_order_is_observable() -> None:
    """ccmp runs before liga: [5,11] -> ccmp([5]->10) -> [10,11] -> liga -> [100].
    If the order were reversed, liga would see [5,11] (no match) and emit
    [10,11] after ccmp instead."""
    _wc, out = _apply(Language.LATIN, "latn", _ccmp_then_liga_map(), [5, 11])
    assert out == [100]


def test_dflt_calt_only_applies_under_dflt_not_latin() -> None:
    """``calt`` is in DFLT's pipeline but not Latin's: DFLT substitutes, Latin
    leaves the run untouched."""
    _wc_dflt, out_dflt = _apply(Language.DFLT, "DFLT", _calt_only_map(), [40, 41])
    assert out_dflt == [600]
    _wc_latin, out_latin = _apply(Language.LATIN, "latn", _calt_only_map(), [40, 41])
    assert out_latin == [40, 41]
