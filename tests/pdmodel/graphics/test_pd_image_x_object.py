from __future__ import annotations

import zlib

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.graphics.image import PDImageXObject


def test_image_xobject_sets_subtype_and_metadata() -> None:
    image = PDImageXObject(COSStream())
    image.set_width(640)
    image.set_height(480)
    image.set_bits_per_component(8)
    image.set_color_space("DeviceRGB")

    cos = image.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "XObject"  # type: ignore[attr-defined]
    assert cos.get_name(COSName.SUBTYPE) == "Image"  # type: ignore[attr-defined]
    assert image.get_width() == 640
    assert image.get_height() == 480
    assert image.get_bits_per_component() == 8
    assert image.get_color_space() == COSName.get_pdf_name("DeviceRGB")


def test_image_xobject_accepts_short_metadata_aliases() -> None:
    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("BPC"), 1)
    stream.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceGray"))

    image = PDImageXObject(stream)
    assert image.get_bits_per_component() == 1
    assert image.get_color_space() == COSName.get_pdf_name("DeviceGray")


def test_image_create_input_stream_delegates_to_pd_stream_stop_filters() -> None:
    encoded = zlib.compress(b"pixels")
    stream = COSStream()
    stream.set_raw_data(encoded)
    stream.set_item(COSName.FILTER, COSName.FLATE_DECODE)  # type: ignore[attr-defined]

    image = PDImageXObject(stream)
    assert image.create_input_stream(["FlateDecode"]).read() == encoded
    assert image.create_input_stream().read() == b"pixels"
