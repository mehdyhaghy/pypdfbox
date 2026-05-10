from __future__ import annotations

import io

from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.image import JPEGFactory, LosslessFactory
from pypdfbox.pdmodel.pd_document import PDDocument


def _jpeg_bytes(size: tuple[int, int] = (5, 7)) -> bytes:
    image = Image.new("RGB", size, color=(20, 40, 60))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_jpeg_factory_java_aliases_forward_to_snake_case() -> None:
    data = _jpeg_bytes()

    from_bytes = JPEGFactory.createFromByteArray(None, data)
    from_stream = JPEGFactory.createFromStream(None, io.BytesIO(data))
    from_image = JPEGFactory.createFromImage(None, Image.new("RGB", (3, 4)))

    assert from_bytes.get_width() == 5
    assert from_bytes.get_height() == 7
    assert from_stream.get_width() == 5
    assert from_stream.get_height() == 7
    assert from_image.get_width() == 3
    assert from_image.get_height() == 4


def test_lossless_factory_create_from_image_java_alias() -> None:
    document = PDDocument()
    source = Image.new("L", (6, 9), color=128)

    image = LosslessFactory.createFromImage(document, source)

    assert image.get_width() == 6
    assert image.get_height() == 9
    assert image.get_bits_per_component() == 8
    assert image.get_filter() == COSName.get_pdf_name("FlateDecode")
