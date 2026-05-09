from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB
from pypdfbox.pdmodel.graphics.color.pd_device_n import (
    PDDeviceN,
    PDDeviceNAttributes,
    PDDeviceNProcess,
)
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab


class _NoCosObject:
    def get_cos_object(self) -> None:
        return None


def _cie_array(name: str, params: object) -> COSArray:
    arr = COSArray()
    arr.add(COSName.get_pdf_name(name))
    arr.add(params)
    return arr


def test_wave726_cal_gray_accessors_and_invalid_dictionary_slot() -> None:
    cs = PDCalGray()
    assert cs.get_initial_color().get_components() == [0.0]
    assert cs.has_white_point() is False
    cs.set_white_point([1.0, 1.0, 1.0])
    assert cs.has_white_point() is True

    with pytest.raises(TypeError, match="CalGray array index 1"):
        PDCalGray(_cie_array("CalGray", COSName.get_pdf_name("Bad"))).get_gamma()


def test_wave726_cal_gray_short_white_point_falls_back_to_default() -> None:
    cs = PDCalGray()
    params = cs.get_cos_object().get_object(1)
    assert isinstance(params, COSDictionary)
    params.set_item(
        COSName.get_pdf_name("WhitePoint"),
        COSArray.of_cos_floats([1.0, 1.0]),
    )
    assert cs.get_white_point() == [1.0, 1.0, 1.0]
    assert cs.is_white_point() is True

    cs.set_white_point([0.5, 1.0, 1.0])
    assert cs.is_white_point() is False
    with pytest.raises(ValueError, match="requires one component"):
        cs.to_rgb([])


def test_wave726_cal_gray_to_rgb_clamps_and_exercises_srgb_edges() -> None:
    cs = PDCalGray()
    cs.set_white_point([1.0, 1.0, 1.0])

    assert cs.to_rgb([-0.5]) == (0.0, 0.0, 0.0)
    assert cs.to_rgb([2.0])[0] == pytest.approx(1.0)

    low = cs.to_rgb([0.0001])
    assert 0.0 < low[1] < 0.002

    with pytest.raises(ValueError, match="requires one component"):
        cs.to_rgb([])


def test_wave726_cal_rgb_invalid_slot_flags_and_short_paths() -> None:
    cs = PDCalRGB()
    assert cs.has_white_point() is False
    assert cs.has_black_point() is False
    cs.set_white_point([1.0, 1.0, 1.0])
    cs.set_black_point([0.1, 0.2, 0.3])
    assert cs.has_white_point() is True
    assert cs.has_black_point() is True
    cs.clear_black_point()
    assert cs.has_black_point() is False

    params = cs.get_cos_object().get_object(1)
    assert isinstance(params, COSDictionary)
    params.set_item(
        COSName.get_pdf_name("WhitePoint"),
        COSArray.of_cos_floats([1.0, 1.0]),
    )
    assert cs.is_white_point() is False

    with pytest.raises(TypeError, match="CalRGB array index 1"):
        PDCalRGB(_cie_array("CalRGB", COSName.get_pdf_name("Bad"))).get_gamma()


def test_wave726_cal_rgb_to_rgb_validates_components_and_short_matrix() -> None:
    cs = PDCalRGB()
    cs.set_matrix([1.0, 0.0, 0.0])

    with pytest.raises(ValueError, match="three components"):
        cs.to_rgb([0.1, 0.2])

    assert cs.to_rgb([-1.0, 2.0, 0.0]) == pytest.approx(cs.to_rgb([0.0, 1.0, 0.0]))


def test_wave726_lab_invalid_slot_flags_and_fallback_decode() -> None:
    cs = PDLab()
    assert cs.has_white_point() is False
    assert cs.has_black_point() is False
    cs.set_white_point([1.0, 1.0, 1.0])
    cs.set_black_point([0.1, 0.2, 0.3])
    assert cs.has_white_point() is True
    assert cs.has_black_point() is True
    cs.clear_black_point()
    assert cs.has_black_point() is False

    params = cs.get_cos_object().get_object(1)
    assert isinstance(params, COSDictionary)
    params.set_item(
        COSName.get_pdf_name("WhitePoint"),
        COSArray.of_cos_floats([1.0, 1.0]),
    )
    params.set_item(COSName.get_pdf_name("Range"), COSArray.of_cos_floats([-5.0]))
    assert cs.is_white_point() is False
    assert cs.get_default_decode(8) == [
        0.0,
        100.0,
        -100.0,
        100.0,
        -100.0,
        100.0,
    ]

    with pytest.raises(TypeError, match="Lab array index 1"):
        PDLab(_cie_array("Lab", COSName.get_pdf_name("Bad"))).get_range()


def test_wave726_device_n_rejects_color_spaces_without_cos_form() -> None:
    process = PDDeviceNProcess()
    attrs = PDDeviceNAttributes()
    cs = PDDeviceN()

    with pytest.raises(TypeError, match="color space with a COS form"):
        process.set_color_space(_NoCosObject())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="color spaces with COS forms"):
        attrs.set_colorants({"Broken": _NoCosObject()})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="alternate_color_space"):
        cs.set_alternate_color_space(_NoCosObject())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="object with a COS form"):
        cs.set_tint_transform(_NoCosObject())


def test_wave726_device_n_colorants_skip_none_and_string_separates_entries() -> None:
    colorants = COSDictionary()
    colorants.set_item("Missing", COSName.get_pdf_name("UnknownColorSpace"))
    colorants.set_item("RGB", COSName.get_pdf_name("DeviceRGB"))
    colorants.set_item("CMYK", COSName.get_pdf_name("DeviceCMYK"))
    attrs_dict = COSDictionary()
    attrs_dict.set_name("Subtype", "DeviceN")
    attrs_dict.set_item("Colorants", colorants)

    attrs = PDDeviceNAttributes(attrs_dict)

    assert list(attrs.get_colorants()) == ["RGB", "CMYK"]
    assert str(attrs) == 'DeviceN{Colorants{"RGB": DeviceRGB "CMYK": DeviceCMYK}}'


def test_wave726_device_n_initial_color_refresh_and_short_array_slots() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    cs = PDDeviceN(arr)
    assert cs.get_alternate_color_space() is None
    assert cs.get_tint_transform_cos() is None

    cs.set_colorant_names(["A", "B"])
    assert cs.get_initial_color().get_components() == [1.0, 1.0]

    cs.clear_tint_transform()
    assert isinstance(cs.get_tint_transform_cos(), COSName)


def test_wave726_device_n_set_tint_transform_accepts_raw_float() -> None:
    cs = PDDeviceN()
    raw = COSFloat(0.5)

    cs.set_tint_transform(raw)

    assert cs.get_tint_transform_cos() is raw
