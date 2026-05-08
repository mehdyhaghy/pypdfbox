from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.graphics.color.pd_device_n import (
    PDDeviceNAttributes,
    PDDeviceNProcess,
)
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB


def test_process_color_space_helpers_round_trip_and_clear() -> None:
    process = PDDeviceNProcess()

    assert not process.has_color_space()
    assert process.get_color_space() is None

    process.set_color_space(PDDeviceRGB.INSTANCE)

    assert process.has_color_space()
    color_space = process.get_color_space()
    assert color_space is PDDeviceRGB.INSTANCE

    process.clear_color_space()

    assert not process.has_color_space()
    assert process.get_color_space() is None
    assert process.get_cos_dictionary().get_dictionary_object("ColorSpace") is None


def test_process_components_helpers_filter_malformed_entries_and_clear() -> None:
    process = PDDeviceNProcess()

    process.set_components(["Cyan", "Spot"])

    assert process.has_components()
    assert process.get_components() == ["Cyan", "Spot"]

    raw_components = COSArray()
    raw_components.add(COSName.get_pdf_name("Cyan"))
    raw_components.add(COSString("not-a-name"))
    raw_components.add(COSName.get_pdf_name("Spot"))
    process.get_cos_dictionary().set_item("Components", raw_components)

    assert process.has_components()
    assert process.get_components() == ["Cyan", "Spot"]

    process.clear_components()

    assert not process.has_components()
    assert process.get_components() == []


def test_process_malformed_recursive_color_space_is_absent() -> None:
    recursive = COSDictionary()
    recursive.set_item("ColorSpace", recursive)

    process = PDDeviceNProcess()
    process.get_cos_dictionary().set_item("ColorSpace", recursive)

    assert process.get_color_space() is None
    assert not process.has_color_space()


def test_attributes_process_helpers_accept_wrapper_dictionary_and_clear() -> None:
    attrs = PDDeviceNAttributes()
    process = PDDeviceNProcess()
    process.set_color_space(PDDeviceRGB.INSTANCE)
    process.set_components(["Red", "Green", "Blue"])

    attrs.set_process(process)

    assert attrs.has_process()
    resolved_process = attrs.get_process()
    assert resolved_process is not None
    assert resolved_process.get_components() == ["Red", "Green", "Blue"]

    raw_process = COSDictionary()
    raw_process.set_item("Components", COSArray.of_cos_names(["Gray"]))
    attrs.set_process(raw_process)

    assert attrs.has_process()
    resolved_process = attrs.get_process()
    assert resolved_process is not None
    assert resolved_process.get_components() == ["Gray"]

    attrs.clear_process()

    assert not attrs.has_process()
    assert attrs.get_process() is None
