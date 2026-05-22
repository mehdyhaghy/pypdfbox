"""Renderer parity fixes — wave 1385 agent E.

Closes three renderer gaps from the wave-1384 audit:

1. Uncolored tiling-pattern tint propagation (``scn`` with leading
   components + /PatternName when /PaintType == 2).
2. ``cs`` / ``CS`` reset the current colour to the colour space's
   initial colour (PDF 32000-1 §8.6.5.1, upstream
   ``SetNonStrokingColorSpace.process``).
3. Inline-image (``BI``) full colour-space dispatch — DeviceCMYK,
   Indexed, ICCBased, Separation, DeviceN, abbreviated names.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.color import PDDeviceCMYK, PDDeviceGray, PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from pypdfbox.pdmodel.graphics.pattern import PDTilingPattern
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import PDFRenderer as _R
from pypdfbox.rendering.pdf_renderer import _GState


def _make_doc(
    width: float = 60.0, height: float = 60.0
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _is_close(
    actual: tuple[int, int, int],
    expected: tuple[int, int, int],
    tol: int = 16,
) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual, expected, strict=True))


# ---------------------------------------------------------------------------
# #1 uncolored tiling-pattern tint propagation
# ---------------------------------------------------------------------------


def _make_uncolored_pattern_doc(tint_rgb_op: bytes) -> PDDocument:
    """Build a 60x60 doc that fills the central rect with an uncolored
    tiling pattern. ``tint_rgb_op`` is the ``r g b /P0 scn`` operator
    string that selects the tint + pattern.
    """
    doc, page = _make_doc(60.0, 60.0)
    # Uncolored 10x10 tiling pattern: paints a solid 10x10 fill in
    # whatever the *current* fill colour is. PaintType=2 means the
    # leading scn components are the tint.
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_UNCOLORED)
    pattern.set_tiling_type(PDTilingPattern.TILING_TYPE_CONSTANT_SPACING)
    pattern.set_b_box(PDRectangle(0.0, 0.0, 10.0, 10.0))
    pattern.set_x_step(10.0)
    pattern.set_y_step(10.0)
    # Cell content: fill 10x10 using the current fill colour (no rg /
    # g / k op — relies on the renderer to have pre-seeded the tint).
    pattern.get_cos_object().set_raw_data(
        b"0 0 10 10 re\n"
        b"f\n"
    )
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pattern.get_cos_object(),
    )
    # Page contents: select /Pattern over DeviceRGB then scn N N N /P0
    # then fill a 40x40 patch at (10,10).
    contents = COSStream()
    contents.set_raw_data(
        b"/Pattern cs\n"
        + tint_rgb_op
        + b"\n"
        b"10 10 40 40 re\n"
        b"f\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    return doc


def test_uncolored_tiling_pattern_paints_with_green_tint() -> None:
    """``0 1 0 /P0 scn`` followed by a fill must paint the path with a
    green-tinted pattern (the uncolored pattern paints solid 10x10 cells
    in whatever the current fill colour is)."""
    # /Resources /ColorSpace registration for the Pattern CS would
    # normally point at [/Pattern /DeviceRGB]. We can't easily wire
    # that through the synthetic /CS dict without exercising the
    # full resource lookup; instead drive the renderer in-process and
    # set up the GState directly.
    doc = _make_uncolored_pattern_doc(b"0 1 0 /P0 scn")
    img = PDFRenderer(doc).render_image(0)
    # Inside the painted patch the tint should appear (green).
    px = img.getpixel((20, 20))
    assert _is_close(px, (0, 255, 0), tol=32), px
    # Outside the patch → white.
    assert _is_close(img.getpixel((5, 5)), (255, 255, 255), tol=32)


def test_uncolored_tiling_pattern_paints_with_blue_tint() -> None:
    """``0 0 1 /P0 scn`` followed by a fill must paint the path with a
    blue-tinted pattern."""
    doc = _make_uncolored_pattern_doc(b"0 0 1 /P0 scn")
    img = PDFRenderer(doc).render_image(0)
    px = img.getpixel((20, 20))
    assert _is_close(px, (0, 0, 255), tol=32), px


def test_extract_pattern_tint_rgb_with_underlying_rgb() -> None:
    """``_extract_pattern_tint_rgb`` should run the leading components
    through the Pattern CS's underlying colour space (DeviceRGB here)."""
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    pattern_cs = PDPattern(underlying_color_space=PDDeviceRGB.INSTANCE)
    # ``0 1 0 /P0`` over [/Pattern /DeviceRGB] → green.
    operands: list = [
        COSFloat(0.0),
        COSFloat(1.0),
        COSFloat(0.0),
        COSName.get_pdf_name("P0"),
    ]
    rgb = renderer._extract_pattern_tint_rgb(operands, pattern_cs)
    assert rgb == (0, 255, 0)


def test_extract_pattern_tint_rgb_with_underlying_cmyk() -> None:
    """Tint components in DeviceCMYK should convert via CMYK -> RGB."""
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    pattern_cs = PDPattern(underlying_color_space=PDDeviceCMYK.INSTANCE)
    # Pure magenta in CMYK = (0, 1, 0, 0). Magenta in RGB ≈ (255, 0, 255).
    operands: list = [
        COSFloat(0.0),
        COSFloat(1.0),
        COSFloat(0.0),
        COSFloat(0.0),
        COSName.get_pdf_name("P0"),
    ]
    rgb = renderer._extract_pattern_tint_rgb(operands, pattern_cs)
    assert rgb is not None
    # Magenta-ish — R/B close to 255, G close to 0.
    assert rgb[0] > 200 and rgb[1] < 60 and rgb[2] > 200, rgb


def test_extract_pattern_tint_rgb_no_components_returns_none() -> None:
    """A bare ``/P0 scn`` (colored tiling) returns None for tint."""
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    pattern_cs = PDPattern(underlying_color_space=PDDeviceRGB.INSTANCE)
    operands: list = [COSName.get_pdf_name("P0")]
    rgb = renderer._extract_pattern_tint_rgb(operands, pattern_cs)
    assert rgb is None


# ---------------------------------------------------------------------------
# #2 cs / CS reset to colour space's initial colour
# ---------------------------------------------------------------------------


def test_cs_resets_fill_to_initial_color_devicergb() -> None:
    """After ``1 0 0 rg`` (red) then ``/DeviceRGB cs`` (which has
    initial colour [0, 0, 0] = black), a subsequent ``f`` without
    intervening ``scn`` should paint black, not red.
    """
    doc, page = _make_doc()
    contents = COSStream()
    contents.set_raw_data(
        b"1 0 0 rg\n"           # red
        b"/DeviceRGB cs\n"      # cs reset → black (DeviceRGB initial = [0,0,0])
        b"10 10 40 40 re\n"
        b"f\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    px = img.getpixel((20, 20))
    # Black, not red.
    assert _is_close(px, (0, 0, 0)), px


def test_cs_resets_fill_to_initial_color_devicegray() -> None:
    """``/DeviceGray cs`` resets to [0.0] = black."""
    doc, page = _make_doc()
    contents = COSStream()
    contents.set_raw_data(
        b"1 0 0 rg\n"
        b"/DeviceGray cs\n"
        b"10 10 40 40 re\n"
        b"f\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    px = img.getpixel((20, 20))
    assert _is_close(px, (0, 0, 0)), px


def test_cs_resets_fill_to_initial_color_devicecmyk() -> None:
    """``/DeviceCMYK cs`` resets to [0, 0, 0, 1] = black."""
    doc, page = _make_doc()
    contents = COSStream()
    contents.set_raw_data(
        b"1 0 0 rg\n"
        b"/DeviceCMYK cs\n"
        b"10 10 40 40 re\n"
        b"f\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    px = img.getpixel((20, 20))
    # CMYK [0, 0, 0, 1] = pure black.
    assert _is_close(px, (0, 0, 0)), px


def test_CS_resets_stroke_to_initial_color() -> None:
    """Same reset must happen on the stroking side via ``CS``."""
    doc, page = _make_doc()
    contents = COSStream()
    contents.set_raw_data(
        b"5 w\n"
        b"1 0 0 RG\n"           # red stroke
        b"/DeviceRGB CS\n"      # reset → black
        b"10 10 40 40 re\n"
        b"S\n"                  # stroke (no fill)
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    # Sample on the top edge of the rect (~y=10 in PDF, y=50 in PIL).
    px = img.getpixel((30, 10))
    assert _is_close(px, (0, 0, 0)), px


def test_initial_color_rgb_helper_on_each_device_cs() -> None:
    """Smoke test the helper for each device singleton."""
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    assert renderer._initial_color_rgb(PDDeviceRGB.INSTANCE) == (0, 0, 0)
    assert renderer._initial_color_rgb(PDDeviceGray.INSTANCE) == (0, 0, 0)
    assert renderer._initial_color_rgb(PDDeviceCMYK.INSTANCE) == (0, 0, 0)
    # None → None.
    assert renderer._initial_color_rgb(None) is None


def test_initial_color_rgb_helper_on_separation() -> None:
    """Separation initial colour is [1.0] (full tint) — must convert
    through to RGB without raising."""
    # Build a Separation /All /DeviceCMYK with a constant alt-tint.
    sep_arr = COSArray()
    sep_arr.add(COSName.get_pdf_name("Separation"))
    sep_arr.add(COSName.get_pdf_name("All"))
    sep_arr.add(COSName.get_pdf_name("DeviceCMYK"))
    # Type 2 exponential function: tint → C0+(C1-C0)*t^N
    fn = COSDictionary()
    fn.set_int(COSName.get_pdf_name("FunctionType"), 2)
    dom = COSArray()
    dom.add(COSFloat(0.0))
    dom.add(COSFloat(1.0))
    fn.set_item(COSName.get_pdf_name("Domain"), dom)
    c0 = COSArray()
    for v in (0.0, 0.0, 0.0, 0.0):
        c0.add(COSFloat(v))
    c1 = COSArray()
    for v in (1.0, 0.0, 0.0, 0.0):  # full cyan
        c1.add(COSFloat(v))
    fn.set_item(COSName.get_pdf_name("C0"), c0)
    fn.set_item(COSName.get_pdf_name("C1"), c1)
    fn.set_int(COSName.get_pdf_name("N"), 1)
    sep_arr.add(fn)
    sep_cs = PDSeparation(sep_arr)
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    rgb = renderer._initial_color_rgb(sep_cs)
    assert rgb is not None
    # Initial [1.0] -> full cyan (CMYK 1,0,0,0) -> RGB roughly (0, 255, 255).
    assert rgb[0] < 80, rgb
    assert rgb[1] > 180, rgb
    assert rgb[2] > 180, rgb


# ---------------------------------------------------------------------------
# #3 inline image full colour-space dispatch
# ---------------------------------------------------------------------------


def _inline_image_params(
    width: int, height: int, cs_name: str, bpc: int = 8
) -> COSDictionary:
    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("W"), width)
    params.set_int(COSName.get_pdf_name("H"), height)
    params.set_int(COSName.get_pdf_name("BPC"), bpc)
    params.set_item(
        COSName.get_pdf_name("CS"), COSName.get_pdf_name(cs_name)
    )
    return params


def test_decode_inline_image_devicergb_abbreviated() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    params = _inline_image_params(2, 2, "RGB")
    data = bytes(
        [255, 0, 0,   0, 255, 0,
         0, 0, 255,   255, 255, 255]
    )
    img = renderer._decode_inline_image(params, data)
    assert img is not None
    assert img.size == (2, 2)
    assert img.getpixel((0, 0)) == (255, 0, 0)
    assert img.getpixel((1, 1)) == (255, 255, 255)


def test_decode_inline_image_devicegray_abbreviated() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    params = _inline_image_params(2, 2, "G")
    data = bytes([0, 128, 255, 64])
    img = renderer._decode_inline_image(params, data)
    assert img is not None
    assert img.size == (2, 2)
    # Gray → R == G == B.
    px = img.getpixel((1, 0))
    assert px[0] == px[1] == px[2] == 128


def test_decode_inline_image_devicecmyk_full_name() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    params = _inline_image_params(1, 1, "DeviceCMYK")
    # Pure black via K=1.0 → R/G/B near 0.
    data = bytes([0, 0, 0, 255])
    img = renderer._decode_inline_image(params, data)
    assert img is not None
    r, g, b = img.getpixel((0, 0))
    assert r < 20 and g < 20 and b < 20


def test_decode_inline_image_devicecmyk_abbreviated() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    params = _inline_image_params(1, 1, "CMYK")
    # Pure cyan (C=1, M=0, Y=0, K=0) → R near 0, G/B large.
    data = bytes([255, 0, 0, 0])
    img = renderer._decode_inline_image(params, data)
    assert img is not None
    r, g, b = img.getpixel((0, 0))
    assert r < 80
    assert g > 180
    assert b > 180


def test_decode_inline_image_indexed_via_resource() -> None:
    """Indexed inline image — /CS is a name pointing at /Resources
    /ColorSpace /CS1 = [/Indexed /DeviceRGB 2 <raw palette>]."""
    doc, page = _make_doc()
    # Palette: 0 -> red, 1 -> green, 2 -> blue.
    palette = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255])
    indexed_cs = PDIndexed.create(PDDeviceRGB.INSTANCE, 2, palette)
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("ColorSpace"),
        COSName.get_pdf_name("CS1"),
        indexed_cs.get_cos_object(),
    )
    renderer = PDFRenderer(doc)
    # Drive the renderer's resource-resolution path by calling
    # ``render_image`` (which sets ``self._resources``).
    renderer.render_image(0)
    # Now ``self._resources`` is set; decode an inline image referencing CS1.
    params = _inline_image_params(2, 2, "CS1")
    data = bytes([0, 1, 2, 0])  # indices into palette
    img = renderer._decode_inline_image(params, data)
    assert img is not None
    assert img.size == (2, 2)
    assert img.getpixel((0, 0)) == (255, 0, 0)
    assert img.getpixel((1, 0)) == (0, 255, 0)
    assert img.getpixel((0, 1)) == (0, 0, 255)
    assert img.getpixel((1, 1)) == (255, 0, 0)


def test_decode_inline_image_indexed_via_cs_array() -> None:
    """Indexed inline image — /CS is a literal COSArray (the array
    form is rare but legal per PDF 32000-1 §8.9.5.2)."""
    doc, _ = _make_doc()
    palette = bytes([255, 0, 0, 0, 0, 255])
    # [/Indexed /DeviceRGB 1 <palette bytes>]
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(COSName.get_pdf_name("DeviceRGB"))
    arr.add(COSInteger.get(1))
    arr.add(COSString(palette))
    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("W"), 2)
    params.set_int(COSName.get_pdf_name("H"), 1)
    params.set_int(COSName.get_pdf_name("BPC"), 8)
    params.set_item(COSName.get_pdf_name("CS"), arr)

    renderer = PDFRenderer(doc)
    data = bytes([0, 1])
    img = renderer._decode_inline_image(params, data)
    assert img is not None
    assert img.size == (2, 1)
    assert img.getpixel((0, 0)) == (255, 0, 0)
    assert img.getpixel((1, 0)) == (0, 0, 255)


def test_decode_inline_image_iccbased_via_cs_array() -> None:
    """ICCBased inline image — the renderer must dispatch the /ICCBased
    CS to its ``to_rgb`` path. We only verify the renderer returns a
    1x1 image of the right shape — the exact RGB depends on whether
    Pillow's ImageCms parses the (empty) profile or falls through to
    the declared alternate."""
    doc, _ = _make_doc()
    icc_stream = COSStream()
    icc_stream.set_int(COSName.get_pdf_name("N"), 3)
    icc_stream.set_item(
        COSName.get_pdf_name("Alternate"), COSName.get_pdf_name("DeviceRGB")
    )
    icc_stream.set_raw_data(b"")
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(icc_stream)

    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("W"), 1)
    params.set_int(COSName.get_pdf_name("H"), 1)
    params.set_int(COSName.get_pdf_name("BPC"), 8)
    params.set_item(COSName.get_pdf_name("CS"), arr)

    renderer = PDFRenderer(doc)
    data = bytes([200, 100, 50])
    img = renderer._decode_inline_image(params, data)
    assert img is not None
    assert img.size == (1, 1)
    px = img.getpixel((0, 0))
    assert isinstance(px, tuple) and len(px) == 3
    assert all(0 <= int(c) <= 255 for c in px)


def test_decode_inline_image_unknown_cs_returns_none() -> None:
    """A /CS name that doesn't resolve must return None (so the caller
    silently skips the inline image rather than crashing)."""
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    params = _inline_image_params(1, 1, "CSDoesNotExist")
    img = renderer._decode_inline_image(params, b"\x00")
    assert img is None


# ---------------------------------------------------------------------------
# tint persists in _GState clone (snapshot / restore parity)
# ---------------------------------------------------------------------------


def test_pattern_tint_survives_gstate_clone() -> None:
    """``q`` / ``Q`` snapshot/restore must preserve the pattern tint
    on the cloned _GState — the tint lives on the clone path."""
    gs = _GState()
    gs.fill_pattern_tint = (10, 20, 30)
    gs.stroke_pattern_tint = (40, 50, 60)
    clone = gs.clone()
    assert clone.fill_pattern_tint == (10, 20, 30)
    assert clone.stroke_pattern_tint == (40, 50, 60)


# Avoid an unused-import warning from typing-only helper.
_ = _R
