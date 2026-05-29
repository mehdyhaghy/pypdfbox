"""Live PDFBox differential parity for GSUB glyph-substitution extraction.

Exercises the FontBox OpenType GSUB substitution surface against Apache
PDFBox 3.0.7 (``oracle/probes/GsubSubstitutionProbe.java``):

    GlyphSubstitutionTable.getGsubData(scriptTag)
        -> GlyphSubstitutionDataExtractor walks ScriptList -> LangSys ->
           FeatureList -> LookupList and materialises a
           ``feature_tag -> {glyph_run -> substitute_glyph_id}`` map.

The Java probe dumps that map for a font + script tag; pypdfbox rebuilds
the same map from the *same font's GSUB bytes* using its own
upstream-mirrored byte parser
(``GlyphSubstitutionTable.read_script_list`` / ``read_feature_list`` /
``read_lookup_list``) feeding the ported
``GlyphSubstitutionDataExtractor.get_gsub_data_for_script``. A divergence
shows up as a single differing line.

Coverage of GSUB lookup machinery:

* **Type 1 — single substitution** (formats 1 & 2): exercised by the
  ``case`` / ``locl`` features (single-glyph runs ``[gid] -> sub``).
* **Type 3 — alternate substitution**: the extractor records the first
  differing alternate as a single substitution; exercised by ``aalt`` /
  ``salt``.
* **Type 4 — ligature substitution**: exercised by ``liga`` / ``dlig`` /
  ``hlig`` (multi-glyph runs like ``f+f -> ff``, ``f+i -> fi``).

The ``ScriptList`` / ``FeatureList`` / ``LookupList`` resolution and the
``getGsubData(scriptTag)`` -> ``MapBackedGsubData`` projection are
verified end to end: feature-tag set, per-feature run count, and every
``run -> substitute`` pair.

Fonts used (permissive, bundled):
  * ``DejaVuSans`` (latn) — richest case: Type 1/3/4 lookups across
    ``aalt`` / ``case`` / ``ccmp`` / ``dlig`` / ``hlig`` / ``liga`` /
    ``locl`` / ``salt``.
  * ``LiberationSans-Regular`` (latn) — ``ccmp`` / ``dlig`` / ``subs`` /
    ``sups`` with Type 1 + Type 4 lookups.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable
from pypdfbox.fontbox.ttf.gsub.feature_record import FeatureRecord
from pypdfbox.fontbox.ttf.gsub.feature_table import FeatureTable
from pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor import (
    GlyphSubstitutionDataExtractor,
)
from pypdfbox.fontbox.ttf.gsub.lang_sys_table import LangSysTable
from pypdfbox.fontbox.ttf.gsub.lookup_subtable import (
    AlternateSetTable,
    LigatureSetTable,
    LigatureTable,
    LookupTypeAlternateSubstitutionFormat1,
    LookupTypeLigatureSubstitutionSubstFormat1,
    LookupTypeSingleSubstFormat1,
    LookupTypeSingleSubstFormat2,
)
from pypdfbox.fontbox.ttf.gsub.lookup_table import LookupTable
from pypdfbox.fontbox.ttf.gsub.script_table import ScriptTable
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from tests.oracle.harness import requires_oracle, run_probe_text

_TTF_DIR = Path(__file__).resolve().parents[5] / "pypdfbox" / "resources" / "ttf"


# ---------------------------------------------------------------------------
# Build the gsub data-class graph from a font's GSUB bytes using pypdfbox's
# own upstream-mirrored byte parser, then drive the ported extractor.
# ---------------------------------------------------------------------------


def _read_gsub_lists(
    table: GlyphSubstitutionTable, raw: bytes
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Parse the GSUB header + the three list blocks from ``raw`` bytes.

    The GSUB header layout (OpenType GSUB §Header) is::

        uint16 majorVersion
        uint16 minorVersion
        Offset16 scriptListOffset      (from table start)
        Offset16 featureListOffset
        Offset16 lookupListOffset
        [Offset32 featureVariationsOffset]   (minorVersion == 1 only)

    Each offset is relative to the start of the GSUB table. We feed each
    one to the matching ``read_*`` parser, which mirrors upstream's SFNT
    decoder byte for byte.
    """
    data = MemoryTTFDataStream(raw)
    data.seek(0)
    data.read_unsigned_short()  # majorVersion
    data.read_unsigned_short()  # minorVersion
    script_list_offset = data.read_unsigned_short()
    feature_list_offset = data.read_unsigned_short()
    lookup_list_offset = data.read_unsigned_short()

    script_list = table.read_script_list(data, script_list_offset)
    feature_list = table.read_feature_list(data, feature_list_offset)
    lookup_list = table.read_lookup_list(data, lookup_list_offset)
    return script_list, feature_list, lookup_list


def _to_script_table(d: dict[str, Any]) -> ScriptTable:
    default_dict = d["default_lang_sys"]
    default_lang_sys = _to_lang_sys(default_dict) if default_dict else None
    lang_sys_tables = {
        tag: _to_lang_sys(ls) for tag, ls in d["lang_sys_tables"].items()
    }
    return ScriptTable(
        default_lang_sys_table=default_lang_sys,
        lang_sys_tables=lang_sys_tables,
    )


def _to_lang_sys(d: dict[str, Any]) -> LangSysTable:
    return LangSysTable(
        lookup_order=d["lookup_order"],
        required_feature_index=d["required_feature_index"],
        feature_indices=tuple(d["feature_indices"]),
    )


def _to_feature_records(d: dict[str, Any]) -> list[FeatureRecord]:
    records: list[FeatureRecord] = []
    for tag, ft in d["feature_records"]:
        feature_table = FeatureTable(
            feature_params=ft["feature_params"],
            lookup_list_indices=tuple(ft["lookup_list_indices"]),
        )
        records.append(
            FeatureRecord(feature_tag=tag, feature_table=feature_table)
        )
    return records


def _to_lookup_tables(d: dict[str, Any]) -> list[LookupTable]:
    return [_to_lookup_table(lt) for lt in d["lookup_tables"]]


def _to_lookup_table(d: dict[str, Any]) -> LookupTable:
    sub_tables = tuple(
        st for st in (_to_subtable(s, d["lookup_type"]) for s in d["sub_tables"])
        if st is not None
    )
    return LookupTable(
        lookup_type=d["lookup_type"],
        lookup_flag=d["lookup_flag"],
        mark_filtering_set=d["mark_filtering_set"],
        sub_tables=sub_tables,
    )


def _to_subtable(s: dict[str, Any] | None, lookup_type: int) -> Any:
    """Convert one parsed-subtable dict into its gsub data class.

    Mirrors the dispatch the byte parser would feed the extractor:
    Type 1 -> SingleSubstFormat1/2, Type 3 -> AlternateSubstitutionFormat1,
    Type 4 -> LigatureSubstitutionSubstFormat1. Type 2 (multiple) and the
    contextual types are not collapsible into the flat map and the
    extractor ignores them, so we skip them here too.
    """
    if s is None:
        return None
    if lookup_type == 1:
        coverage = tuple(s["coverage_table"].get_glyph_array())
        if s["subst_format"] == 1:
            return LookupTypeSingleSubstFormat1(
                delta_glyph_id=s["delta_glyph_id"],
                coverage_table=coverage,
            )
        return LookupTypeSingleSubstFormat2(
            substitute_glyph_ids=tuple(s["substitute_glyph_ids"]),
            coverage_table=coverage,
        )
    if lookup_type == 3:
        coverage = tuple(s["coverage_table"].get_glyph_array())
        alt_sets = tuple(
            AlternateSetTable(
                alternate_glyph_ids=tuple(a["alternate_glyph_ids"]),
            )
            for a in s["alternate_set_tables"]
        )
        return LookupTypeAlternateSubstitutionFormat1(
            coverage_table=coverage,
            alternate_set_tables=alt_sets,
        )
    if lookup_type == 4:
        coverage = tuple(s["coverage_table"].get_glyph_array())
        lig_sets = tuple(
            LigatureSetTable(
                ligature_tables=tuple(
                    LigatureTable(
                        ligature_glyph=lig["ligature_glyph"],
                        # ``read_ligature_table`` already injects the
                        # coverage glyph as component[0], so the full
                        # component list (first + trailing) is the
                        # substitution key the extractor records — keep
                        # it intact, matching upstream FontBox where
                        # ``getComponentGlyphIDs()`` returns the whole
                        # run including the implicit first component.
                        component_glyph_ids=tuple(
                            lig["component_glyph_ids"]
                        ),
                    )
                    for lig in lst["ligature_tables"]
                )
            )
            for lst in s["ligature_set_tables"]
        )
        return LookupTypeLigatureSubstitutionSubstFormat1(
            coverage_table=coverage,
            ligature_set_tables=lig_sets,
        )
    return None


def _py_gsub_lines(ttf_path: Path, script_tag: str) -> str:
    """Reconstruct ``GsubSubstitutionProbe`` output from pypdfbox.

    Parse the GSUB bytes with pypdfbox's own byte parser, build the gsub
    data-class graph, run the ported ``GlyphSubstitutionDataExtractor``,
    and serialise the resulting ``MapBackedGsubData`` exactly as the Java
    probe serialises Apache FontBox's ``GsubData``.
    """
    ttf = TrueTypeFont.from_bytes(ttf_path.read_bytes())
    try:
        raw = ttf.get_table_bytes("GSUB")
        assert raw is not None, f"no GSUB table in {ttf_path.name}"
    finally:
        ttf.close()

    table = GlyphSubstitutionTable()
    script_list_d, feature_list_d, lookup_list_d = _read_gsub_lists(table, raw)

    script_d = script_list_d.get(script_tag)
    extractor = GlyphSubstitutionDataExtractor()

    lines: list[str] = []
    if script_d is None:
        lines.append("SCRIPT\tNO_DATA\t-")
        return "\n".join(lines) + "\n"

    script_table = _to_script_table(script_d)
    feature_records = _to_feature_records(feature_list_d)
    lookup_tables = _to_lookup_tables(lookup_list_d)

    data = extractor.get_gsub_data_for_script(
        script_tag, script_table, feature_records, lookup_tables
    )

    lines.append(
        f"SCRIPT\t{data.get_active_script_name()}\t{data.get_language().name}"
    )
    for feature_tag in sorted(data.get_supported_features()):
        feature = data.get_feature(feature_tag)
        runs = feature.get_all_glyph_ids_for_substitution()
        lines.append(f"FEATURE\t{feature_tag}\t{len(runs)}")
        for run in sorted(runs):
            sub = feature.get_replacement_for_glyphs(list(run))
            run_str = ",".join(str(g) for g in run)
            lines.append(f"SUB\t{feature_tag}\t{run_str}\t{sub}")
    return "\n".join(lines) + "\n"


def _assert_parity(java: str, py: str, label: str) -> None:
    j = java.splitlines()
    p = py.splitlines()
    assert len(j) == len(p), (
        f"line-count mismatch for {label}: java={len(j)} py={len(p)}\n"
        f"java head: {j[:6]}\npy head:   {p[:6]}"
    )
    diffs = [
        f"  line {i}: java={a!r} py={b!r}"
        for i, (a, b) in enumerate(zip(j, p, strict=True))
        if a != b
    ]
    assert not diffs, f"GSUB parity broken for {label}:\n" + "\n".join(diffs[:40])


@requires_oracle
@pytest.mark.parametrize(
    ("ttf_name", "script_tag"),
    [
        ("DejaVuSans.ttf", "latn"),
        ("LiberationSans-Regular.ttf", "latn"),
        ("LiberationSerif-Regular.ttf", "latn"),
    ],
)
def test_gsub_substitution_map_matches_pdfbox(
    ttf_name: str, script_tag: str
) -> None:
    """``GlyphSubstitutionTable.getGsubData(scriptTag)`` -> the
    ``GlyphSubstitutionDataExtractor`` feature-to-substitution map (Type 1
    single, Type 3 alternate, Type 4 ligature) must match Apache PDFBox
    3.0.7 line for line: active script name, language, the supported
    feature-tag set, each feature's run count, and every
    ``glyph_run -> substitute_glyph_id`` pair.
    """
    ttf_path = _TTF_DIR / ttf_name
    assert ttf_path.is_file(), f"missing bundled font: {ttf_path}"
    java = run_probe_text("GsubSubstitutionProbe", str(ttf_path), script_tag)
    py = _py_gsub_lines(ttf_path, script_tag)
    _assert_parity(java, py, f"{ttf_name}:{script_tag}")
