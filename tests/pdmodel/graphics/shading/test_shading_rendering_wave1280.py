"""Hand-written tests for the Wave 1280 shading rendering port.

Covers the new low-level rasterisation primitives:

* :class:`IntPoint`, :class:`Vertex`, :class:`Line`, :class:`CubicBezierCurve`,
  :class:`ShadedTriangle`, :class:`Patch`, :class:`CoonsPatch`,
  :class:`TensorPatch`.
* The abstract :class:`ShadingContext` / :class:`ShadingPaint` surface plus
  the type-specific context/paint classes for Types 1, 2, 3 and the
  patch/Gouraud intermediates.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.pdmodel.graphics.shading import (
    AxialShadingContext,
    AxialShadingPaint,
    CoonsPatch,
    CubicBezierCurve,
    GouraudShadingContext,
    IntPoint,
    Line,
    Patch,
    PatchMeshesShadingContext,
    PDMeshBasedShadingType,
    PDTriangleBasedShadingType,
    RadialShadingContext,
    RadialShadingPaint,
    ShadedTriangle,
    ShadingContext,
    ShadingPaint,
    TensorPatch,
    Type1ShadingContext,
    Type1ShadingPaint,
    Type4ShadingPaint,
    Type5ShadingPaint,
    Type6ShadingPaint,
    Type7ShadingPaint,
    Vertex,
)


# ----------------------------------------------------------------------
# IntPoint
# ----------------------------------------------------------------------
def test_int_point_equality_and_hash() -> None:
    a = IntPoint(3, 4)
    b = IntPoint(3, 4)
    c = IntPoint(4, 3)
    assert a == b
    assert hash(a) == hash(b)
    assert a != c
    assert a != (3, 4)


def test_int_point_hash_formula_matches_upstream() -> None:
    assert hash(IntPoint(0, 0)) == 89 * 623
    assert hash(IntPoint(1, 2)) == 89 * 624 + 2


# ----------------------------------------------------------------------
# Vertex
# ----------------------------------------------------------------------
def test_vertex_defensive_copy() -> None:
    color = [0.1, 0.2, 0.3]
    v = Vertex((1.5, 2.5), color)
    color[0] = 99.0
    assert v.point == (1.5, 2.5)
    assert v.color == [0.1, 0.2, 0.3]


def test_vertex_repr_contains_colors() -> None:
    text = repr(Vertex((0.0, 0.0), [0.5, 0.25]))
    assert "0.50" in text
    assert "0.25" in text


# ----------------------------------------------------------------------
# Line
# ----------------------------------------------------------------------
def test_line_horizontal_includes_endpoints() -> None:
    line = Line((0, 0), (3, 0), [0.0], [1.0])
    assert (0, 0) in line.line_points
    assert (3, 0) in line.line_points
    assert (1, 0) in line.line_points


def test_line_color_interpolation_horizontal() -> None:
    line = Line((0, 0), (4, 0), [0.0], [1.0])
    c = line.calc_color((2, 0))
    assert c == [pytest.approx(0.5)]


def test_line_color_when_endpoints_overlap() -> None:
    line = Line((5, 5), (5, 5), [0.7], [0.2])
    assert line.calc_color((5, 5)) == [0.7]


def test_line_vertical_color_interpolation() -> None:
    line = Line((0, 0), (0, 4), [0.0], [1.0])
    c = line.calc_color((0, 1))
    assert c == [pytest.approx(0.25)]


# ----------------------------------------------------------------------
# CubicBezierCurve
# ----------------------------------------------------------------------
def test_cubic_bezier_curve_endpoints_match_control() -> None:
    curve = CubicBezierCurve([(0.0, 0.0), (1.0, 1.0), (2.0, 1.0), (3.0, 0.0)], 2)
    pts = curve.get_cubic_bezier_curve()
    assert curve.get_level() == 2
    assert len(pts) == (1 << 2) + 1
    assert pts[0] == pytest.approx((0.0, 0.0))
    assert pts[-1] == pytest.approx((3.0, 0.0))


def test_cubic_bezier_curve_negative_level_treated_as_zero() -> None:
    curve = CubicBezierCurve([(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (1.0, 0.0)], -2)
    pts = curve.get_cubic_bezier_curve()
    assert len(pts) == 2  # 2^0 + 1


# ----------------------------------------------------------------------
# ShadedTriangle
# ----------------------------------------------------------------------
def test_shaded_triangle_basic_contains_and_color() -> None:
    triangle = ShadedTriangle(
        [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0)],
        [[1.0], [0.0], [0.0]],
    )
    assert triangle.get_deg() == 3
    assert triangle.contains((1.0, 1.0))
    assert not triangle.contains((100.0, 100.0))
    boundary = triangle.get_boundary()
    assert boundary == [0, 10, 0, 10]
    color_at_origin = triangle.calc_color((0.0, 0.0))
    assert color_at_origin[0] == pytest.approx(1.0)


def test_shaded_triangle_degenerate_point() -> None:
    triangle = ShadedTriangle(
        [(1.0, 1.0), (1.0, 1.0), (1.0, 1.0)],
        [[0.0], [1.0], [0.5]],
    )
    assert triangle.get_deg() == 1
    assert triangle.contains((1.0, 1.0))
    assert triangle.calc_color((1.0, 1.0)) == [pytest.approx(0.5)]


def test_shaded_triangle_degenerate_line() -> None:
    triangle = ShadedTriangle(
        [(0.0, 0.0), (4.0, 0.0), (4.0, 0.0)],
        [[0.0], [1.0], [1.0]],
    )
    assert triangle.get_deg() == 2
    assert triangle.get_line() is not None


# ----------------------------------------------------------------------
# Patch / CoonsPatch / TensorPatch
# ----------------------------------------------------------------------
def _make_square_coons() -> CoonsPatch:
    pts = [
        (0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0),
        (3.0, 1.0), (3.0, 2.0), (3.0, 3.0),
        (2.0, 3.0), (1.0, 3.0), (0.0, 3.0),
        (0.0, 2.0), (0.0, 1.0),
    ]
    colors = [[0.0], [1.0], [1.0], [0.0]]
    return CoonsPatch(pts, colors)


def test_coons_patch_constructs_triangles() -> None:
    patch = _make_square_coons()
    assert patch.list_of_triangles, "expected at least one triangle"
    assert len(patch.control_points) == 4
    assert all(len(row) == 4 for row in patch.control_points)


def test_coons_patch_implicit_edges_and_colors() -> None:
    patch = _make_square_coons()
    edge1 = patch.get_flag1_edge()
    edge2 = patch.get_flag2_edge()
    edge3 = patch.get_flag3_edge()
    assert len(edge1) == 4 and len(edge2) == 4 and len(edge3) == 4
    c1 = patch.get_flag1_color()
    assert len(c1) == 2
    assert len(c1[0]) == 1


def test_patch_is_abstract() -> None:
    with pytest.raises(NotImplementedError):
        Patch([[0.0]]).get_flag1_edge()


def test_patch_get_len_and_edge_equation() -> None:
    assert Patch.get_len((0.0, 0.0), (3.0, 4.0)) == pytest.approx(5.0)
    assert Patch.edge_equation_value((1.0, 1.0), (0.0, 0.0), (2.0, 2.0)) == pytest.approx(0.0)


def test_tensor_patch_constructs() -> None:
    pts = [(float(i % 4), float(i // 4)) for i in range(16)]
    colors = [[0.0], [1.0], [0.0], [1.0]]
    tensor = TensorPatch(pts, colors)
    assert len(tensor.control_points) == 4
    assert all(len(row) == 4 for row in tensor.control_points)


# ----------------------------------------------------------------------
# Context / Paint abstract surfaces
# ----------------------------------------------------------------------
class _FakeShading:
    def __init__(self) -> None:
        self._function = None

    def get_color_space(self) -> object:
        return None  # convert_to_rgb handles None

    def get_background(self) -> object:
        return None

    def get_function(self) -> object:
        return self._function

    def eval_function(self, values: object) -> list[float]:  # pragma: no cover
        return [0.0, 0.0, 0.0]


def test_shading_context_convert_to_rgb_packs_bytes() -> None:
    ctx = ShadingContext(_FakeShading(), color_model=None, xform=None, matrix=None)
    packed = ctx.convert_to_rgb([1.0, 0.5, 0.0])
    r = packed & 0xFF
    g = (packed >> 8) & 0xFF
    b = (packed >> 16) & 0xFF
    assert r == 255 and g == 127 and b == 0


def test_shading_context_get_raster_not_implemented() -> None:
    ctx = ShadingContext(_FakeShading(), color_model=None, xform=None, matrix=None)
    with pytest.raises(NotImplementedError):
        ctx.get_raster(0, 0, 1, 1)


class _RaisingColorSpace:
    """Colour space whose ``to_rgb`` raises ``NotImplementedError`` — used
    to exercise the fallback branch in :py:meth:`ShadingContext.convert_to_rgb`
    that treats values as raw RGB when conversion is unavailable."""

    def to_rgb(self, _values):
        raise NotImplementedError("stub")


class _FakeShadingWithRaisingCS(_FakeShading):
    def get_color_space(self) -> object:
        return _RaisingColorSpace()


def test_shading_context_convert_to_rgb_falls_back_on_to_rgb_failure() -> None:
    """When the colour space exposes ``to_rgb`` but the call raises
    ``TypeError``/``NotImplementedError``, ``convert_to_rgb`` falls back to
    treating the values as already-RGB."""
    ctx = ShadingContext(
        _FakeShadingWithRaisingCS(), color_model=None, xform=None, matrix=None
    )
    packed = ctx.convert_to_rgb([1.0, 0.5, 0.0])
    r = packed & 0xFF
    g = (packed >> 8) & 0xFF
    b = (packed >> 16) & 0xFF
    # Fallback path: values used directly, identical to the colour-space-less
    # path validated in ``test_shading_context_convert_to_rgb_packs_bytes``.
    assert r == 255 and g == 127 and b == 0


def test_shading_paint_holds_shading_and_matrix() -> None:
    shading = _FakeShading()
    paint = ShadingPaint(shading, matrix="m")
    assert paint.get_shading() is shading
    assert paint.get_matrix() == "m"
    assert paint.get_transparency() == 0
    with pytest.raises(NotImplementedError):
        paint.create_context(None, None, None, None)


# ----------------------------------------------------------------------
# Axial / Radial / Type1 paint factories
# ----------------------------------------------------------------------
class _FakeAxialShading(_FakeShading):
    def get_coords(self):
        class _Arr:
            @staticmethod
            def to_float_array():
                return [0.0, 0.0, 10.0, 0.0]
        return _Arr()

    def get_domain(self):
        return None

    def get_extend(self):
        return None

    def eval_function(self, t):
        return [float(t), float(t), float(t)]


def test_axial_shading_context_builds_color_table() -> None:
    ctx = AxialShadingContext(
        _FakeAxialShading(),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    assert ctx.get_domain() == [0.0, 1.0]
    assert ctx.get_extend() == [False, False]
    assert len(ctx.get_coords()) == 4
    assert ctx._factor >= 1
    assert ctx._color_table[0] == ctx.convert_to_rgb([0.0, 0.0, 0.0])


def test_axial_shading_paint_returns_context() -> None:
    paint = AxialShadingPaint(_FakeAxialShading(), matrix=None)
    ctx = paint.create_context(None, (0, 0, 4, 4), None, None)
    assert isinstance(ctx, AxialShadingContext)


class _FakeRadialShading(_FakeAxialShading):
    def get_coords(self):
        class _Arr:
            @staticmethod
            def to_float_array():
                return [0.0, 0.0, 1.0, 10.0, 0.0, 5.0]
        return _Arr()


def test_radial_shading_context_builds_color_table() -> None:
    ctx = RadialShadingContext(
        _FakeRadialShading(),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    assert len(ctx.get_coords()) == 6
    vals = ctx.calculate_input_values(0.0, 0.0)
    assert len(vals) == 2


def test_radial_shading_paint_returns_context() -> None:
    paint = RadialShadingPaint(_FakeRadialShading(), matrix=None)
    ctx = paint.create_context(None, (0, 0, 4, 4), None, None)
    assert isinstance(ctx, RadialShadingContext)


class _FakeType1Shading(_FakeShading):
    def get_domain(self):
        return None


def test_type1_shading_context_default_domain() -> None:
    ctx = Type1ShadingContext(_FakeType1Shading(), color_model=None, xform=None, matrix=None)
    assert ctx.get_domain() == [0.0, 1.0, 0.0, 1.0]


def test_type1_shading_paint_returns_context() -> None:
    paint = Type1ShadingPaint(_FakeType1Shading(), matrix=None)
    ctx = paint.create_context(None, None, None, None)
    assert isinstance(ctx, Type1ShadingContext)


# ----------------------------------------------------------------------
# Gouraud / Patch / Triangle intermediate contexts
# ----------------------------------------------------------------------
def test_gouraud_shading_context_empty_until_triangles_set() -> None:
    ctx = GouraudShadingContext(_FakeShading(), color_model=None, xform=None, matrix=None)
    assert ctx.is_data_empty()
    triangle = ShadedTriangle(
        [(0.0, 0.0), (4.0, 0.0), (0.0, 4.0)],
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    )
    ctx.set_triangle_list([triangle])
    assert not ctx.is_data_empty()


def test_triangle_based_shading_context_calc_pixel_table_fills_cells() -> None:
    ctx = GouraudShadingContext(_FakeShading(), color_model=None, xform=None, matrix=None)
    triangle = ShadedTriangle(
        [(0.0, 0.0), (3.0, 0.0), (0.0, 3.0)],
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    )
    ctx.set_triangle_list([triangle])
    ctx.create_pixel_table((0, 0, 4, 4))
    # Origin pixel should be populated by the (1,0,0) corner colour.
    assert ctx.get_value_from_array(0, 0) != -1


class _FakePatchShading(_FakeShading):
    def collect_patches(self, xform, matrix, control_points):
        # Always return an empty list for the abstract surface test.
        return []


def test_patch_meshes_shading_context_handles_empty_mesh() -> None:
    ctx = PatchMeshesShadingContext(
        _FakePatchShading(),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 2, 2),
        control_points=12,
    )
    assert ctx.is_data_empty()


# ----------------------------------------------------------------------
# Type 4/5/6/7 paints expose the upstream interface
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "paint_cls",
    [Type4ShadingPaint, Type5ShadingPaint, Type6ShadingPaint, Type7ShadingPaint],
)
def test_higher_type_paints_expose_shading_and_matrix(paint_cls: type) -> None:
    shading = _FakeShading()
    paint = paint_cls(shading, matrix="m")
    assert paint.get_shading() is shading
    assert paint.get_matrix() == "m"


# ----------------------------------------------------------------------
# Abstract PD type bases
# ----------------------------------------------------------------------
def test_pd_triangle_based_interpolate() -> None:
    assert PDTriangleBasedShadingType.interpolate(0, 255, 0.0, 1.0) == pytest.approx(0.0)
    assert PDTriangleBasedShadingType.interpolate(255, 255, 0.0, 1.0) == pytest.approx(1.0)
    assert PDTriangleBasedShadingType.interpolate(0, 0, 0.5, 1.0) == pytest.approx(0.5)


def test_pd_mesh_based_generate_patch_is_abstract() -> None:
    base = PDMeshBasedShadingType()
    with pytest.raises(NotImplementedError):
        base.generate_patch([(0.0, 0.0)], [[0.0]])


# ----------------------------------------------------------------------
# Sanity: bezier values
# ----------------------------------------------------------------------
def test_cubic_bezier_midpoint_on_quadratic() -> None:
    # straight line P0 P1 P2 P3 colinear; midpoint must be on the line.
    curve = CubicBezierCurve([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)], 1)
    pts = curve.get_cubic_bezier_curve()
    assert pts[1][1] == pytest.approx(0.0)
    assert math.isclose(pts[1][0], 1.5, abs_tol=1e-6)
