from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.multipdf import Splitter
from tests.multipdf import test_splitter_wave564 as wave564


def test_wave1168_exercises_wave564_page_tree_keep_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def force_page_tree_lookup(
        _self: Splitter,
        _src: object,
        _dst_parent: object,
        _current_page_dict: object,
        page_tree: Any,
    ) -> None:
        assert page_tree.index_of(COSDictionary()) == 0
        return None

    monkeypatch.setattr(Splitter, "_k_create_clone", force_page_tree_lookup)

    wave564.test_wave564_objr_without_payload_is_dropped()
