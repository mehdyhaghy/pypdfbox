"""Ported from upstream ``PDDeviceNTest.java`` (PDFBox 3.0 branch, added by
PDFBOX-5074 for the unreleased 3.0.9).

Tests the conversion of DeviceN color spaces that have a single spot
colorant in the attributes. Java ``WritableRaster`` / ``BufferedImage`` map
to pypdfbox's ``to_rgb_image(bytes, width, height)`` returning a Pillow
image.
"""

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN

COLORANT = "PANTONE 342 C"


def _cos_array_of(*floats: float) -> COSArray:
    ar = COSArray()
    for f in floats:
        ar.add(COSFloat(f))
    return ar


# 1 input, exponent 1: a linear ramp from c0 to c1
def _linear_function(c0: list[float], c1: list[float]) -> COSDictionary:
    function = COSDictionary()
    function.set_int(COSName.get_pdf_name("FunctionType"), 2)
    function.set_item(COSName.get_pdf_name("Domain"), _cos_array_of(0, 1))
    function.set_item(COSName.get_pdf_name("C0"), _cos_array_of(*c0))
    function.set_item(COSName.get_pdf_name("C1"), _cos_array_of(*c1))
    function.set_int(COSName.get_pdf_name("N"), 1)
    return function


# DeviceN with CMYK as alternate and a spot colorant (Separation with RGB
# as alternate)
def _create_device_n(
    spot_at_zero: list[float],
    spot_at_one: list[float],
    cmyk_at_one: list[float],
) -> PDDeviceN:
    separation = COSArray()
    separation.add(COSName.get_pdf_name("Separation"))
    separation.add(COSName.get_pdf_name(COLORANT))
    separation.add(COSName.get_pdf_name("DeviceRGB"))
    separation.add(_linear_function(spot_at_zero, spot_at_one))

    colorants = COSDictionary()
    colorants.set_item(COSName.get_pdf_name(COLORANT), separation)
    attributes = COSDictionary()
    attributes.set_item(COSName.get_pdf_name("Colorants"), colorants)

    device_n = COSArray()
    device_n.add(COSName.get_pdf_name("DeviceN"))
    name_array = COSArray()
    name_array.add(COSName.get_pdf_name(COLORANT))
    device_n.add(name_array)
    device_n.add(COSName.get_pdf_name("DeviceCMYK"))
    device_n.add(_linear_function([0, 0, 0, 0], cmyk_at_one))
    device_n.add(attributes)
    return PDDeviceN(device_n)


def _via_tint_transform(device_n: PDDeviceN, tint: float) -> list[float]:
    alt = device_n.get_tint_transform().eval([tint])
    return list(PDColor(alt, device_n.get_alternate_color_space()).to_rgb())


def _rgb_of(image, x: int) -> tuple[int, int, int]:
    return image.getpixel((x, 0))


def test_spot_colorant_not_white_at_zero_tint() -> None:
    """PDFBOX-5074: the spot colorant is black at zero tint, which would
    make the colorant (and therefore the whole space) dark even if no ink
    is used. The tint transform must be used."""
    device_n = _create_device_n([0, 0, 0], [0, 0.41, 0.31], [1, 0.09, 0.66, 0.41])

    zero = device_n.to_rgb([0])
    for component in zero:
        assert component > 0.9, f"no ink must be white, but was {component}"
    assert list(zero) == pytest.approx(_via_tint_transform(device_n, 0), abs=0.0001)

    tint = device_n.to_rgb([0.4])
    assert list(tint) == pytest.approx(_via_tint_transform(device_n, 0.4), abs=0.0001)
    # the attributes would have resulted in a dark green: 0, 0.16, 0.12
    assert tint[0] > 0.3, f"expected a light color, but red was {tint[0]}"


def test_spot_colorant_not_white_at_zero_tint_image() -> None:
    """Same for images: white where there is no tint, and not the black of
    the colorant."""
    device_n = _create_device_n([0, 0, 0], [0, 0.41, 0.31], [1, 0.09, 0.66, 0.41])

    image = device_n.to_rgb_image(bytes([0, 102]), 2, 1)  # 102 is 0.4

    no_ink = _rgb_of(image, 0)
    assert no_ink[0] == pytest.approx(0xFF, abs=2)
    assert no_ink[1] == pytest.approx(0xFF, abs=2)
    assert no_ink[2] == pytest.approx(0xFF, abs=2)

    expected = _via_tint_transform(device_n, 0.4)
    tint = _rgb_of(image, 1)
    assert tint[0] == pytest.approx(expected[0] * 255, abs=2)
    assert tint[1] == pytest.approx(expected[1] * 255, abs=2)
    assert tint[2] == pytest.approx(expected[2] * 255, abs=2)


def test_spot_colorant_white_at_zero_tint() -> None:
    """A spot colorant that is white at zero tint is what the attributes
    expect, they must still be used and not the tint transform (which is
    red here to make the difference obvious)."""
    device_n = _create_device_n([1, 1, 1], [0, 0.41, 0.31], [0, 1, 1, 0])

    tint = device_n.to_rgb([0.5])
    assert tint[0] == pytest.approx(0.5, abs=0.0001)
    assert tint[1] == pytest.approx(0.705, abs=0.0001)
    assert tint[2] == pytest.approx(0.655, abs=0.0001)

    rgb = _rgb_of(device_n.to_rgb_image(bytes([255]), 1, 1), 0)  # 1.0
    assert rgb[0] == pytest.approx(0, abs=2)
    assert rgb[1] == pytest.approx(0.41 * 255, abs=2)
    assert rgb[2] == pytest.approx(0.31 * 255, abs=2)


def test_zero_tint_check_does_not_affect_near_zero_tints() -> None:
    """Checking whether the spot colorant is white must not change later
    conversions: the result of a Separation is cached per tint, and that
    must not make a tint near zero look like zero."""
    device_n = _create_device_n([1, 1, 1], [0, 0, 0], [0, 1, 1, 0])

    # 0.003 * 255 < 1, so this tint is in the same cache slot as zero
    near_zero = device_n.to_rgb([0.003])
    assert near_zero[0] == pytest.approx(1 - 0.003, abs=0.0001)
