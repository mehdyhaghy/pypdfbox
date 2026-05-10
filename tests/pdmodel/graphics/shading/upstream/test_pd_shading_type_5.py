"""Behavior-parity tests for ``PDShadingType5``.

Apache PDFBox does not ship a dedicated ``PDShadingType5Test``; these tests
cover the public surface of upstream
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PDShadingType5.java``
end-to-end. The lite-surface ``to_paint`` / ``collect_triangles`` /
``create_shaded_triangle_list`` hooks defer mesh rendering to the rendering
cluster — assertions here pin the documented fallback contracts.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSStream
from pypdfbox.pdmodel.graphics.shading import PDShadingType5
from pypdfbox.pdmodel.graphics.shading.pd_shading import PDShading


def _shading_with_full_decode(
    *, vertices_per_row: int = 3, components: int = 1
) -> PDShadingType5:
    shading = PDShadingType5()
    shading.set_bits_per_coordinate(8)
    shading.set_bits_per_component(8)
    shading.set_vertices_per_row(vertices_per_row)
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


def test_get_shading_type_is_five():
    # Upstream PDShadingType5.getShadingType (line 54) returns SHADING_TYPE5.
    assert PDShadingType5().get_shading_type() == PDShading.SHADING_TYPE5


def test_default_backing_object_is_a_stream():
    # Upstream constructor takes a COSDictionary, but PDShadingType5
    # encodes mesh data in a stream body. The default-constructed instance
    # must be backed by a COSStream so /VerticesPerRow + mesh data live
    # together.
    assert isinstance(PDShadingType5().get_cos_object(), COSStream)


def test_vertices_per_row_default_is_unset():
    # Upstream getVerticesPerRow (line 65) returns -1 when the entry is
    # absent; pypdfbox uses get_int's project-wide default (also -1).
    assert PDShadingType5().get_vertices_per_row() == -1


def test_vertices_per_row_round_trip():
    shading = PDShadingType5()
    shading.set_vertices_per_row(5)
    assert shading.get_vertices_per_row() == 5
    assert shading.get_cos_object().get_int("VerticesPerRow") == 5


def test_to_paint_returns_none_lite_surface():
    # Lite-surface stub for upstream PDShadingType5.toPaint (line 81).
    shading = PDShadingType5()
    assert shading.to_paint() is None
    assert shading.to_paint(matrix=object()) is None


def test_collect_triangles_returns_empty_when_decode_missing():
    # Upstream collectTriangles (line 88) returns Collections.emptyList()
    # when /Decode lacks the x/y ranges (lines 97-102).
    shading = PDShadingType5()
    shading.set_vertices_per_row(3)
    assert shading.collect_triangles() == []


def test_collect_triangles_returns_empty_when_x_range_degenerate():
    # Upstream returns an empty list when the x range is degenerate
    # (rangeX.getMin() == rangeX.getMax(), line 99).
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


def test_collect_triangles_returns_empty_when_vertices_per_row_too_small():
    # Upstream returns an empty list when fewer than two rows of vertices
    # are present (lines 140-144). With vertices_per_row < 2 the lattice
    # is degenerate before we even decode the stream.
    shading = _shading_with_full_decode(vertices_per_row=1)
    assert shading.collect_triangles() == []


def test_collect_triangles_raises_when_color_decode_missing():
    # Upstream throws IOException("Range missing in shading /Decode entry")
    # at line 110 when a color-component decode range is absent. We map
    # IOException to OSError per project convention. /Function pins the
    # number of color components to 1 (PDTriangleBasedShadingType
    # getNumberOfColorComponents, line 122) so the loop iterates and
    # discovers the missing range.
    from pypdfbox.cos import COSDictionary

    shading = PDShadingType5()
    shading.set_vertices_per_row(3)
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


def test_create_shaded_triangle_list_emits_two_triangles_per_cell():
    # Upstream createShadedTriangleList (line 157) emits two triangles
    # per lattice cell: (v1, v2, v3) and (v2, v3, v4). For a 2x2 lattice
    # that means exactly two triangles.
    p = lambda x, y: (x, y)  # noqa: E731
    c = (1.0,)
    lattice = [
        [(p(0, 0), c), (p(1, 0), c)],
        [(p(0, 1), c), (p(1, 1), c)],
    ]
    triangles = PDShadingType5().create_shaded_triangle_list(2, 2, lattice)
    assert len(triangles) == 2
    # First triangle is (v1, v2, v3); second is (v2, v3, v4).
    (pts1, _), (pts2, _) = triangles
    assert pts1 == ((0, 0), (1, 0), (0, 1))
    assert pts2 == ((1, 0), (0, 1), (1, 1))


def test_create_shaded_triangle_list_count_matches_upstream_formula():
    # Upstream allocates (rowNum - 1) * (numPerRow - 1) cells (line 161),
    # each contributing two triangles.
    row_num, num_per_row = 4, 5
    p = lambda x, y: (x, y)  # noqa: E731
    c = (0.5,)
    lattice = [
        [(p(j, i), c) for j in range(num_per_row)] for i in range(row_num)
    ]
    triangles = PDShadingType5().create_shaded_triangle_list(
        row_num, num_per_row, lattice
    )
    assert len(triangles) == 2 * (row_num - 1) * (num_per_row - 1)


def test_create_shaded_triangle_list_empty_for_degenerate_lattice():
    # A 1x1 (or generally <2x2) lattice cannot form any triangle.
    assert PDShadingType5().create_shaded_triangle_list(1, 5, []) == []
    assert PDShadingType5().create_shaded_triangle_list(5, 1, []) == []
