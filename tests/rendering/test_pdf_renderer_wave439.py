from __future__ import annotations

import io

from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.rendering.pdf_renderer import PDFRenderer


def _inline_params(
    *,
    width: int | None = 1,
    height: int | None = 1,
    bits_per_component: int | None = 8,
    color_space: str | None = "RGB",
    use_long_names: bool = False,
) -> COSDictionary:
    params = COSDictionary()
    if width is not None:
        params.set_item(
            COSName.get_pdf_name("Width" if use_long_names else "W"),
            COSInteger.get(width),
        )
    if height is not None:
        params.set_item(
            COSName.get_pdf_name("Height" if use_long_names else "H"),
            COSInteger.get(height),
        )
    if bits_per_component is not None:
        params.set_item(
            COSName.get_pdf_name("BitsPerComponent" if use_long_names else "BPC"),
            COSInteger.get(bits_per_component),
        )
    if color_space is not None:
        params.set_item(
            COSName.get_pdf_name("ColorSpace" if use_long_names else "CS"),
            COSName.get_pdf_name(color_space),
        )
    return params


def test_decode_inline_image_expands_abbreviated_rgb_gray_and_jpeg() -> None:
    rgb_params = _inline_params(width=2, height=1, color_space="RGB")
    rgb = PDFRenderer._decode_inline_image(  # noqa: SLF001
        rgb_params,
        bytes([255, 0, 0, 0, 255, 0]),
    )
    assert rgb is not None
    assert rgb.mode == "RGB"
    assert rgb.size == (2, 1)
    assert rgb.getpixel((0, 0)) == (255, 0, 0)
    assert rgb.getpixel((1, 0)) == (0, 255, 0)

    gray_params = _inline_params(
        width=2,
        height=1,
        color_space="DeviceGray",
        use_long_names=True,
    )
    gray = PDFRenderer._decode_inline_image(gray_params, bytes([0, 255]))  # noqa: SLF001
    assert gray is not None
    assert gray.mode == "RGB"
    assert gray.getpixel((0, 0)) == (0, 0, 0)
    assert gray.getpixel((1, 0)) == (255, 255, 255)

    source = Image.new("RGB", (1, 1), (12, 34, 56))
    payload = io.BytesIO()
    source.save(payload, format="JPEG", quality=95)

    jpeg_params = _inline_params(color_space="RGB")
    filters = COSArray()
    filters.add(COSName.get_pdf_name("DCT"))
    jpeg_params.set_item(COSName.get_pdf_name("F"), filters)
    jpeg = PDFRenderer._decode_inline_image(jpeg_params, payload.getvalue())  # noqa: SLF001
    assert jpeg is not None
    assert jpeg.mode == "RGB"
    assert jpeg.size == (1, 1)


def test_decode_inline_image_rejects_malformed_or_deferred_payloads() -> None:
    assert (
        PDFRenderer._decode_inline_image(  # noqa: SLF001
            _inline_params(width=None), b"\x00\x00\x00"
        )
        is None
    )
    assert (
        PDFRenderer._decode_inline_image(  # noqa: SLF001
            _inline_params(height=0), b"\x00\x00\x00"
        )
        is None
    )
    assert (
        PDFRenderer._decode_inline_image(  # noqa: SLF001
            _inline_params(bits_per_component=1), b"\x00"
        )
        is None
    )

    compressed_params = _inline_params()
    compressed_params.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("Fl"))
    assert PDFRenderer._decode_inline_image(compressed_params, b"\x00") is None  # noqa: SLF001

    cmyk_params = _inline_params(color_space="CMYK")
    assert (
        PDFRenderer._decode_inline_image(  # noqa: SLF001
            cmyk_params, bytes([0, 0, 0, 0])
        )
        is None
    )


def test_decode_inline_image_accepts_numeric_float_dimensions() -> None:
    params = COSDictionary()
    params.set_item(COSName.get_pdf_name("W"), COSFloat(1.0))
    params.set_item(COSName.get_pdf_name("H"), COSFloat(1.0))
    params.set_item(COSName.get_pdf_name("BPC"), COSInteger.get(8))

    decoded = PDFRenderer._decode_inline_image(params, bytes([1, 2, 3]))  # noqa: SLF001

    assert decoded is not None
    assert decoded.getpixel((0, 0)) == (1, 2, 3)
