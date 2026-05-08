from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB
from pypdfbox.pdmodel.graphics.color.pd_device_n import (
    PDDeviceN,
    PDDeviceNAttributes,
)
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from pypdfbox.pdmodel.pd_resources import PDResources


def _color_space_array(name: str) -> COSArray:
    array = COSArray()
    array.add(COSName.get_pdf_name(name))
    return array


def test_indexed_malformed_array_getters_are_lenient_and_setters_repair() -> None:
    cs = PDIndexed(_color_space_array("Indexed"))

    assert cs.get_base_color_space() is None
    assert not cs.has_base_color_space()
    assert cs.get_hival() == 0
    assert cs.get_lookup_data() is None
    assert not cs.has_lookup_data()

    cs.set_base_color_space(PDDeviceRGB.INSTANCE)
    cs.set_hival(1)
    cs.set_lookup_data(b"\x00\x7f\xff")

    assert cs.has_base_color_space()
    assert cs.get_hival() == 1
    assert cs.has_lookup_data()
    assert cs.get_lookup_data() == b"\x00\x7f\xff\x00\x00\x00"

    cs.clear_lookup_data()
    assert not cs.has_lookup_data()
    assert cs.get_lookup_data() is None


def test_separation_malformed_array_is_lenient_and_clearable() -> None:
    cs = PDSeparation(_color_space_array("Separation"))

    assert cs.get_colorant_name() is None
    assert cs.get_alternate_color_space() is None
    assert not cs.has_alternate_color_space()
    assert cs.get_tint_transform_cos() is None
    assert not cs.has_tint_transform()

    cs.set_colorant_name("Spot")
    cs.set_alternate_color_space(PDDeviceRGB.INSTANCE)
    cs.clear_tint_transform()

    assert cs.get_colorant_name() == "Spot"
    assert cs.has_alternate_color_space()
    assert cs.get_tint_transform() is None
    assert not cs.has_tint_transform()


def test_device_n_malformed_array_helpers_repair_and_clear() -> None:
    cs = PDDeviceN(_color_space_array("DeviceN"))

    assert cs.get_colorant_names() == []
    assert cs.get_alternate_color_space() is None
    assert not cs.has_alternate_color_space()
    assert cs.get_tint_transform_cos() is None
    assert not cs.has_tint_transform()
    assert not cs.has_attributes()

    attrs = PDDeviceNAttributes()
    attrs.set_subtype("NChannel")
    cs.set_colorant_names(["Cyan", "Spot"])
    cs.set_alternate_color_space(PDDeviceRGB.INSTANCE)
    cs.clear_tint_transform()
    cs.set_attributes(attrs)

    assert cs.get_colorant_names() == ["Cyan", "Spot"]
    assert cs.has_alternate_color_space()
    assert not cs.has_tint_transform()
    assert cs.has_attributes()

    cs.clear_attributes()
    assert not cs.has_attributes()


def test_device_n_attributes_has_and_clear_optional_dictionaries() -> None:
    attrs = PDDeviceNAttributes()
    attrs.get_cos_dictionary().set_item("Process", COSDictionary())
    attrs.get_cos_dictionary().set_item("MixingHints", COSDictionary())
    attrs.set_colorants({"Spot": PDDeviceRGB.INSTANCE})

    assert attrs.has_process()
    assert attrs.has_mixing_hints()
    assert attrs.has_colorants()

    attrs.clear_mixing_hints()
    attrs.clear_colorants()

    assert attrs.has_process()
    assert not attrs.has_mixing_hints()
    assert not attrs.has_colorants()


def test_icc_based_has_and_clear_optional_entries() -> None:
    cs = PDICCBased()
    rng = COSArray.of_cos_floats([0.1, 0.9])
    metadata = COSStream()

    cs.set_alternate(PDDeviceRGB.INSTANCE)
    cs.set_range(rng)
    cs.set_metadata(metadata)

    assert cs.has_alternate()
    assert cs.has_range()
    assert cs.has_metadata()

    cs.clear_alternate()
    cs.clear_range()
    cs.clear_metadata()

    assert not cs.has_alternate()
    assert not cs.has_range()
    assert not cs.has_metadata()
    assert cs.get_range_for_component(0) == (0.0, 1.0)


def test_cie_color_spaces_have_clear_and_presence_helpers() -> None:
    gray = PDCalGray()
    gray.set_black_point([0.1, 0.2, 0.3])
    gray.set_gamma(2.2)
    assert gray.has_black_point()
    assert gray.has_gamma()
    gray.clear_black_point()
    gray.clear_gamma()
    assert not gray.has_black_point()
    assert not gray.has_gamma()
    assert gray.get_black_point() == [0.0, 0.0, 0.0]
    assert gray.get_gamma() == 1.0

    rgb = PDCalRGB()
    rgb.set_gamma([2.0, 2.1, 2.2])
    rgb.set_matrix([1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0])
    assert rgb.has_gamma()
    assert rgb.has_matrix()
    rgb.clear_gamma()
    rgb.clear_matrix()
    assert not rgb.has_gamma()
    assert not rgb.has_matrix()

    lab = PDLab()
    lab.set_range([-50.0, 50.0, -25.0, 25.0])
    assert lab.has_range()
    assert lab.get_initial_color().get_components() == [0.0, 0.0, 0.0]
    lab.set_a_range((10.0, 50.0))
    assert lab.get_initial_color().get_components() == [0.0, 10.0, 0.0]
    lab.clear_range()
    assert not lab.has_range()
    assert lab.get_range() == [-100.0, 100.0, -100.0, 100.0]
    assert lab.get_initial_color().get_components() == [0.0, 0.0, 0.0]


def test_pattern_resources_have_presence_and_clear_helpers() -> None:
    pattern = PDPattern(resources=PDResources())

    assert pattern.has_resources()
    pattern.clear_resources()
    assert not pattern.has_resources()
