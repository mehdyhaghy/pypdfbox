"""Live PDFBox differential parity for the **line-dash phase** operand of the
``d`` operator (PDF 32000-1 §8.4.3.6).

The ``d`` operator takes ``[dashArray] phase``; the phase shifts where in the
repeating dash pattern the stroke begins. A renderer that ignores ``phase``
will always start the dash pattern at the line origin, producing the same
render for ``[10 5] 0`` and ``[10 5] 5`` — but the spec requires the second
case to start 5 user-space units into the on/off cycle, so the visible dashes
shift by 5 units.

Three fixtures cover the surface:

* **(a) ``[10 5] 0``** — control: 10-on, 5-off, starting at the line origin.
* **(b) ``[10 5] 5``** — same pattern, phase = 5; the on-segment now starts
  half-way (the on-period is offset so the first 5 units of the stroke are the
  trailing half of an on-segment, then the gap follows).
* **(c) ``[4 6] 3``** — uneven on/off, non-zero phase; an extra cross-check
  that the phase scales correctly with the pattern.

Each fixture is a one-page PDF synthesised in-memory: a long horizontal
stroked line at mid-page with the dash set immediately before the stroke.

Method mirrors ``oracle/probes/RenderProbe.java``:

* **Exact rendered dimensions** — a mismatch is a real bug, never AA.
* **16x16 average-luminance grid** compared by mean-absolute cell diff (MAD)
  and worst single-cell diff (MAXDIFF). Survives Java2D vs Pillow/skia
  sub-pixel differences while catching a phase that is ignored, applied at
  the wrong sign, or scaled wrong.

Gate is wave 1408's whole-page render tolerance, ``MAD < 6.0`` / ``MAXDIFF <
60``. A guard test asserts the ``phase=0`` vs ``phase=5`` renders DIFFER
materially in the dash-band cells — proving the gate would catch a phase
silently dropped (the regression this surface guards against) rather than
passing any content-bearing render.
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


def _content(dash_array: str, phase: float) -> bytes:
    """Content stream: thick black horizontal line under ``[dash] phase d``."""
    return (
        f"4 w 0 0 0 RG\n"
        f"[{dash_array}] {phase} d\n"
        f"{_X0} {_Y} m {_X1} {_Y} l S\n"
    ).encode("ascii")


def _new_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    page.set_resources(PDResources())
    doc.add_page(page)
    return doc, page


def _save(doc: PDDocument, page: PDPage, content: bytes, out: Path) -> Path:
    stream = COSStream()
    stream.set_raw_data(content)
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


def _build_phase_zero(out: Path) -> Path:
    """(a) ``[10 5] 0`` — control, dash starts at the line origin."""
    doc, page = _new_doc()
    return _save(doc, page, _content("10 5", 0.0), out)


def _build_phase_five(out: Path) -> Path:
    """(b) ``[10 5] 5`` — same pattern, phase 5; the on-segment is shifted by
    half its length, so the first dash is half-on, then a gap follows."""
    doc, page = _new_doc()
    return _save(doc, page, _content("10 5", 5.0), out)


def _build_uneven_phase_three(out: Path) -> Path:
    """(c) ``[4 6] 3`` — uneven 4-on / 6-off with a phase of 3; cross-check
    that the phase scales correctly with an asymmetric pattern."""
    doc, page = _new_doc()
    return _save(doc, page, _content("4 6", 3.0), out)


_BUILDERS = {
    "phase_zero": _build_phase_zero,
    "phase_five": _build_phase_five,
    "uneven_phase_three": _build_uneven_phase_three,
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


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_dash_phase_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each phase variant (zero, mid-cycle, uneven-pattern non-zero) must match
    Java PDFBox's render of the same fixture within the fingerprint gate."""
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
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
        f"(maxdiff={maxdiff}) — dash phase ignored or mis-scaled, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_phase_zero_and_phase_five_differ_materially(tmp_path: Path) -> None:
    """Direct-pixel proof that the phase operand is actually applied: the
    ``[10 5] 0`` and ``[10 5] 5`` renders must differ in the dash-band cells.
    A renderer that ignored the phase would render the two identically."""
    zero_pdf = _build_phase_zero(tmp_path / "phase_zero.pdf")
    five_pdf = _build_phase_five(tmp_path / "phase_five.pdf")

    with PDDocument.load(zero_pdf) as doc:
        zero_img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    with PDDocument.load(five_pdf) as doc:
        five_img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)

    zero_grid = _grid_from_image(zero_img)
    five_grid = _grid_from_image(five_img)

    # The dash band sits at y ≈ _Y == 60 of a 120pt page → grid row index 8.
    row = _GRID // 2
    row_diffs = [
        abs(zero_grid[row * _GRID + c] - five_grid[row * _GRID + c])
        for c in range(_GRID)
    ]
    max_row_diff = max(row_diffs)
    assert max_row_diff >= 25, (
        f"phase=0 and phase=5 renders are nearly identical along the dash row "
        f"(max cell diff = {max_row_diff}) — the phase operand appears to be "
        f"ignored at stroke time"
    )
