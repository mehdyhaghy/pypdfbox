"""PDFBOX-6333 regression (wave 1615): an odd-length ``/Decode`` never
overruns in ``get_decode_for_parameter``; the trailing half-pair is ``None``.
"""

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSStream
from pypdfbox.pdmodel.graphics.shading import (
    PDShadingType4,
    PDShadingType5,
    PDShadingType6,
    PDShadingType7,
)
from pypdfbox.pdmodel.graphics.shading.pd_triangle_based_shading_type import (
    PDTriangleBasedShadingType,
)


def _decode(values: list[float]) -> COSArray:
    arr = COSArray()
    arr.set_float_array(values)
    return arr


@pytest.mark.parametrize(
    "cls",
    [PDShadingType4, PDShadingType5, PDShadingType6, PDShadingType7],
    ids=["type4", "type5", "type6", "type7"],
)
def test_odd_length_decode_last_pair_is_none(cls) -> None:
    stream = COSStream()
    stream.set_item("Decode", _decode([0.0, 1.0, 0.0, 1.0, 0.0]))
    shading = cls(stream)
    assert shading.get_decode_for_parameter(0) == (0.0, 1.0)
    assert shading.get_decode_for_parameter(1) == (0.0, 1.0)
    assert shading.get_decode_for_parameter(2) is None


def test_base_class_odd_length_decode_last_pair_is_none() -> None:
    d = COSDictionary()
    d.set_item("Decode", _decode([0.0, 1.0, 0.5]))
    shading = PDTriangleBasedShadingType(d)
    assert shading.get_decode_for_parameter(0) == (0.0, 1.0)
    assert shading.get_decode_for_parameter(1) is None
