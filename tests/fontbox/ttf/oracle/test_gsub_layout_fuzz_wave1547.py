"""Live PDFBox differential parity for the GSUB *substitution-application* layer
(``oracle/probes/GsubLayoutFuzzProbe.java``, wave 1547).

Where the existing GSUB probes pin the *extraction* half — ``GsubSubstitutionProbe``
dumps the feature map ``GlyphSubstitutionDataExtractor`` materialises for a real
font, and ``GsubExtractorFuzzProbe`` fuzzes the extractor's malformed-graph walk —
this wave fuzzes the *application* half: the engine the per-script ``GsubWorker``s
run inside their ``applyGsubFeature`` body to turn an input glyph-id run into a
substituted one. That engine is:

  * :class:`GlyphArraySplitterRegexImpl` — greedy longest-match tokenizer that
    breaks a glyph run into substitution chunks;
  * :class:`MapBackedScriptFeature` — per-chunk ``canReplaceGlyphs`` /
    ``getReplacementForGlyphs`` decision; and
  * :class:`MapBackedGsubData` — feature lookup, including the unsupported-feature
    throw.

The Java probe re-implements the worker ``applyGsubFeature`` body verbatim (split,
then replace each replaceable chunk) because the concrete worker constructors
(``GsubWorkerForLatin(GsubData)`` etc.) are package-private and a default-package
probe cannot instantiate them. The pypdfbox reproducer below drives the *exact same
public engine* (:func:`pypdfbox.fontbox.ttf.gsub.gsub_worker._apply_gsub_feature`
is the production loop; we inline its body here so the assertion is value-explicit).

Result of the sweep: the substitution-application layer is byte-for-byte faithful
to FontBox over every edge run (empty, no-match, partial / overlapping / back-to-back
ligatures, shared-prefix alternates, duplicate / negative / zero / huge glyph ids).

HONEST DIVERGENCE (pinned, not fixed — it is a deliberate exception-type mapping):
upstream's ``MapBackedGsubData.getFeature(unknownTag)`` and
``MapBackedScriptFeature.getReplacementForGlyphs(unmatchedRun)`` throw
``UnsupportedOperationException``; the pypdfbox port raises ``NotImplementedError``
(the conventional Python equivalent, per PRD §12.1's Java→Python exception table and
the class docstrings). The Java probe projects ``ERROR\tUnsupportedOperationException``
for those two cases; the Python side asserts ``NotImplementedError`` directly rather
than asserting line-equality, with this comment marking the mapping.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.gsub.glyph_array_splitter_regex_impl import (
    GlyphArraySplitterRegexImpl,
)
from pypdfbox.fontbox.ttf.model.language import Language
from pypdfbox.fontbox.ttf.model.map_backed_gsub_data import MapBackedGsubData
from pypdfbox.fontbox.ttf.model.map_backed_script_feature import (
    MapBackedScriptFeature,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "GsubLayoutFuzzProbe"


# --------------------------------------------------------------------------- #
# The canonical "liga" feature shared by every substitution case — identical to
# the map the Java probe builds in ``ligaFeature()``.
# --------------------------------------------------------------------------- #
def _liga_feature() -> MapBackedScriptFeature:
    return MapBackedScriptFeature(
        "liga",
        {
            (10, 11): 100,
            (10, 11, 12): 200,
            (20, 21): 300,
            (30,): 400,
            (10, 99): 500,
        },
    )


def _gsub_data() -> MapBackedGsubData:
    return MapBackedGsubData(
        Language.LATIN,
        "latn",
        {"liga": {(10, 11): 100}, "ccmp": {(30,): 400}},
    )


def _apply(feature: MapBackedScriptFeature, glyphs: list[int]) -> list[int]:
    """Inline the worker ``applyGsubFeature`` body (split, then substitute).

    This is the same loop ``pypdfbox.fontbox.ttf.gsub.gsub_worker._apply_gsub_feature``
    runs in production; reproduced here so each case's expectation is explicit and
    the probe's identical Java loop can be asserted line-for-line.
    """
    keys = feature.get_all_glyph_ids_for_substitution()
    if not keys:
        return list(glyphs)
    splitter = GlyphArraySplitterRegexImpl([list(k) for k in keys])
    tokens = splitter.split(list(glyphs))
    out: list[int] = []
    for chunk in tokens:
        if feature.can_replace_glyphs(chunk):
            out.append(feature.get_replacement_for_glyphs(chunk))
        else:
            out.extend(chunk)
    return out


def _out(glyphs: list[int]) -> str:
    return "OUT\t" + ",".join(str(g) for g in glyphs) + "\n"


# --------------------------------------------------------------------------- #
# Substitution-application cases: case id -> (input run, expected output run).
# Expected values are PDFBox-3.0.7-derived (confirmed against the live oracle).
# --------------------------------------------------------------------------- #
_APPLY_CASES: dict[str, tuple[list[int], list[int]]] = {
    "empty_run": ([], []),
    "no_match": ([1, 2, 3], [1, 2, 3]),
    "single_sub": ([30], [400]),
    "single_sub_in_context": ([1, 30, 2], [1, 400, 2]),
    "ligature_2": ([10, 11], [100]),
    "ligature_3": ([10, 11, 12], [200]),
    "partial_ligature_prefix": ([10], [10]),
    "partial_ligature_short": ([10, 11], [100]),
    "overlap_longest_wins": ([10, 11, 12, 13], [200, 13]),
    "overlap_short_then_tail": ([10, 11, 20, 21], [100, 300]),
    "shared_prefix_alt": ([10, 99], [500]),
    "ligature_in_context": ([7, 10, 11, 8], [7, 100, 8]),
    "back_to_back": ([10, 11, 10, 11, 12], [100, 200]),
    "duplicate_glyphs": ([30, 30, 30], [400, 400, 400]),
    "repeated_prefix_no_complete": ([10, 10, 11], [10, 100]),
    "large_gids": ([65535, 70000, 100000], [65535, 70000, 100000]),
    "negative_gid": ([-1, 30, -5], [-1, 400, -5]),
    "zero_gid": ([0, 10, 11], [0, 100]),
    "all_keys_back_to_back": ([10, 11, 12, 20, 21, 30], [200, 300, 400]),
}


# --------------------------------------------------------------------------- #
# Differential tests (live oracle): pypdfbox output must equal the probe's.
# --------------------------------------------------------------------------- #
@requires_oracle
@pytest.mark.parametrize("case", list(_APPLY_CASES), ids=list(_APPLY_CASES))
def test_gsub_apply_matches_pdfbox(case: str) -> None:
    run, _expected = _APPLY_CASES[case]
    java = run_probe_text(_PROBE, case)
    py = _out(_apply(_liga_feature(), run))
    assert py == java, f"GSUB apply divergence ({case})"


@requires_oracle
def test_empty_feature_identity_matches_pdfbox() -> None:
    empty = MapBackedScriptFeature("liga", {})
    java = run_probe_text(_PROBE, "empty_feature_identity")
    assert _out(_apply(empty, [10, 11, 30])) == java


@requires_oracle
def test_empty_feature_empty_run_matches_pdfbox() -> None:
    empty = MapBackedScriptFeature("liga", {})
    java = run_probe_text(_PROBE, "empty_feature_empty_run")
    assert _out(_apply(empty, [])) == java


@requires_oracle
def test_split_only_matches_pdfbox() -> None:
    """The raw splitter projection (no substitution) must match FontBox's
    ``GlyphArraySplitterRegexImpl.split`` chunking exactly."""
    keys = [list(k) for k in _liga_feature().get_all_glyph_ids_for_substitution()]
    chunks = GlyphArraySplitterRegexImpl(keys).split([10, 11, 12, 20, 21, 5])
    py = "SPLIT\t" + "\t".join(",".join(str(g) for g in c) for c in chunks) + "\n"
    java = run_probe_text(_PROBE, "split_only")
    assert py == java


@requires_oracle
def test_gsub_feature_lookup_matches_pdfbox() -> None:
    data = _gsub_data()
    assert (
        f"META\tsupported={str(data.is_feature_supported('liga')).lower()}\n"
        == run_probe_text(_PROBE, "gsub_supported_feature")
    )
    assert (
        f"META\tsupported={str(data.is_feature_supported('zzzz')).lower()}\n"
        == run_probe_text(_PROBE, "gsub_unknown_feature")
    )


@requires_oracle
def test_gsub_metadata_matches_pdfbox() -> None:
    data = _gsub_data()
    feats = ",".join(sorted(data.get_supported_features()))
    py = (
        f"META\tlang={data.get_language().name}\t"
        f"script={data.get_active_script_name()}\tfeatures={feats}\n"
    )
    assert py == run_probe_text(_PROBE, "gsub_metadata")


@requires_oracle
def test_can_replace_matches_pdfbox() -> None:
    feature = _liga_feature()
    assert (
        f"META\tcan={str(feature.can_replace_glyphs([10, 11])).lower()}\n"
        == run_probe_text(_PROBE, "can_replace_true")
    )
    assert (
        f"META\tcan={str(feature.can_replace_glyphs([10])).lower()}\n"
        == run_probe_text(_PROBE, "can_replace_false_partial")
    )
    assert (
        f"META\tcan={str(feature.can_replace_glyphs([])).lower()}\n"
        == run_probe_text(_PROBE, "can_replace_empty")
    )


@requires_oracle
def test_unsupported_feature_throw_is_mapped_to_not_implemented() -> None:
    """DIVERGENCE pin: upstream throws ``UnsupportedOperationException`` from
    ``getFeature(unknownTag)``; the port raises ``NotImplementedError`` (PRD
    §12.1 Java→Python exception mapping). The probe projects
    ``ERROR\\tUnsupportedOperationException``; we assert the mapped Python type."""
    assert (
        run_probe_text(_PROBE, "gsub_get_unknown_feature_throws")
        == "ERROR\tUnsupportedOperationException\n"
    )
    with pytest.raises(NotImplementedError):
        _gsub_data().get_feature("zzzz")


@requires_oracle
def test_get_replacement_unmatched_throw_is_mapped_to_not_implemented() -> None:
    """DIVERGENCE pin (same mapping as above): upstream
    ``getReplacementForGlyphs(unmatchedRun)`` throws
    ``UnsupportedOperationException``; the port raises ``NotImplementedError``."""
    assert (
        run_probe_text(_PROBE, "gsub_get_replacement_unknown_throws")
        == "ERROR\tUnsupportedOperationException\n"
    )
    with pytest.raises(NotImplementedError):
        _liga_feature().get_replacement_for_glyphs([1, 2])


# --------------------------------------------------------------------------- #
# Self-contained value tests (run even without the oracle): pin the
# PDFBox-3.0.7-derived expected substitution outputs directly.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", list(_APPLY_CASES), ids=list(_APPLY_CASES))
def test_gsub_apply_pinned_values(case: str) -> None:
    run, expected = _APPLY_CASES[case]
    assert _apply(_liga_feature(), run) == expected


def test_split_chunking_pinned_values() -> None:
    keys = [list(k) for k in _liga_feature().get_all_glyph_ids_for_substitution()]
    chunks = GlyphArraySplitterRegexImpl(keys).split([10, 11, 12, 20, 21, 5])
    assert chunks == [[10, 11, 12], [20, 21], [5]]


def test_empty_feature_is_identity_pinned() -> None:
    empty = MapBackedScriptFeature("liga", {})
    assert _apply(empty, [10, 11, 30]) == [10, 11, 30]
    assert _apply(empty, []) == []


def test_unknown_feature_lookup_pinned() -> None:
    data = _gsub_data()
    assert data.is_feature_supported("liga") is True
    assert data.is_feature_supported("zzzz") is False
    with pytest.raises(NotImplementedError):
        data.get_feature("zzzz")


def test_can_replace_pinned() -> None:
    feature = _liga_feature()
    assert feature.can_replace_glyphs([10, 11]) is True
    assert feature.can_replace_glyphs([10]) is False
    assert feature.can_replace_glyphs([]) is False
