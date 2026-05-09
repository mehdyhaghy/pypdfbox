from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream, COSString
from pypdfbox.pdmodel.graphics.color import PDColorSpace, PDDeviceGray, PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.image import PDImageXObject


def _indexed_space(base: PDColorSpace, hival: int, lookup: bytes) -> PDIndexed:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(base.get_cos_object())
    arr.add(COSInteger.get(hival))
    arr.add(COSString(lookup))
    return PDIndexed(arr)


def _indexed_image(data: bytes, indexed: PDIndexed) -> PDImageXObject:
    image = PDImageXObject(COSStream())
    image.set_width(2)
    image.set_height(1)
    image.set_bits_per_component(8)
    image.set_color_space(indexed)
    image.get_cos_object().set_raw_data(data)
    return image


def test_wave1283_to_pil_image_expands_indexed_devicergb_lookup() -> None:
    indexed = _indexed_space(
        PDDeviceRGB.INSTANCE,
        2,
        bytes([255, 0, 0, 0, 255, 0, 0, 0, 255]),
    )
    image = _indexed_image(bytes([2, 1]), indexed)

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.mode == "RGB"
    assert rendered.tobytes() == bytes([0, 0, 255, 0, 255, 0])


def test_wave1283_to_pil_image_expands_indexed_devicegray_lookup() -> None:
    indexed = _indexed_space(PDDeviceGray.INSTANCE, 1, bytes([32, 224]))
    image = _indexed_image(bytes([0, 1]), indexed)

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.tobytes() == bytes([32, 32, 32, 224, 224, 224])


def test_wave1283_to_pil_image_applies_indexed_decode() -> None:
    indexed = _indexed_space(
        PDDeviceRGB.INSTANCE,
        1,
        bytes([10, 20, 30, 200, 210, 220]),
    )
    image = _indexed_image(bytes([0, 255]), indexed)
    image.set_decode([1.0, 0.0])

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.tobytes() == bytes([200, 210, 220, 10, 20, 30])


def test_wave1283_to_pil_image_rejects_short_indexed_raster() -> None:
    indexed = _indexed_space(PDDeviceRGB.INSTANCE, 1, bytes([0, 0, 0, 255, 255, 255]))
    image = _indexed_image(bytes([0]), indexed)

    assert image.to_pil_image() is None


def test_wave1283_to_pil_image_rejects_wrong_length_indexed_decode() -> None:
    indexed = _indexed_space(PDDeviceRGB.INSTANCE, 1, bytes([0, 0, 0, 255, 255, 255]))
    image = _indexed_image(bytes([0, 1]), indexed)
    image.set_decode([0.0, 1.0, 0.0, 1.0])

    assert image.to_pil_image() is None
