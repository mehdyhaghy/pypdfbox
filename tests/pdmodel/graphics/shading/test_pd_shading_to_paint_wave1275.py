"""Wave 1275 parity tests for to_paint hooks on PDShading + Types 1/2."""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.shading.pd_shading import PDShading
from pypdfbox.pdmodel.graphics.shading.pd_shading_type1 import PDShadingType1
from pypdfbox.pdmodel.graphics.shading.pd_shading_type2 import PDShadingType2


def test_pd_shading_to_paint_not_yet_wired() -> None:
    # Base class — abstract via NotImplementedError until the rendering
    # cluster wires through a Paint adapter.
    instance = PDShading.__new__(PDShading)
    with pytest.raises(NotImplementedError):
        instance.to_paint()


def test_pd_shading_type1_to_paint_not_yet_wired() -> None:
    shading = PDShadingType1()
    with pytest.raises(NotImplementedError):
        shading.to_paint()


def test_pd_shading_type2_to_paint_not_yet_wired() -> None:
    shading = PDShadingType2()
    with pytest.raises(NotImplementedError):
        shading.to_paint(matrix=None)
