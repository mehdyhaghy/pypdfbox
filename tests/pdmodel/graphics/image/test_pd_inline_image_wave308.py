from __future__ import annotations

import io

from PIL import Image

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.graphics.image import PDInlineImage


def test_to_pil_image_short_dct_filter_keeps_jpeg_payload_encoded() -> None:
    source = Image.new("RGB", (3, 2), color=(20, 80, 140))
    payload = io.BytesIO()
    source.save(payload, format="JPEG", quality=90)

    parameters = COSDictionary()
    parameters.set_int(COSName.get_pdf_name("W"), source.width)
    parameters.set_int(COSName.get_pdf_name("H"), source.height)
    parameters.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("DCT"))

    image = PDInlineImage(parameters, payload.getvalue(), None)

    rendered = image.to_pil_image()
    assert rendered is not None
    assert rendered.size == source.size
    assert rendered.mode == "RGB"
