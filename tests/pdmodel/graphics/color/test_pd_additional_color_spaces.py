from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation


# ---------- get_name correctness ----------


def test_pd_pattern_name() -> None:
    assert PDPattern().get_name() == "Pattern"


def test_pd_indexed_name() -> None:
    assert PDIndexed().get_name() == "Indexed"


def test_pd_separation_name() -> None:
    assert PDSeparation().get_name() == "Separation"


def test_pd_device_n_name() -> None:
    assert PDDeviceN().get_name() == "DeviceN"


def test_pd_icc_based_name() -> None:
    assert PDICCBased().get_name() == "ICCBased"


def test_pd_cal_gray_name() -> None:
    assert PDCalGray().get_name() == "CalGray"


def test_pd_cal_rgb_name() -> None:
    assert PDCalRGB().get_name() == "CalRGB"


def test_pd_lab_name() -> None:
    assert PDLab().get_name() == "Lab"


# ---------- get_number_of_components ----------


def test_pd_pattern_components() -> None:
    assert PDPattern().get_number_of_components() == 0


def test_pd_indexed_components() -> None:
    assert PDIndexed().get_number_of_components() == 1


def test_pd_separation_components() -> None:
    assert PDSeparation().get_number_of_components() == 1


def test_pd_device_n_components_matches_colorant_names() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["Cyan", "Magenta", "Yellow"])
    assert cs.get_number_of_components() == 3


def test_pd_icc_based_components_default_three() -> None:
    assert PDICCBased().get_number_of_components() == 3


def test_pd_cal_gray_components() -> None:
    assert PDCalGray().get_number_of_components() == 1


def test_pd_cal_rgb_components() -> None:
    assert PDCalRGB().get_number_of_components() == 3


def test_pd_lab_components() -> None:
    assert PDLab().get_number_of_components() == 3


# ---------- subclass checks ----------


def test_all_subclasses_extend_pd_color_space() -> None:
    for cls in (
        PDPattern,
        PDIndexed,
        PDSeparation,
        PDDeviceN,
        PDICCBased,
        PDCalGray,
        PDCalRGB,
        PDLab,
    ):
        assert issubclass(cls, PDColorSpace)


# ---------- initial colors ----------


def test_pd_indexed_initial_color_is_zero() -> None:
    assert PDIndexed().get_initial_color().get_components() == [0.0]


def test_pd_separation_initial_color_is_one() -> None:
    assert PDSeparation().get_initial_color().get_components() == [1.0]


def test_pd_cal_rgb_initial_color_is_black() -> None:
    assert PDCalRGB().get_initial_color().get_components() == [0.0, 0.0, 0.0]


# ---------- PDIndexed round-trips ----------


def test_pd_indexed_round_trip_hival_and_base() -> None:
    cs = PDIndexed()
    cs.set_base_color_space(PDDeviceRGB.INSTANCE)
    cs.set_hival(127)
    assert cs.get_hival() == 127
    arr = cs.get_cos_object()
    assert isinstance(arr, COSArray)
    assert isinstance(arr.get(0), COSName)
    assert arr.get_int(2) == 127


def test_pd_indexed_round_trip_lookup_bytes() -> None:
    # Default PDIndexed: hival=255, base=DeviceRGB (3 components), so the
    # canonical palette length is 768. get_lookup_data clamps the returned
    # bytes to that length — short payloads are right-padded with NULs.
    cs = PDIndexed()
    payload = bytes(range(0, 256, 4))  # 64 bytes < expected 768
    cs.set_lookup_data(payload)
    out = cs.get_lookup_data()
    assert out is not None
    assert out[: len(payload)] == payload
    assert len(out) == (cs.get_hival() + 1) * 3


def test_pd_indexed_lookup_from_cos_string() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(COSName.get_pdf_name("DeviceRGB"))
    arr.add(COSInteger.get(15))
    arr.add(COSString(b"\x00\x10\x20\x30"))
    cs = PDIndexed(arr)
    assert cs.get_hival() == 15
    # hival=15, DeviceRGB → expected 16 * 3 = 48 bytes; the 4-byte payload
    # is right-padded with NULs by get_lookup_data's defensive clamp.
    out = cs.get_lookup_data()
    assert out is not None
    assert out[:4] == b"\x00\x10\x20\x30"
    assert len(out) == 48
    assert out[4:] == b"\x00" * 44


# ---------- PDSeparation round-trip ----------


def test_pd_separation_colorant_name_round_trip() -> None:
    cs = PDSeparation()
    cs.set_colorant_name("PANTONE 185 C")
    assert cs.get_colorant_name() == "PANTONE 185 C"


def test_pd_separation_alternate_color_space_round_trip() -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDDeviceGray.INSTANCE)
    arr = cs.get_cos_object()
    assert isinstance(arr, COSArray)
    assert isinstance(arr.get(2), COSName)
    assert arr.get_name(2) == "DeviceGray"


# ---------- PDDeviceN ----------


def test_pd_device_n_colorant_names_round_trip() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["Cyan", "Magenta"])
    assert cs.get_colorant_names() == ["Cyan", "Magenta"]
    assert cs.get_number_of_components() == 2


def test_pd_device_n_initial_color_refresh() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["Cyan", "Magenta"])
    assert cs.get_initial_color().get_components() == [1.0, 1.0]


# ---------- PDICCBased ----------


def test_pd_icc_based_n_default_three() -> None:
    cs = PDICCBased()
    assert cs.get_n() == 3
    assert cs.get_number_of_components() == 3


def test_pd_icc_based_n_round_trip() -> None:
    cs = PDICCBased()
    cs.set_n(4)
    assert cs.get_n() == 4
    assert cs.get_number_of_components() == 4


def test_pd_icc_based_alternate_round_trip() -> None:
    cs = PDICCBased()
    cs.set_alternate(PDDeviceRGB.INSTANCE)
    alt_obj = cs.get_pdstream()
    assert alt_obj is not None
    name_entry = alt_obj.get_dictionary_object(COSName.get_pdf_name("Alternate"))
    assert isinstance(name_entry, COSName)
    assert name_entry.get_name() == "DeviceRGB"


def test_pd_icc_based_metadata_round_trip() -> None:
    cs = PDICCBased()
    md = COSStream()
    cs.set_metadata(md)
    assert cs.get_metadata() is md


# ---------- PDCalGray ----------


def test_pd_cal_gray_gamma_default_is_one() -> None:
    assert PDCalGray().get_gamma() == 1.0


def test_pd_cal_gray_gamma_round_trip() -> None:
    cs = PDCalGray()
    cs.set_gamma(2.2)
    assert cs.get_gamma() == pytest.approx(2.2)


def test_pd_cal_gray_white_point_round_trip() -> None:
    cs = PDCalGray()
    cs.set_white_point([0.95, 1.0, 1.09])
    assert cs.get_white_point() == pytest.approx([0.95, 1.0, 1.09])


def test_pd_cal_gray_default_white_point_is_unity() -> None:
    assert PDCalGray().get_white_point() == [1.0, 1.0, 1.0]


def test_pd_cal_gray_default_black_point_is_zero() -> None:
    assert PDCalGray().get_black_point() == [0.0, 0.0, 0.0]


# ---------- PDCalRGB ----------


def test_pd_cal_rgb_default_gamma_is_unity_triple() -> None:
    assert PDCalRGB().get_gamma() == [1.0, 1.0, 1.0]


def test_pd_cal_rgb_matrix_round_trip() -> None:
    cs = PDCalRGB()
    identity = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    cs.set_matrix(identity)
    assert cs.get_matrix() == identity


def test_pd_cal_rgb_matrix_default_is_none_until_set() -> None:
    assert PDCalRGB().get_matrix() is None


# ---------- PDLab ----------


def test_pd_lab_range_default() -> None:
    assert PDLab().get_range() == [-100.0, 100.0, -100.0, 100.0]


def test_pd_lab_range_round_trip() -> None:
    cs = PDLab()
    cs.set_range([-50.0, 50.0, -75.0, 75.0])
    assert cs.get_range() == [-50.0, 50.0, -75.0, 75.0]


def test_pd_lab_initial_color_uses_range_minimums() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Lab"))
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Range"), COSArray.of_cos_floats([10.0, 50.0, 20.0, 80.0]))
    arr.add(d)
    cs = PDLab(arr)
    assert cs.get_initial_color().get_components() == [0.0, 10.0, 20.0]


# ---------- PDPattern ----------


def test_pd_pattern_default_cos_object_is_name() -> None:
    cs = PDPattern()
    cos = cs.get_cos_object()
    assert isinstance(cos, COSName)
    assert cos.get_name() == "Pattern"


def test_pd_pattern_with_underlying_is_array() -> None:
    cs = PDPattern(PDDeviceRGB.INSTANCE)
    cos = cs.get_cos_object()
    assert isinstance(cos, COSArray)
    assert cos.size() == 2
    assert cs.get_underlying_color_space() is PDDeviceRGB.INSTANCE


# ---------- PDColorSpace.create dispatch ----------


@pytest.mark.skipif(
    not hasattr(PDColorSpace, "create"),
    reason="PDColorSpace.create factory not yet wired (see CLAUDE wiring instructions)",
)
def test_pd_color_space_create_dispatches_indexed() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(COSName.get_pdf_name("DeviceRGB"))
    arr.add(COSInteger.get(255))
    arr.add(COSString(b"\x00" * 768))
    cs = PDColorSpace.create(arr)  # type: ignore[attr-defined]
    assert isinstance(cs, PDIndexed)
    assert cs.get_hival() == 255


@pytest.mark.skipif(
    not hasattr(PDColorSpace, "create"),
    reason="PDColorSpace.create factory not yet wired (see CLAUDE wiring instructions)",
)
def test_pd_color_space_create_dispatches_device_rgb_name() -> None:
    cs = PDColorSpace.create(COSName.get_pdf_name("DeviceRGB"))  # type: ignore[attr-defined]
    assert cs is PDDeviceRGB.INSTANCE
