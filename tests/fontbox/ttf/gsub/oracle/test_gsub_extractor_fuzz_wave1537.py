"""Live PDFBox differential parity for the substitution-data level of
:class:`GlyphSubstitutionDataExtractor` under malformed GSUB graphs.

Where ``test_gsub_substitution_oracle`` drives the whole
``GlyphSubstitutionTable.getGsubData(scriptTag)`` pipeline over a real font,
this wave-1537 suite constructs *malformed* ScriptTable / FeatureList /
LookupList graphs directly and feeds them to the extractor's two public
``get_gsub_data`` overloads. The Java oracle
(``oracle/probes/GsubExtractorFuzzProbe.java``) runs the same scenarios
through Apache FontBox 3.0.7's ``GlyphSubstitutionDataExtractor`` so each
projected result (or thrown-exception class) can be asserted line for line.

Scenarios (extractor-level fuzz surfaces):

* ``empty_script_list`` — the ``getGsubData(Map, ...)`` overload over an
  empty script map: no supported language -> ``NO_DATA``.
* ``unknown_script_tag`` — a script tag the ``Language`` enum doesn't
  recognise -> ``NO_DATA``.
* ``no_default_langsys`` — a script with neither a default LangSys nor any
  per-language LangSys -> an empty substitution map.
* ``no_features`` — a default LangSys with zero feature indices.
* ``feature_index_out_of_range`` — a LangSys referencing a feature index
  past the end of the FeatureList -> silently skipped.
* ``lookup_index_out_of_range`` — a feature referencing a lookup index past
  the end of the LookupList -> silently skipped (empty feature retained).
* ``unhandled_lookup_type`` — a lookup whose subtable class is outside the
  extractor's ``instanceof`` dispatch chain -> ignored (empty feature).
* ``duplicate_feature_tags`` — two FeatureRecords with the same tag: the
  later record overrides the earlier in the tag-keyed map.
* ``single_f2_size_mismatch`` — a SingleSubstFormat2 whose substitute count
  disagrees with the coverage size -> logged and skipped (empty feature).

The one genuine divergence (``null_feature_table``) is pinned separately:
Apache FontBox dereferences ``getFeatureTable()`` without a null guard and
throws ``NullPointerException``; pypdfbox keeps its defensive guard and
treats the record as carrying no lookups (a documented, intentional
improvement — see CHANGES.md Wave 1537). We assert *both* sides so the
divergence can never drift silently.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.gsub.feature_record import FeatureRecord
from pypdfbox.fontbox.ttf.gsub.feature_table import FeatureTable
from pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor import (
    GlyphSubstitutionDataExtractor,
)
from pypdfbox.fontbox.ttf.gsub.lang_sys_table import LangSysTable
from pypdfbox.fontbox.ttf.gsub.lookup_subtable import (
    LookupTypeSingleSubstFormat1,
    LookupTypeSingleSubstFormat2,
)
from pypdfbox.fontbox.ttf.gsub.lookup_table import LookupTable
from pypdfbox.fontbox.ttf.gsub.script_table import ScriptTable
from pypdfbox.fontbox.ttf.model.map_backed_gsub_data import MapBackedGsubData
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "GsubExtractorFuzzProbe"


# ---------------------------------------------------------------------------
# pypdfbox-side builders mirroring the Java probe's malformed graphs.
# ---------------------------------------------------------------------------


def _single_f1_lookup() -> LookupTable:
    # coverage {10,11,12}, delta +5 -> 10->15, 11->16, 12->17
    st = LookupTypeSingleSubstFormat1(
        delta_glyph_id=5, coverage_table=(10, 11, 12)
    )
    return LookupTable(lookup_type=1, sub_tables=(st,))


def _single_f2_lookup() -> LookupTable:
    # coverage {20,21}, subs {200,201} -> 20->200, 21->201
    st = LookupTypeSingleSubstFormat2(
        substitute_glyph_ids=(200, 201), coverage_table=(20, 21)
    )
    return LookupTable(lookup_type=1, sub_tables=(st,))


def _emit(data: MapBackedGsubData | None) -> str:
    """Serialise pypdfbox's result exactly as the Java probe serialises."""
    if data is None:
        return "RESULT\tNO_DATA\n"
    lines = [
        f"RESULT\t{data.get_active_script_name()}\t{data.get_language().name}"
    ]
    for tag in sorted(data.get_supported_features()):
        feature = data.get_feature(tag)
        runs = feature.get_all_glyph_ids_for_substitution()
        lines.append(f"FEATURE\t{tag}\t{len(runs)}")
        for run in sorted(runs):
            sub = feature.get_replacement_for_glyphs(list(run))
            run_str = ",".join(str(g) for g in run)
            lines.append(f"SUB\t{tag}\t{run_str}\t{sub}")
    return "\n".join(lines) + "\n"


def _run_py_case(name: str) -> str:
    extractor = GlyphSubstitutionDataExtractor()
    if name == "empty_script_list":
        data = extractor.get_gsub_data(
            {},
            [FeatureRecord("liga", FeatureTable(lookup_list_indices=(0,)))],
            [_single_f1_lookup()],
        )
        return _emit(data)
    if name == "unknown_script_tag":
        data = extractor.get_gsub_data(
            {"zzzz": ScriptTable(default_lang_sys_table=LangSysTable(feature_indices=(0,)))},
            [FeatureRecord("liga", FeatureTable(lookup_list_indices=(0,)))],
            [_single_f1_lookup()],
        )
        return _emit(data)
    if name == "no_default_langsys":
        data = extractor.get_gsub_data_for_script(
            "latn",
            ScriptTable(),
            [FeatureRecord("liga", FeatureTable(lookup_list_indices=(0,)))],
            [_single_f1_lookup()],
        )
        return _emit(data)
    if name == "no_features":
        data = extractor.get_gsub_data_for_script(
            "latn",
            ScriptTable(default_lang_sys_table=LangSysTable(feature_indices=())),
            [FeatureRecord("liga", FeatureTable(lookup_list_indices=(0,)))],
            [_single_f1_lookup()],
        )
        return _emit(data)
    if name == "feature_index_out_of_range":
        data = extractor.get_gsub_data_for_script(
            "latn",
            ScriptTable(default_lang_sys_table=LangSysTable(feature_indices=(5,))),
            [FeatureRecord("liga", FeatureTable(lookup_list_indices=(0,)))],
            [_single_f1_lookup()],
        )
        return _emit(data)
    if name == "lookup_index_out_of_range":
        data = extractor.get_gsub_data_for_script(
            "latn",
            ScriptTable(default_lang_sys_table=LangSysTable(feature_indices=(0,))),
            [FeatureRecord("liga", FeatureTable(lookup_list_indices=(9,)))],
            [_single_f1_lookup()],
        )
        return _emit(data)
    if name == "unhandled_lookup_type":
        # A lookup table holding a subtable that is none of the dispatched
        # classes -> ignored, leaving an empty feature (mirrors the Java
        # probe's UnhandledSubTable shell under lookupType 2).
        lt = LookupTable(lookup_type=2, sub_tables=(object(),))
        data = extractor.get_gsub_data_for_script(
            "latn",
            ScriptTable(default_lang_sys_table=LangSysTable(feature_indices=(0,))),
            [FeatureRecord("liga", FeatureTable(lookup_list_indices=(0,)))],
            [lt],
        )
        return _emit(data)
    if name == "duplicate_feature_tags":
        data = extractor.get_gsub_data_for_script(
            "latn",
            ScriptTable(default_lang_sys_table=LangSysTable(feature_indices=(0, 1))),
            [
                FeatureRecord("liga", FeatureTable(lookup_list_indices=(0,))),
                FeatureRecord("liga", FeatureTable(lookup_list_indices=(1,))),
            ],
            [_single_f1_lookup(), _single_f2_lookup()],
        )
        return _emit(data)
    if name == "single_f2_size_mismatch":
        st = LookupTypeSingleSubstFormat2(
            substitute_glyph_ids=(100,), coverage_table=(10, 11)
        )
        lt = LookupTable(lookup_type=1, sub_tables=(st,))
        data = extractor.get_gsub_data_for_script(
            "latn",
            ScriptTable(default_lang_sys_table=LangSysTable(feature_indices=(0,))),
            [FeatureRecord("liga", FeatureTable(lookup_list_indices=(0,)))],
            [lt],
        )
        return _emit(data)
    raise AssertionError(f"unknown case: {name}")


_ALIGNED_CASES = [
    "empty_script_list",
    "unknown_script_tag",
    "no_default_langsys",
    "no_features",
    "feature_index_out_of_range",
    "lookup_index_out_of_range",
    "unhandled_lookup_type",
    "duplicate_feature_tags",
    "single_f2_size_mismatch",
]


@requires_oracle
@pytest.mark.parametrize("case", _ALIGNED_CASES, ids=_ALIGNED_CASES)
def test_extractor_fuzz_matches_pdfbox(case: str) -> None:
    """The extractor's projection of each malformed GSUB graph must match
    Apache PDFBox 3.0.7 line for line (RESULT / FEATURE / SUB)."""
    java = run_probe_text(_PROBE, case)
    py = _run_py_case(case)
    assert py == java, (
        f"GSUB extractor fuzz parity broken for {case!r}:\n"
        f"java={java!r}\npy=  {py!r}"
    )


@requires_oracle
def test_null_feature_table_divergence_pinned() -> None:
    """Pinned intentional divergence (CHANGES.md Wave 1537).

    Apache FontBox dereferences ``FeatureRecord.getFeatureTable()`` with no
    null guard and throws ``NullPointerException`` when the table is null.
    pypdfbox keeps a defensive ``if feature_table is not None`` guard and
    treats the record as carrying no lookups, returning a valid (empty)
    feature rather than crashing. Both sides are asserted so the divergence
    can never drift silently.
    """
    java = run_probe_text(_PROBE, "null_feature_table")
    assert java == "ERROR\tNullPointerException\n"

    extractor = GlyphSubstitutionDataExtractor()
    data = extractor.get_gsub_data_for_script(
        "latn",
        ScriptTable(default_lang_sys_table=LangSysTable(feature_indices=(0,))),
        [FeatureRecord("liga", None)],
        [_single_f1_lookup()],
    )
    # No crash; the feature is present but empty (no lookups resolved).
    assert isinstance(data, MapBackedGsubData)
    assert data.is_feature_supported("liga")
    assert data.get_feature("liga").get_all_glyph_ids_for_substitution() == set()
