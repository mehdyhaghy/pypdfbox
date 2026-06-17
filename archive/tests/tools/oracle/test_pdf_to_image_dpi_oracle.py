"""Live PDFBox differential parity for the DPI -> pixel-size scaling behind
``PDFRenderer.renderImageWithDPI`` (and the ``PDFToImage -dpi`` CLI flag).

The existing ``test_pdf_to_image_oracle.py`` pins the per-page *count* and
filename indexing of the tool, but only on a US-Letter fixture (612x792 pt) —
integer point dimensions whose ``pts * dpi/72`` product lands on a clean integer
at every DPI, so the float32-vs-double rounding boundary is never exercised.

Apache PDFBox computes the raster dimensions as a Java single-precision product
``(int) (widthPt * (dpi / 72f))`` (see ``PDFRenderer.renderImage``). For an A4
page at certain DPIs the float32 floor differs from the double-precision floor by
one pixel — e.g. ``attachment.pdf`` (595.32 x 841.92 pt):

* 150 DPI: height = ``int(841.92f * (150f/72f))`` = **1753**, but the
  double-precision ``int(841.92 * 150/72)`` = **1754**.
* 300 DPI: height = **3507** (float32) vs **3508** (double).

pypdfbox mirrors the single precision with ``numpy.float32`` in
``pdf_renderer.render_image_with_dpi``; this test pins that the rendered
dimensions match Apache PDFBox to the pixel at exactly those boundary DPIs, and
that the painted content still matches within the whole-page AA gate.

``RenderDpiProbe.java`` renders one page at an arbitrary ``float`` DPI and emits
the rendered dimensions + a 16x16 average-luminance fingerprint (same cell
mapping as ``RenderProbe.java``).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel import PDDocument
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
# A4 page (841.92 pt tall) — float32 floor differs from double at 150/300 DPI.
_A4_BOUNDARY = _FIXTURES / "pdfwriter" / "attachment.pdf"
# A4 page (841.89 pt) with real content for the cross-DPI content fingerprint.
_A4_CONTENT = _FIXTURES / "text" / "BidiSample.pdf"


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance grid — mirrors RenderDpiProbe.java's mapping."""
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
        round(total[i] / count[i]) if count[i] else 255
        for i in range(_GRID * _GRID)
    ]


def _oracle_signature(
    fixture: Path, page: int, dpi: float
) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text(
        "RenderDpiProbe", str(fixture), str(page), str(dpi)
    ).splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _mad_maxdiff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


@requires_oracle
@pytest.mark.parametrize(
    "dpi",
    [72.0, 96.0, 150.0, 200.0, 300.0],
    ids=["dpi72", "dpi96", "dpi150", "dpi200", "dpi300"],
)
def test_a4_boundary_dimensions_match_pdfbox(dpi: float) -> None:
    """A4 ``attachment.pdf`` page 1: rendered dimensions must equal Apache
    PDFBox to the pixel at every DPI, including 150/300 where the float32 floor
    is one pixel below the double-precision floor."""
    (java_w, java_h), _ = _oracle_signature(_A4_BOUNDARY, 0, dpi)
    with PDDocument.load(_A4_BOUNDARY) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, dpi)
    py_w, py_h = img.size
    assert (py_w, py_h) == (java_w, java_h), (
        f"A4 dpi={dpi}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )


@requires_oracle
def test_a4_150dpi_uses_float32_floor() -> None:
    """Regression pin for the float32 boundary itself: the 841.92 pt A4 page at
    150 DPI must render 1753 px tall (single precision), NOT 1754 (double).
    A renderer that did the scale product in double precision would diverge by
    one pixel from Apache PDFBox here."""
    (_, java_h), _ = _oracle_signature(_A4_BOUNDARY, 0, 150.0)
    assert java_h == 1753, f"oracle baseline changed: expected 1753, got {java_h}"
    with PDDocument.load(_A4_BOUNDARY) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 150.0)
    assert img.size[1] == 1753, (
        f"A4 150 DPI height {img.size[1]} != 1753 — float32 scale floor "
        "regressed to double precision (would be 1754)"
    )


@requires_oracle
@pytest.mark.parametrize(
    "dpi",
    [72.0, 150.0],
    ids=["dpi72", "dpi150"],
)
def test_a4_content_matches_pdfbox_across_dpi(dpi: float) -> None:
    """Painted content (not just dimensions) must match Apache PDFBox at both a
    base and a high DPI, within the whole-page anti-aliasing gate."""
    (java_w, java_h), java_grid = _oracle_signature(_A4_CONTENT, 0, dpi)
    with PDDocument.load(_A4_CONTENT) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, dpi)
    py_w, py_h = img.size
    assert (py_w, py_h) == (java_w, java_h), (
        f"content dpi={dpi}: dimensions diverge: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )
    py_grid = _grid_from_image(img)
    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"content dpi={dpi}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — content mis-rendered, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"content dpi={dpi}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )
