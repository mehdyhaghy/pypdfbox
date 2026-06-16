"""Fuzz/parity battery for the axial (Type 2) + radial (Type 3) shading
dictionary model (``PDShadingType2`` / ``PDShadingType3`` / ``PDShading``
base), wave 1572 agent C.

Focus is the dictionary accessors + coordinate / domain / extend / function
parsing, NOT the pixel rasterization. Each case pins behavior against
Apache PDFBox 3.0.7:

* ``getCoords`` / ``getDomain`` / ``getExtend`` all delegate to
  ``getCOSObject().getCOSArray(name)`` — they return the stored ``COSArray``
  or ``null``; they do **NOT** materialize the spec default ``[0 1]`` /
  ``[false false]`` and do not coerce to booleans. The default is applied by
  the shading *context*, not the model getter (see ``axial_shading_context``
  / ``radial_shading_context``).
* ``getAntiAlias`` → ``dictionary.getBoolean(ANTI_ALIAS, false)`` (default
  ``False``).
* ``getBackground`` → ``getCOSArray(BACKGROUND)`` or ``null``.
* ``getBBox`` → wraps ``getCOSArray(BBOX)`` in a ``PDRectangle`` or ``null``.
* ``getFunction`` wraps a single dictionary/stream function; for an array
  ``/Function`` pypdfbox returns the raw ``COSArray`` (documented divergence
  — upstream's ``PDFunction.create(COSArray)`` throws). ``evalFunction``
  dispatches a single function vs an array of per-component functions.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.common.function import PDFunction
from pypdfbox.pdmodel.graphics.shading import PDShadingType2, PDShadingType3
from pypdfbox.pdmodel.graphics.shading.pd_shading import PDShading

# ---------- helpers ----------


def _num_array(*values: float) -> COSArray:
    a = COSArray()
    for v in values:
        a.add(COSFloat(float(v)))
    return a


def _bool_array(*values: bool) -> COSArray:
    a = COSArray()
    for v in values:
        a.add(COSBoolean.get(bool(v)))
    return a


def _function_type2_dict(c0: float = 0.0, c1: float = 1.0, n: int = 1) -> COSDictionary:
    """Minimal Type 2 (exponential-interpolation) single-output function."""
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", _num_array(0.0, 1.0))
    d.set_item("C0", _num_array(c0))
    d.set_item("C1", _num_array(c1))
    d.set_int("N", n)
    return d


def _axial(coords=None) -> PDShadingType2:
    s = PDShadingType2()
    if coords is not None:
        s.set_coords(coords)
    return s


def _radial(coords=None) -> PDShadingType3:
    s = PDShadingType3()
    if coords is not None:
        s.set_coords(coords)
    return s


# ---------- shading-type number ----------


def test_axial_shading_type_is_two():
    s = PDShadingType2()
    assert s.get_shading_type() == 2
    assert s.get_shading_type() == PDShading.SHADING_TYPE2
    assert s.get_cos_object().get_int("ShadingType") == 2
    assert s.is_axial()
    assert not s.is_radial()
    assert not s.is_mesh_based()


def test_radial_shading_type_is_three():
    s = PDShadingType3()
    assert s.get_shading_type() == 3
    assert s.get_shading_type() == PDShading.SHADING_TYPE3
    assert s.get_cos_object().get_int("ShadingType") == 3
    assert s.is_radial()
    assert not s.is_axial()
    assert not s.is_mesh_based()


def test_subclass_get_shading_type_ignores_cos_value():
    # The concrete subclass returns its fixed code regardless of a stale
    # /ShadingType entry in COS (upstream returns the hard-coded constant).
    s = PDShadingType2()
    s.get_cos_object().set_int("ShadingType", 99)
    assert s.get_shading_type() == 2


# ---------- /Coords ----------


def test_axial_coords_four_numbers_roundtrip():
    s = _axial(_num_array(0.0, 0.0, 100.0, 0.0))
    coords = s.get_coords()
    assert coords is not None
    assert coords.to_float_array() == [0.0, 0.0, 100.0, 0.0]


def test_radial_coords_six_numbers_roundtrip():
    s = _radial(_num_array(0.0, 0.0, 0.0, 0.0, 0.0, 50.0))
    coords = s.get_coords()
    assert coords is not None
    assert coords.to_float_array() == [0.0, 0.0, 0.0, 0.0, 0.0, 50.0]


def test_axial_coords_missing_returns_none():
    assert PDShadingType2().get_coords() is None


def test_radial_coords_missing_returns_none():
    assert PDShadingType3().get_coords() is None


def test_coords_wrong_length_returned_verbatim():
    # The getter does no length validation — it returns whatever array is
    # stored (upstream getCOSArray returns the array as-is).
    s = _axial(_num_array(1.0, 2.0))  # only 2 of 4
    assert s.get_coords().to_float_array() == [1.0, 2.0]


def test_radial_coords_extra_length_returned_verbatim():
    s = _radial(_num_array(0, 0, 0, 0, 0, 50, 99, 100))  # 8 entries
    assert s.get_coords().size() == 8


def test_coords_non_array_returns_none():
    s = PDShadingType2()
    s.get_cos_object().set_item("Coords", COSInteger.get(5))
    assert s.get_coords() is None


def test_coords_set_none_removes_entry():
    s = _axial(_num_array(1, 2, 3, 4))
    s.set_coords(None)
    assert s.get_coords() is None
    assert not s.get_cos_object().contains_key(COSName.get_pdf_name("Coords"))


def test_radial_negative_radius_preserved():
    # r0/r1 read verbatim — sign is preserved (no clamping in the model).
    s = _radial(_num_array(0, 0, -5, 0, 0, -10))
    arr = s.get_coords().to_float_array()
    assert arr[2] == -5.0
    assert arr[5] == -10.0


# ---------- /Domain ----------


def test_axial_domain_roundtrip():
    s = PDShadingType2()
    s.set_domain(_num_array(0.0, 1.0))
    assert s.get_domain().to_float_array() == [0.0, 1.0]


def test_axial_domain_missing_returns_none_not_default():
    # Upstream getDomain() returns null when absent; the [0 1] default is
    # the *context*'s responsibility, never the model getter.
    assert PDShadingType2().get_domain() is None


def test_radial_domain_missing_returns_none_not_default():
    assert PDShadingType3().get_domain() is None


def test_domain_set_from_float_iterable():
    s = PDShadingType3()
    s.set_domain([0.25, 0.75])
    assert s.get_domain().to_float_array() == [0.25, 0.75]


def test_domain_non_array_returns_none():
    s = PDShadingType2()
    s.get_cos_object().set_item("Domain", COSString("nope"))
    assert s.get_domain() is None


def test_domain_set_none_removes():
    s = PDShadingType2()
    s.set_domain([0.0, 1.0])
    s.set_domain(None)
    assert s.get_domain() is None


def test_domain_wrong_length_returned_verbatim():
    s = PDShadingType3()
    s.set_domain([0.0, 0.5, 1.0])  # 3 entries
    assert s.get_domain().to_float_array() == [0.0, 0.5, 1.0]


# ---------- /Extend ----------


def test_axial_extend_roundtrip_true_false():
    s = PDShadingType2()
    s.set_extend(True, False)
    ext = s.get_extend()
    assert ext is not None
    assert ext.get_object(0).get_value() is True
    assert ext.get_object(1).get_value() is False


def test_extend_roundtrip_both_true():
    s = PDShadingType3()
    s.set_extend(True, True)
    ext = s.get_extend()
    assert ext.get_object(0).get_value() is True
    assert ext.get_object(1).get_value() is True


def test_extend_missing_returns_none_not_default():
    # Upstream getExtend() returns null when absent; the [false false]
    # default lives in the context, not the model getter.
    assert PDShadingType2().get_extend() is None
    assert PDShadingType3().get_extend() is None


def test_extend_single_cosarray_form():
    s = PDShadingType2()
    s.set_extend(_bool_array(False, True))
    ext = s.get_extend()
    assert ext.get_object(0).get_value() is False
    assert ext.get_object(1).get_value() is True


def test_extend_set_none_removes():
    s = PDShadingType3()
    s.set_extend(True, True)
    s.set_extend(None)
    assert s.get_extend() is None


def test_extend_wrong_length_returned_verbatim():
    # A 1-element /Extend is malformed per spec but the getter returns it
    # verbatim — it does no length check (matches getCOSArray).
    s = PDShadingType2()
    s.get_cos_object().set_item("Extend", _bool_array(True))
    ext = s.get_extend()
    assert ext.size() == 1
    assert ext.get_object(0).get_value() is True


def test_extend_non_array_returns_none():
    s = PDShadingType3()
    s.get_cos_object().set_item("Extend", COSBoolean.TRUE)
    assert s.get_extend() is None


def test_extend_truthy_coercion():
    # Two-arg form coerces non-bool truthy/falsy values via bool().
    s = PDShadingType2()
    s.set_extend(1, 0)
    ext = s.get_extend()
    assert ext.get_object(0).get_value() is True
    assert ext.get_object(1).get_value() is False


# ---------- /Function ----------


def test_function_single_dict_wrapped():
    s = PDShadingType2()
    s.set_function(_function_type2_dict())
    fn = s.get_function()
    assert isinstance(fn, PDFunction)
    assert fn.get_function_type() == 2


def test_function_absent_returns_none():
    assert PDShadingType2().get_function() is None
    assert PDShadingType3().get_function() is None


def test_function_array_returns_raw_cosarray():
    # DOCUMENTED DIVERGENCE: upstream getFunction() calls
    # PDFunction.create(COSArray) which throws; pypdfbox returns the raw
    # COSArray so callers can enumerate per-component functions.
    s = PDShadingType3()
    arr = COSArray()
    arr.add(_function_type2_dict(0.0, 1.0))
    arr.add(_function_type2_dict(0.0, 0.5))
    s.set_function(arr)
    fn = s.get_function()
    assert isinstance(fn, COSArray)
    assert fn.size() == 2


def test_functions_array_single_is_one_element_list():
    s = PDShadingType2()
    s.set_function(_function_type2_dict())
    fns = s.get_functions_array()
    assert len(fns) == 1
    assert isinstance(fns[0], PDFunction)


def test_functions_array_multi_enumerated():
    s = PDShadingType3()
    arr = COSArray()
    arr.add(_function_type2_dict(0.0, 1.0))
    arr.add(_function_type2_dict(0.0, 0.5))
    arr.add(_function_type2_dict(0.0, 0.25))
    s.set_function(arr)
    fns = s.get_functions_array()
    assert len(fns) == 3
    assert all(isinstance(f, PDFunction) for f in fns)


def test_functions_array_absent_is_empty_list():
    assert PDShadingType2().get_functions_array() == []


def test_function_set_none_removes():
    s = PDShadingType2()
    s.set_function(_function_type2_dict())
    s.set_function(None)
    assert s.get_function() is None
    assert s.get_functions_array() == []


def test_function_set_iterable_of_pdfunction():
    s = PDShadingType3()
    f0 = PDFunction.create(_function_type2_dict(0.0, 1.0))
    f1 = PDFunction.create(_function_type2_dict(0.0, 0.5))
    s.set_function([f0, f1])
    fn = s.get_function()
    assert isinstance(fn, COSArray)
    assert fn.size() == 2


# ---------- evalFunction dispatch ----------


def test_eval_function_single_clamped():
    # Type 2 with C0=[0], C1=[2], N=1 → at t=1 raw output 2.0, clamped to 1.0.
    s = _axial(_num_array(0, 0, 1, 0))
    s.set_function(_function_type2_dict(0.0, 2.0, 1))
    out = s.eval_function(1.0)
    assert out == [1.0]
    out0 = s.eval_function(0.0)
    assert out0 == [0.0]


def test_eval_function_array_per_component():
    # Array of single-output functions → one output per function.
    s = _radial(_num_array(0, 0, 0, 0, 0, 1))
    arr = COSArray()
    arr.add(_function_type2_dict(0.0, 1.0, 1))
    arr.add(_function_type2_dict(0.5, 0.5, 1))
    arr.add(_function_type2_dict(0.0, 0.25, 1))
    s.set_function(arr)
    out = s.eval_function(1.0)
    assert len(out) == 3
    assert out[0] == pytest.approx(1.0)
    assert out[1] == pytest.approx(0.5)
    assert out[2] == pytest.approx(0.25)


def test_eval_function_missing_raises():
    with pytest.raises(OSError):
        _axial(_num_array(0, 0, 1, 0)).eval_function(0.5)


def test_eval_function_negative_clamped_to_zero():
    s = _axial(_num_array(0, 0, 1, 0))
    s.set_function(_function_type2_dict(-3.0, -1.0, 1))
    assert s.eval_function(0.5) == [0.0]


# ---------- /ColorSpace ----------


def test_color_space_absent_is_none():
    assert PDShadingType2().get_color_space() is None
    assert PDShadingType2().get_color_space_object() is None
    assert not PDShadingType2().has_color_space()


def test_color_space_device_rgb_name():
    s = PDShadingType2()
    s.get_cos_object().set_item("ColorSpace", COSName.get_pdf_name("DeviceRGB"))
    assert s.has_color_space()
    assert s.get_color_space() == COSName.get_pdf_name("DeviceRGB")


def test_color_space_abbreviated_cs_fallback():
    # Upstream reads /CS as a fallback for /ColorSpace.
    s = PDShadingType3()
    s.get_cos_object().set_item("CS", COSName.get_pdf_name("DeviceGray"))
    assert s.has_color_space()
    assert s.get_color_space() == COSName.get_pdf_name("DeviceGray")


# ---------- /Background ----------


def test_background_absent_is_none():
    assert PDShadingType2().get_background() is None
    assert not PDShadingType2().has_background()


def test_background_numeric_array_roundtrip():
    s = PDShadingType3()
    s.set_background(_num_array(1.0, 0.0, 0.0))
    bg = s.get_background()
    assert bg is not None
    assert bg.to_float_array() == [1.0, 0.0, 0.0]
    assert s.has_background()


def test_background_non_array_is_none():
    s = PDShadingType2()
    s.get_cos_object().set_item("Background", COSInteger.get(7))
    assert s.get_background() is None


# ---------- /BBox ----------


def test_bbox_absent_is_none():
    assert PDShadingType2().get_b_box() is None
    assert PDShadingType2().get_b_box_rect() is None
    assert not PDShadingType2().has_b_box()


def test_bbox_four_numbers_roundtrip():
    s = PDShadingType3()
    s.set_b_box(_num_array(0.0, 0.0, 200.0, 100.0))
    assert s.has_b_box()
    rect = s.get_b_box_rect()
    assert rect is not None
    assert rect.get_lower_left_x() == 0.0
    assert rect.get_upper_right_x() == 200.0
    assert rect.get_upper_right_y() == 100.0


def test_bbox_short_array_rect_is_none():
    # get_b_box_rect requires >= 4 entries; a 2-entry array → None.
    s = PDShadingType2()
    s.get_cos_object().set_item("BBox", _num_array(1.0, 2.0))
    assert s.get_b_box_rect() is None


def test_bbox_non_array_is_none():
    s = PDShadingType2()
    s.get_cos_object().set_item("BBox", COSString("x"))
    assert s.get_b_box() is None
    assert s.get_b_box_rect() is None


# ---------- /AntiAlias ----------


def test_anti_alias_default_false():
    s = PDShadingType2()
    assert s.get_anti_alias() is False
    assert s.is_anti_alias() is False
    assert not s.has_anti_alias()


def test_anti_alias_true_roundtrip():
    s = PDShadingType3()
    s.set_anti_alias(True)
    assert s.get_anti_alias() is True
    assert s.is_anti_alias() is True
    assert s.has_anti_alias()


def test_anti_alias_explicit_false():
    s = PDShadingType2()
    s.set_anti_alias(False)
    assert s.get_anti_alias() is False
    assert s.has_anti_alias()  # present even though False


def test_anti_alias_non_boolean_value_default():
    # getBoolean(ANTI_ALIAS, false): a non-boolean value falls back to the
    # default False.
    s = PDShadingType2()
    s.get_cos_object().set_item("AntiAlias", COSInteger.get(1))
    assert s.get_anti_alias() is False
    assert not s.has_anti_alias()


# ---------- cross-type via PDShading.create dispatch ----------


def test_create_dispatches_axial():
    d = COSDictionary()
    d.set_int("ShadingType", 2)
    d.set_item("Coords", _num_array(0, 0, 1, 1))
    d.set_item("Function", _function_type2_dict())
    s = PDShading.create(d)
    assert isinstance(s, PDShadingType2)
    assert s.get_coords().to_float_array() == [0.0, 0.0, 1.0, 1.0]


def test_create_dispatches_radial():
    d = COSDictionary()
    d.set_int("ShadingType", 3)
    d.set_item("Coords", _num_array(0, 0, 0, 0, 0, 5))
    s = PDShading.create(d)
    assert isinstance(s, PDShadingType3)
    assert s.get_coords().size() == 6


def test_create_unknown_type_raises():
    d = COSDictionary()
    d.set_int("ShadingType", 9)
    with pytest.raises(OSError):
        PDShading.create(d)
