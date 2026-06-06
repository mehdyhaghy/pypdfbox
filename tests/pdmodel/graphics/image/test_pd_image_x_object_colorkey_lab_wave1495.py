"""Wave 1495 — coverage round-out for ``PDImageXObject`` color-key /Mask raw
sample reading and the Lab raster decode branch.

Pins the raw-sample comparison path of ``_read_color_key_samples`` (PDF
32000-1 §8.9.6.4) — DeviceGray at 8-bit, sub-byte (1/2/4) and 16-bit, and
Indexed keyed on the palette index with a ``/Decode`` index remap — and the
DeviceRGB-pixel fallback used when the native raster cannot be re-read. Also
pins the Lab raster decode branch of ``decode_pdimage_to_pil`` (the colour
space performs its own L*a*b* scaling, so no /Decode pre-pass is applied).
"""

from __future__ import annotations

from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.color import PDDeviceGray, PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.image import PDImageXObject


def _alpha(img: Image.Image, x: int, y: int) -> int:
    return img.convert("RGBA").getpixel((x, y))[3]


def _gray_image(data: bytes, *, width: int, height: int, bpc: int) -> PDImageXObject:
    image = PDImageXObject(COSStream())
    image.set_width(width)
    image.set_height(height)
    image.set_bits_per_component(bpc)
    image.set_color_space(PDDeviceGray.INSTANCE)
    image.get_cos_object().set_raw_data(data)
    return image


# --------------------------------------------- DeviceGray color-key (raw samples)


def test_color_key_devicegray_8bit_keys_matching_sample() -> None:
    # Two 8-bit gray pixels: 10 (in [0,60]) keyed out, 200 (outside) opaque.
    image = _gray_image(bytes([10, 200]), width=2, height=1, bpc=8)
    image.set_color_key_mask([0, 60])
    out = image.get_image()
    assert out is not None
    assert _alpha(out, 0, 0) == 0
    assert _alpha(out, 1, 0) == 255


def test_color_key_devicegray_sub_byte_keys_matching_sample() -> None:
    # Two 4-bit gray samples packed in one byte: 0x0 (keyed) and 0xF (opaque).
    image = _gray_image(bytes([0x0F]), width=2, height=1, bpc=4)
    image.set_color_key_mask([0, 0])
    out = image.get_image()
    assert out is not None
    assert _alpha(out, 0, 0) == 0
    assert _alpha(out, 1, 0) == 255


def test_color_key_devicegray_16bit_keys_matching_sample() -> None:
    # Two 16-bit big-endian gray samples: 0x0005 (keyed) and 0xFFFF (opaque).
    image = _gray_image(
        bytes([0x00, 0x05, 0xFF, 0xFF]), width=2, height=1, bpc=16
    )
    image.set_color_key_mask([0, 16])
    out = image.get_image()
    assert out is not None
    assert _alpha(out, 0, 0) == 0
    assert _alpha(out, 1, 0) == 255


# ------------------------------------------------ Indexed color-key on palette index


def test_color_key_indexed_keys_palette_index() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(2))
    arr.add(COSString(bytes([255, 0, 0, 0, 255, 0, 0, 0, 255])))
    indexed = PDIndexed(arr)

    image = PDImageXObject(COSStream())
    image.set_width(2)
    image.set_height(1)
    image.set_bits_per_component(8)
    image.set_color_space(indexed)
    image.get_cos_object().set_raw_data(bytes([1, 2]))
    # Key out palette index 1 (the green entry); index 2 stays opaque.
    image.set_color_key_mask([1, 1])
    out = image.get_image()
    assert out is not None
    assert _alpha(out, 0, 0) == 0
    assert _alpha(out, 1, 0) == 255


def test_color_key_indexed_honours_decode_index_remap() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(255))
    arr.add(COSString(bytes([0, 0, 0]) * 256))
    indexed = PDIndexed(arr)

    image = PDImageXObject(COSStream())
    image.set_width(2)
    image.set_height(1)
    image.set_bits_per_component(8)
    image.set_color_space(indexed)
    image.get_cos_object().set_raw_data(bytes([0, 255]))
    # /Decode [255 0] inverts the index: raw 0 -> index 255, raw 255 -> 0.
    decode = COSArray()
    decode.add(COSInteger.get(255))
    decode.add(COSInteger.get(0))
    image.get_cos_object().set_item("Decode", decode)
    # Key out index 255 (which the remap maps the raw-0 pixel to).
    image.set_color_key_mask([255, 255])
    out = image.get_image()
    assert out is not None
    assert _alpha(out, 0, 0) == 0
    assert _alpha(out, 1, 0) == 255


# ------------------------------- DeviceRGB-pixel fallback (DCT raster, no raw read)


def test_color_key_devicergb_jpeg_falls_back_to_srgb_pixels() -> None:
    # A DCT (JPEG) raster cannot be re-read as raw samples, so a 3-component
    # color-key falls back to comparing the decoded sRGB pixels.
    import io

    base = Image.new("RGB", (2, 1))
    base.putpixel((0, 0), (5, 5, 5))
    base.putpixel((1, 0), (250, 250, 250))
    buf = io.BytesIO()
    base.save(buf, format="JPEG", quality=100)

    stream = COSStream()
    stream.set_item("Filter", COSName.get_pdf_name("DCTDecode"))
    stream.create_raw_output_stream().write(buf.getvalue())
    image = PDImageXObject(stream)
    image.set_width(2)
    image.set_height(1)
    image.set_bits_per_component(8)
    image.set_color_space(PDDeviceRGB.INSTANCE)
    image.set_color_key_mask([0, 40, 0, 40, 0, 40])
    out = image.get_image()
    assert out is not None
    # The near-black pixel keys out; the near-white pixel stays opaque.
    assert _alpha(out, 0, 0) == 0
    assert _alpha(out, 1, 0) == 255


# ------------------------------------------------------------- Lab raster decode


def test_lab_raster_decodes_via_colorspace() -> None:
    from pypdfbox.cos import COSDictionary

    lab_arr = COSArray()
    lab_arr.add(COSName.get_pdf_name("Lab"))
    lab_dict = COSDictionary()
    wp = COSArray()
    for v in (0.9642, 1.0, 0.8249):
        wp.add(COSFloat(v))
    lab_dict.set_item("WhitePoint", wp)
    lab_arr.add(lab_dict)
    lab = PDLab(lab_arr)

    # One Lab pixel L*=255-scaled. The colour space consumes the raw 8-bit
    # samples directly (no /Decode pre-pass), so a white-ish L sample yields a
    # bright pixel.
    image = PDImageXObject(COSStream())
    image.set_width(1)
    image.set_height(1)
    image.set_bits_per_component(8)
    image.set_color_space(lab)
    image.get_cos_object().set_raw_data(bytes([255, 128, 128]))

    out = image.to_pil_image()
    assert out is not None
    assert out.mode == "RGB"
    assert out.size == (1, 1)
    r, g, b = out.getpixel((0, 0))
    # L*=100 (white point) with neutral a*/b* renders near-white.
    assert r > 200 and g > 200 and b > 200
