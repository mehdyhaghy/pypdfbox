"""Live PDFBox differential parity for page rasterisation (PDFRenderer).

Pixel-EXACT parity is impossible here — pypdfbox rasterises with
Pillow/aggdraw while Apache PDFBox uses Java2D/AWT, so anti-aliasing and
sub-pixel coverage differ (documented in ``CHANGES.md``). We therefore
compare a coarse, tolerance-comparable *fingerprint* of the rendered page
instead of the raw bytes:

* **Exact page dimensions** — the rendered pixel ``(width, height)`` MUST be
  identical to PDFBox's. A mismatch is a real bug (wrong scale rounding,
  missing ``/Rotate`` width/height swap, etc.), not an AA artefact.
* **16x16 luminance grid** — each page is downsampled to a 16x16 grid of
  average Rec.601 luminance per cell (0..255). We compare the two grids by
  mean-absolute cell difference (MAD) and worst single-cell difference
  (MAXDIFF). This survives anti-aliasing but still catches gross
  divergences (blank page, shifted content, wrong scale, wrong rotation).

Signature format mirrors ``oracle/probes/RenderProbe.java`` exactly:
line 1 ``"<w> <h>"``; line 2 = 256 space-separated ints, row-major.

Tolerance rationale (measured against PDFBox 3.0.7 at 72 DPI over the
fixtures below): correctly rendered pages land at MAD <= ~2.3 and
MAXDIFF <= ~14 (worst case = thin diagonal vector strokes + small text,
where a 1-2px AA edge dominates a downsampled cell). A *blank* render of
the same pages measures MAD 10.8-21.8 and MAXDIFF 120+. We gate at
``MAD < 6.0`` and ``MAXDIFF < 60`` — comfortably above the AA ceiling yet
well below any gross-failure floor, so a correct page passes and a
blank/shifted/wrong-scale page fails.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

_GRID = 16
# Tolerances — see module docstring for the measured rationale.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

# (relative fixture path, page index, human label). Mix of: simple text +
# vector lines (rot0), rotated pages (90/180/270 — width/height swap), a
# multi-glyph text page (eu-001), a bidi/Unicode text page with a
# fractional media box (BidiSample, exercises dimension truncation), a
# generic writer fixture, and an AcroForm page.
_CASES = [
    ("multipdf/rot0.pdf", 0, "rotate_0"),
    ("multipdf/rot90.pdf", 0, "rotate_90"),
    ("multipdf/rot180.pdf", 0, "rotate_180"),
    ("multipdf/rot270.pdf", 0, "rotate_270"),
    ("text/input/eu-001.pdf", 0, "text_page"),
    ("text/BidiSample.pdf", 0, "bidi_fractional_mediabox"),
    ("pdfwriter/unencrypted.pdf", 0, "writer_page"),
    ("pdmodel/with_outline.pdf", 0, "outline_doc"),
]


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint of ``img`` — must match the
    cell mapping in ``RenderProbe.java`` (integer-division of pixel
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


def _oracle_signature(fixture: Path, page: int) -> tuple[tuple[int, int], list[int]]:
    """Run the Java oracle and parse its (dims, 16x16 grid) signature."""
    lines = run_probe_text("RenderProbe", str(fixture), str(page)).splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


@requires_oracle
@pytest.mark.parametrize(
    ("rel_path", "page", "label"),
    _CASES,
    ids=[c[2] for c in _CASES],
)
def test_render_matches_pdfbox(rel_path: str, page: int, label: str) -> None:
    fixture = _FIXTURES / rel_path
    (java_w, java_h), java_grid = _oracle_signature(fixture, page)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(page, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — grossly divergent render, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_blank_render_would_fail_tolerance() -> None:
    """Guard the threshold: a blank-white page is far outside tolerance for
    a fixture PDFBox renders with content. Confirms the gate actually
    discriminates correct renders from gross failures rather than passing
    everything."""
    fixture = _FIXTURES / "text/input/eu-001.pdf"
    _dims, java_grid = _oracle_signature(fixture, 0)
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: a blank render passes the MAD gate"
    )
