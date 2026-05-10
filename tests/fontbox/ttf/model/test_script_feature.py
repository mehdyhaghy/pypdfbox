"""Hand-written tests for :class:`pypdfbox.fontbox.ttf.model.ScriptFeature`."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.model import ScriptFeature


def test_script_feature_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        ScriptFeature()  # type: ignore[abstract]


def test_script_feature_subclass_must_implement_all_methods() -> None:
    class Partial(ScriptFeature):
        def get_name(self) -> str:
            return "x"

    with pytest.raises(TypeError):
        Partial()  # type: ignore[abstract]
