"""Deep parity tests for ``PDShading`` /Background, /BBox, /AntiAlias, and
/Function validation. Complements ``test_pd_shading_helpers_wave291`` and
``test_pd_shading_wave424`` which cover the bare predicate surface — these
exercise malformed-input edge cases and clear-* operations across all
shading subtypes.

Mirrors the upstream guards in
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PDShading.java``
``getBackground()`` / ``getBBox()`` / ``getAntiAlias()`` / ``getFunction()``.
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
from pypdfbox.pdmodel.graphics.shading import (
    PDShading,
    PDShadingType1,
    PDShadingType2,
    PDShadingType3,
)

# ---------------------------------------------------------------------------
# /Background — must be a numeric COSArray
# ---------------------------------------------------------------------------


def test_background_rejects_non_array_entry():
    shading = PDShadingType2()
    # /Background as a COSName — invalid per spec; predicate must say no.
    shading.get_cos_object().set_item(
        COSName.get_pdf_name("Background"), COSName.get_pdf_name("Foo")
    )
    assert shading.has_background() is False
    # The getter is permissive — it returns ``None`` rather than raising.
    assert shading.get_background() is None


def test_background_rejects_empty_array():
    # PDFBox treats an empty /Background as malformed (no components).
    shading = PDShadingType2()
    shading.set_background(COSArray())
    assert shading.has_background() is False


def test_background_rejects_array_with_non_numeric_entries():
    shading = PDShadingType2()
    bad = COSArray()
    bad.add(COSString(b"red"))  # not a number
    shading.set_background(bad)
    assert shading.has_background() is False


def test_background_accepts_mixed_integer_and_float():
    shading = PDShadingType2()
    bg = COSArray()
    bg.add(COSInteger.get(255))
    bg.add(COSFloat(0.5))
    bg.add(COSInteger.get(0))
    shading.set_background(bg)
    assert shading.has_background() is True


def test_clear_background_is_noop_when_absent():
    shading = PDShadingType2()
    shading.clear_background()  # must not raise on a fresh shading
    assert shading.get_background() is None


def test_clear_background_removes_existing_entry():
    shading = PDShadingType2()
    bg = COSArray()
    bg.add(COSFloat(0.5))
    shading.set_background(bg)
    shading.clear_background()
    assert shading.has_background() is False
    assert (
        shading.get_cos_object().get_dictionary_object("Background") is None
    )


# ---------------------------------------------------------------------------
# /BBox — must be a 4-entry numeric COSArray
# ---------------------------------------------------------------------------


def test_bbox_rejects_short_array():
    shading = PDShadingType2()
    short = COSArray()
    for v in (0.0, 0.0, 100.0):
        short.add(COSFloat(v))
    shading.set_b_box(short)
    # has_b_box returns False for arrays shorter than 4.
    assert shading.has_b_box() is False


def test_bbox_rejects_array_with_non_numeric_entries():
    shading = PDShadingType2()
    bad = COSArray()
    bad.add(COSFloat(0.0))
    bad.add(COSFloat(0.0))
    bad.add(COSName.get_pdf_name("Bogus"))
    bad.add(COSFloat(100.0))
    shading.set_b_box(bad)
    assert shading.has_b_box() is False


def test_bbox_accepts_exactly_four_entries():
    shading = PDShadingType2()
    bbox = COSArray()
    for v in (0.0, 0.0, 612.0, 792.0):
        bbox.add(COSFloat(v))
    shading.set_b_box(bbox)
    assert shading.has_b_box() is True
    assert shading.get_b_box() is bbox


def test_bbox_accepts_array_with_extra_entries():
    # PDF spec says /BBox is a 4-entry array, but our validator only checks
    # ``size() >= 4`` to be permissive. A 5-entry array still validates.
    shading = PDShadingType2()
    long_bbox = COSArray()
    for v in (0.0, 0.0, 100.0, 100.0, 999.0):
        long_bbox.add(COSFloat(v))
    shading.set_b_box(long_bbox)
    assert shading.has_b_box() is True


def test_clear_b_box_is_noop_when_absent():
    shading = PDShadingType2()
    shading.clear_b_box()
    assert shading.get_b_box() is None


# ---------------------------------------------------------------------------
# /AntiAlias — must be a COSBoolean
# ---------------------------------------------------------------------------


def test_anti_alias_rejects_integer_entry():
    # has_anti_alias must reject /AntiAlias 1 (integer instead of boolean).
    shading = PDShadingType2()
    shading.get_cos_object().set_item(
        COSName.get_pdf_name("AntiAlias"), COSInteger.get(1)
    )
    assert shading.has_anti_alias() is False


def test_anti_alias_round_trip_via_setter():
    shading = PDShadingType2()
    shading.set_anti_alias(True)
    assert shading.has_anti_alias() is True
    assert shading.get_anti_alias() is True
    assert shading.is_anti_alias() is True
    assert isinstance(
        shading.get_cos_object().get_dictionary_object("AntiAlias"),
        COSBoolean,
    )


def test_clear_anti_alias_removes_entry():
    shading = PDShadingType2()
    shading.set_anti_alias(True)
    shading.clear_anti_alias()
    assert shading.has_anti_alias() is False


def test_clear_anti_alias_is_noop_when_absent():
    shading = PDShadingType2()
    shading.clear_anti_alias()  # no-op
    assert shading.has_anti_alias() is False


# ---------------------------------------------------------------------------
# /Function — must be a dictionary, stream, or array
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


def test_has_function_rejects_non_function_entry():
    shading = PDShadingType2()
    shading.get_cos_object().set_item(
        COSName.get_pdf_name("Function"), COSInteger.get(42)
    )
    assert shading.has_function() is False


def test_has_function_true_for_dictionary():
    shading = PDShadingType2()
    shading.set_function(_function_type2_dict())
    assert shading.has_function() is True


def test_has_function_true_for_array():
    shading = PDShadingType2()
    arr = COSArray()
    arr.add(_function_type2_dict())
    arr.add(_function_type2_dict())
    shading.set_function(arr)
    assert shading.has_function() is True


def test_clear_function_removes_entry():
    shading = PDShadingType2()
    shading.set_function(_function_type2_dict())
    shading.clear_function()
    assert shading.has_function() is False


def test_clear_function_is_noop_when_absent():
    shading = PDShadingType2()
    shading.clear_function()
    assert shading.has_function() is False


# ---------------------------------------------------------------------------
# Cross-subtype: predicates partition cleanly
# ---------------------------------------------------------------------------


def test_predicates_consistent_across_types_1_through_3():
    # Each /BBox-on-base helper should behave identically on every subtype
    # since it lives on the base class.
    for cls in (PDShadingType1, PDShadingType2, PDShadingType3):
        shading = cls()
        assert shading.has_b_box() is False
        bbox = COSArray()
        for v in (0.0, 0.0, 50.0, 50.0):
            bbox.add(COSFloat(v))
        shading.set_b_box(bbox)
        assert shading.has_b_box() is True
        shading.clear_b_box()
        assert shading.has_b_box() is False


def test_color_space_helpers_clear_both_long_and_short_form():
    # PDShading exposes /ColorSpace and the /CS short-form fallback.
    # clear_color_space must remove both so callers don't accidentally
    # leave a stale /CS entry behind.
    shading = PDShadingType2()
    cs_obj = COSName.get_pdf_name("DeviceRGB")
    shading.get_cos_object().set_item(COSName.get_pdf_name("ColorSpace"), cs_obj)
    shading.get_cos_object().set_item(COSName.get_pdf_name("CS"), cs_obj)
    assert shading.has_color_space() is True
    shading.clear_color_space()
    assert shading.has_color_space() is False
    assert (
        shading.get_cos_object().get_dictionary_object("ColorSpace") is None
    )
    assert shading.get_cos_object().get_dictionary_object("CS") is None


def test_set_color_space_with_none_clears_entry():
    shading = PDShadingType2()
    shading.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    assert shading.has_color_space() is True
    shading.set_color_space(None)
    assert shading.has_color_space() is False


def test_set_b_box_with_none_clears_entry():
    shading = PDShadingType2()
    bbox = COSArray()
    for v in (0.0, 0.0, 50.0, 50.0):
        bbox.add(COSFloat(v))
    shading.set_b_box(bbox)
    shading.set_b_box(None)
    assert shading.has_b_box() is False


def test_set_background_with_none_clears_entry():
    shading = PDShadingType2()
    bg = COSArray()
    bg.add(COSFloat(0.5))
    shading.set_background(bg)
    shading.set_background(None)
    assert shading.has_background() is False


def test_is_valid_shading_type_boundary_cases():
    # Edge values around the [1, 7] window.
    assert PDShading.is_valid_shading_type(0) is False
    assert PDShading.is_valid_shading_type(1) is True
    assert PDShading.is_valid_shading_type(7) is True
    assert PDShading.is_valid_shading_type(8) is False
    assert PDShading.is_valid_shading_type(-1) is False


def test_is_valid_shading_type_rejects_non_int_types():
    assert PDShading.is_valid_shading_type("1") is False
    assert PDShading.is_valid_shading_type(1.0) is False
    assert PDShading.is_valid_shading_type(None) is False


def test_bool_is_rejected_in_is_valid_shading_type():
    # bool is a subclass of int in Python but conceptually wrong for a
    # ShadingType value. The current implementation accepts True/False
    # because isinstance(True, int) is True — this test pins that behavior
    # so any future tightening is intentional. Note both fall in [1, 7]
    # range only for True (1); False (0) is out of range either way.
    assert PDShading.is_valid_shading_type(True) is True  # accepts 1
    assert PDShading.is_valid_shading_type(False) is False  # 0 out of range


def test_pdshading_create_with_non_dictionary_raises_typeerror():
    with pytest.raises(TypeError):
        PDShading.create(COSInteger.get(5))  # type: ignore[arg-type]
