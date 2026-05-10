"""Upstream-shaped tests for ``FeatureTable``.

There is no standalone ``FeatureTableTest`` upstream — the table is
exercised through ``GsubWorkerForLatinTest`` /
``GlyphSubstitutionDataExtractorTest``. These tests capture the
constructor / accessor invariants those workers depend on, mirroring
the surface of ``org.apache.fontbox.ttf.table.common.FeatureTable``.

Upstream Java reference:
- fontbox/src/main/java/org/apache/fontbox/ttf/table/common/FeatureTable.java
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import FeatureTable


def test_constructor_round_trip() -> None:
    # Java: new FeatureTable(0, 3, new int[]{0, 2, 5})
    ft = FeatureTable(feature_params=0, lookup_list_indices=(0, 2, 5))
    assert ft.get_feature_params() == 0
    assert ft.get_lookup_index_count() == 3
    assert ft.get_lookup_list_indices() == (0, 2, 5)


def test_get_lookup_index_count_zero_for_empty_table() -> None:
    assert FeatureTable().get_lookup_index_count() == 0


def test_to_string_mirrors_java_format() -> None:
    # Java: String.format("FeatureTable[lookupListIndicesCount=%d]",
    #     lookupListIndices.length);
    ft = FeatureTable(lookup_list_indices=(1, 2, 3, 4, 5))
    assert str(ft) == "FeatureTable[lookupListIndicesCount=5]"


def test_to_string_method_equivalent_to_dunder() -> None:
    # Explicit ``to_string`` is the upstream-name-mirroring entry point;
    # ``__str__`` delegates to it.
    ft = FeatureTable(lookup_list_indices=(1, 2, 3, 4, 5))
    assert ft.to_string() == str(ft)
