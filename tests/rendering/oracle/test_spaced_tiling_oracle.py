"""Live PDFBox differential parity for *spaced* tiling-pattern fills.

Companion to ``test_pattern_render_oracle.py`` / ``test_pattern_fill_oracle.py``
(tiling fills where ``/XStep`` == ``/YStep`` == the cell ``/BBox`` size, so
tiles abut with no gap) and ``test_stroke_pattern_oracle.py`` (pattern stroke).
This module pins the one tiling sub-case those miss: **``/XStep`` / ``/YStep``
LARGER than the cell ``/BBox``** (PDF 32000-1 §8.7.3.1).

When the step exceeds the /BBox the cell content fills only the /BBox and the
surplus strip up to the next step is a *gap* where the page background shows
through. PDFBox renders the tile as a ``TexturePaint`` over a step-sized anchor
rectangle, so those gap pixels stay transparent; pypdfbox mirrors this in
``PageDrawer._paint_tiling_pattern`` (the tile is step-sized, the /BBox cell is
clipped into it, and the alpha-keyed paste leaves the gaps transparent). A
renderer that mistakenly tiled the /BBox edge-to-edge (ignoring the step) would
paint a solid lattice with no background showing — a gross divergence this gate
catches.

Unlike the companion oracles (which build the fixture in Python and render it
through ``RenderProbe``), the Java side here is ``SpacedTilingProbe``, which
synthesises the *same* spaced-tiling PDF inside Apache PDFBox and renders it.
So both engines build and render their own fixture from identical parameters —
a tighter differential for the spaced-lattice geometry (gap width, cell
footprint, lattice phase).

Two cases, each a 120x120 page whose inner 100x100 box is filled with a
PaintType-1 tiling pattern (20pt red-square cell):

* **square** — ``/XStep`` = ``/YStep`` = 40 over a 20pt /BBox: wide square
  gaps, cells on a 40pt lattice.
* **wide**   — ``/XStep`` = 50, ``/YStep`` = 25 over a 20pt /BBox: asymmetric
  gaps, exercising independent x / y step handling.

Both engines emit the shared render fingerprint:

* **Exact page dimensions** — a mismatch is a real bug (scale / media-box).
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared by
  mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF).

The gate is wave 1408's whole-page render tolerance, ``MAD < 6`` /
``MAXDIFF < 60``. Measured against PDFBox 3.0.7 both cases land at
**MAD 0.00 / MAXDIFF 0** — the two engines lay the spaced lattice down pixel
for pixel (the 20pt cell on a 40pt / 50x25pt step lands on integer device
boundaries at 72 DPI, so there is no sub-pixel rounding to diverge on). A guard
test proves an *edge-to-edge* (step == /BBox, no gap) tiling of the same cell —
the failure mode if the step were ignored — diverges materially (MAD ~60+) from
the spaced reference, so the gate genuinely discriminates a spaced lattice from
a packed one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.pattern import PDTilingPattern
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_PAGE = 120.0  # square page; fill region is the inner 100x100 box at (10, 10).
_BBOX = 20.0   # cell /BBox edge — smaller than the step so gaps appear.
_MOTIF = b"1 0 0 rg 2 2 16 16 re f\n"  # red square inset in the 20pt cell.

# (x_step, y_step) per case — both exceed the 20pt /BBox so the background
# shows through the gaps. Must match SpacedTilingProbe.java exactly.
_STEPS = {
    "square": (40.0, 40.0),
    "wide": (50.0, 25.0),
}


# ---------------------------------------------------------------------------
# fixture builder — synthesise the spaced-tiling PDF via the pypdfbox API
# ---------------------------------------------------------------------------


def _new_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    return doc, page


def _save(doc: PDDocument, page: PDPage, content: bytes, out: Path) -> Path:
    stream = COSStream()
    stream.set_raw_data(content)
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


def _build_spaced(out: Path, *, x_step: float, y_step: float) -> Path:
    """PaintType 1 spaced tiling fill — ``x_step`` / ``y_step`` exceed the
    20pt /BBox so the page background shows through the gaps between cells."""
    doc, page = _new_doc()
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_COLORED)
    pattern.set_tiling_type(PDTilingPattern.TILING_TYPE_CONSTANT_SPACING)
    pattern.set_b_box(PDRectangle(0.0, 0.0, _BBOX, _BBOX))
    pattern.set_x_step(x_step)
    pattern.set_y_step(y_step)
    pattern.get_cos_object().set_raw_data(_MOTIF)
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pattern.get_cos_object(),
    )
    return _save(doc, page, b"/Pattern cs /P0 scn 10 10 100 100 re f\n", out)


def _build_packed(out: Path) -> Path:
    """Control: an edge-to-edge tiling (``/XStep`` == ``/YStep`` == /BBox) of
    the same 20pt cell — no gaps. This is the failure mode if the step were
    ignored; the guard test asserts it diverges from the spaced reference."""
    doc, page = _new_doc()
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_COLORED)
    pattern.set_tiling_type(PDTilingPattern.TILING_TYPE_CONSTANT_SPACING)
    pattern.set_b_box(PDRectangle(0.0, 0.0, _BBOX, _BBOX))
    pattern.set_x_step(_BBOX)
    pattern.set_y_step(_BBOX)
    pattern.get_cos_object().set_raw_data(_MOTIF)
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pattern.get_cos_object(),
    )
    return _save(doc, page, b"/Pattern cs /P0 scn 10 10 100 100 re f\n", out)


# ---------------------------------------------------------------------------
# fingerprint helpers — must mirror SpacedTilingProbe.java's cell mapping
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


def _oracle_signature(case: str) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text("SpacedTilingProbe", case).splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _pypdfbox_grid(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    return img.size, _grid_from_image(img)


def _mad_maxdiff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("case", list(_STEPS), ids=list(_STEPS))
def test_spaced_tiling_matches_pdfbox(case: str, tmp_path: Path) -> None:
    x_step, y_step = _STEPS[case]
    fixture = _build_spaced(
        tmp_path / f"{case}.pdf", x_step=x_step, y_step=y_step
    )
    (java_w, java_h), java_grid = _oracle_signature(case)
    (py_w, py_h), py_grid = _pypdfbox_grid(fixture)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{case}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity — catches a step ignored (packed lattice, no
    #     gaps), the wrong gap width, or a mis-placed lattice phase.
    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{case}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — spaced lattice grossly divergent (step "
        f"ignored / wrong gap / wrong phase), not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{case}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("case", list(_STEPS), ids=list(_STEPS))
def test_packed_tiling_differs_from_spaced(case: str, tmp_path: Path) -> None:
    """Guard the gate: an edge-to-edge (step == /BBox, no gap) tiling of the
    same cell — the failure mode if ``/XStep`` / ``/YStep`` were ignored —
    must diverge materially from PDFBox's spaced reference. A packed lattice
    covers far more of the fill region with the red cell (no background gaps),
    so its luminance grid differs strongly from the spaced render."""
    _dims, java_grid = _oracle_signature(case)
    packed = _build_packed(tmp_path / f"{case}_packed.pdf")
    _pdims, packed_grid = _pypdfbox_grid(packed)
    mad, _maxdiff = _mad_maxdiff(java_grid, packed_grid)
    assert mad >= _MAD_TOLERANCE, (
        f"{case}: tolerance too loose — a packed (no-gap) lattice is within "
        f"the MAD gate of the spaced reference (mad={mad:.2f}); the gate "
        f"would not catch a step-ignored regression"
    )
