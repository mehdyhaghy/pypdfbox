from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.multipdf import Splitter
from tests.multipdf import test_splitter_wave624 as wave624


def test_wave1167_exercises_wave624_page_tree_drop_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def force_page_tree_lookup(
        _self: Splitter,
        _src: object,
        _dst_parent: object,
        _current_page_dict: object,
        page_tree: Any,
    ) -> None:
        assert page_tree.index_of(COSDictionary()) == -1
        return None

    monkeypatch.setattr(Splitter, "_k_create_clone", force_page_tree_lookup)

    wave624.test_wave624_k_clone_array_returns_none_when_all_children_are_dropped()
