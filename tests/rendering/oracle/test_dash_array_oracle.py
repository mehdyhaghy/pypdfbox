"""Live PDFBox differential parity for the **dash array** operand of the ``d``
operator (PDF 32000-1 §8.4.3.6) — the on/off interval list itself, as opposed
to the *phase* (covered by ``test_dash_phase_oracle.py``).

Three fixtures, each a one-page PDF with a single thick horizontal stroke:

* **(a) ``[3 3] 0``** — even dash: 3-on, 3-off. The stroke breaks into a row of
  short dashes.
* **(b) ``[6 2] 3``** — uneven dash, 6-on / 2-off, phase 3; longer dashes with
  small gaps, shifted half-way into the first on-segment.
* **(c) ``[0 0] 0``** — the **degenerate all-zero dash array**. PDF 32000-1
  §8.4.3.6 only forbids an array that is *all zeros* implicitly (every dash
  length is zero → no on-segment ever begins). Apache PDFBox's
  ``PageDrawer.getStroke`` detects this via ``isAllZeroDash`` and returns a
  stroke whose ``createStrokedShape`` yields an empty ``java.awt.geom.Area`` —
  i.e. the stroke paints **nothing** (the line is invisible). This is NOT the
  same as an empty dash array (``[] 0``), which is a *solid* line. A renderer
  that conflates the two — treating ``[0 0]`` as "solid, fall back to no dash"
  — paints a solid line where PDFBox paints blank: a real, visible divergence,
  not anti-aliasing noise.

Method mirrors ``oracle/probes/RenderProbe.java`` (reused; it renders any PDF
fixture at 72 DPI and emits dims + a 16x16 average-luminance grid):

* **Exact rendered dimensions** — a mismatch is a real bug, never AA.
* **16x16 luminance grid** compared by mean-absolute cell diff (MAD) and worst
  single-cell diff (MAXDIFF), gated at wave-1408's whole-page render tolerance
  ``MAD < 6.0`` / ``MAXDIFF < 60`` — above the Java2D-vs-skia AA ceiling, well
  below a gross divergence (a solid line where PDFBox draws nothing differs far
  past this).

A guard test proves the all-zero case renders genuinely blank (not merely
"close to blank"): the page must be all-white, and it must differ materially
from the same line stroked *solid* (``[] 0``) — the exact regression the
``isAllZeroDash`` handling guards against.
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
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_PAGE = 120.0  # square page (== px at 72 DPI)
_Y = 60.0  # mid-page y for the horizontal stroked line
_X0 = 10.0
_X1 = 110.0


def _content(dash_clause: str) -> bytes:
    """Content stream: a thick black horizontal line under ``dash_clause``
    (a full ``[...] phase d`` clause, or empty for a solid control)."""
    clause = f"{dash_clause}\n" if dash_clause else ""
    return (
        f"4 w 0 0 0 RG\n"
        f"{clause}"
        f"{_X0} {_Y} m {_X1} {_Y} l S\n"
    ).encode("ascii")


def _build(dash_clause: str, out: Path) -> Path:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    page.set_resources(PDResources())
    doc.add_page(page)
    stream = COSStream()
    stream.set_raw_data(_content(dash_clause))
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


_FIXTURES = {
    "even_3_3": "[3 3] 0 d",
    "uneven_6_2_phase_3": "[6 2] 3 d",
    "all_zero_invisible": "[0 0] 0 d",
}


# ---------------------------------------------------------------------------
# fingerprint helpers — must mirror RenderProbe.java's cell mapping exactly
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
    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _mad_maxdiff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


def _dark_pixel_count(img: Image.Image) -> int:
    gray = img.convert("L")
    px = gray.load()
    width, height = gray.size
    return sum(
        1 for y in range(height) for x in range(width) if px[x, y] < 128
    )


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_FIXTURES), ids=list(_FIXTURES))
def test_dash_array_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each dash-array variant (even, uneven, and the degenerate all-zero →
    invisible case) must match Java PDFBox's render of the same fixture within
    the 16x16 fingerprint gate."""
    fixture = _build(_FIXTURES[label], tmp_path / f"{label}.pdf")
    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — dash array mis-rendered, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_all_zero_dash_paints_nothing_unlike_solid(tmp_path: Path) -> None:
    """Guard the regression directly: an all-zero dash array (``[0 0] 0 d``)
    must paint NOTHING (PDFBox ``isAllZeroDash`` → empty stroked shape), and
    must therefore differ materially from the SAME line stroked solid
    (``[] 0 d`` / no dash). A renderer that collapsed ``[0 0]`` to "solid"
    would paint an identical solid line for both — the bug this surface pins.
    """
    zero_pdf = _build("[0 0] 0 d", tmp_path / "all_zero.pdf")
    solid_pdf = _build("", tmp_path / "solid.pdf")

    with PDDocument.load(zero_pdf) as doc:
        zero_img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    with PDDocument.load(solid_pdf) as doc:
        solid_img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)

    zero_dark = _dark_pixel_count(zero_img)
    solid_dark = _dark_pixel_count(solid_img)

    # The all-zero dash paints nothing — the page is blank.
    assert zero_dark == 0, (
        f"all-zero dash painted {zero_dark} dark pixels — PDFBox renders it "
        "invisible (isAllZeroDash → empty stroke); this is a solid-where-blank "
        "regression, not AA"
    )
    # The solid control paints a real line — proving the fixtures are otherwise
    # identical and the difference is purely the dash semantics.
    assert solid_dark > 100, (
        f"solid control only painted {solid_dark} dark pixels — the control "
        "fixture failed to render a line, so the comparison is meaningless"
    )
