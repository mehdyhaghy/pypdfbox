from __future__ import annotations

import zlib

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSName, COSStream, COSString
from pypdfbox.pdmodel.graphics.image import LosslessFactory, lossless_factory
from pypdfbox.pdmodel.pd_document import PDDocument


def _decoded_body(image_x) -> bytes:
    cos = image_x.get_cos_object()
    assert isinstance(cos, COSStream)
    return zlib.decompress(cos.get_raw_data())


def test_large_one_bit_image_falls_back_to_flate_when_ccitt_encoding_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_from_encode(*_args, **_kwargs) -> None:
        raise OSError("ccitt unavailable")

    monkeypatch.setattr(lossless_factory.CCITTFaxDecode, "encode", raise_from_encode)
    document = PDDocument()
    source = Image.new("1", (64, 64), color=1)
    source.putpixel((0, 0), 0)

    image_x = LosslessFactory.create_from_image(document, source)

    assert isinstance(image_x.get_filter(), COSName)
    assert image_x.get_filter().name == "FlateDecode"
    assert image_x.get_bits_per_component() == 1
    assert _decoded_body(image_x) == source.tobytes()


def test_palette_without_palette_data_converts_to_rgb(monkeypatch: pytest.MonkeyPatch) -> None:
    document = PDDocument()
    source = Image.new("P", (2, 1))
    source.putpixel((0, 0), 0)
    source.putpixel((1, 0), 1)
    monkeypatch.setattr(source, "getpalette", lambda: None)

    image_x = LosslessFactory.create_from_image(document, source)

    color_space = image_x.get_color_space_cos_object()
    assert isinstance(color_space, COSName)
    assert color_space.name == "DeviceRGB"
    assert _decoded_body(image_x) == source.convert("RGB").tobytes()


def test_rgba_palette_is_normalized_to_indexed_rgb_lookup() -> None:
    document = PDDocument()
    source = Image.new("P", (2, 1))
    source.putpalette(
        bytes([10, 20, 30, 255, 40, 50, 60, 128]),
        rawmode="RGBA",
    )
    source.putpixel((0, 0), 0)
    source.putpixel((1, 0), 1)

    image_x = LosslessFactory.create_from_image(document, source)

    color_space = image_x.get_color_space_cos_object()
    assert isinstance(color_space, COSArray)
    lookup = color_space.get_object(3)
    assert isinstance(lookup, COSString)
    assert lookup.get_bytes() == bytes([10, 20, 30, 40, 50, 60])
    assert _decoded_body(image_x) == b"\x00\x01"


def test_palette_alpha_table_builds_eight_bit_soft_mask() -> None:
    document = PDDocument()
    source = Image.new("P", (3, 1))
    source.putpalette([10, 20, 30, 40, 50, 60, 70, 80, 90] + [0] * (256 * 3 - 9))
    source.putpixel((0, 0), 0)
    source.putpixel((1, 0), 1)
    source.putpixel((2, 0), 2)
    source.info["transparency"] = bytes([0, 128])

    image_x = LosslessFactory.create_from_image(document, source)

    smask = image_x.get_soft_mask()
    assert smask is not None
    assert smask.get_bits_per_component() == 8
    assert _decoded_body(smask) == bytes([0, 128, 255])


def test_palette_lookup_is_padded_when_palette_is_short() -> None:
    source = Image.new("P", (2, 1))
    source.putpalette([10, 20, 30] + [0] * (256 * 3 - 3))
    source.putpixel((0, 0), 0)
    source.putpixel((1, 0), 3)
    source.palette.palette = bytes([10, 20, 30])

    image_x = LosslessFactory.create_from_image(PDDocument(), source)

    color_space = image_x.get_color_space_cos_object()
    assert isinstance(color_space, COSArray)
    assert color_space.get_int(2, -1) == 3
    lookup = color_space.get_object(3)
    assert isinstance(lookup, COSString)
    assert lookup.get_bytes() == bytes([10, 20, 30]) + b"\x00" * 9


def test_pa_image_converts_through_palette_path() -> None:
    document = PDDocument()
    source = Image.new("PA", (2, 1))
    source.putpalette([1, 2, 3, 4, 5, 6] + [0] * (256 * 3 - 6))
    source.putpixel((0, 0), (0, 255))
    source.putpixel((1, 0), (1, 128))

    image_x = LosslessFactory.create_from_image(document, source)

    color_space = image_x.get_color_space_cos_object()
    assert isinstance(color_space, COSArray)
    first = color_space.get_object(0)
    assert isinstance(first, COSName)
    assert first.name == "Indexed"
    assert _decoded_body(image_x) == b"\x00\x01"
