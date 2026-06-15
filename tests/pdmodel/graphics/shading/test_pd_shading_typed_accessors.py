"""Round-out tests for :class:`PDShading` typed accessors and
shading-type predicate helpers added in Wave 199.

Covers four small parity gaps against upstream
``org.apache.pdfbox.pdmodel.graphics.shading.PDShading``:

1. ``get_b_box_rect`` / ``set_b_box_rect`` — typed ``PDRectangle``
   accessors (mirroring upstream's ``getBBox()``/``setBBox(PDRectangle)``).
2. ``get_color_space_object`` / ``set_color_space_object`` — typed
   ``PDColorSpace`` accessors with the upstream-compatible
   ``/CS`` short-form fallback (mirroring
   ``COSDictionary.getDictionaryObject(COSName.CS, COSName.COLORSPACE)``).
3. Shading-type predicates: ``is_function_based``, ``is_axial``,
   ``is_radial``, ``is_mesh_based``.
4. ``is_anti_alias`` boolean predicate companion plus
   ``is_valid_shading_type`` range validator.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
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
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# ---------- get_b_box_rect / set_b_box_rect ----------


def test_get_b_box_rect_returns_none_when_absent():
    s = PDShadingType2()
    assert s.get_b_box_rect() is None


def test_get_b_box_rect_unwraps_cos_array_to_pd_rectangle():
    s = PDShadingType2()
    arr = COSArray()
    for v in (10.0, 20.0, 110.0, 220.0):
        arr.add(COSFloat(v))
    s.set_b_box(arr)

    rect = s.get_b_box_rect()

    assert isinstance(rect, PDRectangle)
    assert rect.lower_left_x == 10.0
    assert rect.lower_left_y == 20.0
    assert rect.upper_right_x == 110.0
    assert rect.upper_right_y == 220.0


def test_get_b_box_rect_returns_none_for_short_array():
    # A 3-entry array isn't a valid bbox; typed accessor refuses rather
    # than fabricating a default.
    s = PDShadingType2()
    short = COSArray()
    for v in (0.0, 0.0, 100.0):
        short.add(COSFloat(v))
    s.set_b_box(short)

    assert s.get_b_box_rect() is None


def test_get_b_box_rect_coerces_non_numeric_entries():
    # Heterogeneous 4-entry arrays (e.g. a stray name) are coerced by
    # upstream ``new PDRectangle(COSArray)``: the non-numeric slot becomes
    # 0.0 and corners normalize, so ``[0, 0, 100, /NotANumber]`` yields
    # ``PDRectangle(0, 0, 100, 0)``.
    s = PDShadingType2()
    bogus = COSArray()
    for v in (0.0, 0.0, 100.0):
        bogus.add(COSFloat(v))
    bogus.add(COSName.get_pdf_name("NotANumber"))
    s.set_b_box(bogus)

    assert s.get_b_box_rect() == PDRectangle(0.0, 0.0, 100.0, 0.0)


def test_set_b_box_rect_accepts_pd_rectangle():
    s = PDShadingType2()
    rect = PDRectangle(5.0, 10.0, 50.0, 100.0)
    s.set_b_box_rect(rect)

    stored = s.get_cos_object().get_dictionary_object("BBox")
    assert isinstance(stored, COSArray)
    assert stored.size() == 4
    # Values are written as COSFloat in lower-left-first order.
    assert [stored.get_object(i).value for i in range(4)] == [5.0, 10.0, 50.0, 100.0]
    # Round-trip through the typed accessor.
    rt = s.get_b_box_rect()
    assert rt is not None
    assert rt.lower_left_x == 5.0
    assert rt.upper_right_y == 100.0


def test_set_b_box_rect_accepts_cos_array_unchanged():
    s = PDShadingType2()
    arr = COSArray()
    for v in (1.0, 2.0, 3.0, 4.0):
        arr.add(COSFloat(v))
    s.set_b_box_rect(arr)

    assert s.get_cos_object().get_dictionary_object("BBox") is arr


def test_set_b_box_rect_with_none_clears_entry():
    s = PDShadingType2()
    s.set_b_box_rect(PDRectangle(0.0, 0.0, 100.0, 100.0))
    assert s.get_cos_object().get_dictionary_object("BBox") is not None

    s.set_b_box_rect(None)

    assert s.get_cos_object().get_dictionary_object("BBox") is None
    assert s.get_b_box_rect() is None


def test_set_b_box_rect_rejects_unsupported_type():
    s = PDShadingType2()
    with pytest.raises(TypeError):
        s.set_b_box_rect("not a rectangle")  # type: ignore[arg-type]


# ---------- get_color_space_object / set_color_space_object ----------


def test_get_color_space_object_returns_none_when_absent():
    s = PDShadingType2()
    assert s.get_color_space_object() is None


def test_get_color_space_object_dispatches_device_rgb_name():
    s = PDShadingType2()
    s.set_color_space(COSName.get_pdf_name("DeviceRGB"))

    cs = s.get_color_space_object()

    assert cs is PDDeviceRGB.INSTANCE


def test_get_color_space_object_dispatches_device_gray_name():
    s = PDShadingType1()
    s.set_color_space(COSName.get_pdf_name("DeviceGray"))

    cs = s.get_color_space_object()

    assert cs is PDDeviceGray.INSTANCE


def test_get_color_space_object_dispatches_device_cmyk_name():
    s = PDShadingType3()
    s.set_color_space(COSName.get_pdf_name("DeviceCMYK"))

    cs = s.get_color_space_object()

    assert cs is PDDeviceCMYK.INSTANCE


def test_get_color_space_object_falls_back_to_cs_short_form():
    # Upstream looks up /CS as a fallback when /ColorSpace is absent.
    # Per PDFBox's COSDictionary.getDictionaryObject(CS, COLORSPACE).
    s = PDShadingType2()
    s.get_cos_object().set_item(
        COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceRGB")
    )

    cs = s.get_color_space_object()

    assert cs is PDDeviceRGB.INSTANCE


def test_get_color_space_object_prefers_color_space_over_cs():
    # When both are present /ColorSpace wins (it's the primary key).
    s = PDShadingType2()
    s.get_cos_object().set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    s.get_cos_object().set_item(
        COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceCMYK")
    )

    cs = s.get_color_space_object()

    assert cs is PDDeviceRGB.INSTANCE


def test_set_color_space_object_accepts_pd_color_space_singleton():
    s = PDShadingType2()
    s.set_color_space_object(PDDeviceRGB.INSTANCE)

    stored = s.get_cos_object().get_dictionary_object("ColorSpace")
    assert stored is PDDeviceRGB.INSTANCE.get_cos_object()
    # Round-trip via the typed getter.
    assert s.get_color_space_object() is PDDeviceRGB.INSTANCE


def test_set_color_space_object_accepts_raw_cos_name():
    s = PDShadingType2()
    name = COSName.get_pdf_name("DeviceCMYK")
    s.set_color_space_object(name)

    assert s.get_cos_object().get_dictionary_object("ColorSpace") is name


def test_set_color_space_object_with_none_clears_entry():
    s = PDShadingType2()
    s.set_color_space_object(PDDeviceRGB.INSTANCE)
    assert s.get_cos_object().get_dictionary_object("ColorSpace") is not None

    s.set_color_space_object(None)

    assert s.get_cos_object().get_dictionary_object("ColorSpace") is None
    assert s.get_color_space_object() is None


def test_set_color_space_object_rejects_unsupported_type():
    s = PDShadingType2()
    with pytest.raises(TypeError):
        s.set_color_space_object(42)  # type: ignore[arg-type]


# ---------- shading-type predicates ----------


def test_is_function_based_only_for_type1():
    assert PDShadingType1().is_function_based() is True
    assert PDShadingType2().is_function_based() is False
    assert PDShadingType3().is_function_based() is False
    assert PDShadingType4().is_function_based() is False
    assert PDShadingType5().is_function_based() is False
    assert PDShadingType6().is_function_based() is False
    assert PDShadingType7().is_function_based() is False


def test_is_axial_only_for_type2():
    assert PDShadingType1().is_axial() is False
    assert PDShadingType2().is_axial() is True
    assert PDShadingType3().is_axial() is False
    assert PDShadingType4().is_axial() is False


def test_is_radial_only_for_type3():
    assert PDShadingType1().is_radial() is False
    assert PDShadingType2().is_radial() is False
    assert PDShadingType3().is_radial() is True
    assert PDShadingType7().is_radial() is False


def test_is_mesh_based_for_types_4_through_7():
    assert PDShadingType1().is_mesh_based() is False
    assert PDShadingType2().is_mesh_based() is False
    assert PDShadingType3().is_mesh_based() is False
    assert PDShadingType4().is_mesh_based() is True
    assert PDShadingType5().is_mesh_based() is True
    assert PDShadingType6().is_mesh_based() is True
    assert PDShadingType7().is_mesh_based() is True


def test_predicates_partition_the_shading_type_space():
    # Every concrete shading instance is in exactly one of the four
    # predicate families.
    instances = [
        PDShadingType1(),
        PDShadingType2(),
        PDShadingType3(),
        PDShadingType4(),
        PDShadingType5(),
        PDShadingType6(),
        PDShadingType7(),
    ]
    for s in instances:
        flags = (
            s.is_function_based(),
            s.is_axial(),
            s.is_radial(),
            s.is_mesh_based(),
        )
        # Exactly one True per instance.
        assert sum(1 for f in flags if f) == 1


# ---------- is_anti_alias ----------


def test_is_anti_alias_default_is_false():
    assert PDShadingType2().is_anti_alias() is False


def test_is_anti_alias_round_trip_via_setter():
    s = PDShadingType2()
    s.set_anti_alias(True)
    assert s.is_anti_alias() is True
    s.set_anti_alias(False)
    assert s.is_anti_alias() is False


# ---------- is_valid_shading_type ----------


@pytest.mark.parametrize("value", [1, 2, 3, 4, 5, 6, 7])
def test_is_valid_shading_type_accepts_defined_ids(value):
    assert PDShading.is_valid_shading_type(value) is True


@pytest.mark.parametrize("value", [0, -1, 8, 99, 1000])
def test_is_valid_shading_type_rejects_out_of_range(value):
    assert PDShading.is_valid_shading_type(value) is False


def test_is_valid_shading_type_rejects_non_int():
    assert PDShading.is_valid_shading_type("1") is False  # type: ignore[arg-type]
    assert PDShading.is_valid_shading_type(None) is False  # type: ignore[arg-type]
    assert PDShading.is_valid_shading_type(3.0) is False  # type: ignore[arg-type]


def test_is_valid_shading_type_aligns_with_create_dispatch():
    # Whatever PDShading.create accepts, is_valid_shading_type should
    # also accept (and vice versa for non-dispatchable values).
    for t in (1, 2, 3):
        d = COSDictionary()
        d.set_int("ShadingType", t)
        assert PDShading.create(d) is not None
        assert PDShading.is_valid_shading_type(t) is True
    for t in (4, 5, 6, 7):
        st = COSStream()
        st.set_int("ShadingType", t)
        assert PDShading.create(st) is not None
        assert PDShading.is_valid_shading_type(t) is True
    # And invalid types are rejected by both the predicate and create().
    bad = COSDictionary()
    bad.set_int("ShadingType", 99)
    with pytest.raises(OSError):
        PDShading.create(bad)
    assert PDShading.is_valid_shading_type(99) is False
