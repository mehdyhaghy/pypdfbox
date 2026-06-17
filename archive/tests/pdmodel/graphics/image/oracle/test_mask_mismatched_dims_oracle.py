"""Live PDFBox differential parity for an explicit ``/Mask`` stencil whose
dimensions DIFFER from the base image (PDF 32000-1 §8.9.6.3).

The earlier explicit-/Mask oracle (``tests/rendering/oracle/``) only ever used
a mask matching the base image's dimensions. The spec is explicit that an
image's explicit ``/Mask`` (a 1-bpc image mask) need NOT share the base
image's dimensions: the mask is conceptually mapped across the base image's
unit square, i.e. scaled to the base coordinate space. PDFBox upscales the
mask to the base dims (nearest sample) before compositing. So a 2×2 mask over
an 8×8 base image tiles/scales across the whole base — a stencil applied 1:1
at the top-left only (or otherwise un-scaled) masks the wrong region.

Cases:

* **mask_smaller_than_base** — an 8×8 solid-red DeviceRGB base with a 2×2
  1-bpc explicit ``/Mask``. Two of the four mask samples mark *masked-out*
  (transparent) positions; scaled to 8×8 each sample covers a 4×4 quadrant,
  so two opposite quadrants of the base drop to the white backdrop. A
  renderer that applies the mask 1:1 at the top-left (no scaling) masks only
  a 2×2 corner and diverges grossly (see the guard test).
* **mask_equals_base** — control: an 8×8 base with an 8×8 mask carrying the
  same quadrant pattern. Mask dims == base dims, no scaling involved; both
  fixtures must render identically to PDFBox.

Pixel-EXACT parity is impossible (Pillow vs Java2D AA — see ``CHANGES.md``),
so we compare the proven coarse fingerprint: exact rendered dimensions plus a
16×16 average-luminance grid, gated at ``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/RenderProbe.java`` (72 DPI render). A guard test renders the
mismatched-dims fixture with the mask applied 1:1 (un-scaled, top-left only)
and asserts it scores materially worse, proving the gate detects an un-scaled
mask rather than passing both.

Fixtures are tiny one-page PDFs synthesised in-memory via pypdfbox's own
``LosslessFactory`` + content-stream API (no committed binaries).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as test_render_oracle.py / test_image_decode_mask_oracle.py —
# comfortably above the AA ceiling yet well below the gross-failure floor (an
# un-scaled mask diverges far past it; see the guard test below).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_BASE = 8  # base image side, px
_MB = 200  # media-box side, pt
_IMG_X, _IMG_Y, _IMG_W, _IMG_H = 40, 60, 120, 120  # draw_image placement, pt


def _grid_from_image(img: Image.Image) -> list[int]:
    """16×16 average-luminance fingerprint — identical cell mapping to
    ``RenderProbe.java`` (integer-division of pixel coord over image size,
    clamped to the last cell)."""
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    total = [0] * (_GRID * _GRID)
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            total[idx] += pixels[x, y]
            count[idx] += 1
    return [
        round(total[i] / count[i]) if count[i] else 255 for i in range(_GRID * _GRID)
    ]


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    """Run RenderProbe on page 0 and parse its (dims, 16×16 grid)."""
    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _quadrant_mask(side: int) -> Image.Image:
    """A 1-bpc stencil of ``side × side`` carrying the canonical quadrant
    pattern: the top-left and bottom-right halves marked *masked-out*
    (sample 1 → transparent), the other two quadrants paint (sample 0).

    With ``side == 2`` each sample covers a quadrant once scaled to the base;
    with ``side == _BASE`` the same pattern is drawn per-quadrant directly.
    """
    mask = Image.new("1", (side, side), 0)
    px = mask.load()
    half = side // 2
    for y in range(side):
        for x in range(side):
            top_left = x < half and y < half
            bottom_right = x >= half and y >= half
            px[x, y] = 1 if (top_left or bottom_right) else 0
    return mask


def _build_masked_fixture(path: Path, *, mask_side: int) -> None:
    """8×8 solid-red base image with an explicit 1-bpc ``/Mask`` of
    ``mask_side × mask_side`` carrying the quadrant pattern, over a white
    backdrop. The masked-out quadrants show the white backdrop; the painted
    quadrants show red."""
    base = Image.new("RGB", (_BASE, _BASE), (230, 40, 40))
    mask = _quadrant_mask(mask_side)

    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    image = LosslessFactory.create_from_image(doc, base)
    mask_xobj = LosslessFactory.create_from_image(doc, mask)
    mask_xobj.set_image_mask(True)
    image.set_mask(mask_xobj)
    assert image.get_mask() is not None

    cs = PDPageContentStream(doc, page)
    cs.set_non_stroking_color(1.0, 1.0, 1.0)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()
    cs.draw_image(image, _IMG_X, _IMG_Y, _IMG_W, _IMG_H)
    cs.close()
    doc.save(str(path))
    doc.close()


_BUILDERS = {
    "mask_smaller_than_base": lambda p: _build_masked_fixture(p, mask_side=2),
    "mask_equals_base": lambda p: _build_masked_fixture(p, mask_side=_BASE),
}


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_mask_mismatched_dims_render_matches_pdfbox(
    label: str, tmp_path: Path
) -> None:
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)

    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance. A mask applied 1:1 (not
    # scaled to the base) masks the wrong region and lands far outside this
    # gate (see the guard test below).
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — explicit /Mask mis-scaled, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_unscaled_mask_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: applying the 2×2 mask 1:1 at the base's top-left
    (NO scaling to the base dims) masks only a 2×2 corner instead of two 4×4
    quadrants. Compared against the PDFBox (correctly scaled) signature it
    must land outside tolerance, proving the gate detects an un-scaled mask
    rather than passing both."""
    fixture = tmp_path / "mask_smaller_than_base.pdf"
    _build_masked_fixture(fixture, mask_side=2)
    _dims, java_grid = _oracle_signature(fixture)

    # Reconstruct what an un-scaled (1:1, top-left) mask application produces:
    # only the top-left 2×2 of the 8×8 base sees the mask; the rest is opaque.
    base = Image.new("RGB", (_BASE, _BASE), (230, 40, 40))
    mask = _quadrant_mask(2)
    mpx = mask.load()
    rgba = base.convert("RGBA")
    apx = rgba.load()
    for y in range(_BASE):
        for x in range(_BASE):
            # Mask never reaches outside the 2×2 corner when applied 1:1, so
            # the rest of the base stays opaque (alpha 255).
            in_mask_region = x < 2 and y < 2
            alpha = (0 if mpx[x, y] == 1 else 255) if in_mask_region else 255
            r, g, b, _a = apx[x, y]
            apx[x, y] = (r, g, b, alpha)

    # Mimic the renderer's nearest-neighbour upscale + placement (bottom-left
    # origin: device top y = MB - IMG_Y - IMG_H).
    big = rgba.resize((_IMG_W, _IMG_H), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (_MB, _MB), (255, 255, 255, 255))
    canvas.alpha_composite(big, (_IMG_X, _MB - _IMG_Y - _IMG_H))
    py_grid = _grid_from_image(canvas)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: an explicit /Mask applied 1:1 (un-scaled) "
        "passes the MAD gate"
    )
