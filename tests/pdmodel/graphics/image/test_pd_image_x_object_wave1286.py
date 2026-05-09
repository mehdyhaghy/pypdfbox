from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream, COSString
from pypdfbox.pdmodel.graphics.color import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.image import PDImageXObject


def _image(data: bytes, color_space: str, *, width: int, height: int, bpc: int) -> PDImageXObject:
    image = PDImageXObject(COSStream())
    image.set_width(width)
    image.set_height(height)
    image.set_bits_per_component(bpc)
    image.set_color_space(color_space)
    image.get_cos_object().set_raw_data(data)
    return image


def _indexed_space(hival: int, lookup: bytes) -> PDIndexed:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(hival))
    arr.add(COSString(lookup))
    return PDIndexed(arr)


def _indexed_image(
    data: bytes, indexed: PDIndexed, *, width: int, height: int, bpc: int
) -> PDImageXObject:
    image = PDImageXObject(COSStream())
    image.set_width(width)
    image.set_height(height)
    image.set_bits_per_component(bpc)
    image.set_color_space(indexed)
    image.get_cos_object().set_raw_data(data)
    return image


def test_wave1286_to_pil_image_decodes_one_bit_devicegray() -> None:
    image = _image(b"\xa0", "DeviceGray", width=4, height=1, bpc=1)

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.tobytes() == bytes(
        [255, 255, 255, 0, 0, 0, 255, 255, 255, 0, 0, 0]
    )


def test_wave1286_to_pil_image_applies_one_bit_devicegray_decode() -> None:
    image = _image(b"\xa0", "DeviceGray", width=4, height=1, bpc=1)
    image.set_decode([1.0, 0.0])

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.tobytes() == bytes(
        [0, 0, 0, 255, 255, 255, 0, 0, 0, 255, 255, 255]
    )


def test_wave1286_to_pil_image_expands_two_bit_indexed_samples() -> None:
    indexed = _indexed_space(
        3,
        bytes(
            [
                10,
                0,
                0,
                0,
                20,
                0,
                0,
                0,
                30,
                40,
                50,
                60,
            ]
        ),
    )
    image = _indexed_image(b"\x1b", indexed, width=4, height=1, bpc=2)

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.tobytes() == bytes([10, 0, 0, 0, 20, 0, 0, 0, 30, 40, 50, 60])


def test_wave1286_to_pil_image_expands_four_bit_indexed_with_row_padding() -> None:
    lookup = bytearray()
    for value in range(7):
        lookup.extend([value, value + 10, value + 20])
    indexed = _indexed_space(6, bytes(lookup))
    image = _indexed_image(b"\x12\x30\x45\x60", indexed, width=3, height=2, bpc=4)

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.tobytes() == bytes(
        [
            1,
            11,
            21,
            2,
            12,
            22,
            3,
            13,
            23,
            4,
            14,
            24,
            5,
            15,
            25,
            6,
            16,
            26,
        ]
    )


def test_wave1286_to_pil_image_applies_two_bit_indexed_decode() -> None:
    indexed = _indexed_space(3, bytes([10, 0, 0, 0, 20, 0, 0, 0, 30, 40, 50, 60]))
    image = _indexed_image(b"\x30", indexed, width=2, height=1, bpc=2)
    image.set_decode([3.0, 0.0])

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.tobytes() == bytes([40, 50, 60, 10, 0, 0])
