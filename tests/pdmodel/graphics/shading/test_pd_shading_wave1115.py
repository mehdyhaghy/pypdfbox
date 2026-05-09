from __future__ import annotations

from pypdfbox.pdmodel.graphics.shading import PDShading
from tests.pdmodel.graphics.shading.test_pd_shading_wave424 import _ConcreteShading


def test_wave1115_concrete_shading_helper_returns_stored_shading_type() -> None:
    shading = _ConcreteShading(shading_type=PDShading.SHADING_TYPE7)

    assert shading.get_shading_type() == PDShading.SHADING_TYPE7
