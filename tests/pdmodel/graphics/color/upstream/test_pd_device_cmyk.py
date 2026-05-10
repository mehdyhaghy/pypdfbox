"""Ported parity tests for ``PDDeviceCMYK``.

Translated from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/color/PDDeviceCMYKTest.java``
(PDFBox 3.0.x). Upstream's suite is small — it covers the power-user
override pattern (``PDDeviceCMYK.INSTANCE = new CustomDeviceCMYK()``)
and a JVM-specific colour-management regression (PDFBOX-5787) that
has no Python analogue.
"""

from __future__ import annotations

from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_color_space import (
    PDDeviceColorSpace,
)

# ---------- testCMYK (PDDeviceCMYKTest.java line 44) ----------


class _CustomDeviceCMYK(PDDeviceCMYK):
    """Mirrors the inner ``CustomDeviceCMYK`` class in the upstream test
    (PDDeviceCMYKTest.java line 49) — a subclass exists purely so the
    power-user can swap ``PDDeviceCMYK.INSTANCE`` with a custom default
    CMYK colour space.
    """


def test_cmyk_singleton_can_be_replaced() -> None:
    # Upstream just assigns a custom subclass to the static INSTANCE
    # field. We do the same and put the original back so we don't leak
    # the substitution into other tests.
    original = PDDeviceCMYK.INSTANCE
    try:
        PDDeviceCMYK.INSTANCE = _CustomDeviceCMYK()
        assert isinstance(PDDeviceCMYK.INSTANCE, PDDeviceCMYK)
        assert isinstance(PDDeviceCMYK.INSTANCE, _CustomDeviceCMYK)
    finally:
        PDDeviceCMYK.INSTANCE = original


# ---------- testPDFBox5787 ----------
# Skipped: the upstream regression test exercises a JVM-specific
# ColorConvertOp + ICC_ColorSpace race that has no Python analogue
# (Pillow does not expose the same ColorConvertOp pipeline).


# ---------- structural parity (asserted by the upstream class itself) ----------


def test_get_name() -> None:
    # PDDeviceCMYK.java line 117: returns COSName.DEVICECMYK.getName().
    assert PDDeviceCMYK.INSTANCE.get_name() == "DeviceCMYK"


def test_get_number_of_components() -> None:
    # PDDeviceCMYK.java line 122: returns 4.
    assert PDDeviceCMYK.INSTANCE.get_number_of_components() == 4


def test_get_default_decode() -> None:
    # PDDeviceCMYK.java line 129: returns {0,1,0,1,0,1,0,1}.
    assert PDDeviceCMYK.INSTANCE.get_default_decode(8) == [
        0.0,
        1.0,
        0.0,
        1.0,
        0.0,
        1.0,
        0.0,
        1.0,
    ]


def test_get_initial_color() -> None:
    # PDDeviceCMYK.java line 49: initial color is (0, 0, 0, 1) — pure K.
    initial = PDDeviceCMYK.INSTANCE.get_initial_color()
    assert isinstance(initial, PDColor)
    assert initial.get_components() == [0.0, 0.0, 0.0, 1.0]
    assert initial.get_color_space() is PDDeviceCMYK.INSTANCE


def test_extends_pd_device_color_space() -> None:
    # PDDeviceCMYK.java line 40: ``extends PDDeviceColorSpace``.
    assert isinstance(PDDeviceCMYK.INSTANCE, PDDeviceColorSpace)


# ---------- toRGB (PDDeviceCMYK.java line 141) ----------
# Upstream relies on the bundled CGATS001Compat-v2-micro ICC profile;
# pypdfbox does not bundle ICC and uses the K-zero subtractive
# approximation, which is also what Pillow's built-in CMYK to RGB
# transform emits (and what upstream's pure-Java path produces for
# ``K = 0``). Endpoint cases are deterministic across both paths.


def test_to_rgb_white_paper() -> None:
    # 0% ink everywhere -> pure white.
    assert PDDeviceCMYK.INSTANCE.to_rgb([0.0, 0.0, 0.0, 0.0]) == [1.0, 1.0, 1.0]


def test_to_rgb_pure_black_via_k() -> None:
    # 100% K -> pure black regardless of CMY.
    assert PDDeviceCMYK.INSTANCE.to_rgb([0.0, 0.0, 0.0, 1.0]) == [0.0, 0.0, 0.0]


def test_to_rgb_pure_cyan() -> None:
    # 100% C, no K -> r=0, g=1, b=1.
    assert PDDeviceCMYK.INSTANCE.to_rgb([1.0, 0.0, 0.0, 0.0]) == [0.0, 1.0, 1.0]


def test_to_rgb_pure_magenta() -> None:
    assert PDDeviceCMYK.INSTANCE.to_rgb([0.0, 1.0, 0.0, 0.0]) == [1.0, 0.0, 1.0]


def test_to_rgb_pure_yellow() -> None:
    assert PDDeviceCMYK.INSTANCE.to_rgb([0.0, 0.0, 1.0, 0.0]) == [1.0, 1.0, 0.0]


# ---------- init / get_icc_profile (PDDeviceCMYK.java lines 63, 97) ----------


def test_init_is_idempotent() -> None:
    cs = _CustomDeviceCMYK()
    cs.init()
    cs.init()  # second call is a no-op (parity with upstream's initDone latch)
    assert cs._init_done is True


def test_get_icc_profile_returns_none_when_not_bundled() -> None:
    # pypdfbox does not bundle CGATS001Compat-v2-micro, so the base
    # implementation returns None. Subclasses may override.
    assert PDDeviceCMYK().get_icc_profile() is None


# ---------- toRawImage (PDDeviceCMYK.java line 148) ----------


def test_to_raw_image_returns_none() -> None:
    # Upstream explicitly returns null: device CMYK has no canonical
    # raw form because it is device-dependent.
    assert PDDeviceCMYK.INSTANCE.to_raw_image(b"\x00" * 4, 1, 1) is None


# ---------- toRGBImage (PDDeviceCMYK.java line 156) ----------


def test_to_rgb_image_white_paper() -> None:
    # 1x1 raster, zero ink -> white pixel via Pillow CMYK->RGB.
    img = PDDeviceCMYK.INSTANCE.to_rgb_image(b"\x00\x00\x00\x00", 1, 1)
    assert img.mode == "RGB"
    assert img.size == (1, 1)
    assert img.getpixel((0, 0)) == (255, 255, 255)


def test_to_rgb_image_full_ink() -> None:
    # 1x1 raster with full ink -> black pixel.
    img = PDDeviceCMYK.INSTANCE.to_rgb_image(
        bytes([255, 255, 255, 255]), 1, 1
    )
    assert img.getpixel((0, 0)) == (0, 0, 0)


def test_to_rgb_image_awt_delegates_to_to_rgb_image() -> None:
    # awt_color_space is accepted for surface compatibility but ignored
    # in pypdfbox; output must match to_rgb_image.
    raster = bytes([0, 0, 0, 0, 255, 255, 255, 255])
    via_awt = PDDeviceCMYK.INSTANCE.to_rgb_image_awt(
        raster, None, 2, 1
    )
    direct = PDDeviceCMYK.INSTANCE.to_rgb_image(raster, 2, 1)
    assert list(via_awt.getdata()) == list(direct.getdata())
