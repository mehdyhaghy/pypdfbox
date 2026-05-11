"""Wave 1275 parity tests for to_paint hooks on PDShading + Types 1/2.

Updated in Wave 1284 to exercise the now-implemented paint adapters.
"""

from __future__ import annotations

from pypdfbox.pdmodel.graphics.shading.axial_shading_paint import AxialShadingPaint
from pypdfbox.pdmodel.graphics.shading.pd_shading_type1 import PDShadingType1
from pypdfbox.pdmodel.graphics.shading.pd_shading_type2 import PDShadingType2
from pypdfbox.pdmodel.graphics.shading.type1_shading_paint import Type1ShadingPaint


def test_pd_shading_type1_to_paint_returns_type1_paint() -> None:
    shading = PDShadingType1()
    paint = shading.to_paint()
    assert isinstance(paint, Type1ShadingPaint)
    assert paint.get_shading() is shading


def test_pd_shading_type2_to_paint_returns_axial_paint() -> None:
    shading = PDShadingType2()
    paint = shading.to_paint(matrix=None)
    assert isinstance(paint, AxialShadingPaint)
    assert paint.get_shading() is shading
    assert paint.get_matrix() is None
