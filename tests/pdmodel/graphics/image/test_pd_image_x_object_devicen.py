"""Hand-written tests for DeviceN/Separation decoding in
``PDImageXObject.to_pil_image()``.

A small 2x2 raster is synthesised with a ``[/DeviceN [/Spot1 /Spot2]
/DeviceCMYK <Type 4 PS function>]`` colour space; the tint transform
reduces the two-component tint vector to a CMYK quadruple, and we
verify that each pixel composites through to the expected sRGB
triple.
"""

from __future__ import annotations

from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.graphics.image import PDImageXObject


def _float_array(values: list[float]) -> COSArray:
    arr = COSArray()
    for v in values:
        arr.add(COSFloat(float(v)))
    return arr


def _build_tint_transform_cmyk() -> COSStream:
    """Type 4 PostScript tint transform mapping (t1, t2) -> (C, M, Y, K).

    Program: ``{ 0 exch 0 }`` would only fit a single output; we need 4.
    The tint vector ``(t1, t2)`` is on the stack on entry. We map:

        C = t1
        M = t2
        Y = 0
        K = 0

    Using the PostScript program ``{ 0 0 }`` would only push two
    constants — we keep the inputs in place and then push two zeros, so
    the exit stack is ``[t1, t2, 0, 0]`` interpreted bottom-up as
    ``(C, M, Y, K)``.
    """
    body = b"{ 0 0 }"
    stream = COSStream()
    stream.set_int("FunctionType", 4)
    stream.set_item("Domain", _float_array([0.0, 1.0, 0.0, 1.0]))
    stream.set_item("Range", _float_array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]))
    stream.set_data(body)
    return stream


def _build_devicen_color_space() -> COSArray:
    """``[/DeviceN [/Spot1 /Spot2] /DeviceCMYK <tint transform stream>]``."""
    cs = COSArray()
    cs.add(COSName.get_pdf_name("DeviceN"))
    colorants = COSArray()
    colorants.add(COSName.get_pdf_name("Spot1"))
    colorants.add(COSName.get_pdf_name("Spot2"))
    cs.add(colorants)
    cs.add(COSName.get_pdf_name("DeviceCMYK"))
    cs.add(_build_tint_transform_cmyk())
    return cs


def _build_separation_color_space() -> COSArray:
    """``[/Separation /Spot1 /DeviceCMYK <tint transform>]`` mapping the
    single tint ``t`` to ``(0, t, 0, 0)`` (pure magenta scaled by tint).
    """
    body = b"{ 0 exch 0 0 }"
    tint = COSStream()
    tint.set_int("FunctionType", 4)
    tint.set_item("Domain", _float_array([0.0, 1.0]))
    tint.set_item("Range", _float_array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]))
    tint.set_data(body)

    cs = COSArray()
    cs.add(COSName.get_pdf_name("Separation"))
    cs.add(COSName.get_pdf_name("Spot1"))
    cs.add(COSName.get_pdf_name("DeviceCMYK"))
    cs.add(tint)
    return cs


# ---------- DeviceN ----------


def test_devicen_2x2_decodes_to_rgb() -> None:
    """A 2x2 DeviceN image with two spot components mapped to CMYK via
    the tint transform produces the expected sRGB pixels."""
    # Pixel layout: 2 colorants × 2x2 = 8 bytes total.
    #   (0, 0) tint = (255, 0)   -> CMYK(1.0, 0.0, 0.0, 0.0) -> RGB(0, 1, 1) cyan
    #   (1, 0) tint = (0, 255)   -> CMYK(0.0, 1.0, 0.0, 0.0) -> RGB(1, 0, 1) magenta
    #   (0, 1) tint = (0, 0)     -> CMYK(0.0, 0.0, 0.0, 0.0) -> RGB(1, 1, 1) white
    #   (1, 1) tint = (255, 255) -> CMYK(1.0, 1.0, 0.0, 0.0) -> RGB(0, 0, 1) blue
    raw = bytes([
        255, 0,   0, 255,
        0, 0,     255, 255,
    ])

    stream = COSStream()
    stream.set_raw_data(raw)
    image = PDImageXObject(stream)
    image.set_width(2)
    image.set_height(2)
    image.set_bits_per_component(8)
    stream.set_item("ColorSpace", _build_devicen_color_space())

    pil = image.to_pil_image()
    assert pil is not None
    assert pil.mode == "RGB"
    assert pil.size == (2, 2)
    assert pil.getpixel((0, 0)) == (0, 255, 255)
    assert pil.getpixel((1, 0)) == (255, 0, 255)
    assert pil.getpixel((0, 1)) == (255, 255, 255)
    assert pil.getpixel((1, 1)) == (0, 0, 255)


def test_devicen_falls_back_to_luminance_on_eval_failure() -> None:
    """A broken tint transform (unsupported operator) must not raise — the
    decoder logs at debug level and falls back to a luminance display."""
    bad_body = b"{ thisOperatorDoesNotExist }"
    bad_tint = COSStream()
    bad_tint.set_int("FunctionType", 4)
    bad_tint.set_item("Domain", _float_array([0.0, 1.0, 0.0, 1.0]))
    bad_tint.set_data(bad_body)

    cs = COSArray()
    cs.add(COSName.get_pdf_name("DeviceN"))
    colorants = COSArray()
    colorants.add(COSName.get_pdf_name("Spot1"))
    colorants.add(COSName.get_pdf_name("Spot2"))
    cs.add(colorants)
    cs.add(COSName.get_pdf_name("DeviceCMYK"))
    cs.add(bad_tint)

    raw = bytes([100, 200,  50, 150,
                 0, 0,      255, 255])
    stream = COSStream()
    stream.set_raw_data(raw)
    image = PDImageXObject(stream)
    image.set_width(2)
    image.set_height(2)
    image.set_bits_per_component(8)
    stream.set_item("ColorSpace", cs)

    pil = image.to_pil_image()
    assert pil is not None
    assert pil.mode == "RGB"
    # Each pixel should be the per-pixel byte average painted as gray.
    # (100+200)/2 = 150, (50+150)/2 = 100, (0+0)/2 = 0, (255+255)/2 = 255.
    assert pil.getpixel((0, 0)) == (150, 150, 150)
    assert pil.getpixel((1, 0)) == (100, 100, 100)
    assert pil.getpixel((0, 1)) == (0, 0, 0)
    assert pil.getpixel((1, 1)) == (255, 255, 255)


def test_devicen_short_raster_returns_none() -> None:
    """If the raster is shorter than ``width * height * n``, the helper
    declines rather than producing garbage."""
    stream = COSStream()
    stream.set_raw_data(b"\x00")  # 1 byte for a 2-component 2x2 image
    image = PDImageXObject(stream)
    image.set_width(2)
    image.set_height(2)
    image.set_bits_per_component(8)
    stream.set_item("ColorSpace", _build_devicen_color_space())

    assert image.to_pil_image() is None


# ---------- Separation ----------


def test_separation_2x2_decodes_to_rgb() -> None:
    """Single-component Separation -> CMYK(0, t, 0, 0). Tint 0/255 maps
    to white/magenta respectively."""
    raw = bytes([
        0, 255,
        128, 64,
    ])
    stream = COSStream()
    stream.set_raw_data(raw)
    image = PDImageXObject(stream)
    image.set_width(2)
    image.set_height(2)
    image.set_bits_per_component(8)
    stream.set_item("ColorSpace", _build_separation_color_space())

    pil = image.to_pil_image()
    assert pil is not None
    assert pil.mode == "RGB"
    assert pil.size == (2, 2)
    assert pil.getpixel((0, 0)) == (255, 255, 255)  # tint 0   -> white
    assert pil.getpixel((1, 0)) == (255, 0, 255)    # tint 1.0 -> magenta
    # tint 0.502 (128/255) -> (1, ~0.498, 1) -> approx (255, 127, 255)
    r1, g1, b1 = pil.getpixel((1, 1))
    assert r1 == 255 and b1 == 255
    r2, g2, b2 = pil.getpixel((0, 1))
    assert r2 == 255 and b2 == 255
    # Higher tint -> darker green channel.
    assert g1 > g2  # tint 64 < tint 128 → less magenta → more green at (1,1)


def test_separation_no_tint_transform_falls_back_to_luminance() -> None:
    """Separation with no tint transform (placeholder ``COSName("")``)
    must drop to the luminance fallback rather than crashing."""
    cs = COSArray()
    cs.add(COSName.get_pdf_name("Separation"))
    cs.add(COSName.get_pdf_name("Spot1"))
    cs.add(COSName.get_pdf_name("DeviceCMYK"))
    cs.add(COSName.get_pdf_name(""))  # invalid tint transform placeholder

    raw = bytes([0, 64, 192, 255])
    stream = COSStream()
    stream.set_raw_data(raw)
    image = PDImageXObject(stream)
    image.set_width(2)
    image.set_height(2)
    image.set_bits_per_component(8)
    stream.set_item("ColorSpace", cs)

    pil = image.to_pil_image()
    assert pil is not None
    assert pil.mode == "RGB"
    # Luminance fallback for n=1: each tint byte becomes the gray value.
    assert pil.getpixel((0, 0)) == (0, 0, 0)
    assert pil.getpixel((1, 0)) == (64, 64, 64)
    assert pil.getpixel((0, 1)) == (192, 192, 192)
    assert pil.getpixel((1, 1)) == (255, 255, 255)


# ---------- Inline image equivalent ----------


def test_inline_image_devicen_2x2_decodes_to_rgb() -> None:
    """Mirror ``test_devicen_2x2_decodes_to_rgb`` against the inline-image
    surface to confirm the shared decode helper is wired through."""
    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage

    parameters = COSDictionary()
    parameters.set_int("W", 2)
    parameters.set_int("H", 2)
    parameters.set_int("BPC", 8)
    parameters.set_item("CS", _build_devicen_color_space())

    raw = bytes([
        255, 0,   0, 255,
        0, 0,     255, 255,
    ])
    inline = PDInlineImage(parameters, raw, None)

    pil = inline.to_pil_image()
    assert pil is not None
    assert pil.mode == "RGB"
    assert pil.getpixel((0, 0)) == (0, 255, 255)
    assert pil.getpixel((1, 0)) == (255, 0, 255)
    assert pil.getpixel((0, 1)) == (255, 255, 255)
    assert pil.getpixel((1, 1)) == (0, 0, 255)


def test_returns_pil_image_instance() -> None:
    """Sanity check on the helper's return type."""
    raw = bytes([255, 0, 0, 255, 0, 0, 255, 255])
    stream = COSStream()
    stream.set_raw_data(raw)
    image = PDImageXObject(stream)
    image.set_width(2)
    image.set_height(2)
    image.set_bits_per_component(8)
    stream.set_item("ColorSpace", _build_devicen_color_space())
    pil = image.to_pil_image()
    assert isinstance(pil, Image.Image)
