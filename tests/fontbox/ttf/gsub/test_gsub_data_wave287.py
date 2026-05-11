from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.gsub import GsubData


def test_no_data_found_is_typed_class_sentinel() -> None:
    sentinel: GsubData = GsubData.NO_DATA_FOUND

    with pytest.raises(TypeError):
        sentinel.get_language()
    with pytest.raises(TypeError):
        sentinel.get_supported_features()


def test_supported_features_returns_mutable_copy() -> None:
    data = GsubData(feature_list={"liga": {}, "salt": {}})

    supported = data.get_supported_features()
    supported.clear()

    assert data.get_supported_features() == {"liga", "salt"}
