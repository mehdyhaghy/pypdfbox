"""Wave 1590 — image-XObject unit-square -> device CTM mapping + stencil
paint fuzz.

Hammers the helpers behind upstream ``PageDrawer.drawImage`` as ported in
``pypdfbox.rendering.pdf_renderer``:

* ``_full_ctm`` / ``_apply`` — a PDF image XObject occupies the unit square
  [0,1]x[0,1] in user space; the ``w 0 0 h x y cm`` operator that precedes
  ``Do`` places + scales (+ rotates) it. The image's top row (unit-square
  y=1) must land at device y-min (screen top) because the page device CTM
  already bakes in the user-space y-flip (the ``-scale`` d component). We
  assert the mapped bbox of the unit square matches ``[x, y, x+w, y+h]``
  in *flipped* device pixels with no extra image-side FLIP_TOP_BOTTOM.
* ``_paste_image`` — the raster blit is mocked so we can assert *where*
  the image lands (origin + target size) for identity, pure-scale,
  translated, and rotated CTMs, independent of pixel content.
* ``_paint_stencil_mask`` — an ``/ImageMask true`` stencil is painted in
  the current *non-stroking* (fill) colour, not from the image samples;
  ``/Decode [0 1]`` (default) makes sample-0 opaque, ``/Decode [1 0]``
  reverses the polarity. We assert the RGBA matte handed to the blit
  carries the fill RGB everywhere and the alpha tracks the decode sense.
* ``/Interpolate`` threading — false -> NEAREST, true -> BICUBIC resample.

These exercise the CTM mapping + stencil-colour selection directly with a
mocked blit, then a handful of end-to-end ``render_image`` placements pin
the on-canvas result.
"""

from __future__ import annotations

import math

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _matmul

# ----------------------------------------------------------------- helpers


def _make_doc(width: float = 100.0, height: float = 100.0):
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _renderer_with_canvas(width_px: int = 100, height_px: int = 100, scale: float = 1.0):
    """Build a PDFRenderer with a live RGB canvas and a device CTM whose
    d-component carries the user-space y-flip (origin lower-left -> pixel
    upper-left), exactly as ``_render_page_into`` sets up."""
    doc, _ = _make_doc(float(width_px) / scale, float(height_px) / scale)
    rdr = PDFRenderer(doc)
    rdr._image = Image.new("RGB", (width_px, height_px), (255, 255, 255))
    from pypdfbox.rendering import _aggdraw_compat as aggdraw

    rdr._draw = aggdraw.Draw(rdr._image)
    rdr._gs_stack = [_gstate_fresh()]
    # Device CTM: scale + y-flip (matches set_page_size's flip_scale with a
    # zero mediabox origin and no page rotation).
    rdr._device_ctm = (scale, 0.0, 0.0, -scale, 0.0, float(height_px))
    return doc, rdr


def _gstate_fresh():
    from pypdfbox.rendering.pdf_renderer import _GState

    return _GState()


class _BlitRecorder:
    """Captures the args passed to ``Image.paste`` so a test can assert the
    paste origin / pasted-image size without inspecting pixels."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def install(self, rdr) -> None:
        recorder = self

        def fake_paste(im, box=None, mask=None):  # noqa: ANN001
            recorder.calls.append(
                {
                    "image": im,
                    "box": box,
                    "mask": mask,
                }
            )

        rdr._image.paste = fake_paste  # type: ignore[method-assign]


# ============================================================ CTM mapping


def _unit_square_bbox(rdr):
    """Map the unit square's four corners through the full CTM and return
    the integer device bbox the way ``_paste_image`` computes it."""
    ctm = rdr._full_ctm()
    corners = [
        rdr._apply((0.0, 0.0), ctm),
        rdr._apply((1.0, 0.0), ctm),
        rdr._apply((1.0, 1.0), ctm),
        rdr._apply((0.0, 1.0), ctm),
    ]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    return (
        round(min(xs)),
        round(min(ys)),
        round(max(xs)),
        round(max(ys)),
    )


@pytest.mark.parametrize(
    ("w", "h", "x", "y"),
    [
        (40.0, 40.0, 10.0, 10.0),
        (50.0, 20.0, 0.0, 0.0),
        (30.0, 30.0, 70.0, 70.0),
        (100.0, 100.0, 0.0, 0.0),
        (25.0, 60.0, 5.0, 30.0),
        (1.0, 1.0, 50.0, 50.0),
    ],
    ids=["centered", "fullw_at_origin", "topright", "fullpage", "tall", "tiny"],
)
def test_unit_square_maps_to_cm_box_with_yflip(w, h, x, y) -> None:
    """A ``w 0 0 h x y cm`` places the unit-square image to cover the
    user-space rect [x, y, x+w, y+h]. With the page y-flip the device bbox
    is [x, H-(y+h), x+w, H-y]. The image top (unit y=1) lands at the
    *smaller* device y (screen top)."""
    page_h = 100.0
    doc, rdr = _renderer_with_canvas(int(page_h), int(page_h))
    try:
        # cm: scale (w,h), translate (x,y), post-multiplied onto identity.
        rdr._gs.ctm = (w, 0.0, 0.0, h, x, y)
        bx0, by0, bx1, by1 = _unit_square_bbox(rdr)
        assert bx0 == round(x)
        assert bx1 == round(x + w)
        # y-flip: user y=y+h (top) -> device y = H-(y+h) = bbox min y.
        assert by0 == round(page_h - (y + h))
        assert by1 == round(page_h - y)
    finally:
        doc.close()


def test_image_top_row_lands_at_device_top_not_bottom() -> None:
    """The unit-square corner (0,1) — the image's top-left, row 0 of the
    raster — must map to the *minimum* device y, confirming no double
    y-flip. A missing or doubled flip would put it at max device y."""
    doc, rdr = _renderer_with_canvas(100, 100)
    try:
        rdr._gs.ctm = (40.0, 0.0, 0.0, 40.0, 10.0, 10.0)
        ctm = rdr._full_ctm()
        top_left = rdr._apply((0.0, 1.0), ctm)  # image row 0
        bottom_left = rdr._apply((0.0, 0.0), ctm)  # image last row
        # Device y grows downward; the image top row must have the smaller
        # device y so the raster is pasted upright (row 0 at screen top).
        assert top_left[1] < bottom_left[1]
        # Specifically: user y=50 (10+40) -> device y=50; user y=10 -> 90.
        assert round(top_left[1]) == 50
        assert round(bottom_left[1]) == 90
    finally:
        doc.close()


@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0, 0.5])
def test_dpi_scale_multiplies_image_box(scale) -> None:
    """A non-identity device scale (dpi) multiplies the device bbox
    extent. A 40x40 image at (10,10) scales to 40*scale device px wide."""
    page_h_px = int(100 * scale)
    doc, rdr = _renderer_with_canvas(page_h_px, page_h_px, scale=scale)
    try:
        rdr._gs.ctm = (40.0, 0.0, 0.0, 40.0, 10.0, 10.0)
        bx0, by0, bx1, by1 = _unit_square_bbox(rdr)
        assert (bx1 - bx0) == round(40.0 * scale)
        assert (by1 - by0) == round(40.0 * scale)
        assert bx0 == round(10.0 * scale)
    finally:
        doc.close()


@pytest.mark.parametrize("deg", [30.0, 45.0, 90.0, 135.0, 180.0])
def test_rotated_ctm_bbox_is_rotated_extent(deg) -> None:
    """A rotated CTM rotates the unit square; the axis-aligned device bbox
    grows to the rotated extent. For a square image the rotated bbox side
    is w*(|cos|+|sin|). Confirms the CTM rotation is actually applied to
    every corner (not dropped)."""
    doc, rdr = _renderer_with_canvas(200, 200)
    try:
        rad = math.radians(deg)
        cos_r, sin_r = math.cos(rad), math.sin(rad)
        w = 40.0
        # cm = scale(w) * rotate(deg) * translate(80,80)
        scale_m = (w, 0.0, 0.0, w, 0.0, 0.0)
        rot_m = (cos_r, sin_r, -sin_r, cos_r, 0.0, 0.0)
        trans_m = (1.0, 0.0, 0.0, 1.0, 80.0, 80.0)
        rdr._gs.ctm = _matmul(_matmul(scale_m, rot_m), trans_m)
        bx0, by0, bx1, by1 = _unit_square_bbox(rdr)
        expected_side = w * (abs(cos_r) + abs(sin_r))
        assert abs((bx1 - bx0) - expected_side) <= 2
        assert abs((by1 - by0) - expected_side) <= 2
    finally:
        doc.close()


# ====================================================== _paste_image blit


@pytest.mark.parametrize(
    ("w", "h", "x", "y"),
    [
        (40.0, 40.0, 10.0, 10.0),
        (60.0, 30.0, 20.0, 5.0),
        (100.0, 100.0, 0.0, 0.0),
    ],
    ids=["square", "wide", "fullpage"],
)
def test_paste_image_blits_at_yflipped_origin(w, h, x, y) -> None:
    """``_paste_image`` blits the resized raster at the y-flipped bbox
    origin (min device x, min device y). The pasted image's size equals
    the device bbox extent."""
    page_h = 100
    doc, rdr = _renderer_with_canvas(page_h, page_h)
    rec = _BlitRecorder()
    rec.install(rdr)
    try:
        rdr._gs.ctm = (w, 0.0, 0.0, h, x, y)
        src = Image.new("RGB", (8, 8), (10, 20, 30))
        rdr._paste_image(src, interpolate=False)
        assert rec.calls, "no blit recorded"
        call = rec.calls[-1]
        box = call["box"]
        assert box == (round(x), round(page_h - (y + h)))
        # Pasted image resized to the device bbox extents.
        assert call["image"].size == (round(w), round(h))
    finally:
        doc.close()


def test_paste_image_does_not_double_flip_raster() -> None:
    """The source raster is pasted as-is (decoders already produce row-0-
    at-top). A regression that re-applied FLIP_TOP_BOTTOM would mirror the
    pasted image vertically. We assert the top row of the pasted raster
    still equals the source's top row."""
    doc, rdr = _renderer_with_canvas(100, 100)
    rec = _BlitRecorder()
    rec.install(rdr)
    try:
        rdr._gs.ctm = (40.0, 0.0, 0.0, 40.0, 10.0, 10.0)
        # A 1-px-tall coloured top row, black elsewhere.
        src = Image.new("RGB", (4, 4), (0, 0, 0))
        for px in range(4):
            src.putpixel((px, 0), (255, 0, 0))
        rdr._paste_image(src, interpolate=False)
        pasted = rec.calls[-1]["image"]
        # NEAREST resize to 40x40 keeps the top stripe at the top rows.
        assert pasted.getpixel((20, 0)) == (255, 0, 0)
        assert pasted.getpixel((20, 39)) == (0, 0, 0)
    finally:
        doc.close()


@pytest.mark.parametrize(
    ("interpolate", "expected"),
    [(True, Image.Resampling.BICUBIC), (False, Image.Resampling.NEAREST)],
)
def test_paste_image_interpolate_selects_resample(
    interpolate, expected, monkeypatch
) -> None:
    """``interpolate`` picks the resampling filter: True -> BICUBIC
    (PDFBox VALUE_INTERPOLATION_BICUBIC), False -> NEAREST."""
    doc, rdr = _renderer_with_canvas(100, 100)
    rec = _BlitRecorder()
    rec.install(rdr)
    captured = {}
    orig_resize = Image.Image.resize

    def spy_resize(self, size, resample=None, *a, **k):  # noqa: ANN001
        captured["resample"] = resample
        return orig_resize(self, size, resample, *a, **k)

    monkeypatch.setattr(Image.Image, "resize", spy_resize)
    try:
        rdr._gs.ctm = (40.0, 0.0, 0.0, 40.0, 10.0, 10.0)
        src = Image.new("RGB", (4, 4), (1, 2, 3))
        rdr._paste_image(src, interpolate=interpolate)
        assert captured["resample"] == expected
    finally:
        doc.close()


# ====================================================== stencil paint


def _make_stencil(width, height, sample_bytes, decode=None):
    stream = COSStream()
    stream.set_raw_data(sample_bytes)
    image = PDImageXObject(stream)
    image.set_width(width)
    image.set_height(height)
    image.set_bits_per_component(1)
    image.set_stencil(True)
    if decode is not None:
        arr = COSArray()
        for v in decode:
            arr.add(COSFloat(float(v)))
        image.get_cos_object().set_item(COSName.get_pdf_name("Decode"), arr)
    return image


def _stencil_capture(fill_rgb, sample_bytes, decode=None, width=4, height=4):
    """Run ``_paint_stencil_mask`` with the blit mocked and return the
    RGBA matte handed to ``_paste_image``."""
    doc, rdr = _renderer_with_canvas(60, 60)
    captured = {}
    orig = rdr._paste_image

    def spy(pil_image, interpolate=True):  # noqa: ANN001
        captured["rgba"] = pil_image.copy()
        captured["interpolate"] = interpolate

    rdr._paste_image = spy  # type: ignore[method-assign]
    try:
        rdr._gs.fill_rgb = fill_rgb
        rdr._gs.ctm = (40.0, 0.0, 0.0, 40.0, 10.0, 10.0)
        image = _make_stencil(width, height, sample_bytes, decode)
        rdr._paint_stencil_mask(image)
        return captured
    finally:
        del orig
        doc.close()


def test_stencil_uses_fill_color_not_image_samples() -> None:
    """Every opaque pixel of the stencil matte carries the *non-stroking*
    fill RGB — the image samples only select the alpha, never the colour
    (upstream feeds isStencil() into a coloured-mask paint)."""
    fill = (12, 200, 64)
    # Row 0 opaque (0x00 bits), rows 1-3 transparent (0xF0).
    cap = _stencil_capture(fill, bytes([0x00, 0xF0, 0xF0, 0xF0]))
    rgba = cap["rgba"]
    assert rgba.mode == "RGBA"
    # Opaque pixel (row 0) must be the fill colour, full alpha.
    assert rgba.getpixel((0, 0)) == (12, 200, 64, 255)
    # Transparent pixel (row 1) keeps the fill RGB but alpha 0.
    assert rgba.getpixel((0, 1)) == (12, 200, 64, 0)


@pytest.mark.parametrize("fill", [(255, 0, 0), (0, 0, 0), (128, 128, 255)])
def test_stencil_tints_with_active_fill_color(fill) -> None:
    cap = _stencil_capture(fill, bytes([0x00, 0xF0, 0xF0, 0xF0]))
    rgba = cap["rgba"]
    r, g, b, a = rgba.getpixel((0, 0))
    assert (r, g, b) == fill
    assert a == 255


def test_stencil_default_decode_sample0_is_opaque() -> None:
    """Default ``/Decode [0 1]``: sample 0 paints (alpha 255), sample 1 is
    transparent (alpha 0)."""
    # All-opaque top row (0x00), all-transparent bottom rows (0xF0).
    cap = _stencil_capture((255, 0, 0), bytes([0x00, 0xF0, 0xF0, 0xF0]))
    rgba = cap["rgba"]
    assert rgba.getpixel((0, 0))[3] == 255  # sample 0 -> opaque
    assert rgba.getpixel((0, 1))[3] == 0    # sample 1 -> transparent


def test_stencil_decode_1_0_inverts_polarity() -> None:
    """``/Decode [1 0]`` swaps the sense: sample 1 paints, sample 0 is
    transparent — the exact inverse of the default."""
    cap = _stencil_capture(
        (255, 0, 0), bytes([0x00, 0xF0, 0xF0, 0xF0]), decode=[1, 0]
    )
    rgba = cap["rgba"]
    # Now sample 0 (row 0) is transparent, sample 1 (rows 1-3) is opaque.
    assert rgba.getpixel((0, 0))[3] == 0
    assert rgba.getpixel((0, 1))[3] == 255


@pytest.mark.parametrize(
    ("decode", "row0_alpha", "row1_alpha"),
    [
        (None, 255, 0),
        ([0, 1], 255, 0),
        ([1, 0], 0, 255),
    ],
    ids=["default", "explicit_0_1", "inverted_1_0"],
)
def test_stencil_decode_matrix(decode, row0_alpha, row1_alpha) -> None:
    cap = _stencil_capture(
        (10, 20, 30), bytes([0x00, 0xF0, 0xF0, 0xF0]), decode=decode
    )
    rgba = cap["rgba"]
    assert rgba.getpixel((0, 0))[3] == row0_alpha
    assert rgba.getpixel((0, 1))[3] == row1_alpha


@pytest.mark.parametrize("interpolate_flag", [True, False])
def test_stencil_threads_interpolate_flag(interpolate_flag) -> None:
    """The stencil paint reads the image's ``/Interpolate`` and threads it
    into ``_paste_image`` so a 1-bit matte isn't bicubic-blurred unless the
    flag asks for it."""
    doc, rdr = _renderer_with_canvas(60, 60)
    captured = {}

    def spy(pil_image, interpolate=True):  # noqa: ANN001
        captured["interpolate"] = interpolate

    rdr._paste_image = spy  # type: ignore[method-assign]
    try:
        rdr._gs.fill_rgb = (0, 0, 0)
        rdr._gs.ctm = (40.0, 0.0, 0.0, 40.0, 10.0, 10.0)
        image = _make_stencil(4, 4, bytes([0x00, 0xF0, 0xF0, 0xF0]))
        image.set_interpolate(interpolate_flag)
        rdr._paint_stencil_mask(image)
        assert captured["interpolate"] is interpolate_flag
    finally:
        doc.close()


def test_stencil_reports_1bpc_even_with_bpc_set() -> None:
    """A stencil always reports 1 bpc (upstream ``getBitsPerComponent``
    short-circuits via ``isStencil()``), so the renderer's bpc guard never
    rejects a real stencil — confirm it still paints when /BPC is set to 8.
    """
    doc, rdr = _renderer_with_canvas(60, 60)
    called = {"n": 0}

    def spy(pil_image, interpolate=True):  # noqa: ANN001
        called["n"] += 1

    rdr._paste_image = spy  # type: ignore[method-assign]
    try:
        rdr._gs.fill_rgb = (0, 0, 0)
        rdr._gs.ctm = (40.0, 0.0, 0.0, 40.0, 10.0, 10.0)
        image = _make_stencil(4, 4, bytes([0x00, 0xF0, 0xF0, 0xF0]))
        image.set_bits_per_component(8)
        assert image.get_bits_per_component() == 1
        rdr._paint_stencil_mask(image)
        assert called["n"] == 1
    finally:
        doc.close()


def test_stencil_zero_size_is_noop() -> None:
    doc, rdr = _renderer_with_canvas(60, 60)
    called = {"n": 0}

    def spy(pil_image, interpolate=True):  # noqa: ANN001
        called["n"] += 1

    rdr._paste_image = spy  # type: ignore[method-assign]
    try:
        rdr._gs.fill_rgb = (0, 0, 0)
        image = _make_stencil(0, 4, b"")
        rdr._paint_stencil_mask(image)
        assert called["n"] == 0
    finally:
        doc.close()


# ====================================================== end-to-end placement


def _render_stencil_page(content_bytes, stencil_bytes, decode=None, page=60.0):
    doc, pg = _make_doc(page, page)
    image = _make_stencil(4, 4, stencil_bytes, decode)
    contents = COSStream()
    contents.set_raw_data(content_bytes)
    pg.get_cos_object().set_item(COSName.CONTENTS, contents)
    res = PDResources()
    pg.set_resources(res)
    res.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Im0"),
        image.get_cos_object(),
    )
    img = PDFRenderer(doc).render_image(0)
    doc.close()
    return img


def _is_close(actual, expected, tol=60):
    return all(abs(a - e) <= tol for a, e in zip(actual[:3], expected, strict=False))


def test_end_to_end_stencil_paints_fill_color_in_box() -> None:
    """A red-fill stencil placed by ``40 0 0 40 10 10 cm`` paints red
    pixels inside the device box and leaves the rest white."""
    img = _render_stencil_page(
        b"1 0 0 rg\nq\n40 0 0 40 10 10 cm\n/Im0 Do\nQ\n",
        # all rows opaque so the whole box paints red
        bytes([0x00, 0x00, 0x00, 0x00]),
    )
    # Center of box (device ~ (30, 30)) should be red.
    assert _is_close(img.getpixel((30, 30)), (255, 0, 0))
    # A corner outside the box stays white.
    assert _is_close(img.getpixel((2, 2)), (255, 255, 255))


def test_end_to_end_stencil_box_position_matches_cm() -> None:
    """The painted box's left edge lines up with the ``cm`` x-translate;
    pixels left of x=10 stay white."""
    img = _render_stencil_page(
        b"0 0 1 rg\nq\n40 0 0 40 10 10 cm\n/Im0 Do\nQ\n",
        bytes([0x00, 0x00, 0x00, 0x00]),
    )
    # Just left of the box (x<10) is background.
    assert _is_close(img.getpixel((4, 30)), (255, 255, 255))
    # Inside the box is blue.
    assert _is_close(img.getpixel((30, 30)), (0, 0, 255))


def test_end_to_end_stencil_decode_inversion_flips_paint() -> None:
    """With an all-zero-sample stencil, default decode paints everywhere
    inside the box; ``/Decode [1 0]`` makes the same samples transparent so
    the box stays background."""
    painted = _render_stencil_page(
        b"1 0 0 rg\nq\n40 0 0 40 10 10 cm\n/Im0 Do\nQ\n",
        bytes([0x00, 0x00, 0x00, 0x00]),
        decode=None,
    )
    inverted = _render_stencil_page(
        b"1 0 0 rg\nq\n40 0 0 40 10 10 cm\n/Im0 Do\nQ\n",
        bytes([0x00, 0x00, 0x00, 0x00]),
        decode=[1, 0],
    )
    assert _is_close(painted.getpixel((30, 30)), (255, 0, 0))
    # Inverted: same samples now transparent -> background white.
    assert _is_close(inverted.getpixel((30, 30)), (255, 255, 255))
