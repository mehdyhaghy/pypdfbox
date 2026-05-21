"""Wave 1368 ``PDColorSpace.create`` dispatch matrix.

Exhaustively cover every recognised name + array form so future re-syncs
catch a missed dispatch arm.

Names (long + short inline forms):
  ``/DeviceGray`` ``/G``  → :class:`PDDeviceGray`
  ``/DeviceRGB``  ``/RGB`` → :class:`PDDeviceRGB`
  ``/DeviceCMYK`` ``/CMYK`` → :class:`PDDeviceCMYK`
  ``/Pattern``     → :class:`PDPattern` (colored)

Arrays (head COSName):
  ``[/Indexed ...]`` / ``[/I ...]`` → :class:`PDIndexed`
  ``[/Separation ...]``             → :class:`PDSeparation`
  ``[/DeviceN ...]``                → :class:`PDDeviceN`
  ``[/ICCBased <stream>]``          → :class:`PDICCBased`
  ``[/CalGray <dict>]``             → :class:`PDCalGray`
  ``[/CalRGB <dict>]``              → :class:`PDCalRGB`
  ``[/Lab <dict>]``                 → :class:`PDLab`
  ``[/Pattern <CS>]``               → :class:`PDPattern` (uncolored)
  ``[/DeviceGray]`` / ``[/G]``      → :class:`PDDeviceGray`
  ``[/DeviceRGB]``  / ``[/RGB]``    → :class:`PDDeviceRGB`
  ``[/DeviceCMYK]`` / ``[/CMYK]``   → :class:`PDDeviceCMYK`

Plus the PDFBOX-4833 dictionary-wrapping unwrap path and the PDFBOX-5315
self-referencing-dictionary recursion guard.
"""

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
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation

# ---------- name-form dispatch ----------


@pytest.mark.parametrize(
    ("name", "expected_singleton"),
    [
        ("DeviceGray", "device_gray"),
        ("G", "device_gray"),
        ("DeviceRGB", "device_rgb"),
        ("RGB", "device_rgb"),
        ("DeviceCMYK", "device_cmyk"),
        ("CMYK", "device_cmyk"),
    ],
    ids=[
        "long-gray",
        "short-G",
        "long-rgb",
        "short-RGB",
        "long-cmyk",
        "short-CMYK",
    ],
)
def test_create_name_returns_device_singleton(
    name: str, expected_singleton: str
) -> None:
    singletons = {
        "device_gray": PDDeviceGray.INSTANCE,
        "device_rgb": PDDeviceRGB.INSTANCE,
        "device_cmyk": PDDeviceCMYK.INSTANCE,
    }
    cs = PDColorSpace.create(COSName.get_pdf_name(name))
    assert cs is singletons[expected_singleton]


def test_create_pattern_name_returns_colored_pattern() -> None:
    cs = PDColorSpace.create(COSName.get_pdf_name("Pattern"))
    assert isinstance(cs, PDPattern)
    assert cs.is_colored() is True


def test_create_unknown_name_returns_none_without_resources() -> None:
    cs = PDColorSpace.create(COSName.get_pdf_name("DefaultUnknown"))
    assert cs is None


def test_create_none_returns_none() -> None:
    assert PDColorSpace.create(None) is None


# ---------- array-form dispatch ----------


def _arr(*items) -> COSArray:
    arr = COSArray()
    for x in items:
        arr.add(x)
    return arr


@pytest.mark.parametrize(
    ("head_name", "expected_singleton"),
    [
        ("DeviceGray", "device_gray"),
        ("G", "device_gray"),
        ("DeviceRGB", "device_rgb"),
        ("RGB", "device_rgb"),
        ("DeviceCMYK", "device_cmyk"),
        ("CMYK", "device_cmyk"),
    ],
    ids=[
        "arr-long-gray",
        "arr-short-G",
        "arr-long-rgb",
        "arr-short-RGB",
        "arr-long-cmyk",
        "arr-short-CMYK",
    ],
)
def test_create_array_with_device_name_head_returns_singleton(
    head_name: str, expected_singleton: str
) -> None:
    singletons = {
        "device_gray": PDDeviceGray.INSTANCE,
        "device_rgb": PDDeviceRGB.INSTANCE,
        "device_cmyk": PDDeviceCMYK.INSTANCE,
    }
    cs = PDColorSpace.create(_arr(COSName.get_pdf_name(head_name)))
    assert cs is singletons[expected_singleton]


def test_create_indexed_array_dispatches_to_indexed() -> None:
    arr = _arr(
        COSName.get_pdf_name("Indexed"),
        PDDeviceRGB.INSTANCE.get_cos_object(),
        COSInteger.get(1),
        COSString(b"\x00\x00\x00\xff\xff\xff"),
    )
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDIndexed)


def test_create_indexed_short_form_I_dispatches_to_indexed() -> None:
    arr = _arr(
        COSName.get_pdf_name("I"),
        PDDeviceRGB.INSTANCE.get_cos_object(),
        COSInteger.get(0),
        COSString(b"\x00\x00\x00"),
    )
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDIndexed)


def test_create_separation_array_dispatches_to_separation() -> None:
    arr = _arr(
        COSName.get_pdf_name("Separation"),
        COSName.get_pdf_name("Spot1"),
        PDDeviceRGB.INSTANCE.get_cos_object(),
        COSName.get_pdf_name(""),
    )
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDSeparation)
    assert cs.get_colorant_name() == "Spot1"


def test_create_devicen_array_dispatches_to_devicen() -> None:
    names = COSArray()
    names.add(COSName.get_pdf_name("Cyan"))
    arr = _arr(
        COSName.get_pdf_name("DeviceN"),
        names,
        PDDeviceRGB.INSTANCE.get_cos_object(),
        COSName.get_pdf_name(""),
    )
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDDeviceN)
    assert cs.get_colorant_names() == ["Cyan"]


def test_create_iccbased_array_dispatches_to_iccbased() -> None:
    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("N"), 3)
    arr = _arr(COSName.get_pdf_name("ICCBased"), stream)
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDICCBased)
    assert cs.get_n() == 3


def test_create_calgray_array_dispatches_to_calgray() -> None:
    d = COSDictionary()
    arr = _arr(COSName.get_pdf_name("CalGray"), d)
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDCalGray)


def test_create_calrgb_array_dispatches_to_calrgb() -> None:
    d = COSDictionary()
    arr = _arr(COSName.get_pdf_name("CalRGB"), d)
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDCalRGB)


def test_create_lab_array_dispatches_to_lab() -> None:
    d = COSDictionary()
    arr = _arr(COSName.get_pdf_name("Lab"), d)
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDLab)


def test_create_pattern_array_with_underlying_dispatches_to_uncolored() -> None:
    arr = _arr(
        COSName.get_pdf_name("Pattern"),
        PDDeviceRGB.INSTANCE.get_cos_object(),
    )
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDPattern)
    assert cs.is_uncolored() is True
    assert cs.get_underlying_color_space() is PDDeviceRGB.INSTANCE


def test_create_pattern_array_without_underlying_returns_colored() -> None:
    arr = _arr(COSName.get_pdf_name("Pattern"))
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDPattern)
    assert cs.is_colored() is True


def test_create_empty_array_returns_none() -> None:
    arr = COSArray()
    assert PDColorSpace.create(arr) is None


def test_create_array_with_non_name_head_returns_none() -> None:
    arr = _arr(COSInteger.get(42))
    assert PDColorSpace.create(arr) is None


# ---------- PDFBOX-4833 dictionary unwrap ----------


def test_create_dictionary_with_colorspace_entry_unwraps_recursively() -> None:
    """PDFBOX-4833: a dictionary with a /ColorSpace entry is unwrapped."""
    inner = COSName.get_pdf_name("DeviceGray")
    outer = COSDictionary()
    outer.set_item(COSName.get_pdf_name("ColorSpace"), inner)
    cs = PDColorSpace.create(outer)
    assert cs is PDDeviceGray.INSTANCE


def test_create_dictionary_self_recursion_raises_oserror() -> None:
    """PDFBOX-5315: /ColorSpace pointing to its own dict raises OSError."""
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("ColorSpace"), d)
    with pytest.raises(OSError, match="Recursion in colorspace"):
        PDColorSpace.create(d)


def test_create_dictionary_with_no_colorspace_entry_returns_none() -> None:
    """A dict with no /ColorSpace entry can't be a color space directly."""
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Foo"), COSName.get_pdf_name("Bar"))
    assert PDColorSpace.create(d) is None


def test_create_dictionary_two_level_loop_raises_oserror() -> None:
    """Two dictionaries whose /ColorSpace entries chain into a cycle."""
    a = COSDictionary()
    b = COSDictionary()
    a.set_item(COSName.get_pdf_name("ColorSpace"), b)
    b.set_item(COSName.get_pdf_name("ColorSpace"), a)
    with pytest.raises(OSError, match="Recursion in colorspace"):
        PDColorSpace.create(a)


# ---------- get_array round-trip ----------


def test_get_array_returns_underlying_array_for_array_form() -> None:
    cs = PDICCBased()
    arr = cs.get_array()
    assert arr is not None
    assert arr.size() >= 2
    assert arr.get_object(0).get_name() == "ICCBased"


def test_get_array_returns_none_for_device_singletons() -> None:
    """Device singletons are name-only — no backing array."""
    assert PDDeviceGray.INSTANCE.get_array() is None
    assert PDDeviceRGB.INSTANCE.get_array() is None
    assert PDDeviceCMYK.INSTANCE.get_array() is None
