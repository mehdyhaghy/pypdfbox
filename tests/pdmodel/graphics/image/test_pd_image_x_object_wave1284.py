from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.graphics.image import PDImageXObject


def _cmyk_image(data: bytes) -> PDImageXObject:
    image = PDImageXObject(COSStream())
    image.set_width(2)
    image.set_height(1)
    image.set_bits_per_component(8)
    image.set_color_space("DeviceCMYK")
    image.get_cos_object().set_raw_data(data)
    return image


def test_wave1284_to_pil_image_converts_raw_devicecmyk_to_rgb() -> None:
    image = _cmyk_image(bytes([0, 0, 0, 0, 255, 0, 0, 0]))

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.mode == "RGB"
    assert rendered.tobytes() == bytes([255, 255, 255, 0, 255, 255])


def test_wave1284_to_pil_image_applies_devicecmyk_decode() -> None:
    image = _cmyk_image(bytes([0, 255, 255, 255, 255, 0, 255, 255]))
    image.set_decode([1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0])

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.tobytes() == bytes([0, 255, 255, 255, 0, 255])


def test_wave1284_to_pil_image_rejects_short_devicecmyk_raster() -> None:
    image = _cmyk_image(bytes([0, 0, 0, 0, 255, 0, 0]))

    assert image.to_pil_image() is None


def test_wave1284_to_pil_image_rejects_wrong_length_devicecmyk_decode() -> None:
    image = _cmyk_image(bytes([0, 0, 0, 0, 255, 0, 0, 0]))
    image.set_decode([0.0, 1.0])

    assert image.to_pil_image() is None
