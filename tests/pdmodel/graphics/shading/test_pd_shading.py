from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSStream
from pypdfbox.pdmodel.graphics.shading import (
    PDShading,
    PDShadingType1,
    PDShadingType2,
    PDShadingType3,
    PDShadingType4,
    PDShadingType5,
    PDShadingType6,
    PDShadingType7,
)

# ---------- shading-type identity ----------


def test_pd_shading_is_abstract():
    base = PDShading(COSDictionary())
    with pytest.raises(NotImplementedError):
        base.get_shading_type()


def test_type1_fresh_has_correct_shading_type():
    s = PDShadingType1()
    assert s.get_shading_type() == 1
    assert s.get_cos_object().get_int("ShadingType") == 1


def test_type2_fresh_has_correct_shading_type():
    s = PDShadingType2()
    assert s.get_shading_type() == 2
    assert s.get_cos_object().get_int("ShadingType") == 2


def test_type3_fresh_has_correct_shading_type():
    s = PDShadingType3()
    assert s.get_shading_type() == 3
    assert s.get_cos_object().get_int("ShadingType") == 3


def test_type4_fresh_has_correct_shading_type():
    s = PDShadingType4()
    assert s.get_shading_type() == 4
    assert s.get_cos_object().get_int("ShadingType") == 4
    # Type 4-7 are stream-based.
    assert isinstance(s.get_cos_object(), COSStream)


def test_type5_fresh_has_correct_shading_type():
    s = PDShadingType5()
    assert s.get_shading_type() == 5
    assert s.get_cos_object().get_int("ShadingType") == 5
    assert isinstance(s.get_cos_object(), COSStream)


def test_type6_fresh_has_correct_shading_type():
    s = PDShadingType6()
    assert s.get_shading_type() == 6
    assert s.get_cos_object().get_int("ShadingType") == 6
    assert isinstance(s.get_cos_object(), COSStream)


def test_type7_fresh_has_correct_shading_type():
    s = PDShadingType7()
    assert s.get_shading_type() == 7
    assert s.get_cos_object().get_int("ShadingType") == 7
    assert isinstance(s.get_cos_object(), COSStream)


# ---------- inherited PDShading surface ----------


def test_pd_shading_anti_alias_round_trip():
    s = PDShadingType2()
    assert s.get_anti_alias() is False
    s.set_anti_alias(True)
    assert s.get_anti_alias() is True


def test_pd_shading_bbox_round_trip():
    s = PDShadingType2()
    assert s.get_b_box() is None
    bbox = COSArray()
    for v in (0.0, 0.0, 100.0, 100.0):
        bbox.add(COSFloat(v))
    s.set_b_box(bbox)
    assert s.get_b_box() is bbox
    s.set_b_box(None)
    assert s.get_b_box() is None


def test_pd_shading_background_round_trip():
    s = PDShadingType2()
    assert s.get_background() is None
    bg = COSArray()
    bg.add(COSFloat(0.5))
    s.set_background(bg)
    assert s.get_background() is bg


# ---------- type-specific accessors ----------


def test_type2_axial_coords_round_trip():
    s = PDShadingType2()
    coords = COSArray()
    for v in (0, 0, 100, 0):
        coords.add(COSFloat(float(v)))
    s.set_coords(coords)
    got = s.get_coords()
    assert got is coords
    assert got.size() == 4
    assert [got.get_object(i).value for i in range(4)] == [0.0, 0.0, 100.0, 0.0]


def test_type3_radial_coords_round_trip():
    s = PDShadingType3()
    coords = COSArray()
    for v in (50, 50, 0, 50, 50, 100):
        coords.add(COSFloat(float(v)))
    s.set_coords(coords)
    got = s.get_coords()
    assert got is coords
    assert got.size() == 6
    assert [got.get_object(i).value for i in range(6)] == [
        50.0,
        50.0,
        0.0,
        50.0,
        50.0,
        100.0,
    ]


def test_type1_domain_and_matrix_round_trip():
    s = PDShadingType1()
    domain = COSArray()
    for v in (0.0, 1.0, 0.0, 1.0):
        domain.add(COSFloat(v))
    s.set_domain(domain)
    assert s.get_domain() is domain

    matrix = COSArray()
    for v in (1.0, 0.0, 0.0, 1.0, 0.0, 0.0):
        matrix.add(COSFloat(v))
    s.set_matrix(matrix)
    assert s.get_matrix() is matrix


def test_type4_mesh_metadata_round_trip():
    s = PDShadingType4()
    s.set_bits_per_coordinate(16)
    s.set_bits_per_component(8)
    s.set_bits_per_flag(2)
    assert s.get_bits_per_coordinate() == 16
    assert s.get_bits_per_component() == 8
    assert s.get_bits_per_flag() == 2

    decode = COSArray()
    for v in (0.0, 100.0, 0.0, 100.0, 0.0, 1.0):
        decode.add(COSFloat(v))
    s.set_decode(decode)
    assert s.get_decode() == [0.0, 100.0, 0.0, 100.0, 0.0, 1.0]
    assert s.get_cos_object().get_dictionary_object("Decode") is decode


def test_type5_vertices_per_row_round_trip():
    s = PDShadingType5()
    s.set_vertices_per_row(4)
    assert s.get_vertices_per_row() == 4


# ---------- factory dispatch ----------


def _make_shading_dict(shading_type: int) -> COSDictionary:
    d = COSDictionary()
    d.set_int("ShadingType", shading_type)
    return d


def _make_shading_stream(shading_type: int) -> COSStream:
    s = COSStream()
    s.set_int("ShadingType", shading_type)
    return s


def test_create_dispatches_type1():
    s = PDShading.create(_make_shading_dict(1))
    assert isinstance(s, PDShadingType1)
    assert s.get_shading_type() == 1


def test_create_dispatches_type2():
    s = PDShading.create(_make_shading_dict(2))
    assert isinstance(s, PDShadingType2)
    assert s.get_shading_type() == 2


def test_create_dispatches_type3():
    s = PDShading.create(_make_shading_dict(3))
    assert isinstance(s, PDShadingType3)
    assert s.get_shading_type() == 3


def test_create_dispatches_type4():
    s = PDShading.create(_make_shading_stream(4))
    assert isinstance(s, PDShadingType4)
    assert s.get_shading_type() == 4


def test_create_dispatches_type5():
    s = PDShading.create(_make_shading_stream(5))
    assert isinstance(s, PDShadingType5)


def test_create_dispatches_type6():
    s = PDShading.create(_make_shading_stream(6))
    assert isinstance(s, PDShadingType6)


def test_create_dispatches_type7():
    s = PDShading.create(_make_shading_stream(7))
    assert isinstance(s, PDShadingType7)


def test_create_returns_none_for_none_input():
    assert PDShading.create(None) is None


def test_create_rejects_non_dictionary():
    with pytest.raises(TypeError):
        PDShading.create(COSArray())  # type: ignore[arg-type]


def test_create_rejects_invalid_shading_type():
    with pytest.raises(OSError):
        PDShading.create(_make_shading_dict(99))


def test_create_requires_stream_for_type4_through_7():
    for t in (4, 5, 6, 7):
        with pytest.raises(OSError):
            PDShading.create(_make_shading_dict(t))


# ---------- base /Function + eval_function + bounds (PDShading parity) ----------


def _make_axial_function(c0: tuple[float, ...], c1: tuple[float, ...]) -> COSDictionary:
    """Build a Type 2 (axial / exponential interpolation) function dict."""
    fn = COSDictionary()
    fn.set_int("FunctionType", 2)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    fn.set_item("Domain", domain)
    c0_arr = COSArray()
    for v in c0:
        c0_arr.add(COSFloat(v))
    fn.set_item("C0", c0_arr)
    c1_arr = COSArray()
    for v in c1:
        c1_arr.add(COSFloat(v))
    fn.set_item("C1", c1_arr)
    fn.set_int("N", 1)
    return fn


def test_pd_shading_get_function_returns_typed_pdfunction():
    s = PDShadingType2()
    fn_dict = _make_axial_function((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    s.get_cos_object().set_item("Function", fn_dict)
    fn = s.get_function()
    assert fn is not None
    assert fn.get_function_type() == 2


def test_pd_shading_get_function_returns_none_when_absent():
    # Use a fresh base (abstract) instance — no /Function entry.
    s = PDShading(COSDictionary())
    assert s.get_function() is None


def test_pd_shading_get_functions_array_unwraps_array_form():
    s = PDShadingType2()
    arr = COSArray()
    arr.add(_make_axial_function((0.0,), (1.0,)))
    arr.add(_make_axial_function((0.0,), (0.5,)))
    arr.add(_make_axial_function((0.0,), (0.25,)))
    s.get_cos_object().set_item("Function", arr)
    funcs = s.get_functions_array()
    assert len(funcs) == 3
    assert all(f.get_function_type() == 2 for f in funcs)


def test_pd_shading_get_functions_array_empty_when_absent():
    s = PDShading(COSDictionary())
    assert s.get_functions_array() == []


def test_pd_shading_set_function_round_trip_via_base():
    # Set on the abstract base (used directly via a concrete subclass).
    s = PDShadingType2()
    fn_dict = _make_axial_function((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    # Bypass the subclass override to exercise the base method explicitly.
    PDShading.set_function(s, fn_dict)
    assert s.get_cos_object().get_dictionary_object("Function") is fn_dict
    PDShading.set_function(s, None)
    assert s.get_cos_object().get_dictionary_object("Function") is None


def test_pd_shading_eval_function_clamps_to_unit_interval():
    # Axial fn with C1 > 1 — eval must clamp result to [0, 1].
    s = PDShadingType2()
    fn = _make_axial_function((0.0,), (5.0,))
    s.get_cos_object().set_item("Function", fn)
    out = s.eval_function(1.0)
    assert out == [1.0]


def test_pd_shading_eval_function_clamps_negative_to_zero():
    s = PDShadingType2()
    fn = _make_axial_function((-3.0,), (-1.0,))
    s.get_cos_object().set_item("Function", fn)
    out = s.eval_function(0.0)
    assert out == [0.0]


def test_pd_shading_eval_function_accepts_scalar_or_sequence():
    s = PDShadingType2()
    fn = _make_axial_function((0.0,), (0.5,))
    s.get_cos_object().set_item("Function", fn)
    # Scalar input form (upstream ``evalFunction(float)``).
    assert s.eval_function(1.0) == [0.5]
    # Sequence input form (upstream ``evalFunction(float[])``).
    assert s.eval_function([1.0]) == [0.5]


def test_pd_shading_eval_function_array_form():
    # When /Function is an array, each function contributes one component.
    s = PDShadingType2()
    arr = COSArray()
    arr.add(_make_axial_function((0.0,), (0.25,)))
    arr.add(_make_axial_function((0.0,), (0.5,)))
    arr.add(_make_axial_function((0.0,), (0.75,)))
    s.get_cos_object().set_item("Function", arr)
    out = s.eval_function(1.0)
    assert out == [0.25, 0.5, 0.75]


def test_pd_shading_eval_function_raises_when_function_missing():
    s = PDShading(COSDictionary())
    with pytest.raises(OSError):
        s.eval_function(0.5)


def test_pd_shading_get_bounds_default_is_none():
    # PDShading.getBounds default returns null upstream; we mirror with None.
    s = PDShadingType2()
    assert s.get_bounds() is None
    # Both args optional and ignored for the default impl.
    assert s.get_bounds(None, None) is None
