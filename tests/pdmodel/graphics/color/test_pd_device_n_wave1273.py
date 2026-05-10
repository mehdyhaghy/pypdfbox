"""Wave 1273 round-out: ``PDDeviceNProcess.to_string()`` explicit method."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceNProcess


def test_to_string_empty() -> None:
    process = PDDeviceNProcess()
    # No /ColorSpace and no /Components — Java appends ``null`` for the
    # color space; pypdfbox lite path surfaces ``None`` instead (the
    # ``get_color_space`` lenient default).
    assert process.to_string() == "Process{None}"


def test_to_string_with_components() -> None:
    dictionary = COSDictionary()
    dictionary.set_item("ColorSpace", COSName.get_pdf_name("DeviceCMYK"))
    components = COSArray()
    components.add(COSName.get_pdf_name("Cyan"))
    components.add(COSName.get_pdf_name("Magenta"))
    dictionary.set_item("Components", components)

    process = PDDeviceNProcess(dictionary)
    # Mirrors upstream ``PDDeviceNProcess.toString()`` —
    # ``Process{<color-space> "<comp0>" "<comp1>" ...}``.
    assert process.to_string() == 'Process{DeviceCMYK "Cyan" "Magenta"}'


def test_to_string_matches_str() -> None:
    dictionary = COSDictionary()
    dictionary.set_item("ColorSpace", COSName.get_pdf_name("DeviceGray"))
    process = PDDeviceNProcess(dictionary)
    assert process.to_string() == str(process)
