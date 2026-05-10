"""Hand-written tests for :class:`MapBackedGsubData`."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.model import Language, MapBackedGsubData, ScriptFeature


def _make() -> MapBackedGsubData:
    return MapBackedGsubData(
        Language.BENGALI,
        "bng2",
        {
            "liga": {(84, 93): 256},
            "ccmp": {(10,): 11},
        },
    )


def test_get_language() -> None:
    assert _make().get_language() is Language.BENGALI


def test_get_active_script_name() -> None:
    assert _make().get_active_script_name() == "bng2"


def test_is_feature_supported() -> None:
    data = _make()
    assert data.is_feature_supported("liga")
    assert data.is_feature_supported("ccmp")
    assert not data.is_feature_supported("kern")


def test_get_feature_returns_script_feature() -> None:
    data = _make()
    feature = data.get_feature("liga")
    assert isinstance(feature, ScriptFeature)
    assert feature.get_name() == "liga"
    assert feature.get_all_glyph_ids_for_substitution() == {(84, 93)}


def test_get_feature_raises_for_unknown_feature() -> None:
    data = _make()
    with pytest.raises(NotImplementedError):
        data.get_feature("aalt")


def test_get_supported_features() -> None:
    assert _make().get_supported_features() == {"liga", "ccmp"}
