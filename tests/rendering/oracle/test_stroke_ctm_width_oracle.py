"""Live PDFBox differential parity for **CTM-transformed stroke width**: a
stroke (``w`` line width) painted under a non-identity ``cm`` — uniform scale
and anisotropic scale (PDF 32000-1 §8.5.3.1).

Distinct from ``test_stroke_geometry_oracle.py`` (wave 1461 — cap / join /
miter-limit / dash at an *identity* CTM): this surface pins how the line width
scales when the current transformation matrix is non-identity.

The PDF spec models a stroke as a pen swept along the path with the pen itself
transformed by the CTM, so under an anisotropic ``cm`` the pen would become an
ellipse (a stroke whose device width varies by direction). Apache PDFBox does
*not* render that ellipse: ``PageDrawer.transformWidth`` collapses the pen to a
single isotropic scalar device width

    lineWidth * sqrt((x² + y²) / 2)   where  x = a + c,  y = b + d

(``a, b, c, d`` are the CTM's linear block) and strokes the device-space path
with that scalar width. pypdfbox mirrors this exactly in
``PdfRenderer._stroke_path_device_space`` / ``_transform_width_scale`` (see
``CHANGES.md`` wave 1472 — previously the pen was pre-scaled by
``sqrt(|det(CTM)|)`` *and* scaled again by the canvas transform, double-applying
the scale).

Fixtures (one-page PDFs synthesised in-memory, thick black strokes on white):

* **uniform_2x** — ``cm 2 0 0 2`` with ``4 w``; the stroke renders at device
  width 8 (== ``4 * sqrt((2²+2²)/2)`` == ``4 * 2``).
* **uniform_3x** — ``cm 3 0 0 3`` with ``3 w``; device width 9.
* **aniso_3x1** — ``cm 3 0 0 1`` with ``6 w``; PDFBox device width
  ``6 * sqrt((3²+1²)/2)`` == ``6 * sqrt(5)`` ≈ 13.4 (NOT 6, and NOT 18).
* **aniso_1x3** — ``cm 1 0 0 3`` with ``6 w``; same scalar ``6 * sqrt(5)``
  (the formula is symmetric in the two scale factors) so the width matches
  ``aniso_3x1`` even though the line orientation differs — a renderer that
  produced skia's true elliptical pen would give different widths.

Pixel-EXACT parity is impossible (Java2D vs skia AA — see ``CHANGES.md`` /
``test_render_oracle.py``); we compare the proven coarse fingerprint: exact
rendered dimensions plus a 16x16 average-luminance grid, gated at
``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/StrokeCtmWidthProbe.java`` (72 DPI, RenderProbe luminance
math). A guard test proves the anisotropic stroke is materially wider than the
naive ``cm``-determinant scaling would give, so the gate would catch a
regression to either the double-scaled or the determinant-only width.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same whole-page render gate as test_stroke_geometry_oracle.py /
# test_render_oracle.py — comfortably above the Java2D-vs-skia AA ceiling yet
# well below the gross-failure floor (a double-scaled stroke width, or one
# scaled by the CTM determinant instead of PDFBox's sqrt((x²+y²)/2), diverges
# far past this).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_PAGE = 120.0  # square page (== px at 72 DPI)


def _content_for(label: str) -> bytes:
    """Content stream for one CTM-stroke-width fixture. A thick black stroke
    painted under a non-identity ``cm``; the geometry is chosen so the device-
    space stroke lands well inside the 120x120 page in every case."""
    if label == "uniform_2x":
        # cm 2x: 4 w -> device width 8. Segment 10->50 in scaled space spans
        # 20->100 device.
        return b"2 0 0 2 0 0 cm\n4 w 0 0 0 RG\n10 30 m 50 30 l S\n"
    if label == "uniform_3x":
        # cm 3x: 3 w -> device width 9.
        return b"3 0 0 3 0 0 cm\n3 w 0 0 0 RG\n8 20 m 30 20 l S\n"
    if label == "aniso_3x1":
        # cm 3 0 0 1: 6 w -> device width 6*sqrt(5) ~= 13.4. Horizontal line.
        return b"3 0 0 1 0 0 cm\n6 w 0 0 0 RG\n10 60 m 33 60 l S\n"
    if label == "aniso_1x3":
        # cm 1 0 0 3: 6 w -> same scalar 6*sqrt(5). Vertical line.
        return b"1 0 0 3 0 0 cm\n6 w 0 0 0 RG\n60 10 m 60 33 l S\n"
    raise ValueError(label)  # pragma: no cover


def _build(label: str, out: Path) -> Path:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    page.set_resources(PDResources())
    doc.add_page(page)
    stream = COSStream()
    stream.set_raw_data(_content_for(label))
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


_LABELS = ["uniform_2x", "uniform_3x", "aniso_3x1", "aniso_1x3"]


# ---------------------------------------------------------------------------
# fingerprint helpers — must mirror StrokeCtmWidthProbe.java's cell mapping
# ---------------------------------------------------------------------------


def _grid_from_image(img: Image.Image) -> list[int]:
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


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    """Run StrokeCtmWidthProbe on page 0 and parse its (dims, 16x16 grid).
    The probe emits the grid comma-separated (see the probe header)."""
    lines = run_probe_text("StrokeCtmWidthProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _mad_maxdiff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", _LABELS, ids=_LABELS)
def test_stroke_ctm_width_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each CTM-transformed stroke-width variant must match Java PDFBox's
    render of the same fixture within the 16x16 fingerprint gate."""
    fixture = _build(label, tmp_path / f"{label}.pdf")

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

    # (b) Perceptual grid parity within tolerance.
    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — CTM stroke width mis-applied, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


def _stroke_width_px(fixture: Path, *, axis: str) -> int:
    """Measure the rendered stroke's thickness in device pixels along ``axis``
    ('y' for a horizontal line, 'x' for a vertical line) — the extent of the
    dark-pixel band perpendicular to the line direction."""
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("L")
    px = img.load()
    width, height = img.size
    coords: list[int] = []
    for y in range(height):
        for x in range(width):
            if px[x, y] < 128:
                coords.append(y if axis == "y" else x)
    assert coords, "no stroke rendered"
    return max(coords) - min(coords) + 1


@requires_oracle
def test_anisotropic_width_is_isotropic_scalar(tmp_path: Path) -> None:
    """Direct proof of PDFBox's ``transformWidth`` model: the anisotropic
    ``cm 3 0 0 1`` (horizontal line) and ``cm 1 0 0 3`` (vertical line)
    fixtures use the same ``6 w`` and the formula ``sqrt((x²+y²)/2)`` is
    symmetric in the two scale factors, so BOTH render at the same scalar
    device width ``6*sqrt(5) ~= 13`` px.

    A renderer that produced skia's true elliptical pen would instead give
    width 6 (perpendicular axis scaled by 1) for one and 18 for the other —
    so this asserts the two thicknesses agree, and that they sit near the
    isotropic scalar (well above 6, well below 18)."""
    h_fixture = _build("aniso_3x1", tmp_path / "aniso_3x1.pdf")
    v_fixture = _build("aniso_1x3", tmp_path / "aniso_1x3.pdf")

    h_width = _stroke_width_px(h_fixture, axis="y")
    v_width = _stroke_width_px(v_fixture, axis="x")

    # The two device widths must be (near-)equal — the scalar is symmetric.
    assert abs(h_width - v_width) <= 2, (
        f"anisotropic stroke widths diverge by orientation "
        f"(horizontal={h_width}px, vertical={v_width}px) — the stroke is "
        "rendering as an elliptical pen, not PDFBox's isotropic scalar"
    )
    # And both sit at the scalar 6*sqrt(5) ~= 13.4, clearly above the naive
    # perpendicular-only width (6) and below the other-axis width (18).
    for label, w in (("horizontal", h_width), ("vertical", v_width)):
        assert 10 <= w <= 16, (
            f"{label} anisotropic stroke width {w}px not near the PDFBox "
            f"scalar 6*sqrt(5)~=13 — width scaling diverges from transformWidth"
        )


@requires_oracle
def test_uniform_width_scales_with_ctm(tmp_path: Path) -> None:
    """Guard the gate: a uniform ``cm`` must actually scale the stroke width.
    ``cm 3 0 0 3`` with ``3 w`` renders a device width of 9 px — materially
    thicker than the same ``3 w`` at identity (3 px). A renderer that ignored
    the CTM scale (the pre-fix double-scale bug went the other way, but a
    no-scale regression is equally wrong) would render both at 3 px."""
    scaled = _build("uniform_3x", tmp_path / "uniform_3x.pdf")
    scaled_width = _stroke_width_px(scaled, axis="y")
    # 3 w under cm 3x -> 9 device px; allow AA slack.
    assert 8 <= scaled_width <= 11, (
        f"uniform 3x stroke width {scaled_width}px not near the expected 9px "
        "— the CTM scale is not being applied to the line width"
    )
