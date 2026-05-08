from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.color.pd_device_n_process import PDDeviceNProcess


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
