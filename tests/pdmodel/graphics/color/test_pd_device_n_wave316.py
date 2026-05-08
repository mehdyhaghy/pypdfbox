from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceNAttributes


def test_wave316_device_n_colorants_skip_recursive_color_space() -> None:
    colorants = COSDictionary()
    recursive = COSDictionary()
    recursive.set_item(COSName.get_pdf_name("ColorSpace"), recursive)
    colorants.set_item("BrokenSpot", recursive)
    colorants.set_item("ProcessRGB", COSName.get_pdf_name("DeviceRGB"))

    attrs_dict = COSDictionary()
    attrs_dict.set_item("Colorants", colorants)
    attrs = PDDeviceNAttributes(attrs_dict)

    out = attrs.get_colorants()

    assert list(out) == ["ProcessRGB"]
    assert out["ProcessRGB"].get_name() == "DeviceRGB"
