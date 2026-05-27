"""Wave 1373 audit closures — rendering parity.

Two regressions documented in CHANGES.md were closed in wave 1373:

1. **Tiling pattern step > cell stretched the cell to fill the step.**
   Spec-correct behaviour (PDF 32000-1 §8.7.3.3): when ``/XStep`` or
   ``/YStep`` exceeds the cell's ``/BBox`` dimension, the cell paints
   only the ``/BBox`` sub-region of each lattice tile and the surrounding
   gap stays transparent (the page background shows through).

2. **Even-odd fill flattened Beziers and XOR-merged polygon masks**,
   which produced a binary mask without sub-pixel anti-aliasing on the
   outer edge. The mask builder now rasterises the path through
   ``skia.Path`` with ``PathFillType.kEvenOdd`` so edge pixels carry
   sub-pixel AA values.

Tests use structural assertions (background visible in gap pixels, AA
edge alpha values, mask centroid containment) rather than pixel-exact
comparison so the suite stays stable across skia / Pillow versions and
platforms.
"""
from __future__ import annotations

from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.pattern import PDTilingPattern
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import _GState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(width: float, height: float) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _build_tiling_pattern(
    *,
    cell_bytes: bytes,
    bbox: PDRectangle,
    x_step: float,
    y_step: float,
) -> PDTilingPattern:
    pat = PDTilingPattern()
    pat.set_paint_type(PDTilingPattern.PAINT_TYPE_COLORED)
    pat.set_tiling_type(PDTilingPattern.TILING_TYPE_CONSTANT_SPACING)
    pat.set_b_box(bbox)
    pat.set_x_step(x_step)
    pat.set_y_step(y_step)
    pat.get_cos_object().set_raw_data(cell_bytes)
    return pat


def _render_pattern_page(
    pat: PDTilingPattern,
    *,
    page_size: float,
    fill_rect: tuple[float, float, float, float],
) -> Image.Image:
    doc, page = _make_doc(page_size, page_size)
    try:
        resources = PDResources()
        page.set_resources(resources)
        resources.put(
            COSName.get_pdf_name("Pattern"),
            COSName.get_pdf_name("P0"),
            pat.get_cos_object(),
        )
        x, y, w, h = fill_rect
        contents = COSStream()
        contents.set_raw_data(
            b"/Pattern cs\n/P0 scn\n"
            + f"{x} {y} {w} {h} re\n".encode("ascii")
            + b"f\n"
        )
        page.get_cos_object().set_item(COSName.CONTENTS, contents)
        return PDFRenderer(doc).render_image(0)
    finally:
        doc.close()


def _is_white(pixel: tuple[int, int, int], tol: int = 4) -> bool:
    return all(abs(c - 255) <= tol for c in pixel[:3])


# ---------------------------------------------------------------------------
# 1. Tiling pattern step > cell — gap is transparent (shows page background).
# ---------------------------------------------------------------------------


def test_tiling_pattern_step_greater_than_cell_leaves_gap_pixels_unchanged() -> None:
    """``/XStep`` and ``/YStep`` of 20 with a 5x5 ``/BBox`` cell — each
    20x20 tile paints the cell at the lattice origin and the remaining
    15-pixel wide gap on the right + bottom stays transparent so the
    page background (white) shows through.
    """
    pat = _build_tiling_pattern(
        cell_bytes=b"1 0 0 rg\n0 0 5 5 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 5.0, 5.0),
        x_step=20.0,
        y_step=20.0,
    )
    img = _render_pattern_page(pat, page_size=80.0, fill_rect=(0.0, 0.0, 80.0, 80.0))

    # Sample a pixel that's clearly in the (XStep - BBox) gap region
    # between two adjacent cell tiles. With cells at lattice (0,0) and
    # (20,0), pixel (10, 10) is in the gap and should stay white. Note
    # the y-axis is flipped, so PIL y=10 corresponds to PDF y=70 — that
    # pixel is still in the gap of the (0, 60) tile.
    gap_pixel = img.getpixel((10, 10))
    assert _is_white(gap_pixel), f"gap should be background, got {gap_pixel}"

    # Sample a pixel that falls inside one of the cell paints. The /BBox cell
    # is painted at the *lower-left* of each lattice cell (PDF 32000-1
    # §8.7.3.3, wave 1443 bottom-alignment fix), and the device y-axis is
    # flipped, so the 5x5 red square of the lattice-origin cell (PDF y in
    # [0, 5]) lands at the bottom of the image — PIL rows ~[75, 80]. Pixel
    # (2, 77) is inside that cell.
    cell_pixel = img.getpixel((2, 77))
    assert cell_pixel[0] >= 200 and cell_pixel[1] <= 60 and cell_pixel[2] <= 60, (
        f"expected red cell pixel, got {cell_pixel}"
    )


def test_tiling_pattern_step_greater_than_cell_gap_count_significant() -> None:
    """When the step is 4x the cell on each axis, the gap region covers
    roughly 15/16 of the fill area. Count gap (white) pixels and verify
    they outnumber painted cell pixels by a wide margin — a structural
    check that the gap genuinely shows background instead of stretched
    cell colour."""
    pat = _build_tiling_pattern(
        cell_bytes=b"0 1 0 rg\n0 0 5 5 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 5.0, 5.0),
        x_step=20.0,
        y_step=20.0,
    )
    img = _render_pattern_page(pat, page_size=80.0, fill_rect=(0.0, 0.0, 80.0, 80.0))

    green_pixels = 0
    white_pixels = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            pixel = img.getpixel((x, y))
            if _is_white(pixel):
                white_pixels += 1
            elif pixel[1] >= 200 and pixel[0] <= 60 and pixel[2] <= 60:
                green_pixels += 1

    # Cell occupies 5x5 of every 20x20 lattice tile — 25 / 400 = 6.25%
    # of fill area. Background occupies the remaining 93.75%. Even
    # allowing for AA edge bleed, the gap (background) count must
    # dominate the cell count by at least 5x.
    assert white_pixels > 5 * green_pixels, (
        f"gap={white_pixels} should dominate cells={green_pixels}"
    )


def test_tiling_pattern_equal_step_and_cell_produces_continuous_coverage() -> None:
    """When ``/XStep == /BBox.width`` and ``/YStep == /BBox.height`` the
    cells tile seamlessly with no gap — the entire fill region picks
    up the cell colour."""
    pat = _build_tiling_pattern(
        cell_bytes=b"0 0 1 rg\n0 0 10 10 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 10.0, 10.0),
        x_step=10.0,
        y_step=10.0,
    )
    img = _render_pattern_page(pat, page_size=40.0, fill_rect=(0.0, 0.0, 40.0, 40.0))

    blue_pixels = 0
    white_pixels = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            pixel = img.getpixel((x, y))
            if _is_white(pixel):
                white_pixels += 1
            elif pixel[2] >= 200 and pixel[0] <= 60 and pixel[1] <= 60:
                blue_pixels += 1

    # Seamless tiling: blue should dominate. (Small AA tolerance lets
    # us not pin the exact ratio.)
    assert blue_pixels > 5 * white_pixels, (
        f"seamless tiling expected blue-dominated, got blue={blue_pixels}, "
        f"white={white_pixels}"
    )


# ---------------------------------------------------------------------------
# 2. Even-odd fill via skia — AA-correct mask on the outer edge.
# ---------------------------------------------------------------------------


def _prepared_renderer(size: tuple[int, int]) -> tuple[PDDocument, PDFRenderer]:
    doc, _page = _make_doc(float(size[0]), float(size[1]))
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", size, (255, 255, 255))
    renderer._draw = aggdraw.Draw(renderer._image)
    renderer._draw.setantialias(True)
    renderer._gs_stack = [_GState()]
    renderer._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    return doc, renderer


def test_even_odd_mask_outer_edge_has_anti_aliasing() -> None:
    """A diagonal-edged subpath produces a mask with AA values
    (strictly between 0 and 255) on the outer edge. With the legacy
    PIL XOR-of-polygons code this never happened — the mask was strictly
    binary. skia's ``PathFillType.kEvenOdd`` rasterisation preserves
    sub-pixel coverage.
    """
    doc, renderer = _prepared_renderer((16, 16))
    try:
        # Right-triangle whose hypotenuse runs from (2, 2) to (12, 12).
        # The hypotenuse passes through pixel centres at integer offsets,
        # so several edge pixels MUST have AA values if the mask is AA.
        renderer._subpaths = [
            [
                ("M", 2.0, 2.0),
                ("L", 12.0, 2.0),
                ("L", 12.0, 12.0),
                ("Z",),
            ],
        ]
        mask = renderer._build_path_mask(even_odd=True)
        assert mask is not None
        assert mask.mode == "L"

        # Count distinct pixel intensities. With the legacy XOR-of-
        # polygons code the set would be {0, 255}; with skia AA we
        # expect at least one intermediate value somewhere along the
        # hypotenuse.
        intensities = set(mask.tobytes())
        intermediates = [v for v in intensities if 0 < v < 255]
        assert intermediates, (
            f"expected AA edge pixels, got binary mask intensities={sorted(intensities)}"
        )

        # The triangle interior at pixel (10, 4) (well inside the upper-
        # right corner) must still be fully covered.
        assert mask.getpixel((10, 4)) >= 200
        # Outside the triangle, pixel (1, 14), stays at zero.
        assert mask.getpixel((1, 14)) == 0
    finally:
        doc.close()


def test_even_odd_mask_self_intersecting_path_cancels_hole_via_skia() -> None:
    """A self-intersecting figure-eight path produces an even-odd hole.
    Verify the hole is fully cancelled (mask value ~0 in the overlap
    region) with the new skia path while the outer regions stay solid.
    """
    doc, renderer = _prepared_renderer((20, 20))
    try:
        # Outer square (2..18) plus inner square (6..14) — even-odd cancels
        # the inner area so the result is an annulus.
        renderer._subpaths = [
            [
                ("M", 2.0, 2.0),
                ("L", 18.0, 2.0),
                ("L", 18.0, 18.0),
                ("L", 2.0, 18.0),
                ("Z",),
            ],
            [
                ("M", 6.0, 6.0),
                ("L", 14.0, 6.0),
                ("L", 14.0, 14.0),
                ("L", 6.0, 14.0),
                ("Z",),
            ],
        ]
        mask = renderer._build_path_mask(even_odd=True)
        assert mask is not None

        # Annulus body: pixel (3, 10) — outer-square interior, outside
        # the inner square → fully covered.
        assert mask.getpixel((3, 10)) >= 240
        # Hole interior: pixel (10, 10) — inside both squares → cancels.
        assert mask.getpixel((10, 10)) <= 8
        # Outside both: pixel (1, 1) → zero.
        assert mask.getpixel((1, 1)) == 0
    finally:
        doc.close()


def test_non_zero_mask_outer_edge_also_anti_aliased() -> None:
    """Non-zero fill rule also routes through skia so its outer edge
    carries AA — verifies the wave 1373 refactor didn't regress
    non-zero fills."""
    doc, renderer = _prepared_renderer((16, 16))
    try:
        renderer._subpaths = [
            [
                ("M", 2.0, 2.0),
                ("L", 12.0, 2.0),
                ("L", 12.0, 12.0),
                ("Z",),
            ],
        ]
        mask = renderer._build_path_mask(even_odd=False)
        assert mask is not None
        intensities = set(mask.tobytes())
        intermediates = [v for v in intensities if 0 < v < 255]
        assert intermediates, (
            f"non-zero mask should also be AA, got intensities="
            f"{sorted(intensities)}"
        )
    finally:
        doc.close()


def test_even_odd_clip_mask_keeps_anti_aliased_silhouette() -> None:
    """``W*`` clip path also goes through the skia builder — its clip
    mask carries AA on the outer edge instead of the legacy binary
    silhouette."""
    doc, renderer = _prepared_renderer((20, 20))
    try:
        renderer._subpaths = [
            [
                ("M", 2.0, 2.0),
                ("L", 17.0, 2.0),
                ("L", 17.0, 17.0),
                ("Z",),
            ],
        ]
        renderer._pending_clip = "W*"
        renderer._apply_pending_clip(default_even_odd=True)
        clip = renderer._gs.clip_mask
        assert clip is not None
        intensities = set(clip.tobytes())
        intermediates = [v for v in intensities if 0 < v < 255]
        assert intermediates, (
            f"W* clip mask should be AA, got intensities={sorted(intensities)}"
        )
    finally:
        doc.close()


def test_paint_pattern_fill_even_odd_paints_through_aa_mask() -> None:
    """End-to-end: fill a self-intersecting path with a tiling pattern
    using ``f*``. The cell-coloured pixels must show inside the path
    interior; the even-odd hole stays at page background."""
    pat = _build_tiling_pattern(
        cell_bytes=b"1 0 0 rg\n0 0 4 4 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 4.0, 4.0),
        x_step=4.0,
        y_step=4.0,
    )
    doc, page = _make_doc(60.0, 60.0)
    try:
        resources = PDResources()
        page.set_resources(resources)
        resources.put(
            COSName.get_pdf_name("Pattern"),
            COSName.get_pdf_name("P0"),
            pat.get_cos_object(),
        )
        contents = COSStream()
        # Outer square (10..50) plus inner square (22..38) filled with
        # even-odd rule → annulus painted in pattern.
        contents.set_raw_data(
            b"/Pattern cs\n/P0 scn\n"
            b"10 10 40 40 re\n"
            b"22 22 16 16 re\n"
            b"f*\n"
        )
        page.get_cos_object().set_item(COSName.CONTENTS, contents)
        img = PDFRenderer(doc).render_image(0)
    finally:
        doc.close()

    # Annulus body pixel (12, 30) → red (pattern colour).
    body = img.getpixel((12, 30))
    assert body[0] >= 200 and body[1] <= 60 and body[2] <= 60, body
    # Hole pixel (30, 30) → background (page white).
    hole = img.getpixel((30, 30))
    assert _is_white(hole, tol=8), hole
