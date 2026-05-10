"""Behavior-parity tests for ``PDShadingType4``.

Apache PDFBox does not ship a dedicated ``PDShadingType4Test``; these tests
cover the public surface of upstream
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PDShadingType4.java``
end-to-end. The lite-surface ``to_paint`` / ``collect_triangles`` hooks
defer mesh rendering to the rendering cluster — assertions here pin the
documented fallback contracts.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSStream
from pypdfbox.pdmodel.graphics.shading import PDShadingType4
from pypdfbox.pdmodel.graphics.shading.pd_shading import PDShading


def _shading_with_full_decode(
    *, bits_per_flag: int = 2, components: int = 1
) -> PDShadingType4:
    shading = PDShadingType4()
    shading.set_bits_per_coordinate(8)
    shading.set_bits_per_component(8)
    shading.set_bits_per_flag(bits_per_flag)
    decode = COSArray()
    # x range, y range
    decode.add(COSFloat(0.0))
    decode.add(COSFloat(1.0))
    decode.add(COSFloat(0.0))
    decode.add(COSFloat(1.0))
    # color ranges
    for _ in range(components):
        decode.add(COSFloat(0.0))
        decode.add(COSFloat(1.0))
    shading.set_decode(decode)
    return shading


def test_get_shading_type_is_four():
    # Upstream PDShadingType4.getShadingType (line 58) returns SHADING_TYPE4.
    assert PDShadingType4().get_shading_type() == PDShading.SHADING_TYPE4


def test_default_backing_object_is_a_stream():
    # Upstream constructor takes a COSDictionary, but PDShadingType4
    # encodes mesh data in a stream body. The default-constructed instance
    # must be backed by a COSStream so /BitsPerFlag + mesh data live
    # together.
    assert isinstance(PDShadingType4().get_cos_object(), COSStream)


def test_bits_per_flag_default_is_unset():
    # Upstream getBitsPerFlag (line 69) returns -1 when /BitsPerFlag is
    # absent; pypdfbox uses get_int's project-wide default (also -1).
    assert PDShadingType4().get_bits_per_flag() == -1


def test_bits_per_flag_round_trip():
    shading = PDShadingType4()
    shading.set_bits_per_flag(2)
    assert shading.get_bits_per_flag() == 2
    assert shading.get_cos_object().get_int("BitsPerFlag") == 2


@pytest.mark.parametrize("bits", [2, 4, 8])
def test_bits_per_flag_accepts_spec_values(bits):
    # PDF 32000-1 §8.7.4.5.5 allows BitsPerFlag of 2, 4, or 8. Upstream
    # only masks the low two bits but stores whatever value we set.
    shading = PDShadingType4()
    shading.set_bits_per_flag(bits)
    assert shading.get_bits_per_flag() == bits


def test_to_paint_returns_none_lite_surface():
    # Lite-surface stub for upstream PDShadingType4.toPaint (line 86).
    shading = PDShadingType4()
    assert shading.to_paint() is None
    assert shading.to_paint(matrix=object()) is None


def test_collect_triangles_returns_empty_when_decode_missing():
    # Upstream collectTriangles (line 92) returns Collections.emptyList()
    # when /Decode lacks the x/y ranges (lines 101-108).
    shading = PDShadingType4()
    shading.set_bits_per_flag(2)
    assert shading.collect_triangles() == []


def test_collect_triangles_returns_empty_when_x_range_degenerate():
    # Upstream returns an empty list when the x range is degenerate
    # (rangeX.getMin() == rangeX.getMax(), line 104).
    shading = _shading_with_full_decode()
    decode = COSArray()
    for value in (1.0, 1.0, 0.0, 1.0, 0.0, 1.0):
        decode.add(COSFloat(value))
    shading.set_decode(decode)
    assert shading.collect_triangles() == []


def test_collect_triangles_returns_empty_when_y_range_degenerate():
    shading = _shading_with_full_decode()
    decode = COSArray()
    for value in (0.0, 1.0, 0.5, 0.5, 0.0, 1.0):
        decode.add(COSFloat(value))
    shading.set_decode(decode)
    assert shading.collect_triangles() == []


def test_collect_triangles_raises_when_color_decode_missing():
    # Upstream throws IOException("Range missing in shading /Decode entry")
    # at line 115 when a color-component decode range is absent. We map
    # IOException to OSError per project convention. /Function pins the
    # number of color components to 1 (PDTriangleBasedShadingType
    # getNumberOfColorComponents) so the loop iterates and discovers the
    # missing range.
    from pypdfbox.cos import COSDictionary

    shading = PDShadingType4()
    shading.set_bits_per_flag(2)
    fn = COSDictionary()
    fn.set_int("FunctionType", 2)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    fn.set_item("Domain", domain)
    c0 = COSArray()
    c0.add(COSFloat(0.0))
    fn.set_item("C0", c0)
    c1 = COSArray()
    c1.add(COSFloat(1.0))
    fn.set_item("C1", c1)
    fn.set_int("N", 1)
    shading.set_function(fn)
    decode = COSArray()
    # Only the x/y ranges — color range omitted.
    for value in (0.0, 1.0, 0.0, 1.0):
        decode.add(COSFloat(value))
    shading.set_decode(decode)
    with pytest.raises(OSError):
        shading.collect_triangles()
