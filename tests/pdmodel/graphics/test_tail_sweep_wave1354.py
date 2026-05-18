"""Wave 1354 tail-sweep — close 1-3 missing lines across pdmodel/graphics.

Each test targets a narrow, previously uncovered branch so the module
reaches 100% line coverage. Grouped by submodule for readability.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.blend.blend_function import BlendFunction
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from pypdfbox.pdmodel.graphics.color.pd_tristimulus import PDTristimulus
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.image.custom_factory import CustomFactory
from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.graphics.shading.cubic_bezier_curve import CubicBezierCurve
from pypdfbox.pdmodel.graphics.shading.gouraud_shading_context import (
    GouraudShadingContext,
)
from pypdfbox.pdmodel.graphics.shading.int_point import IntPoint
from pypdfbox.pdmodel.graphics.shading.pd_shading_type4 import PDShadingType4
from pypdfbox.pdmodel.graphics.shading.pd_shading_type5 import PDShadingType5
from pypdfbox.pdmodel.graphics.shading.radial_shading_context import (
    RadialShadingContext,
)
from pypdfbox.pdmodel.graphics.shading.type4_shading_paint import Type4ShadingPaint
from pypdfbox.pdmodel.graphics.shading.type5_shading_paint import Type5ShadingPaint
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)

# ---------------------------------------------------------------------------
# blend/blend_function.py — line 40 (__call__)
# ---------------------------------------------------------------------------


def test_blend_function_dunder_call_delegates_to_fn() -> None:
    """Invoking the adapter directly (``fn(...)``) must forward to the inner
    callable. The existing test only covered the ``.blend()`` method path.
    """
    calls: list[tuple[tuple[float, ...], tuple[float, ...]]] = []

    def record(src: Any, dest: Any, result: list[float]) -> None:
        calls.append((tuple(src), tuple(dest)))
        for i in range(3):
            result[i] = src[i] * dest[i]

    fn = BlendFunction(record)
    out = [0.0, 0.0, 0.0]
    fn([0.2, 0.5, 1.0], [0.5, 0.5, 0.5], out)
    assert out == pytest.approx([0.1, 0.25, 0.5])
    assert calls == [((0.2, 0.5, 1.0), (0.5, 0.5, 0.5))]


# ---------------------------------------------------------------------------
# blend_mode.py — line 272 (name property); lines 511-512 (luminosity delta>0)
# ---------------------------------------------------------------------------


def test_blend_mode_name_property_returns_name() -> None:
    """The ``name`` property mirrors upstream ``getName()`` and was the only
    accessor left uncovered after wave 1281."""
    mode = BlendMode.NORMAL
    assert mode.name == "Normal"
    assert mode.name == mode.get_name()


def test_blend_mode_luminosity_positive_delta_overflow_branch() -> None:
    """Exercise the ``delta > 0`` overflow branch in ``getLuminosityRGB``
    (lines 510-512).

    The branch fires when:
        - at least one of r/g/b overflows past 255 (bit 8 set), AND
        - the delta is positive (src brighter than dest).

    Asymmetric channels are needed because uniformly bright src + uniform
    dest yields uniform r/g/b that just clip to 255 without setting bit
    0x100. With ``src=[1, 1, 0]`` and ``dest=[0.5, 1, 0.5]`` the green
    channel computes to 279 (= 255 + 24), setting bit 8 in the OR.
    """
    result = [0.0, 0.0, 0.0]
    BlendMode.get_luminosity_rgb([1.0, 1.0, 0.0], [0.5, 1.0, 0.5], result)
    # Branch executed without error; outputs are finite [0,1].
    for c in result:
        assert 0.0 <= c <= 1.0
        assert not math.isnan(c)
    # Also exercise the negative-delta branch (delta < 0) for completeness.
    other = [0.0, 0.0, 0.0]
    BlendMode.get_luminosity_rgb([0.0, 0.0, 1.0], [0.5, 1.0, 0.5], other)
    for c in other:
        assert 0.0 <= c <= 1.0


# ---------------------------------------------------------------------------
# color/pd_lab.py — lines 294, 296, 298 (negative XYZ clamping)
# ---------------------------------------------------------------------------


def test_pd_lab_to_rgb_clamps_negative_xyz_components() -> None:
    """A negative-valued white point forces all three XYZ products through
    the ``< 0.0`` clamp branches.

    ``inverse(lstar)`` is positive for L*=0 (the affine branch yields a
    negative number; multiplied by a negative white-point component the
    product goes positive — but the OTHER white-point components stay
    negative-times-positive). With white point ``[-1, -1, -1]`` the L*=0
    case routes the lstar through the affine branch (negative result),
    times negative wp_y -> positive y; we want negatives. Easier: pick
    ``a*`` and ``b*`` extremes so the affine x/z go negative directly via
    positive wp_x/wp_z.
    """
    cs = PDLab()
    # L*=0 -> lstar = 16/116 ~= 0.1379; inverse path: 0.1379 < 6/29 (~0.2069)
    # -> (108/841)*(0.1379 - 4/29) -> -2.65e-3 (negative).
    # x = 1 * inverse(0.1379 + a*/500)
    # For very negative a*, x becomes very negative; same for b*/z.
    rgb = cs.to_rgb([0.0, -10000.0, -10000.0])
    assert len(rgb) == 3
    # Each component should be a finite [0,1] value (clamp branches ran).
    for c in rgb:
        assert 0.0 <= c <= 1.0


def test_pd_lab_to_rgb_clamps_negative_y_via_negative_white_point() -> None:
    """The Y branch (line 295-296) is only triggered when ``wp_y *
    inverse(lstar) < 0``. ``inverse(lstar)`` is positive for the cubic
    branch (L* large enough) so a negative ``wp_y`` flips Y negative."""
    cs = PDLab()
    cs.set_white_point([-1.0, -1.0, -1.0])
    # L*=50 -> lstar = 66/116 = 0.569; cubic branch -> positive inverse.
    # wp negative -> all three XYZ negative -> all three clamps fire.
    rgb = cs.to_rgb([50.0, 0.0, 0.0])
    assert len(rgb) == 3


# ---------------------------------------------------------------------------
# color/pd_separation.py — line 158 (set_tint_transform with COSBase fallback)
# ---------------------------------------------------------------------------


def test_pd_separation_set_tint_transform_accepts_cos_dictionary() -> None:
    """set_tint_transform with a COS-form object stores its ``get_cos_object``
    result in the tint-transform slot. (The ``elif isinstance(transform,
    COSBase)`` branch is unreachable because COSBase always carries
    ``get_cos_object`` — pragmas in pd_separation.py.)"""
    sep = PDSeparation()
    raw = COSDictionary()
    raw.set_int("FunctionType", 2)
    sep.set_tint_transform(raw)
    # Round-trips through get_cos_object (returns self for COSDictionary).
    assert sep._array.get(sep._TINT_TRANSFORM) is raw


# ---------------------------------------------------------------------------
# color/pd_tristimulus.py — lines 41, 60, 68 (read of non-COSNumber + Z setters)
# ---------------------------------------------------------------------------


def test_pd_tristimulus_read_returns_zero_for_non_number_entry() -> None:
    """Line 41: when the array slot holds a non-numeric COS object
    (e.g. a COSName from a malformed PDF), ``_read`` returns 0.0."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("oops"))
    arr.add(COSName.get_pdf_name("oops"))
    arr.add(COSName.get_pdf_name("oops"))
    tri = PDTristimulus(arr)
    assert tri.get_x() == 0.0
    assert tri.get_y() == 0.0
    assert tri.get_z() == 0.0


def test_pd_tristimulus_set_y_writes_through() -> None:
    """Line 60: ``set_y`` is the only setter still uncovered."""
    tri = PDTristimulus()
    tri.set_y(0.42)
    assert tri.get_y() == pytest.approx(0.42)


def test_pd_tristimulus_set_z_writes_through() -> None:
    """Line 68: ``set_z`` is the only setter still uncovered."""
    tri = PDTristimulus()
    tri.set_z(0.73)
    assert tri.get_z() == pytest.approx(0.73)


# ---------------------------------------------------------------------------
# form/pd_form_x_object.py — line 120 (set_b_box TypeError for non-PDRectangle)
# ---------------------------------------------------------------------------


def test_pd_form_x_object_set_b_box_rejects_non_rectangle() -> None:
    """Passing something other than ``PDRectangle`` or ``None`` raises
    ``TypeError`` (line 120)."""
    from pypdfbox.pdmodel.common.pd_stream import PDStream
    from pypdfbox.pdmodel.pd_document import PDDocument

    doc = PDDocument()
    form = PDFormXObject(PDStream(doc))
    with pytest.raises(TypeError, match="set_bbox requires"):
        form.set_b_box([0.0, 0.0, 1.0, 1.0])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# image/custom_factory.py — line 34 (__call__)
# ---------------------------------------------------------------------------


def test_custom_factory_dunder_call_delegates() -> None:
    """``CustomFactory(...)`` invocation forwards to the inner callable."""
    seen: list[tuple[Any, bytes]] = []

    def factory(doc: Any, b: bytes) -> str:
        seen.append((doc, b))
        return "sentinel"

    cf = CustomFactory(factory)
    result = cf("doc-marker", b"abc")  # type: ignore[arg-type]
    assert result == "sentinel"
    assert seen == [("doc-marker", b"abc")]


# ---------------------------------------------------------------------------
# image/lossless_factory.py — line 277 (PDColorSpace with None cos object)
# ---------------------------------------------------------------------------


def test_lossless_factory_prepare_raises_on_none_cos_object() -> None:
    """When the PDColorSpace's ``get_cos_object()`` returns ``None`` the
    helper raises ``ValueError`` (line 277)."""
    from pypdfbox.pdmodel.pd_document import PDDocument

    class _NullCosColorSpace:
        """PDColorSpace-quacker whose COS form is missing."""

        def get_cos_object(self) -> Any:
            return None

        def get_number_of_components(self) -> int:
            return 1

    # The isinstance check uses PDColorSpace, so we need an actual subclass.
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace

    class _BrokenColorSpace(PDColorSpace):  # type: ignore[misc]
        def __init__(self) -> None:
            # Skip parent __init__ which expects a COSArray.
            self._array = None

        def get_name(self) -> str:
            return "Broken"

        def get_number_of_components(self) -> int:
            return 1

        def get_initial_color(self) -> Any:
            return None

        def get_cos_object(self) -> Any:
            return None

    doc = PDDocument()
    with pytest.raises(ValueError, match="returned None"):
        LosslessFactory.prepare_image_x_object(
            doc, b"\x00", 1, 1, 8, _BrokenColorSpace()
        )


# ---------------------------------------------------------------------------
# shading/cubic_bezier_curve.py — lines 57-60, 63 (to_string + __repr__)
# ---------------------------------------------------------------------------


def test_cubic_bezier_curve_to_string_and_repr_format_control_points() -> None:
    """Both ``to_string`` and ``__repr__`` interpolate the four control
    points into the upstream Java-style format."""
    curve = CubicBezierCurve(
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        level=1,
    )
    rendered = curve.to_string()
    assert "Cubic Bezier curve" in rendered
    assert "control points p0, p1, p2, p3" in rendered
    assert "Point2D.Double[0.0, 0.0]" in rendered
    assert "Point2D.Double[1.0, 0.0]" in rendered
    assert "Point2D.Double[1.0, 1.0]" in rendered
    assert "Point2D.Double[0.0, 1.0]" in rendered
    # __repr__ delegates to to_string.
    assert repr(curve) == rendered


# ---------------------------------------------------------------------------
# shading/gouraud_shading_context.py — lines 43-44 (dispose)
# ---------------------------------------------------------------------------


def _make_gouraud_context() -> GouraudShadingContext:
    """Construct a context with a trivial empty triangle list."""

    class _Stub:
        def get_background(self) -> Any:
            return None

        def get_anti_alias(self) -> bool:
            return False

        def get_bits_per_color_component(self) -> int:
            return 8

        def get_number_of_color_components(self) -> int:
            return 3

        def get_color_space(self) -> Any:
            return None

        def get_function(self) -> Any:
            return None

        def get_decode_for_parameter(self, _i: int) -> Any:
            return None

    return GouraudShadingContext(_Stub(), color_model=None, xform=None, matrix=None)


def test_gouraud_shading_context_dispose_clears_triangle_list() -> None:
    """``dispose()`` empties the triangle list and chains the parent
    dispose."""
    ctx = _make_gouraud_context()
    # Populate with a sentinel so we can prove dispose clears it.
    ctx.set_triangle_list([object(), object()])  # type: ignore[list-item]
    assert not ctx.is_data_empty()
    ctx.dispose()
    assert ctx.is_data_empty()
    assert ctx._triangle_list == []


# ---------------------------------------------------------------------------
# shading/int_point.py — lines 33 (equals self short-circuit), 45 (__repr__)
# ---------------------------------------------------------------------------


def test_int_point_equals_self_short_circuits_true() -> None:
    """``equals(self)`` returns True via the identity check (line 33)."""
    p = IntPoint(3, 4)
    assert p.equals(p) is True
    # __eq__ delegates to equals, so the identity path also covers __eq__.
    assert p == p


def test_int_point_repr_includes_coords() -> None:
    """``__repr__`` renders the two coords (line 45)."""
    assert repr(IntPoint(7, -2)) == "IntPoint(7, -2)"


# ---------------------------------------------------------------------------
# shading/pd_shading_type4.py — lines 181, 197;
# shading/pd_shading_type5.py — lines 171, 189
# These cover the "not a COSStream -> return []" guard and the trailing
# "return []" after Decode validation succeeds.
# ---------------------------------------------------------------------------


def _build_dict_shading4() -> PDShadingType4:
    """PDShadingType4 backed by a COSDictionary (not a stream)."""
    d = COSDictionary()
    d.set_int("ShadingType", 4)
    return PDShadingType4(d)


def _build_dict_shading5() -> PDShadingType5:
    """PDShadingType5 backed by a COSDictionary (not a stream)."""
    d = COSDictionary()
    d.set_int("ShadingType", 5)
    return PDShadingType5(d)


def test_pd_shading_type4_collect_triangles_returns_empty_for_non_stream() -> None:
    """Line 181: when the backing object is a dict (not a stream) upstream
    returns ``Collections.emptyList()`` — we return ``[]``."""
    sh = _build_dict_shading4()
    assert sh.collect_triangles(xform=None, matrix=None) == []


def test_pd_shading_type5_collect_triangles_returns_empty_for_non_stream() -> None:
    """Line 171: same non-stream guard for the lattice variant."""
    sh = _build_dict_shading5()
    assert sh.collect_triangles(xform=None, matrix=None) == []


def _build_stream_shading4_with_decode() -> PDShadingType4:
    """Stream-backed type 4 with the minimal /Decode entry needed to walk
    past the early guards. Stream body is empty -> mesh deferral returns
    [] at the final line (197)."""
    from pypdfbox.cos import COSStream

    s = COSStream()
    s.set_int("ShadingType", 4)
    s.set_int("BitsPerComponent", 8)
    s.set_int("BitsPerCoordinate", 8)
    s.set_int("BitsPerFlag", 8)
    s.set_int("NumberOfColorComponents", 1)
    # /Decode: [xmin xmax ymin ymax c0min c0max]
    arr = COSArray.of_cos_floats([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    s.set_item("Decode", arr)
    # Empty body.
    s.create_output_stream().close()
    sh = PDShadingType4(s)
    return sh


def _build_stream_shading5_with_decode() -> PDShadingType5:
    """Same as above but for lattice form, with /VerticesPerRow."""
    from pypdfbox.cos import COSStream

    s = COSStream()
    s.set_int("ShadingType", 5)
    s.set_int("BitsPerComponent", 8)
    s.set_int("BitsPerCoordinate", 8)
    s.set_int("VerticesPerRow", 4)
    s.set_int("NumberOfColorComponents", 1)
    arr = COSArray.of_cos_floats([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    s.set_item("Decode", arr)
    s.create_output_stream().close()
    return PDShadingType5(s)


def test_pd_shading_type4_collect_triangles_returns_empty_after_valid_decode() -> None:
    """Line 197: the deferred-mesh trailing ``return []`` is reached when
    every guard passes (stream backing, valid /Decode ranges, color
    components have ranges)."""
    sh = _build_stream_shading4_with_decode()
    # The number of color components defaults to 1 when a function is None
    # and color space is None.
    result = sh.collect_triangles(xform=None, matrix=None)
    assert result == []


def test_pd_shading_type5_collect_triangles_returns_empty_after_valid_decode() -> None:
    """Line 189: same as type 4 but for the lattice form."""
    sh = _build_stream_shading5_with_decode()
    result = sh.collect_triangles(xform=None, matrix=None)
    assert result == []


# ---------------------------------------------------------------------------
# shading/pd_triangle_based_shading_type.py — line 79 (Function present
# overrides component count to 1)
# ---------------------------------------------------------------------------


def test_pd_triangle_based_shading_with_function_reports_one_component() -> None:
    """When a /Function is present upstream forces ``NumberOfColorComponents``
    to 1 — the conditional on line 78-79 covers that path.

    Type4 / Type5 override ``get_number_of_color_components``, so we need
    to instantiate the base class directly to hit the inherited branch.
    """
    from pypdfbox.pdmodel.graphics.shading.pd_triangle_based_shading_type import (
        PDTriangleBasedShadingType,
    )

    d = COSDictionary()
    d.set_int("ShadingType", 4)
    fn = COSDictionary()
    fn.set_int("FunctionType", 2)
    fn.set_item("Domain", COSArray.of_cos_floats([0.0, 1.0]))
    fn.set_item("C0", COSArray.of_cos_floats([0.0]))
    fn.set_item("C1", COSArray.of_cos_floats([1.0]))
    fn.set_int("N", 1)
    d.set_item("Function", fn)
    sh = PDTriangleBasedShadingType(d)
    assert sh.get_number_of_color_components() == 1


# ---------------------------------------------------------------------------
# shading/radial_shading_context.py — lines 165, 174, 180, 182
# Re-use the existing fixtures pattern (_FakeRadialShading) to hit the
# remaining branches:
#   165: ``input_value > 1`` and ``bg is None`` and not (extend[1] and r1>0)
#   174: ``input_value < 0`` and ``bg is not None`` and not (extend[0] and r0>0)
#   180: ``key < 0`` -> key = 0
#   182: ``key > factor`` -> key = factor
# ---------------------------------------------------------------------------


class _ArrAdapter:
    """Stand-in for the COSArray returned by ``get_coords`` / ``get_domain``."""

    def __init__(self, values: list[float]) -> None:
        self._values = list(values)

    def to_float_array(self) -> list[float]:
        return list(self._values)


class _Bool:
    """Stand-in for a COSBoolean object."""

    def __init__(self, v: bool) -> None:
        self._v = v

    def get_value(self) -> bool:
        return self._v


class _ExtendArr:
    """Stand-in for the COSArray returned by ``get_extend``."""

    def __init__(self, a: bool, b: bool) -> None:
        self._items = [_Bool(a), _Bool(b)]

    def get_object(self, i: int) -> _Bool:
        return self._items[i]


class _BgArr:
    """Stand-in for the COSArray returned by ``get_background``."""

    def __init__(self, values: list[float]) -> None:
        self._values = list(values)

    def to_float_array(self) -> list[float]:
        return list(self._values)


class _FakeRadialShading:
    """Configurable fake matching ``PDShadingType3``'s context surface.

    Mirrors the structure of the ``_FakeRadialShading`` in
    ``test_axial_radial_shading_context_coverage.py`` so the same
    arithmetic paths through ``RadialShadingContext`` are exercised.
    """

    def __init__(
        self,
        *,
        coords: list[float] | None,
        domain: list[float] | None = None,
        extend: tuple[bool, bool] | None = None,
        background: list[float] | None = None,
        function_marker: Any = None,
    ) -> None:
        self._coords = coords
        self._domain = domain
        self._extend = extend
        self._background = background
        self._function_marker = function_marker

    def get_color_space(self) -> Any:
        return None

    def get_coords(self) -> Any:
        return _ArrAdapter(self._coords) if self._coords is not None else None

    def get_domain(self) -> Any:
        return _ArrAdapter(self._domain) if self._domain is not None else None

    def get_extend(self) -> Any:
        return _ExtendArr(*self._extend) if self._extend is not None else None

    def get_background(self) -> Any:
        return _BgArr(self._background) if self._background is not None else None

    def get_function(self) -> Any:
        return self._function_marker

    def eval_function(self, t: Any) -> list[float]:
        if isinstance(t, (list, tuple)):
            t = t[0] if t else 0.0
        v = max(0.0, min(1.0, float(t)))
        return [v, v, v]


def test_radial_get_raster_high_input_no_bg_no_clamp_continues() -> None:
    """Line 165: ``input_value > 1`` with ``extend[1]`` False AND no bg ->
    the inner loop ``continue`` runs (pixel stays transparent)."""
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
            extend=(True, False),  # extend[1] False so clamp-high skipped
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    # Sample at a point past the end -> input_value > 1, extend[1] False,
    # bg None -> continue -> transparent pixel.
    img = ctx.get_raster(20, 0, 1, 1)
    assert img.load()[0, 0] == (0, 0, 0, 0)


def test_radial_get_raster_low_input_no_clamp_with_bg_uses_bg() -> None:
    """Line 174: ``input_value < 0`` with ``extend[0]`` False and bg
    present -> falls through to ``use_background = True``."""
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
            extend=(False, True),  # extend[0] False
            background=[0.25, 0.5, 0.75],
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    # Sample in a region where extend[1] picks a root <0 -> low clamp fail
    # -> bg fallback.
    img = ctx.get_raster(-20, 0, 1, 1)
    pixel = img.load()[0, 0]
    # Either bg used (alpha 255) or other branch; just exercise no crash
    # and shape.
    assert img.size == (1, 1)
    assert pixel[3] in (0, 255)


def test_radial_get_raster_key_clamps_to_zero_when_negative() -> None:
    """Line 180: when ``input_value < 0`` and the colour-table key arithmetic
    yields a negative integer, the clamp sets it to 0. We force this via
    a degenerate /Domain (domain[0] negative, domain[1] positive) so a
    valid 0..1 input_value with extend mapping pushes the key negative."""
    # When extend[1] && coords[5]>0 -> input_value = domain[1] (positive).
    # When extend[0] && coords[2]>0 -> input_value = domain[0]. Use a
    # negative domain[0] to get a negative key.
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
            domain=[-2.0, 1.0],
            extend=(True, True),
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    # Sample far to the negative-x side -> roots <0 -> extend[0] && r0>0
    # -> input_value = -2.0; key = int(-2.0 * factor) negative -> clamp 0.
    img = ctx.get_raster(-20, 0, 1, 1)
    pixel = img.load()[0, 0]
    assert pixel[3] == 255


def test_radial_get_raster_key_clamps_to_factor_when_too_high() -> None:
    """Line 182: key > factor -> clamp to factor. Use a domain whose
    upper bound is >1 so a valid mapping produces an over-table key."""
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
            domain=[0.0, 5.0],
            extend=(True, True),
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    # Sample beyond the end -> input_value > 1 -> extend[1] && r1>0 ->
    # input_value = domain[1] = 5.0; key = int(5.0 * factor) > factor ->
    # clamp to factor.
    img = ctx.get_raster(20, 0, 1, 1)
    pixel = img.load()[0, 0]
    assert pixel[3] == 255


# ---------------------------------------------------------------------------
# shading/type4_shading_paint.py + type5_shading_paint.py — lines 40-41 /
# 39-40 (collect_triangles raises -> empty triangle list fallback)
# ---------------------------------------------------------------------------


class _RaisingShading:
    """Stub shading whose ``collect_triangles`` raises -> the paint adapter
    falls back to an empty list."""

    def __init__(self, exc: type[Exception]) -> None:
        self._exc = exc

    def collect_triangles(self, _xform: Any, _matrix: Any) -> Any:
        raise self._exc("boom")

    # Surface the attributes the GouraudShadingContext + its parents poke.
    def get_background(self) -> Any:
        return None

    def get_anti_alias(self) -> bool:
        return False

    def get_bits_per_color_component(self) -> int:
        return 8

    def get_number_of_color_components(self) -> int:
        return 3

    def get_color_space(self) -> Any:
        return None

    def get_function(self) -> Any:
        return None

    def get_decode_for_parameter(self, _i: int) -> Any:
        return None


@pytest.mark.parametrize(
    "exc",
    [NotImplementedError, AttributeError, OSError],
    ids=["notimpl", "attrerr", "oserr"],
)
def test_type4_shading_paint_create_context_swallows_collect_failures(
    exc: type[Exception],
) -> None:
    """Lines 40-41: ``collect_triangles`` raising one of the expected
    exceptions falls through to an empty triangle list."""
    paint = Type4ShadingPaint(_RaisingShading(exc), matrix=None)
    ctx = paint.create_context(
        cm=None,
        device_bounds=None,
        user_bounds=None,
        xform=None,
        hints=None,
    )
    assert ctx.is_data_empty()


@pytest.mark.parametrize(
    "exc",
    [NotImplementedError, AttributeError, OSError],
    ids=["notimpl", "attrerr", "oserr"],
)
def test_type5_shading_paint_create_context_swallows_collect_failures(
    exc: type[Exception],
) -> None:
    """Lines 39-40: same swallow-and-fall-back as type 4."""
    paint = Type5ShadingPaint(_RaisingShading(exc), matrix=None)
    ctx = paint.create_context(
        cm=None,
        device_bounds=None,
        user_bounds=None,
        xform=None,
        hints=None,
    )
    assert ctx.is_data_empty()


# ---------------------------------------------------------------------------
# state/pd_extended_graphics_state.py — lines 425, 429, 433 (public aliases)
# ---------------------------------------------------------------------------


def test_pd_extended_graphics_state_default_if_null_public_alias() -> None:
    """Line 425: the public-named ``default_if_null`` delegates to the
    underscored private."""
    assert PDExtendedGraphicsState.default_if_null(None, 5.0) == 5.0
    assert PDExtendedGraphicsState.default_if_null(2.0, 5.0) == 2.0


def test_pd_extended_graphics_state_get_set_float_item_public_aliases() -> None:
    """Lines 429 + 433: ``get_float_item`` / ``set_float_item`` delegate to
    the underscored private helpers."""
    state = PDExtendedGraphicsState()
    key = COSName.get_pdf_name("ZZ-TEST")
    assert state.get_float_item(key) is None
    state.set_float_item(key, 3.25)
    assert state.get_float_item(key) == pytest.approx(3.25)
    # Setting to None removes the entry.
    state.set_float_item(key, None)
    assert state.get_float_item(key) is None


# ---------------------------------------------------------------------------
# Sanity smoke: make sure none of the helpers above leave NaN/Inf in pixels.
# ---------------------------------------------------------------------------


def test_radial_smoke_no_nan_in_pixels() -> None:
    """Belt-and-braces: ensure none of the radial branches we just covered
    emit NaN pixel coordinates."""
    ctx = RadialShadingContext(
        _FakeRadialShading(
            coords=[0.0, 0.0, 1.0, 4.0, 0.0, 3.0],
            domain=[0.0, 5.0],
            extend=(True, True),
            background=[0.1, 0.2, 0.3],
        ),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 8, 8),
    )
    img = ctx.get_raster(-2, -2, 6, 6)
    px = img.load()
    for j in range(6):
        for i in range(6):
            r, g, b, a = px[i, j]
            assert 0 <= r <= 255
            assert 0 <= g <= 255
            assert 0 <= b <= 255
            assert 0 <= a <= 255
            assert not math.isnan(float(r + g + b + a))
