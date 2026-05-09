from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pypdfbox.fontbox.ttf import GlyphPositioningTable


class _FakeTTFont:
    def __init__(self, gpos_table: Any, glyph_order: list[str]) -> None:
        self.gpos_table = gpos_table
        self.glyph_order = glyph_order

    def __getitem__(self, key: str) -> Any:
        assert key == "GPOS"
        return SimpleNamespace(table=self.gpos_table)

    def getGlyphOrder(self) -> list[str]:  # noqa: N802 - fontTools API spelling
        return self.glyph_order


def test_wave528_populate_deduplicates_scripts_and_strips_features() -> None:
    gpos_table = SimpleNamespace(
        ScriptList=SimpleNamespace(
            ScriptRecord=[
                SimpleNamespace(ScriptTag="latn"),
                SimpleNamespace(ScriptTag="latn"),
                SimpleNamespace(ScriptTag="DFLT"),
            ]
        ),
        FeatureList=SimpleNamespace(
            FeatureRecord=[
                SimpleNamespace(FeatureTag=" kern "),
                SimpleNamespace(FeatureTag="mark"),
                SimpleNamespace(FeatureTag="kern"),
            ]
        ),
        LookupList=SimpleNamespace(Lookup=[]),
    )
    table = GlyphPositioningTable()

    table.populate_from_fonttools(_FakeTTFont(gpos_table, [".notdef", "A"]))

    assert table.get_initialized() is True
    assert table.get_raw_table() is gpos_table
    assert table.get_supported_script_tags() == {"latn", "DFLT"}
    assert table.get_supported_feature_tags() == ["kern", "mark"]


def test_wave528_empty_structures_return_empty_inventory() -> None:
    gpos_table = SimpleNamespace(
        ScriptList=None,
        FeatureList=None,
        LookupList=None,
    )
    table = GlyphPositioningTable()

    table.populate_from_fonttools(_FakeTTFont(gpos_table, [".notdef"]))

    assert table.get_supported_script_tags() == set()
    assert table.get_supported_feature_tags() == []
    assert table.get_lookup_count() == 0
    assert table.get_lookup_types() == []
    assert table.get_script_list() is None
    assert table.get_feature_list() is None
    assert table.get_lookup_list() is None


def test_wave528_lookup_indices_skip_missing_features_and_deduplicate() -> None:
    table = GlyphPositioningTable()
    table._gpos_table = SimpleNamespace(
        FeatureList=SimpleNamespace(
            FeatureRecord=[
                SimpleNamespace(
                    FeatureTag="kern",
                    Feature=SimpleNamespace(LookupListIndex=[2, 3, 2]),
                ),
                SimpleNamespace(FeatureTag="kern", Feature=None),
                SimpleNamespace(
                    FeatureTag="kern",
                    Feature=SimpleNamespace(LookupListIndex=[3, 4]),
                ),
                SimpleNamespace(
                    FeatureTag="mark",
                    Feature=SimpleNamespace(LookupListIndex=[9]),
                ),
            ]
        )
    )

    assert table.get_lookup_indices_for_feature("kern") == [2, 3, 4]
    assert table.get_lookup_indices_for_feature("mark") == [9]


def test_wave528_pair_format1_ignores_malformed_records_and_last_wins() -> None:
    table = GlyphPositioningTable()
    table._glyph_order = [".notdef", "A", "B", "C"]
    table._glyph_name_to_gid = {
        name: gid for gid, name in enumerate(table._glyph_order)
    }
    table._gpos_table = SimpleNamespace(
        LookupList=SimpleNamespace(
            Lookup=[
                SimpleNamespace(
                    LookupType=GlyphPositioningTable.LOOKUP_TYPE_SINGLE_ADJUSTMENT,
                    SubTable=[],
                ),
                SimpleNamespace(
                    LookupType=GlyphPositioningTable.LOOKUP_TYPE_PAIR_ADJUSTMENT,
                    SubTable=[
                        SimpleNamespace(Format=99),
                        SimpleNamespace(Format=1, Coverage=None, PairSet=[]),
                        SimpleNamespace(
                            Format=1,
                            Coverage=SimpleNamespace(glyphs=["A", "Missing", "A"]),
                            PairSet=[
                                SimpleNamespace(
                                    PairValueRecord=[
                                        SimpleNamespace(
                                            SecondGlyph="B",
                                            Value1=SimpleNamespace(XAdvance=-10),
                                        ),
                                        SimpleNamespace(SecondGlyph="C", Value1=None),
                                        SimpleNamespace(SecondGlyph="Missing"),
                                    ]
                                ),
                                SimpleNamespace(
                                    PairValueRecord=[
                                        SimpleNamespace(
                                            SecondGlyph="B",
                                            Value1=SimpleNamespace(XAdvance=-50),
                                        )
                                    ]
                                ),
                                SimpleNamespace(
                                    PairValueRecord=[
                                        SimpleNamespace(
                                            SecondGlyph="B",
                                            Value1=SimpleNamespace(XAdvance=-99),
                                        )
                                    ]
                                ),
                            ],
                        ),
                    ],
                ),
            ]
        )
    )

    assert table.get_kerning(1, 2) == -99
    assert table.get_kerning(1, 3) == 0
    assert table.has_kerning() is True


def test_wave528_pair_format2_ignores_missing_and_out_of_range_classes() -> None:
    table = GlyphPositioningTable()
    table._glyph_order = [".notdef", "A", "B", "C", "D"]
    table._glyph_name_to_gid = {
        name: gid for gid, name in enumerate(table._glyph_order)
    }
    table._gpos_table = SimpleNamespace(
        LookupList=SimpleNamespace(
            Lookup=[
                SimpleNamespace(
                    LookupType=GlyphPositioningTable.LOOKUP_TYPE_PAIR_ADJUSTMENT,
                    SubTable=[
                        SimpleNamespace(Format=2, Coverage=None),
                        SimpleNamespace(
                            Format=2,
                            Coverage=SimpleNamespace(glyphs=["A", "C", "Missing"]),
                            ClassDef1=SimpleNamespace(classDefs={"C": 5}),
                            ClassDef2=SimpleNamespace(classDefs={"D": 1}),
                            Class1Record=[
                                SimpleNamespace(
                                    Class2Record=[
                                        SimpleNamespace(
                                            Value1=SimpleNamespace(XAdvance=-20)
                                        ),
                                        SimpleNamespace(
                                            Value1=SimpleNamespace(XAdvance=-40)
                                        ),
                                    ]
                                )
                            ],
                        ),
                    ],
                )
            ]
        )
    )

    assert table.get_kerning(1, 2) == -20
    assert table.get_kerning(1, 4) == -40
    assert table.get_kerning(3, 2) == 0
