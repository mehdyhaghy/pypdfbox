"""Wave 1589 — PDFRenderer page-setup parity fuzz.

Hammers the deterministic page-setup arithmetic behind
``PDFRenderer.renderImageWithDPI`` and the device-CTM construction in
``_render_page_into``, mirroring Apache PDFBox 3.0.7's
``PDFRenderer.renderImage`` transform setup:

* output bitmap size = ``floor(cropbox_dim * (dpi / 72f))`` computed in
  single precision (Java ``float``), with the ``/Rotate`` 90/270 swap of
  width and height,
* the device CTM that flips the y-axis (PDF origin bottom-left -> image
  top-left), translates by the crop-box lower-left, and folds in the
  clockwise page rotation,
* the DPI -> scale relation (``scale == dpi / 72``),
* ``/Rotate`` normalisation (mod 360, snap to {0,90,180,270}),
* a non-zero-origin crop box and a crop box smaller than the media box.

The size/transform computation is exercised directly (no full
rasterisation needed): the renderer reproduces the same float32 floor and
the same ``_matmul(_matmul(translate, rotate), flip)`` device CTM that
upstream builds, so we pin those rather than per-pixel output.

Ported parity reference: ``oracle/probes/PageRotateRenderProbe.java`` and
``oracle/probes/RenderDpiProbe.java`` (PDFBox 3.0.7
``PDFRenderer.renderImageWithDPI``).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import (
    _IDENTITY,
    _matmul,
    _normalise_rotation,
    _page_rotation_matrix,
)


# ---------------------------------------------------------------------
# helpers mirroring the production size + device-CTM arithmetic.
# ---------------------------------------------------------------------
def _apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _expected_size(width_pt, height_pt, dpi, rotation):
    """Upstream ``PDFRenderer.renderImage`` raster size: ``pts * (dpi/72f)``
    floored in single precision, with the 90/270 width/height swap."""
    scale_f32 = np.float32(float(dpi)) / np.float32(72.0)
    w_f32 = np.float32(width_pt)
    h_f32 = np.float32(height_pt)
    if rotation in (90, 270):
        return (
            max(1, int(h_f32 * scale_f32)),
            max(1, int(w_f32 * scale_f32)),
        )
    return (
        max(1, int(w_f32 * scale_f32)),
        max(1, int(h_f32 * scale_f32)),
    )


def _device_ctm(rotation, mb_x, mb_y, width_pt, height_pt, scale, height_px):
    """Reproduce ``_render_page_into``'s device CTM exactly."""
    rotate_into_box = _page_rotation_matrix(rotation, width_pt, height_pt)
    translate_origin = (1.0, 0.0, 0.0, 1.0, -mb_x, -mb_y)
    flip_scale = (scale, 0.0, 0.0, -scale, 0.0, float(height_px))
    return _matmul(_matmul(translate_origin, rotate_into_box), flip_scale)


@pytest.fixture
def make_renderer():
    """Build a single-page renderer, closing every document at teardown so
    the suite stays free of ``COSDocument was not closed`` warnings."""
    docs = []

    def _build(media, crop=None, rotation=0):
        doc = PDDocument()
        docs.append(doc)
        page = PDPage(media)
        if crop is not None:
            page.set_crop_box(crop)
        if rotation:
            page.set_rotation(rotation)
        doc.add_page(page)
        return PDFRenderer(doc), page

    yield _build
    for doc in docs:
        doc.close()


# ---------------------------------------------------------------------
# 1. bitmap size == floor(cropbox * scale), float32, with rotate swap.
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    ("w_pt", "h_pt"),
    [
        (612.0, 792.0),  # US Letter
        (595.276, 841.89),  # A4 (float32-boundary widths)
        (200.0, 300.0),  # the rotate probe's asymmetric box
        (100.0, 100.0),  # square
        (1.0, 1.0),  # tiny -> clamped to 1px
        (841.92, 1190.55),  # A3-ish
    ],
)
@pytest.mark.parametrize("dpi", [72.0, 96.0, 150.0, 300.0, 36.0])
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_render_image_size_matches_float32_floor(make_renderer, w_pt, h_pt, dpi, rotation):
    renderer, _page = make_renderer(
        PDRectangle(0.0, 0.0, w_pt, h_pt), rotation=rotation
    )
    img = renderer.render_image_with_dpi(0, dpi=dpi)
    # The renderer narrows the rect coords to float32 on construction, so
    # read the box back to mirror exactly what the renderer floored.
    box = renderer.get_document().get_page(0).get_crop_box()
    expected = _expected_size(
        box.get_width(), box.get_height(), dpi, rotation
    )
    assert img.size == expected


# ---------------------------------------------------------------------
# 2. rotation swaps the rendered width and height for 90 / 270 only.
# ---------------------------------------------------------------------
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_rotation_swaps_dimensions_for_quarter_turns(make_renderer, rotation):
    renderer, _page = make_renderer(
        PDRectangle(0.0, 0.0, 200.0, 300.0), rotation=rotation
    )
    img = renderer.render_image_with_dpi(0, dpi=72.0)
    if rotation in (90, 270):
        assert img.size == (300, 200)
    else:
        assert img.size == (200, 300)


# ---------------------------------------------------------------------
# 3. DPI -> scale: render_image(scale) == render_image_with_dpi(72*scale).
# ---------------------------------------------------------------------
@pytest.mark.parametrize("scale", [0.5, 1.0, 1.5, 2.0, 4.0])
def test_scale_equals_dpi_over_72(make_renderer, scale):
    renderer, _page = make_renderer(PDRectangle(0.0, 0.0, 200.0, 300.0))
    by_scale = renderer.render_image(0, scale=scale)
    by_dpi = renderer.render_image_with_dpi(0, dpi=72.0 * scale)
    assert by_scale.size == by_dpi.size


# ---------------------------------------------------------------------
# 4. /Rotate normalisation (mod 360, snap to canonical set).
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "norm"),
    [
        (0, 0),
        (90, 90),
        (180, 180),
        (270, 270),
        (360, 0),
        (450, 90),
        (-90, 270),
        (720, 0),
        (-360, 0),
        (45, 0),  # non-multiple -> falls back to 0
        (135, 0),
        (None, 0),
    ],
)
def test_rotation_normalisation(raw, norm):
    assert _normalise_rotation(raw) == norm


# ---------------------------------------------------------------------
# 5. device CTM flips Y: PDF lower-left maps to image bottom row, the
#    upper-left maps to image top.
# ---------------------------------------------------------------------
def test_device_ctm_flips_y_axis_zero_rotation():
    w_pt, h_pt, scale = 200.0, 300.0, 1.0
    h_px = int(h_pt * scale)
    m = _device_ctm(0, 0.0, 0.0, w_pt, h_pt, scale, h_px)
    # Lower-left (0,0) in PDF -> image bottom-left (x=0, y=height).
    assert _apply(m, 0.0, 0.0) == pytest.approx((0.0, float(h_px)))
    # Upper-left (0, h) in PDF -> image top-left (x=0, y=0).
    assert _apply(m, 0.0, h_pt) == pytest.approx((0.0, 0.0))
    # Upper-right (w, h) -> image top-right.
    assert _apply(m, w_pt, h_pt) == pytest.approx(
        (w_pt * scale, 0.0)
    )


# ---------------------------------------------------------------------
# 6. non-zero-origin crop box translates the content by the lower-left.
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    ("mb_x", "mb_y"),
    [(50.0, 100.0), (10.0, 0.0), (0.0, 25.0), (33.0, 77.0)],
)
def test_crop_lower_left_translation(mb_x, mb_y):
    w_pt, h_pt, scale = 200.0, 300.0, 1.0
    h_px = int(h_pt * scale)
    m = _device_ctm(0, mb_x, mb_y, w_pt, h_pt, scale, h_px)
    # The crop's own lower-left maps to image pixel (0, height) regardless
    # of where it sits in media space — the translate cancels the origin.
    assert _apply(m, mb_x, mb_y) == pytest.approx((0.0, float(h_px)))
    # The crop's upper-right maps to (w*scale, 0).
    assert _apply(m, mb_x + w_pt, mb_y + h_pt) == pytest.approx(
        (w_pt * scale, 0.0)
    )


# ---------------------------------------------------------------------
# 7. rotation composed with the Y-flip keeps every crop corner inside the
#    (possibly swapped) bitmap bounds, for a non-zero-origin crop.
# ---------------------------------------------------------------------
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("scale", [1.0, 2.0])
def test_rotation_keeps_corners_in_bounds(rotation, scale):
    mb_x, mb_y, w_pt, h_pt = 40.0, 60.0, 200.0, 300.0
    if rotation in (90, 270):
        w_px, h_px = int(h_pt * scale), int(w_pt * scale)
    else:
        w_px, h_px = int(w_pt * scale), int(h_pt * scale)
    m = _device_ctm(rotation, mb_x, mb_y, w_pt, h_pt, scale, h_px)
    corners = [
        (mb_x, mb_y),
        (mb_x + w_pt, mb_y),
        (mb_x, mb_y + h_pt),
        (mb_x + w_pt, mb_y + h_pt),
    ]
    xs, ys = [], []
    for cx, cy in corners:
        px, py = _apply(m, cx, cy)
        xs.append(px)
        ys.append(py)
        assert -1e-6 <= px <= w_px + 1e-6
        assert -1e-6 <= py <= h_px + 1e-6
    # The mapped corners span the full bitmap (axis-aligned in every case).
    assert min(xs) == pytest.approx(0.0)
    assert max(xs) == pytest.approx(float(w_px))
    assert min(ys) == pytest.approx(0.0)
    assert max(ys) == pytest.approx(float(h_px))


# ---------------------------------------------------------------------
# 8. clockwise direction: /Rotate 90 sends the page's left edge to the
#    image top edge (clockwise viewing rotation, PDF 32000-1 §7.7.3.3).
# ---------------------------------------------------------------------
def test_rotate_90_is_clockwise():
    w_pt, h_pt, scale = 200.0, 300.0, 1.0
    # 90/270 swap: image is (h, w).
    w_px, h_px = int(h_pt * scale), int(w_pt * scale)
    m = _device_ctm(90, 0.0, 0.0, w_pt, h_pt, scale, h_px)
    # Page bottom-left (0,0) under a clockwise quarter turn lands at the
    # image top-left.
    assert _apply(m, 0.0, 0.0) == pytest.approx((0.0, 0.0))
    # Page bottom-right (w, 0) -> image bottom-left.
    assert _apply(m, w_pt, 0.0) == pytest.approx((0.0, float(h_px)))
    # Page top-left (0, h) -> image top-right.
    assert _apply(m, 0.0, h_pt) == pytest.approx((float(w_px), 0.0))


def test_rotate_270_is_counter_to_90():
    w_pt, h_pt, scale = 200.0, 300.0, 1.0
    w_px, h_px = int(h_pt * scale), int(w_pt * scale)
    m = _device_ctm(270, 0.0, 0.0, w_pt, h_pt, scale, h_px)
    # 270 = clockwise three-quarter turn: page bottom-left -> image
    # bottom-right (the opposite diagonal from /Rotate 90).
    assert _apply(m, 0.0, 0.0) == pytest.approx(
        (float(w_px), float(h_px))
    )
    assert _apply(m, w_pt, 0.0) == pytest.approx((float(w_px), 0.0))


# ---------------------------------------------------------------------
# 9. crop box smaller than the media box drives the raster, not media.
# ---------------------------------------------------------------------
def test_crop_smaller_than_media_drives_raster(make_renderer):
    media = PDRectangle(0.0, 0.0, 600.0, 800.0)
    crop = PDRectangle(100.0, 150.0, 400.0, 500.0)  # 300 x 350 window
    renderer, page = make_renderer(media, crop=crop)
    box = page.get_crop_box()
    assert (box.get_width(), box.get_height()) == pytest.approx(
        (300.0, 350.0)
    )
    img = renderer.render_image_with_dpi(0, dpi=72.0)
    # Sized from the crop window (300 x 350), not the 600 x 800 media.
    assert img.size == _expected_size(
        box.get_width(), box.get_height(), 72.0, 0
    )
    assert img.size != (600, 800)


def test_oversized_crop_clipped_to_media(make_renderer):
    media = PDRectangle(0.0, 0.0, 300.0, 400.0)
    crop = PDRectangle(-50.0, -50.0, 500.0, 600.0)  # overflows media
    renderer, page = make_renderer(media, crop=crop)
    box = page.get_crop_box()
    # Upstream clipToMediaBox clamps the crop to the media bounds.
    assert box.get_lower_left_x() >= -1e-6
    assert box.get_lower_left_y() >= -1e-6
    assert box.get_upper_right_x() <= 300.0 + 1e-6
    assert box.get_upper_right_y() <= 400.0 + 1e-6
    img = renderer.render_image_with_dpi(0, dpi=72.0)
    assert img.size == _expected_size(
        box.get_width(), box.get_height(), 72.0, 0
    )


# ---------------------------------------------------------------------
# 10. rotation matrix algebra: 90 and 270 are mutual inverses; 180 is its
#     own inverse; identity for 0.
# ---------------------------------------------------------------------
def test_rotation_matrix_inverse_relations():
    w, h = 200.0, 300.0
    assert _page_rotation_matrix(0, w, h) == _IDENTITY
    # 90 then 270 (in the swapped frame) should round-trip a point.
    m90 = _page_rotation_matrix(90, w, h)
    # After 90 the extents are (h, w); the inverse turn operates on those.
    m270_back = _page_rotation_matrix(270, h, w)
    for x, y in ((0.0, 0.0), (w, 0.0), (0.0, h), (w, h)):
        ix, iy = _apply(m90, x, y)
        rx, ry = _apply(m270_back, ix, iy)
        assert (rx, ry) == pytest.approx((x, y))


def test_rotation_180_is_own_inverse():
    w, h = 200.0, 300.0
    m = _page_rotation_matrix(180, w, h)
    for x, y in ((0.0, 0.0), (w, 0.0), (0.0, h), (w, h)):
        ix, iy = _apply(m, x, y)
        rx, ry = _apply(m, ix, iy)
        assert (rx, ry) == pytest.approx((x, y))


# ---------------------------------------------------------------------
# 11. tiny crop boxes clamp to a 1px floor instead of 0.
# ---------------------------------------------------------------------
@pytest.mark.parametrize("dim", [0.5, 0.1, 0.01])
def test_subpixel_crop_clamps_to_one_pixel(make_renderer, dim):
    renderer, _page = make_renderer(PDRectangle(0.0, 0.0, dim, dim))
    img = renderer.render_image_with_dpi(0, dpi=72.0)
    assert img.size == (1, 1)


# ---------------------------------------------------------------------
# 12. float32 floor boundary: A4 width at 150 DPI floors low (the
#     single-precision boundary the production code documents).
# ---------------------------------------------------------------------
def test_float32_floor_boundary_a4_at_150dpi(make_renderer):
    # 595.276 pt at 150 DPI: double = 1240.16, float32 path floors the
    # same here, but the canonical boundary is the height 841.89 at 150.
    renderer, _page = make_renderer(PDRectangle(0.0, 0.0, 595.276, 841.89))
    img = renderer.render_image_with_dpi(0, dpi=150.0)
    box = renderer.get_document().get_page(0).get_crop_box()
    scale_f32 = np.float32(150.0) / np.float32(72.0)
    exp_w = max(1, int(np.float32(box.get_width()) * scale_f32))
    exp_h = max(1, int(np.float32(box.get_height()) * scale_f32))
    assert img.size == (exp_w, exp_h)
    # Sanity: matches the documented single-precision floor, not a naive
    # double-precision product rounded up.
    assert img.size[1] == int(math.floor(float(np.float32(box.get_height()) * scale_f32)))
