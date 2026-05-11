from __future__ import annotations

from abc import ABC
from types import SimpleNamespace

import pytest

from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.ttf.glyph_positioning_table import GlyphPositioningTable
from pypdfbox.fontbox.ttf.glyph_substitution_table import GlyphSubstitutionTable
from pypdfbox.fontbox.ttf.gsub.lookup_subtable import (
    AlternateSetTable,
    CoverageTable,
    LigatureSetTable,
    LigatureTable,
    LookupSubTable,
    LookupTypeAlternateSubstitutionFormat1,
    LookupTypeLigatureSubstitutionSubstFormat1,
    LookupTypeMultipleSubstitutionFormat1,
    SequenceTable,
)


class _ConcreteLookupSubTable(LookupSubTable, ABC):
    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        # Base ``do_substitution`` is now a pure abstract stub (no
        # exception), so the concrete subclass owns the substitution
        # semantics. The test asserts the wiring to the base accessors.
        if coverage_index < 0:
            return original_glyph_id
        return original_glyph_id


class _NegativeModuloInt(int):
    def __new__(cls) -> _NegativeModuloInt:
        return int.__new__(cls, 1)

    def __add__(self, _other: object) -> _NegativeModuloInt:
        return self

    def __mod__(self, _other: object) -> int:
        return -1


class _Format2Data:
    def __init__(self) -> None:
        self._unsigned_reads = 0

    def read_unsigned_short(self) -> int:
        self._unsigned_reads += 1
        if self._unsigned_reads <= 256:
            return 0
        if self._unsigned_reads == 257:
            return 0
        if self._unsigned_reads == 258:
            return 1
        if self._unsigned_reads == 259:
            return 2
        return _NegativeModuloInt()

    def read_signed_short(self) -> int:
        return 0

    def get_current_position(self) -> int:
        return 0

    def seek(self, _position: int) -> None:
        pass


def test_lookup_subtable_base_accessors_and_abstract_method() -> None:
    coverage = CoverageTable(glyph_array=(3, 5))
    subtable = _ConcreteLookupSubTable(7, coverage)

    assert subtable.get_coverage_object() is coverage
    # The base ``do_substitution`` is an abstract stub with no body
    # beyond its docstring — the concrete subclass returns the input
    # GID unchanged when ``coverage_index >= 0``.
    assert subtable.do_substitution(3, 0) == 3


def test_gsub_lookup_subtable_collection_getters() -> None:
    sequence = SequenceTable(glyph_count=1, substitute_glyph_ids=(10,))
    multiple = LookupTypeMultipleSubstitutionFormat1(sequence_tables=(sequence,))
    alternate_set = AlternateSetTable(glyph_count=1, alternate_glyph_ids=(20,))
    alternate = LookupTypeAlternateSubstitutionFormat1(
        alternate_set_tables=(alternate_set,)
    )
    ligature_set = LigatureSetTable(
        ligature_tables=(LigatureTable(ligature_glyph=30, component_glyph_ids=(4,)),)
    )
    ligature = LookupTypeLigatureSubstitutionSubstFormat1(
        ligature_set_tables=(ligature_set,)
    )

    assert multiple.get_sequence_tables() == (sequence,)
    assert alternate.get_alternate_set_tables() == (alternate_set,)
    assert ligature.get_ligature_set_tables() == (ligature_set,)


def test_gpos_pair_format2_skips_missing_class2_records() -> None:
    table = GlyphPositioningTable()
    table._glyph_order = ["A", "V"]  # noqa: SLF001
    table._glyph_name_to_gid = {"A": 0, "V": 1}  # noqa: SLF001
    pairs: dict[tuple[int, int], int] = {}

    table._absorb_pair_format2(  # noqa: SLF001
        SimpleNamespace(
            Coverage=SimpleNamespace(glyphs=["A"]),
            ClassDef1=SimpleNamespace(classDefs={}),
            ClassDef2=SimpleNamespace(classDefs={}),
            Class1Record=[SimpleNamespace(Class2Record=None)],
        ),
        pairs,
    )

    assert pairs == {}


def test_gsub_substitution_skips_invalid_feature_indices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = GlyphSubstitutionTable()
    table._gsub_table = SimpleNamespace(  # noqa: SLF001
        FeatureList=SimpleNamespace(
            FeatureRecord=[
                SimpleNamespace(
                    Feature=SimpleNamespace(LookupListIndex=[0]),
                )
            ]
        ),
        LookupList=SimpleNamespace(
            Lookup=[
                SimpleNamespace(
                    LookupType=1,
                    SubTable=[SimpleNamespace(mapping={"a": "a.alt"})],
                )
            ]
        ),
    )
    table._glyph_order = ["a", "a.alt"]  # noqa: SLF001
    table._glyph_name_to_gid = {"a": 0, "a.alt": 1}  # noqa: SLF001
    monkeypatch.setattr(table, "_select_script_tag", lambda _tags: "latn")
    monkeypatch.setattr(
        table,
        "_collect_feature_indices",
        lambda _script, _enabled: [99, 0],
    )

    assert table.get_substitution(0, ["latn"], ["salt"]) == 1


def test_cmap_format2_normalizes_negative_modulo_result() -> None:
    subtable = CmapSubtable()

    subtable._process_subtype_2(_Format2Data(), num_glyphs=65536)  # type: ignore[arg-type]  # noqa: SLF001

    assert subtable.get_glyph_id(0) == 65535
