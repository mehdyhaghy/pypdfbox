from __future__ import annotations

import io

from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.graphics.image import PDImageXObject


def _jpeg_bytes(size: tuple[int, int] = (4, 3)) -> bytes:
    source = Image.new("RGB", size, color=(40, 90, 150))
    payload = io.BytesIO()
    source.save(payload, format="JPEG", quality=90)
    return payload.getvalue()


def test_wave327_short_dct_filter_classifies_as_jpeg() -> None:
    image = PDImageXObject(COSStream())
    image.get_cos_object().set_item(
        COSName.FILTER, COSName.get_pdf_name("DCT")  # type: ignore[attr-defined]
    )

    assert image.is_jpeg() is True
    assert image.get_suffix() == "jpg"


def test_wave327_to_pil_image_short_dct_keeps_payload_encoded() -> None:
    image = PDImageXObject(COSStream())
    image.set_width(4)
    image.set_height(3)
    image.set_bits_per_component(8)
    image.set_color_space("DeviceRGB")
    image.get_cos_object().set_raw_data(_jpeg_bytes((4, 3)))
    image.get_cos_object().set_item(
        COSName.FILTER, COSName.get_pdf_name("DCT")  # type: ignore[attr-defined]
    )

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.size == (4, 3)
    assert rendered.mode == "RGB"
