from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pypdfbox.fontbox.ttf.glyph_data import BoundingBox, GlyphData, GlyphDescription
from pypdfbox.fontbox.ttf.glyph_positioning_table import GlyphPositioningTable
from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable


class _FakeTTFont:
    def __init__(self, table: Any, glyph_order: list[str]) -> None:
        self._table = table
        self._glyph_order = glyph_order

    def __getitem__(self, key: str) -> Any:
        assert key in {"GSUB", "GPOS"}
        return SimpleNamespace(table=self._table)

    def getGlyphOrder(self) -> list[str]:
        return self._glyph_order


def _lang_sys(feature_indices: list[int], required: int = 0xFFFF) -> Any:
    return SimpleNamespace(ReqFeatureIndex=required, FeatureIndex=feature_indices)


def _script_record(
    tag: str,
    default_lang_sys: Any,
    lang_systems: list[Any] | None = None,
) -> Any:
    return SimpleNamespace(
        ScriptTag=tag,
        Script=SimpleNamespace(
            DefaultLangSys=default_lang_sys,
            LangSysRecord=[
                SimpleNamespace(LangSys=lang_sys) for lang_sys in (lang_systems or [])
            ],
        ),
    )


def _feature_record(tag: str, lookup_indices: list[int], feature: Any | None = None) -> Any:
    return SimpleNamespace(
        FeatureTag=tag,
        Feature=feature
        if feature is not None
        else SimpleNamespace(LookupListIndex=lookup_indices),
    )


def _gsub_table(scripts: list[Any], features: list[Any], lookups: list[Any]) -> Any:
    return SimpleNamespace(
        ScriptList=SimpleNamespace(ScriptRecord=scripts),
        FeatureList=SimpleNamespace(FeatureRecord=features),
        LookupList=SimpleNamespace(Lookup=lookups),
    )


def test_gsub_lookup_indices_missing_feature_list_and_none_feature_record() -> None:
    table = GlyphSubstitutionTable()
    table._gsub_table = SimpleNamespace(FeatureList=None)
    assert table.get_lookup_indices_for_feature("liga") == []

    table._gsub_table = SimpleNamespace(
        FeatureList=SimpleNamespace(
            FeatureRecord=[
                SimpleNamespace(FeatureTag="liga", Feature=None),
                _feature_record("liga", [2]),
            ]
        )
    )
    assert table.get_lookup_indices_for_feature("liga") == [2]


def test_gsub_selection_and_feature_collection_empty_edges() -> None:
    table = GlyphSubstitutionTable()

    assert table._select_script_tag(()) is None
    assert table._select_script_tag(("DFLT",)) == "DFLT"
    assert table._collect_feature_indices(None, None) == []

    table._script_tags = ["latn"]
    table._last_used_supported_script = "latn"
    assert table._select_script_tag(()) == "latn"


def test_gsub_collects_none_langsys_and_skips_invalid_feature_indices() -> None:
    raw = _gsub_table(
        [_script_record("latn", None, [_lang_sys([99, 0])])],
        [_feature_record("sups", [0])],
        [
            SimpleNamespace(
                LookupType=1,
                SubTable=[SimpleNamespace(mapping={}), SimpleNamespace(mapping={"a": "a.sups"})],
            )
        ],
    )
    table = GlyphSubstitutionTable()
    table.populate_from_fonttools(_FakeTTFont(raw, ["a", "a.sups"]))

    assert table.get_substitution(0, ["latn"], ["sups"]) == 1


def test_gpos_has_kerning_builds_empty_cache_when_lookup_list_absent() -> None:
    table = GlyphPositioningTable()
    table._gpos_table = SimpleNamespace(LookupList=None)

    assert table.has_kerning() is False
    assert table._kerning_pairs == {}


def test_gpos_pair_format1_ignores_records_without_second_glyph() -> None:
    table = GlyphPositioningTable()
    table._glyph_name_to_gid = {"A": 1, "V": 2}
    pairs: dict[tuple[int, int], int] = {}
    sub = SimpleNamespace(
        Coverage=SimpleNamespace(glyphs=["A"]),
        PairSet=[
            SimpleNamespace(
                PairValueRecord=[
                    SimpleNamespace(SecondGlyph=None, Value1=SimpleNamespace(XAdvance=-10)),
                    SimpleNamespace(SecondGlyph="V", Value1=SimpleNamespace(XAdvance=-20)),
                ]
            )
        ],
    )

    table._absorb_pair_format1(sub, pairs)

    assert pairs == {(1, 2): -20}


def test_gpos_pair_format2_ignores_missing_and_zero_class_records() -> None:
    table = GlyphPositioningTable()
    table._glyph_order = [".notdef", "A", "V", "missing"]
    table._glyph_name_to_gid = {"A": 1, "V": 2}

    missing_class_pairs: dict[tuple[int, int], int] = {}
    table._absorb_pair_format2(
        SimpleNamespace(
            Coverage=SimpleNamespace(glyphs=["A"]),
            ClassDef1=SimpleNamespace(classDefs={}),
            ClassDef2=SimpleNamespace(classDefs={}),
            Class1Record=None,
        ),
        missing_class_pairs,
    )
    assert missing_class_pairs == {}

    pairs: dict[tuple[int, int], int] = {}
    table._absorb_pair_format2(
        SimpleNamespace(
            Coverage=SimpleNamespace(glyphs=["A"]),
            ClassDef1=SimpleNamespace(classDefs={}),
            ClassDef2=SimpleNamespace(classDefs={"V": 1, "missing": 1}),
            Class1Record=[
                SimpleNamespace(
                    Class2Record=[
                        SimpleNamespace(Value1=SimpleNamespace(XAdvance=0)),
                        SimpleNamespace(Value1=SimpleNamespace(XAdvance=-30)),
                    ]
                )
            ],
        ),
        pairs,
    )

    assert pairs == {(1, 2): -30}


class _CompositeGlyph:
    numberOfContours = -1

    def isComposite(self) -> bool:  # noqa: N802 - fontTools API
        return True

    def getCoordinates(self, _glyf_table: Any) -> tuple[list[tuple[int, int]], list[int], bytes]:
        return [(0, 0), (10, 0), (10, 10), (20, 20)], [1, 3], bytes([1, 1, 1, 1])


class _NoOutlineGlyph:
    numberOfContours = 0


class _GlyfTable:
    def __init__(self, glyph: Any) -> None:
        self._glyph = glyph

    def __getitem__(self, _name: str) -> Any:
        return self._glyph


def test_glyph_description_composite_contour_count_uses_resolved_endpoints() -> None:
    desc = GlyphDescription(_GlyfTable(_CompositeGlyph()), _CompositeGlyph())

    assert desc.is_composite() is True
    assert desc.get_contour_count() == 2
    assert desc.get_point_count() == 4


def test_glyph_data_no_outline_initialises_empty_bbox() -> None:
    glyph = GlyphData(_GlyfTable(_NoOutlineGlyph()), "space")

    assert glyph.get_bounding_box().as_tuple() == (0.0, 0.0, 0.0, 0.0)
    assert glyph.get_number_of_contours() == 0


def test_bounding_box_repr_is_explicit() -> None:
    assert repr(BoundingBox(1, 2, 3, 4)) == "BoundingBox(1.0, 2.0, 3.0, 4.0)"
