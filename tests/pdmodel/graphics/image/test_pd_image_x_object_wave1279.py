from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.graphics.image import PDImageXObject


def _image(data: bytes, color_space: str) -> PDImageXObject:
    image = PDImageXObject(COSStream())
    image.set_width(2)
    image.set_height(1)
    image.set_bits_per_component(8)
    image.set_color_space(color_space)
    image.get_cos_object().set_raw_data(data)
    return image


def test_wave1279_to_pil_image_applies_devicegray_decode_inversion() -> None:
    image = _image(bytes([0, 255]), "DeviceGray")
    image.set_decode([1.0, 0.0])

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.mode == "RGB"
    assert rendered.tobytes() == bytes([255, 255, 255, 0, 0, 0])


def test_wave1279_to_pil_image_applies_devicergb_decode_per_component() -> None:
    image = _image(bytes([0, 255, 128, 255, 0, 64]), "DeviceRGB")
    image.set_decode([1.0, 0.0, 0.0, 1.0, 0.25, 0.75])

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.tobytes() == bytes([255, 255, 128, 0, 0, 96])


def test_wave1279_to_pil_image_rejects_wrong_length_decode_array() -> None:
    image = _image(bytes([0, 255]), "DeviceGray")
    image.set_decode([0.0, 1.0, 0.0, 1.0])

    assert image.to_pil_image() is None
