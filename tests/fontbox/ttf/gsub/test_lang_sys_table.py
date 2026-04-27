from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import LangSysTable


def test_default_construction() -> None:
    ls = LangSysTable()
    assert ls.get_lookup_order() == 0
    assert ls.get_required_feature_index() == 0xFFFF
    assert ls.get_feature_indices() == ()


def test_explicit_required_feature_and_indices() -> None:
    ls = LangSysTable(
        lookup_order=0,
        required_feature_index=4,
        feature_indices=(0, 1, 2),
    )
    assert ls.get_required_feature_index() == 4
    assert ls.get_feature_indices() == (0, 1, 2)


def test_no_required_feature_sentinel() -> None:
    ls = LangSysTable(required_feature_index=0xFFFF)
    # 0xFFFF is the spec sentinel for "no required feature".
    assert ls.get_required_feature_index() == 0xFFFF
