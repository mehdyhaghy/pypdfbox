"""Hand-written coverage tests for ``PDTriangleBasedShadingType`` and
``PDMeshBasedShadingType``.

The two abstract shading bases are exercised directly through a tiny
concrete subclass that supplies the ``shadingType`` constant. We drive:

* the bits-per-coordinate / -component caching getters and setters
* the ``/Decode`` array helpers including the out-of-range guard
* ``interpolate`` (zero-span and normal span)
* ``read_vertex`` / ``collect_triangles`` raise ``NotImplementedError``
* ``get_bounds`` returns ``None`` when the subclass cannot collect
  triangles, and computes a real bounding box when it can
* ``PDMeshBasedShadingType.generate_patch`` / ``read_patch`` raise
* ``PDMeshBasedShadingType.get_bounds`` aggregates triangles across
  every patch
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat
from pypdfbox.pdmodel.graphics.shading.pd_mesh_based_shading_type import (
    PDMeshBasedShadingType,
)
from pypdfbox.pdmodel.graphics.shading.pd_triangle_based_shading_type import (
    PDTriangleBasedShadingType,
)


class _StubTriangle:
    """Minimal stand-in for ``ShadedTriangle`` used by ``get_bounds``."""

    def __init__(self, corners: list[tuple[float, float]]) -> None:
        self.corner = corners


class _StubPatch:
    def __init__(self, triangles: list[_StubTriangle]) -> None:
        self.list_of_triangles = triangles


class _ConcreteTriangle(PDTriangleBasedShadingType):
    """Concrete triangle shading that lets tests inject the triangle list."""

    def __init__(
        self,
        dictionary: COSDictionary | None = None,
        triangles: list[_StubTriangle] | None = None,
    ) -> None:
        super().__init__(dictionary)
        self._triangles = triangles

    def get_shading_type(self) -> int:
        return PDTriangleBasedShadingType.SHADING_TYPE4

    def collect_triangles(
        self, xform: Any = None, matrix: Any = None
    ) -> list[Any]:
        if self._triangles is None:
            raise NotImplementedError
        return list(self._triangles)


class _ConcreteMesh(PDMeshBasedShadingType):
    """Concrete mesh shading that lets tests inject patches."""

    def __init__(
        self,
        dictionary: COSDictionary | None = None,
        patches: list[_StubPatch] | None = None,
    ) -> None:
        super().__init__(dictionary)
        self._patches = patches

    def get_shading_type(self) -> int:
        return PDMeshBasedShadingType.SHADING_TYPE6

    def collect_patches(
        self,
        xform: Any = None,
        matrix: Any = None,
        control_points: int = 12,
    ) -> list[Any]:
        if self._patches is None:
            raise NotImplementedError
        return list(self._patches)


def _dict_with(items: dict[str, int]) -> COSDictionary:
    d = COSDictionary()
    for k, v in items.items():
        d.set_int(k, v)
    return d


# ----------------------------------------------------------------------
# Bits-per-coordinate / -component getters + caching
# ----------------------------------------------------------------------


def test_bits_per_coordinate_returns_default_when_absent() -> None:
    shading = _ConcreteTriangle()
    assert shading.get_bits_per_coordinate() == -1
    # Cached on a second call.
    assert shading.get_bits_per_coordinate() == -1


def test_bits_per_coordinate_reads_dict_value() -> None:
    shading = _ConcreteTriangle(_dict_with({"BitsPerCoordinate": 16}))
    assert shading.get_bits_per_coordinate() == 16


def test_set_bits_per_coordinate_updates_dict_and_cache() -> None:
    shading = _ConcreteTriangle()
    shading.set_bits_per_coordinate(8)
    assert shading.get_bits_per_coordinate() == 8
    assert shading._dict.get_int("BitsPerCoordinate") == 8


def test_bits_per_component_returns_default_when_absent() -> None:
    shading = _ConcreteTriangle()
    assert shading.get_bits_per_component() == -1


def test_bits_per_component_reads_dict_value_and_caches() -> None:
    shading = _ConcreteTriangle(_dict_with({"BitsPerComponent": 12}))
    assert shading.get_bits_per_component() == 12
    assert shading.get_bits_per_component() == 12  # cached


def test_set_bits_per_component_updates_dict_and_cache() -> None:
    shading = _ConcreteTriangle()
    shading.set_bits_per_component(8)
    assert shading.get_bits_per_component() == 8


# ----------------------------------------------------------------------
# number_of_color_components
# ----------------------------------------------------------------------


def test_number_of_color_components_zero_without_function_or_cs() -> None:
    shading = _ConcreteTriangle()
    assert shading.get_number_of_color_components() == 0
    # Cached on a second call.
    assert shading.get_number_of_color_components() == 0


# ----------------------------------------------------------------------
# /Decode array
# ----------------------------------------------------------------------


def test_get_decode_values_returns_none_when_absent() -> None:
    shading = _ConcreteTriangle()
    assert shading.get_decode_values() is None


def test_set_decode_values_round_trips() -> None:
    shading = _ConcreteTriangle()
    arr = COSArray([COSFloat(0.0), COSFloat(1.0), COSFloat(0.0), COSFloat(255.0)])
    shading.set_decode_values(arr)
    out = shading.get_decode_values()
    assert out is arr


def test_get_decode_for_parameter_returns_none_when_missing() -> None:
    shading = _ConcreteTriangle()
    assert shading.get_decode_for_parameter(0) is None


def test_get_decode_for_parameter_returns_none_when_too_short() -> None:
    shading = _ConcreteTriangle()
    shading.set_decode_values(COSArray([COSFloat(0.0)]))
    assert shading.get_decode_for_parameter(0) is None


def test_get_decode_for_parameter_returns_min_max_pair() -> None:
    shading = _ConcreteTriangle()
    shading.set_decode_values(
        COSArray([COSFloat(0.0), COSFloat(1.0), COSFloat(2.0), COSFloat(3.0)])
    )
    assert shading.get_decode_for_parameter(0) == (0.0, 1.0)
    assert shading.get_decode_for_parameter(1) == (2.0, 3.0)


def test_get_decode_for_parameter_works_with_plain_list_fallback() -> None:
    """Coverage for the ``[base]`` fallback when ``decode_values`` is not a
    COSArray-like object (no ``.size`` / ``.get_object``)."""
    shading = _ConcreteTriangle()
    # Bypass set_decode_values (which would coerce to a COSArray-like) and
    # plant a bare list directly on the cached field.
    shading._decode = [0.0, 5.0, 10.0, 15.0]
    result = shading.get_decode_for_parameter(1)
    assert result == (10.0, 15.0)


def test_get_decode_for_parameter_returns_none_when_plain_list_too_short() -> None:
    shading = _ConcreteTriangle()
    shading._decode = [0.0, 1.0]
    assert shading.get_decode_for_parameter(1) is None


# ----------------------------------------------------------------------
# interpolate
# ----------------------------------------------------------------------


def test_interpolate_zero_span_returns_dst_min() -> None:
    assert PDTriangleBasedShadingType.interpolate(5.0, 0, 0.0, 1.0) == 0.0


def test_interpolate_normal_span() -> None:
    assert (
        PDTriangleBasedShadingType.interpolate(5.0, 10, 0.0, 100.0) == 50.0
    )


# ----------------------------------------------------------------------
# read_vertex / collect_triangles abstract
# ----------------------------------------------------------------------


def test_read_vertex_is_abstract() -> None:
    shading = _ConcreteTriangle()
    with pytest.raises(NotImplementedError):
        shading.read_vertex(None, 0, 0, None, None, None, None, None)


def test_collect_triangles_is_abstract_on_bare_base() -> None:
    # Bypass _ConcreteTriangle's override by calling the base directly.
    shading = _ConcreteTriangle()
    with pytest.raises(NotImplementedError):
        PDTriangleBasedShadingType.collect_triangles(shading)


# ----------------------------------------------------------------------
# get_bounds for triangle shading
# ----------------------------------------------------------------------


def test_get_bounds_returns_none_when_collect_raises() -> None:
    shading = _ConcreteTriangle(triangles=None)
    assert shading.get_bounds() is None


def test_get_bounds_returns_none_for_empty_triangle_list() -> None:
    shading = _ConcreteTriangle(triangles=[])
    assert shading.get_bounds() is None


def test_get_bounds_aggregates_triangle_corners() -> None:
    triangles = [
        _StubTriangle([(0.0, 0.0), (10.0, 0.0), (5.0, 10.0)]),
        _StubTriangle([(20.0, -5.0), (30.0, 5.0), (25.0, 15.0)]),
    ]
    shading = _ConcreteTriangle(triangles=triangles)
    x, y, w, h = shading.get_bounds()
    assert x == 0.0
    assert y == -5.0
    assert w == 30.0
    assert h == 20.0


# ----------------------------------------------------------------------
# PDMeshBasedShadingType — abstract method shape
# ----------------------------------------------------------------------


def test_mesh_generate_patch_is_abstract() -> None:
    mesh = _ConcreteMesh()
    with pytest.raises(NotImplementedError):
        mesh.generate_patch([(0.0, 0.0)], [[0.0]])


def test_mesh_collect_patches_returns_empty_when_not_a_stream() -> None:
    """Wave 1507: ``PDMeshBasedShadingType.collect_patches`` is no longer an
    abstract stub — it now mirrors upstream's concrete ``collectPatches``.
    When the backing object is a bare ``COSDictionary`` (not a ``COSStream``)
    it returns an empty list, exactly like upstream
    (``collectPatches`` returns ``Collections.emptyList()`` when the dict is
    not a ``COSStream``). Concrete Type 6 / 7 shadings inherit this working
    implementation."""
    mesh = _ConcreteMesh()
    assert PDMeshBasedShadingType.collect_patches(mesh) == []


def test_mesh_read_patch_is_abstract() -> None:
    mesh = _ConcreteMesh()
    with pytest.raises(NotImplementedError):
        mesh.read_patch(
            input_stream=None,
            is_free=False,
            implicit_edge=None,
            implicit_corner_color=None,
            max_src_coord=0,
            max_src_color=0,
            range_x=None,
            range_y=None,
            col_range=None,
            matrix=None,
            xform=None,
            control_points=12,
        )


# ----------------------------------------------------------------------
# Mesh get_bounds
# ----------------------------------------------------------------------


def test_mesh_get_bounds_returns_none_when_collect_raises() -> None:
    mesh = _ConcreteMesh(patches=None)
    assert mesh.get_bounds() is None


def test_mesh_get_bounds_returns_none_when_patches_empty() -> None:
    mesh = _ConcreteMesh(patches=[])
    assert mesh.get_bounds() is None


def test_mesh_get_bounds_returns_none_when_patches_have_no_triangles() -> None:
    mesh = _ConcreteMesh(patches=[_StubPatch(triangles=[])])
    assert mesh.get_bounds() is None


def test_mesh_get_bounds_aggregates_triangle_corners_over_patches() -> None:
    patches = [
        _StubPatch(
            triangles=[_StubTriangle([(0.0, 0.0), (10.0, 0.0), (5.0, 5.0)])]
        ),
        _StubPatch(
            triangles=[
                _StubTriangle([(20.0, -10.0), (30.0, 10.0), (25.0, 0.0)])
            ]
        ),
    ]
    mesh = _ConcreteMesh(patches=patches)
    x, y, w, h = mesh.get_bounds()
    assert x == 0.0
    assert y == -10.0
    assert w == 30.0
    assert h == 20.0
