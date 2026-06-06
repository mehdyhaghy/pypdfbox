"""Wave 1496 — coverage round-out for the raster-decode branches of
:mod:`pypdfbox.pdmodel.graphics.image.pd_image_x_object`.

Pins still-uncovered deterministic decode paths:

* 16-bit DeviceRGB and 16-bit DeviceGray rasters (the ``bpc == 16`` legs of
  ``decode_pdimage_to_pil`` — big-endian sample unpack + /Decode scaling).
* ICCBased ``/N == 3`` raster decode through the embedded-or-alternate
  colour space.
* ``_apply_devicen_decode`` as a pure function: identity passthrough,
  inverted ``[1 0...]`` decode ramp, short raster, decode-length mismatch,
  and the ``components <= 0`` guard.
* ``_read_color_key_samples`` rejection legs — filtered (DCT) payload,
  zero geometry, unsupported colour space, component-count mismatch — and
  the ``_apply_color_key_mask`` odd-range / non-3-component-fallback guards.
* The ``/SMask`` ``/Matte`` un-premultiply pass and the explicit 1-bit
  ``/Mask`` stencil application (with a reversed ``/Decode [1 0]`` polarity).

Each test asserts an observable pixel/return contract, not bare execution.
"""

from __future__ import annotations

import struct

from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.graphics.color import PDDeviceGray, PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
    _apply_color_key_mask,
    _apply_devicen_decode,
    _read_color_key_samples,
)


def _rgb_image(
    data: bytes, *, width: int, height: int, bpc: int, cs=PDDeviceRGB.INSTANCE
) -> PDImageXObject:
    image = PDImageXObject(COSStream())
    image.set_width(width)
    image.set_height(height)
    image.set_bits_per_component(bpc)
    image.set_color_space(cs)
    image.get_cos_object().set_raw_data(data)
    return image


# ---------------------------------------------------------------------
# 16-bit DeviceRGB.
# ---------------------------------------------------------------------
def test_devicergb_16bit_downshifts_to_8bit() -> None:
    # One pixel, big-endian 16-bit: R=0xFFFF -> 255, G=0x0000 -> 0, B=0x8080.
    data = struct.pack(">HHH", 0xFFFF, 0x0000, 0x8080)
    image = _rgb_image(data, width=1, height=1, bpc=16)
    out = image.to_pil_image()
    assert out is not None
    assert out.mode == "RGB"
    r, g, b = out.getpixel((0, 0))
    assert r == 255
    assert g == 0
    # 0x8080 / 65535 * 255 ~= 128.
    assert 127 <= b <= 129


def test_devicergb_16bit_short_data_returns_none() -> None:
    image = _rgb_image(b"\x00\x01", width=1, height=1, bpc=16)
    assert image.to_pil_image() is None


# ---------------------------------------------------------------------
# 16-bit DeviceGray.
# ---------------------------------------------------------------------
def test_devicegray_16bit_decodes_to_rgb() -> None:
    data = struct.pack(">HH", 0x0000, 0xFFFF)
    image = _rgb_image(data, width=2, height=1, bpc=16, cs=PDDeviceGray.INSTANCE)
    out = image.to_pil_image()
    assert out is not None
    assert out.getpixel((0, 0)) == (0, 0, 0)
    assert out.getpixel((1, 0)) == (255, 255, 255)


# ---------------------------------------------------------------------
# ICCBased /N == 3.
# ---------------------------------------------------------------------
def _icc_based_n3() -> PDICCBased:
    icc_stream = COSStream()
    icc_stream.set_item(COSName.get_pdf_name("N"), COSInteger.get(3))
    icc_stream.set_raw_data(b"")  # no real profile -> alternate fallback
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(icc_stream)
    return PDICCBased(arr)


def test_iccbased_n3_decodes_raster() -> None:
    cs = _icc_based_n3()
    assert cs.get_number_of_components() == 3
    data = bytes([255, 0, 0, 0, 255, 0])  # two RGB-ish pixels
    image = _rgb_image(data, width=2, height=1, bpc=8, cs=cs)
    out = image.to_pil_image()
    assert out is not None
    assert out.size == (2, 1)


def test_iccbased_short_data_returns_none() -> None:
    cs = _icc_based_n3()
    image = _rgb_image(b"\xff\x00", width=2, height=1, bpc=8, cs=cs)
    assert image.to_pil_image() is None


# ---------------------------------------------------------------------
# _apply_devicen_decode — pure function.
# ---------------------------------------------------------------------
def test_devicen_decode_identity_passthrough() -> None:
    data = bytes([10, 20, 30, 40])
    out = _apply_devicen_decode(data, 2, 2, 1, [0.0, 1.0])
    assert out == data


def test_devicen_decode_none_decode_passthrough() -> None:
    data = bytes([10, 20, 30, 40])
    out = _apply_devicen_decode(data, 2, 2, 1, None)
    assert out == data


def test_devicen_decode_inverted_ramp() -> None:
    # decode [1 0]: raw 0 -> 255, raw 255 -> 0.
    out = _apply_devicen_decode(bytes([0, 255]), 2, 1, 1, [1.0, 0.0])
    assert out is not None
    assert out[0] == 255
    assert out[1] == 0


def test_devicen_decode_short_raster_is_none() -> None:
    assert _apply_devicen_decode(bytes([1, 2]), 4, 4, 1, None) is None


def test_devicen_decode_length_mismatch_is_none() -> None:
    # decode length must be components * 2; 3 elems for 1 component is wrong.
    assert _apply_devicen_decode(bytes([1, 2]), 2, 1, 1, [0.0, 1.0, 0.5]) is None


def test_devicen_decode_zero_components_is_none() -> None:
    assert _apply_devicen_decode(bytes([1, 2]), 2, 1, 0, None) is None


# ---------------------------------------------------------------------
# _read_color_key_samples / _apply_color_key_mask rejection legs.
# ---------------------------------------------------------------------
def test_color_key_samples_filtered_payload_is_none() -> None:
    image = _rgb_image(b"", width=2, height=1, bpc=8)
    image.get_cos_object().set_item(
        COSName.get_pdf_name("Filter"), COSName.get_pdf_name("DCTDecode")
    )
    assert _read_color_key_samples(image, 3) is None


def test_color_key_samples_zero_geometry_is_none() -> None:
    image = _rgb_image(b"\x00", width=0, height=0, bpc=8)
    assert _read_color_key_samples(image, 3) is None


def test_color_key_samples_component_mismatch_is_none() -> None:
    # DeviceRGB has 3 components; ask for 4 -> mismatch rejection.
    image = _rgb_image(bytes([1, 2, 3]), width=1, height=1, bpc=8)
    assert _read_color_key_samples(image, 4) is None


def test_color_key_samples_devicergb_8bit_interleaved() -> None:
    image = _rgb_image(bytes([10, 20, 30, 40, 50, 60]), width=2, height=1, bpc=8)
    samples = _read_color_key_samples(image, 3)
    assert samples == [10, 20, 30, 40, 50, 60]


def test_apply_color_key_odd_range_returns_image() -> None:
    img = Image.new("RGB", (2, 1), (0, 0, 0))
    pd_image = _rgb_image(bytes([0, 0, 0, 0, 0, 0]), width=2, height=1, bpc=8)
    # Odd-length range -> unchanged opaque image.
    out = _apply_color_key_mask(img, [0, 1, 2], pd_image)
    assert out is img


def test_apply_color_key_non3_fallback_returns_image_when_samples_none() -> None:
    # 4-component range but a DeviceRGB(3) image -> _read_color_key_samples
    # returns None and components != 3, so the raster stays opaque.
    img = Image.new("RGB", (1, 1), (5, 5, 5))
    pd_image = _rgb_image(bytes([5, 5, 5]), width=1, height=1, bpc=8)
    out = _apply_color_key_mask(img, [0, 9, 0, 9, 0, 9, 0, 9], pd_image)
    assert out is img


def test_apply_color_key_rgb_pixel_fallback_keys() -> None:
    # DCT-filtered image so _read_color_key_samples returns None; with a
    # 3-component range we fall back to the sRGB-pixel comparison.
    img = Image.new("RGB", (2, 1), (10, 10, 10))
    img.putpixel((1, 0), (200, 200, 200))
    pd_image = _rgb_image(b"", width=2, height=1, bpc=8)
    pd_image.get_cos_object().set_item(
        COSName.get_pdf_name("Filter"), COSName.get_pdf_name("DCTDecode")
    )
    out = _apply_color_key_mask(img, [0, 50, 0, 50, 0, 50], pd_image)
    rgba = out.convert("RGBA")
    assert rgba.getpixel((0, 0))[3] == 0  # (10,10,10) in [0,50] -> keyed
    assert rgba.getpixel((1, 0))[3] == 255  # (200,..) outside -> opaque


# ---------------------------------------------------------------------
# DeviceCMYK color-key (4-component raw-sample path).
# ---------------------------------------------------------------------
def test_color_key_devicecmyk_keys_four_components() -> None:
    from pypdfbox.pdmodel.graphics.color import PDDeviceCMYK

    # Two CMYK pixels: first all-zero (keyed by [0 5]*4), second all-255.
    data = bytes([0, 0, 0, 0, 255, 255, 255, 255])
    image = _rgb_image(data, width=2, height=1, bpc=8, cs=PDDeviceCMYK.INSTANCE)
    image.set_color_key_mask([0, 5, 0, 5, 0, 5, 0, 5])
    out = image.get_image()
    assert out is not None
    rgba = out.convert("RGBA")
    assert rgba.getpixel((0, 0))[3] == 0
    assert rgba.getpixel((1, 0))[3] == 255


# ---------------------------------------------------------------------
# /SMask /Matte un-premultiply.
# ---------------------------------------------------------------------
def test_smask_matte_unpremultiplies_base_colour() -> None:
    # Base: single mid-grey pixel pre-blended against a black matte.
    base = _rgb_image(bytes([128, 128, 128]), width=1, height=1, bpc=8)

    smask = PDImageXObject(COSStream())
    smask.set_width(1)
    smask.set_height(1)
    smask.set_bits_per_component(8)
    smask.set_color_space(PDDeviceGray.INSTANCE)
    smask.get_cos_object().set_raw_data(bytes([128]))  # alpha 0.5
    # /Matte [0 0 0] (black) on the soft mask dictionary.
    matte = COSArray()
    for _ in range(3):
        matte.add(COSFloat(0.0))
    smask.get_cos_object().set_item(COSName.get_pdf_name("Matte"), matte)
    base.get_cos_object().set_item(COSName.get_pdf_name("SMask"), smask.get_cos_object())

    out = base.get_image()
    assert out is not None
    rgba = out.convert("RGBA")
    px = rgba.getpixel((0, 0))
    assert px[3] == 128  # alpha band replaced by the SMask sample
    # c = m + (c' - m)/alpha = 0 + (128-0)/0.5 = 256 -> clamped 255.
    assert px[0] == 255


# ---------------------------------------------------------------------
# Explicit 1-bit /Mask stencil with reversed /Decode polarity.
# ---------------------------------------------------------------------
def test_explicit_mask_decode_reverses_polarity() -> None:
    base = _rgb_image(bytes([200, 0, 0, 0, 200, 0]), width=2, height=1, bpc=8)

    mask = PDImageXObject(COSStream())
    mask.set_width(2)
    mask.set_height(1)
    mask.set_bits_per_component(1)
    mask.set_color_space(PDDeviceGray.INSTANCE)
    # Two 1-bit samples packed MSB-first: 0b10000000 -> sample0=1, sample1=0.
    mask.get_cos_object().set_raw_data(bytes([0b10000000]))
    mask.get_cos_object().set_item(
        COSName.get_pdf_name("ImageMask"), COSName.get_pdf_name("true")
    )
    # /Decode [1 0] flips the stencil polarity: masked_sample becomes 0.
    decode = COSArray()
    decode.add(COSInteger.get(1))
    decode.add(COSInteger.get(0))
    mask.get_cos_object().set_item(COSName.get_pdf_name("Decode"), decode)

    base.get_cos_object().set_item(
        COSName.get_pdf_name("Mask"), mask.get_cos_object()
    )

    out = base.get_image()
    assert out is not None
    rgba = out.convert("RGBA")
    # /Decode [1 0] sets masked_sample = 0, so a sample of 0 is transparent
    # and a sample of 1 is opaque (reversed from the default polarity).
    assert rgba.getpixel((0, 0))[3] == 255  # sample0=1 -> opaque
    assert rgba.getpixel((1, 0))[3] == 0  # sample1=0 -> transparent
