"""Deep parity tests for the ``/Decode`` validation logic shared by
``PDShadingType4`` / ``5`` / ``6`` / ``7`` (the four mesh-based shading
types). Mirrors upstream
``PDTriangleBasedShadingType.getDecodeForParameter`` plus the per-subtype
``collect_triangles`` / ``generate_patch`` consumers.

The math/format guard surface:
  * ``/Decode`` must be a numeric ``COSArray`` of length ``2 * (2 + N)``
    where ``N`` is the number of color components.
  * Index 0 = x-coordinate range, 1 = y-coordinate range, ``2 + i`` =
    component-i range.
  * Negative indexes and out-of-range entries return ``None`` (never raise).
  * Non-numeric pair entries return ``None`` (defensive parsing).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)
from pypdfbox.pdmodel.graphics.shading import (
    PDShadingType4,
    PDShadingType5,
    PDShadingType6,
    PDShadingType7,
)

_MESH_TYPES = (PDShadingType4, PDShadingType5, PDShadingType6, PDShadingType7)


# ---------------------------------------------------------------------------
# get_decode_for_parameter — base contract uniform across types 4-7
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cls", _MESH_TYPES)
def test_get_decode_for_parameter_returns_none_when_decode_absent(cls):
    shading = cls()
    for param_num in (0, 1, 2, 5):
        assert shading.get_decode_for_parameter(param_num) is None


@pytest.mark.parametrize("cls", _MESH_TYPES)
def test_get_decode_for_parameter_returns_none_when_not_an_array(cls):
    shading = cls()
    # Set /Decode to a name instead of an array — must reject gracefully.
    shading.get_cos_object().set_item(
        COSName.get_pdf_name("Decode"), COSName.get_pdf_name("Bad")
    )
    assert shading.get_decode_for_parameter(0) is None


@pytest.mark.parametrize("cls", _MESH_TYPES)
def test_get_decode_for_parameter_rejects_negative_index(cls):
    shading = cls()
    shading.set_decode([0.0, 1.0, 0.0, 1.0])
    assert shading.get_decode_for_parameter(-1) is None
    assert shading.get_decode_for_parameter(-100) is None


@pytest.mark.parametrize("cls", _MESH_TYPES)
def test_get_decode_for_parameter_returns_none_when_array_too_short(cls):
    shading = cls()
    # Provide only the x range (2 entries) — y range query (index 1) needs
    # entries at positions 2 and 3 which are absent.
    shading.set_decode([0.0, 1.0])
    assert shading.get_decode_for_parameter(1) is None
    # Index 0 succeeds because positions 0 and 1 are present.
    assert shading.get_decode_for_parameter(0) == (0.0, 1.0)


@pytest.mark.parametrize("cls", _MESH_TYPES)
def test_get_decode_for_parameter_returns_none_when_pair_is_non_numeric(cls):
    shading = cls()
    # Build a /Decode array where the y-range pair contains a non-numeric
    # entry. Upstream's ``PDRange`` ctor would throw; we mirror by returning
    # None per the project's defensive-parsing convention.
    arr = COSArray()
    arr.add(COSFloat(0.0))
    arr.add(COSFloat(1.0))
    arr.add(COSName.get_pdf_name("Bogus"))  # non-numeric
    arr.add(COSFloat(2.0))
    shading.set_decode(arr)
    assert shading.get_decode_for_parameter(1) is None
    # But the x range (entirely numeric) still resolves.
    assert shading.get_decode_for_parameter(0) == (0.0, 1.0)


@pytest.mark.parametrize("cls", _MESH_TYPES)
def test_get_decode_for_parameter_accepts_integer_pairs(cls):
    shading = cls()
    # Mixing COSInteger with the implicit COSFloat from set_decode must
    # still yield a (float, float) pair.
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSInteger.get(100))
    shading.set_decode(arr)
    pair = shading.get_decode_for_parameter(0)
    assert pair == (0.0, 100.0)
    assert isinstance(pair[0], float)
    assert isinstance(pair[1], float)


# ---------------------------------------------------------------------------
# get_decode round-trip — sequence vs COSArray
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cls", _MESH_TYPES)
def test_get_decode_returns_none_when_absent(cls):
    assert cls().get_decode() is None


@pytest.mark.parametrize("cls", _MESH_TYPES)
def test_set_decode_with_list_stores_floats(cls):
    shading = cls()
    shading.set_decode([0.0, 100.0, 0.0, 200.0, 0.0, 1.0])
    assert shading.get_decode() == [0.0, 100.0, 0.0, 200.0, 0.0, 1.0]


@pytest.mark.parametrize("cls", _MESH_TYPES)
def test_set_decode_with_tuple_stores_floats(cls):
    shading = cls()
    shading.set_decode((0.0, 50.0, 0.0, 50.0, 0.0, 1.0))
    assert shading.get_decode() == [0.0, 50.0, 0.0, 50.0, 0.0, 1.0]


@pytest.mark.parametrize("cls", _MESH_TYPES)
def test_set_decode_with_generator_consumed_once(cls):
    shading = cls()
    # set_decode must accept an iterator and write a fresh COSArray.
    shading.set_decode(float(v) for v in range(6))
    assert shading.get_decode() == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]


@pytest.mark.parametrize("cls", _MESH_TYPES)
def test_set_decode_with_cos_array_preserves_instance(cls):
    shading = cls()
    arr = COSArray()
    for v in (0.0, 1.0, 0.0, 1.0, 0.0, 0.5):
        arr.add(COSFloat(v))
    shading.set_decode(arr)
    # Identity preserved (so any indirect refs survive serialization).
    assert shading.get_cos_object().get_dictionary_object("Decode") is arr


@pytest.mark.parametrize("cls", _MESH_TYPES)
def test_set_decode_with_none_clears_entry(cls):
    shading = cls()
    shading.set_decode([0.0, 1.0, 0.0, 1.0])
    shading.set_decode(None)
    assert shading.get_decode() is None
    assert shading.get_cos_object().get_dictionary_object("Decode") is None


# ---------------------------------------------------------------------------
# get_number_of_color_components dispatch
# ---------------------------------------------------------------------------


def _function_type2_dict() -> COSDictionary:
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
    return fn


@pytest.mark.parametrize("cls", _MESH_TYPES)
def test_get_number_of_color_components_function_pins_to_one(cls):
    shading = cls()
    shading.set_function(_function_type2_dict())
    assert shading.get_number_of_color_components() == 1


@pytest.mark.parametrize("cls", _MESH_TYPES)
def test_get_number_of_color_components_no_function_no_cs_returns_minus_one(cls):
    assert cls().get_number_of_color_components() == -1


# ---------------------------------------------------------------------------
# Edge: Type 4/5 collect_triangles guard branches
# ---------------------------------------------------------------------------


def test_type4_collect_triangles_skips_when_x_min_equals_max():
    # Degenerate x range — collect_triangles returns empty list per upstream.
    shading = PDShadingType4()
    shading.set_bits_per_flag(2)
    shading.set_decode([1.0, 1.0, 0.0, 1.0, 0.0, 1.0])  # x: 1..1 degenerate
    assert shading.collect_triangles() == []


def test_type5_collect_triangles_skips_when_y_min_equals_max():
    shading = PDShadingType5()
    shading.set_vertices_per_row(3)
    shading.set_decode([0.0, 1.0, 0.5, 0.5, 0.0, 1.0])  # y: 0.5..0.5 degenerate
    assert shading.collect_triangles() == []


def test_type5_collect_triangles_skips_when_vertices_per_row_zero():
    shading = PDShadingType5()
    shading.set_vertices_per_row(0)
    shading.set_decode([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    assert shading.collect_triangles() == []
