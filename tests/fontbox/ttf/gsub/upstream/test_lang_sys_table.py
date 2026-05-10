"""Upstream-derived parity tests for ``LangSysTable``.

Upstream has no dedicated ``LangSysTableTest.java``; these tests exercise
the public surface mirrored from
``org.apache.fontbox.ttf.table.common.LangSysTable`` (PDFBox 3.0.x):
constructor, getters, and ``toString`` formatting.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import LangSysTable


def test_constructor_and_getters() -> None:
    ls = LangSysTable(
        lookup_order=0,
        required_feature_index=2,
        feature_indices=(0, 1, 3, 5),
    )
    assert ls.get_lookup_order() == 0
    assert ls.get_required_feature_index() == 2
    assert ls.get_feature_index_count() == 4
    assert ls.get_feature_indices() == (0, 1, 3, 5)


def test_get_feature_index_count_empty() -> None:
    ls = LangSysTable()
    assert ls.get_feature_index_count() == 0


def test_to_string_matches_upstream_format() -> None:
    ls = LangSysTable(required_feature_index=7)
    # Upstream format: "LangSysTable[requiredFeatureIndex=%d]"
    assert ls.to_string() == "LangSysTable[requiredFeatureIndex=7]"
    assert str(ls) == "LangSysTable[requiredFeatureIndex=7]"


def test_to_string_with_no_required_feature() -> None:
    ls = LangSysTable()
    assert ls.to_string() == "LangSysTable[requiredFeatureIndex=65535]"
