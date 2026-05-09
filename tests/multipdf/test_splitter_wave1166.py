from __future__ import annotations

from tests.multipdf import test_splitter_wave675


def test_wave1166_number_tree_without_kids_returns_none() -> None:
    number_tree = test_splitter_wave675._NumberTree({})

    assert number_tree.get_kids() is None
