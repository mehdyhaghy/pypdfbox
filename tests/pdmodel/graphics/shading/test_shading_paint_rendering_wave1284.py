"""Wave 1284 tests for the filled-in shading paint / context surfaces.

Covers:

* :meth:`PDShading.to_paint` dispatch on ``/ShadingType``.
* :meth:`PDShadingType1.to_paint`, :meth:`PDShadingType2.to_paint`,
  :meth:`PDShadingType3.to_paint` returning their type-specific paint
  adapters.
* :meth:`AxialShadingContext.get_raster`,
  :meth:`RadialShadingContext.get_raster`,
  :meth:`Type1ShadingContext.get_raster`,
  :meth:`TriangleBasedShadingContext.get_raster` producing a Pillow image.
* :meth:`Type4ShadingPaint.create_context` through
  :meth:`Type7ShadingPaint.create_context` returning the shared
  Gouraud / PatchMeshes contexts.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.pdmodel.graphics.shading import (
    AxialShadingContext,
    AxialShadingPaint,
    GouraudShadingContext,
    PatchMeshesShadingContext,
    PDShading,
    PDShadingType1,
    PDShadingType2,
    PDShadingType3,
    RadialShadingContext,
    RadialShadingPaint,
    ShadedTriangle,
    Type1ShadingContext,
    Type1ShadingPaint,
    Type4ShadingPaint,
    Type5ShadingPaint,
    Type6ShadingPaint,
    Type7ShadingPaint,
)


# ----------------------------------------------------------------------
# to_paint dispatchers
# ----------------------------------------------------------------------
def test_pd_shading_type1_to_paint_returns_type1_paint() -> None:
    shading = PDShadingType1()
    paint = shading.to_paint()
    assert isinstance(paint, Type1ShadingPaint)
    assert paint.get_shading() is shading


def test_pd_shading_type2_to_paint_returns_axial_paint() -> None:
    shading = PDShadingType2()
    paint = shading.to_paint(matrix=None)
    assert isinstance(paint, AxialShadingPaint)


def test_pd_shading_type3_to_paint_returns_radial_paint() -> None:
    shading = PDShadingType3()
    paint = shading.to_paint(matrix="m")
    assert isinstance(paint, RadialShadingPaint)
    assert paint.get_matrix() == "m"


def test_pd_shading_base_to_paint_dispatches_on_shading_type() -> None:
    shading = PDShadingType2()
    base = PDShading(shading.get_cos_object())
    paint = base.to_paint(matrix=None)
    assert isinstance(paint, AxialShadingPaint)


def test_pd_shading_base_to_paint_returns_none_for_unknown_type() -> None:
    base = PDShading()
    assert base.to_paint() is None


# ----------------------------------------------------------------------
# get_shading_type base-class fallback
# ----------------------------------------------------------------------
def test_pd_shading_get_shading_type_from_dict() -> None:
    shading = PDShadingType2()
    base = PDShading(shading.get_cos_object())
    assert base.get_shading_type() == 2


def test_pd_shading_get_shading_type_raises_when_missing() -> None:
    base = PDShading()
    with pytest.raises(NotImplementedError):
        base.get_shading_type()


# ----------------------------------------------------------------------
# Raster output — simple "must not raise" smokes
# ----------------------------------------------------------------------
class _FakeAxialShading:
    def get_color_space(self) -> Any:
        return None

    def get_background(self) -> Any:
        return None

    def get_function(self) -> Any:
        return None

    def get_coords(self) -> Any:
        class _Arr:
            @staticmethod
            def to_float_array() -> list[float]:
                return [0.0, 0.0, 4.0, 0.0]
        return _Arr()

    def get_domain(self) -> Any:
        return None

    def get_extend(self) -> Any:
        return None

    def eval_function(self, t: Any) -> list[float]:
        # Use t as a scalar for the axial gradient.
        if isinstance(t, (list, tuple)):
            t = t[0] if t else 0.0
        return [float(t), float(t), float(t)]


def test_axial_shading_context_get_raster_returns_pillow_image() -> None:
    from PIL import Image

    ctx = AxialShadingContext(
        _FakeAxialShading(),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(0, 0, 4, 4)
    assert isinstance(img, Image.Image)
    assert img.size == (4, 4)


class _FakeRadialShading(_FakeAxialShading):
    def get_coords(self) -> Any:
        class _Arr:
            @staticmethod
            def to_float_array() -> list[float]:
                return [2.0, 2.0, 0.0, 2.0, 2.0, 4.0]
        return _Arr()


def test_radial_shading_context_get_raster_returns_pillow_image() -> None:
    from PIL import Image

    ctx = RadialShadingContext(
        _FakeRadialShading(),
        color_model=None,
        xform=None,
        matrix=None,
        device_bounds=(0, 0, 4, 4),
    )
    img = ctx.get_raster(0, 0, 4, 4)
    assert isinstance(img, Image.Image)
    assert img.size == (4, 4)


class _FakeType1Shading(_FakeAxialShading):
    def get_domain(self) -> Any:
        return None

    def eval_function(self, value: Any) -> list[float]:
        # Single value; map directly to a gray RGB.
        if isinstance(value, (list, tuple)):
            v = sum(float(x) for x in value) / max(1, len(value))
        else:
            v = float(value)
        normalised = max(0.0, min(1.0, v / 4.0))
        return [normalised, normalised, normalised]


def test_type1_shading_context_get_raster_returns_pillow_image() -> None:
    from PIL import Image

    ctx = Type1ShadingContext(
        _FakeType1Shading(),
        color_model=None,
        xform=None,
        matrix=None,
    )
    img = ctx.get_raster(0, 0, 4, 4)
    assert isinstance(img, Image.Image)
    assert img.size == (4, 4)


def test_triangle_based_get_raster_via_gouraud_context() -> None:
    from PIL import Image

    ctx = GouraudShadingContext(
        _FakeAxialShading(),
        color_model=None,
        xform=None,
        matrix=None,
    )
    triangle = ShadedTriangle(
        [(0.0, 0.0), (3.0, 0.0), (0.0, 3.0)],
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    )
    ctx.set_triangle_list([triangle])
    ctx.create_pixel_table((0, 0, 4, 4))
    img = ctx.get_raster(0, 0, 4, 4)
    assert isinstance(img, Image.Image)
    assert img.size == (4, 4)


def test_triangle_based_get_raster_empty_data_returns_image() -> None:
    from PIL import Image

    ctx = GouraudShadingContext(
        _FakeAxialShading(),
        color_model=None,
        xform=None,
        matrix=None,
    )
    img = ctx.get_raster(0, 0, 2, 2)
    assert isinstance(img, Image.Image)
    assert img.size == (2, 2)


# ----------------------------------------------------------------------
# Type 4-7 paint create_context
# ----------------------------------------------------------------------
class _FakeMeshShading(_FakeAxialShading):
    def collect_triangles(self, _xform: Any, _matrix: Any) -> list[Any]:
        return []

    def collect_patches(
        self, _xform: Any, _matrix: Any, _control_points: int,
    ) -> list[Any]:
        return []


@pytest.mark.parametrize("paint_cls", [Type4ShadingPaint, Type5ShadingPaint])
def test_gouraud_paint_create_context_returns_context(paint_cls: type) -> None:
    paint = paint_cls(_FakeMeshShading(), matrix=None)
    ctx = paint.create_context(None, (0, 0, 4, 4), None, None)
    assert isinstance(ctx, GouraudShadingContext)


@pytest.mark.parametrize("paint_cls", [Type6ShadingPaint, Type7ShadingPaint])
def test_patch_mesh_paint_create_context_returns_context(paint_cls: type) -> None:
    paint = paint_cls(_FakeMeshShading(), matrix=None)
    ctx = paint.create_context(None, (0, 0, 4, 4), None, None)
    assert isinstance(ctx, PatchMeshesShadingContext)


# ----------------------------------------------------------------------
# Pattern type fallback
# ----------------------------------------------------------------------
def test_pd_abstract_pattern_get_pattern_type_from_dict() -> None:
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.graphics.pattern.pd_abstract_pattern import (
        PDAbstractPattern,
    )

    dictionary = COSDictionary()
    dictionary.set_int(COSName.get_pdf_name("PatternType"), 1)
    pattern = PDAbstractPattern(dictionary)
    assert pattern.get_pattern_type() == 1


def test_pd_abstract_pattern_get_pattern_type_raises_without_entry() -> None:
    from pypdfbox.pdmodel.graphics.pattern.pd_abstract_pattern import (
        PDAbstractPattern,
    )

    pattern = PDAbstractPattern.__new__(PDAbstractPattern)
    from pypdfbox.cos import COSDictionary

    pattern._dict = COSDictionary()
    with pytest.raises(NotImplementedError):
        pattern.get_pattern_type()
