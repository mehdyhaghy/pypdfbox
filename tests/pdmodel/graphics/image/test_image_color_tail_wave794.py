from __future__ import annotations

import zlib

from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.image import LosslessFactory, PDInlineImage
from pypdfbox.pdmodel.pd_document import PDDocument


class _ArraylessDeviceColor(PDColorSpace):
    def get_name(self) -> str:
        return "SyntheticDevice"

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self) -> object:
        return object()


def _decoded_body(image_x: object) -> bytes:
    cos = image_x.get_cos_object()
    assert isinstance(cos, COSStream)
    return zlib.decompress(cos.get_raw_data())


def _inline_params() -> COSDictionary:
    params = COSDictionary()
    params.set_int("W", 1)
    params.set_int("H", 1)
    params.set_int("BPC", 8)
    return params


def test_lossless_rgba_palette_list_is_normalized_and_padded() -> None:
    source = Image.new("P", (2, 1))
    source.putpalette(bytes([10, 20, 30, 255]), rawmode="RGBA")
    source.putpixel((0, 0), 0)
    source.putpixel((1, 0), 1)
    assert source.palette is not None
    source.palette.palette = [10, 20, 30, 255]

    document = PDDocument()
    try:
        image_x = LosslessFactory.create_from_image(document, source)

        color_space = image_x.get_color_space_cos_object()
        assert isinstance(color_space, COSArray)
        assert color_space.get_name(0) == "Indexed"
        assert color_space.get_int(2, -1) == 1
        lookup = color_space.get_object(3)
        assert isinstance(lookup, COSString)
        assert lookup.get_bytes() == bytes([10, 20, 30]) + b"\x00" * 3
        assert _decoded_body(image_x) == b"\x00\x01"
    finally:
        document.close()


def test_inline_image_arrayless_color_space_setter_stores_name() -> None:
    image = PDInlineImage(_inline_params(), b"\x00", None)

    image.set_color_space(_ArraylessDeviceColor())

    stored = image.get_color_space_cos_object()
    assert isinstance(stored, COSName)
    assert stored.get_name() == "SyntheticDevice"
