"""Live PDFBox differential parity for page ``/Rotate`` rasterisation.

PDF 32000-1 §7.7.3.3: a page's ``/Rotate`` entry rotates the page clockwise
by a multiple of 90 degrees when displayed or printed. Apache PDFBox's
``PDFRenderer.renderImageWithDPI`` honours this by rotating the rendered
raster so content appears upright — and, crucially, **swaps the output
width and height for 90 / 270** (a portrait 200x300 page rendered at 90
becomes a 300x200 landscape raster).

This surface differs from ``test_render_oracle.py`` (which renders four
*distinct* fixtures): here a single, deliberately asymmetric content stream
is rendered at each of the four ``/Rotate`` values, so the comparison
isolates the renderer's rotation transform. The Java probe both renders the
page and writes the exact PDF bytes it rendered to disk, so pypdfbox
rasterises the *identical* document — any divergence is in the rotation
transform, not in page serialisation.

Pixel-exact parity is impossible (Java2D vs Pillow/aggdraw anti-aliasing),
so we compare the same tolerance-comparable fingerprint used by
``test_render_oracle.py``:

* **Exact dimensions** — ``(width, height)`` MUST match PDFBox, and for
  90 / 270 the portrait page's dimensions are swapped. A mismatch is a real
  bug (missing width/height swap), not anti-aliasing.
* **16x16 luminance grid** — compared by mean-absolute cell difference
  (MAD) and worst single-cell difference (MAXDIFF), gated at the same
  thresholds established by ``test_render_oracle.py``.

A dedicated guard asserts the rendered grid at 90 differs substantially
from 0 — proving the rotation is actually applied (a renderer that ignored
``/Rotate`` would emit the same grid for every rotation).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Tolerances — identical rationale to test_render_oracle.py.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

# Portrait media box baked into the probe (non-square so the 90/270 swap
# is observable).
_PORTRAIT = (200, 300)
_LANDSCAPE = (300, 200)

# (rotation, expected pypdfbox dimensions). 90/270 swap W/H.
_CASES = [
    (0, _PORTRAIT),
    (90, _LANDSCAPE),
    (180, _PORTRAIT),
    (270, _LANDSCAPE),
]


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint of ``img`` — matches the cell
    mapping in ``PageRotateRenderProbe.java`` (integer division of the pixel
    coordinate over image size, clamped to the last cell)."""
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


def _run_probe(rotation: int, out_pdf: Path) -> tuple[tuple[int, int], list[int]]:
    """Run the probe for ``rotation``; it writes the rendered PDF to
    ``out_pdf`` and emits its (dims, 16x16 grid) signature."""
    lines = run_probe_text(
        "PageRotateRenderProbe", str(rotation), str(out_pdf)
    ).splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


@requires_oracle
@pytest.mark.parametrize(
    ("rotation", "expected_dims"),
    _CASES,
    ids=[f"rotate_{c[0]}" for c in _CASES],
)
def test_page_rotate_render_matches_pdfbox(
    rotation: int, expected_dims: tuple[int, int]
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out_pdf = Path(tmp) / f"rot{rotation}.pdf"
        (java_w, java_h), java_grid = _run_probe(rotation, out_pdf)

        # Java's own dimensions confirm the probe's expectation (and the
        # 90/270 swap) before we even render with pypdfbox.
        assert (java_w, java_h) == expected_dims, (
            f"rotate {rotation}: PDFBox dims {java_w}x{java_h} != expected "
            f"{expected_dims[0]}x{expected_dims[1]}"
        )

        with PDDocument.load(out_pdf) as doc:
            img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # (a) Exact pixel dimensions — for 90/270 this asserts the W/H swap.
    assert (py_w, py_h) == (java_w, java_h), (
        f"rotate {rotation}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"rotate {rotation}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — grossly divergent render, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"rotate {rotation}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_rotate_90_differs_from_0() -> None:
    """Guard: the rendered grid at 90 must differ substantially from 0.

    A renderer that ignored ``/Rotate`` (or rotated content without moving
    it) would emit a near-identical grid for every rotation. Because the
    content is asymmetric (an L-bar in one corner), a real 90 rotation
    relocates the dark mass to a different region of the raster — the MAD
    between the two grids is far above the parity tolerance."""
    with tempfile.TemporaryDirectory() as tmp:
        _dims0, grid0 = _run_probe(0, Path(tmp) / "rot0.pdf")
        _dims90, grid90 = _run_probe(90, Path(tmp) / "rot90.pdf")

    # The 16x16 grid is rotation-agnostic in shape (16x16 regardless of the
    # raster's aspect ratio), so the two grids are directly comparable.
    diffs = [abs(a - b) for a, b in zip(grid0, grid90, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"rotate 90 grid is within parity tolerance of rotate 0 (mad={mad:.2f}) "
        "— the /Rotate transform does not appear to move content"
    )
