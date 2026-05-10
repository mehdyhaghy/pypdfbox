"""Wave 1275 round-out: ``PDDeviceNAttributes.to_string()`` explicit method."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceNAttributes


def test_to_string_default_empty() -> None:
    attrs = PDDeviceNAttributes()
    # No /Subtype, no /Process, no /Colorants → just empty braces.
    # Mirrors upstream ``PDDeviceNAttributes.toString``
    # (PDDeviceNAttributes.java line 150).
    assert attrs.to_string() == "{Colorants{}}"


def test_to_string_with_subtype_only() -> None:
    dictionary = COSDictionary()
    dictionary.set_item("Subtype", COSName.get_pdf_name("NChannel"))
    attrs = PDDeviceNAttributes(dictionary)
    assert attrs.to_string() == "NChannel{Colorants{}}"


def test_to_string_matches_str() -> None:
    attrs = PDDeviceNAttributes()
    assert attrs.to_string() == str(attrs)
