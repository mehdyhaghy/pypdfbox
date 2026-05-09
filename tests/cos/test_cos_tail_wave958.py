from __future__ import annotations

from . import test_cos_tail_wave799 as wave799


def test_wave958_slice_contains_minus_only_non_slice_index_uses_str_getitem() -> None:
    value = wave799._SliceContainsMinusOnly("abc")

    assert value[1] == "b"


def test_wave958_post_still_contains_minus_default_count_and_split() -> None:
    value = wave799._PostStillContainsMinus("alpha beta alpha")

    assert value.count("alpha") == 2
    assert value.split() == ["alpha", "beta", "alpha"]

