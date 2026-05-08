from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.color.pd_device_n import (
    PDDeviceNAttributes,
)
from pypdfbox.pdmodel.graphics.color.pd_device_n import (
    PDDeviceNProcess as CanonicalPDDeviceNProcess,
)
from pypdfbox.pdmodel.graphics.color.pd_device_n_process import PDDeviceNProcess


def test_standalone_module_reexports_canonical_process_class() -> None:
    assert PDDeviceNProcess is CanonicalPDDeviceNProcess


def test_standalone_process_interoperates_with_attributes_setter() -> None:
    process = PDDeviceNProcess()
    process.set_components(["Cyan", "Spot"])

    attributes = PDDeviceNAttributes()
    attributes.set_process(process)

    resolved = attributes.get_process()
    assert resolved is not None
    assert resolved.get_components() == ["Cyan", "Spot"]


def test_str_empty_default_matches_pdfbox_to_string() -> None:
    assert str(PDDeviceNProcess()) == "Process{None}"


def test_str_renders_color_space_and_components() -> None:
    dictionary = COSDictionary()
    dictionary.set_item("ColorSpace", COSName.get_pdf_name("DeviceCMYK"))
    dictionary.set_item(
        "Components",
        COSArray.of_cos_names(["Cyan", "Magenta", "Yellow", "Black"]),
    )

    assert (
        str(PDDeviceNProcess(dictionary))
        == 'Process{DeviceCMYK "Cyan" "Magenta" "Yellow" "Black"}'
    )


def test_str_skips_malformed_component_entries() -> None:
    components = COSArray()
    components.add(COSName.get_pdf_name("Cyan"))
    components.add(COSDictionary())
    components.add(COSName.get_pdf_name("Spot"))
    dictionary = COSDictionary()
    dictionary.set_item("Components", components)

    assert str(PDDeviceNProcess(dictionary)) == 'Process{None "Cyan" "Spot"}'
