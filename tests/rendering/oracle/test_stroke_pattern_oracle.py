"""Live PDFBox differential parity for **stroke patterns** and **tiling
step spacing** — the sub-cases the existing pattern-fill oracles
(``test_pattern_fill_oracle.py`` / ``test_pattern_render_oracle.py``) do not
exercise.

Those companions cover patterns used as the *non-stroking* (fill) colour and
tiling patterns whose ``/XStep``/``/YStep`` equal the ``/BBox``. This file adds
the orthogonal axes:

* **(a) stroke pattern** — a colored tiling pattern selected as the *stroking*
  colour (``/Pattern`` CS + ``SCN /P1`` on the stroke, then a wide-line
  stroked rectangle ``re S``). The stroke band must show the pattern, not a
  solid colour (PDF 32000-1 §8.7.3.1). Before wave 1443 the renderer ignored
  ``stroke_pattern`` entirely and painted the band solid black; see
  ``CHANGES.md``.
* **(b) gapped tiles** — a tiling-pattern *fill* whose ``/XStep``/``/YStep``
  are LARGER than the ``/BBox`` width/height, so the lattice spaces the cells
  apart and the page background shows through the gaps (§8.7.3.3).
* **(c) overlapping tiles** — ``/XStep``/``/YStep`` SMALLER than the ``/BBox``,
  so successive cells overlap.

Method mirrors the render oracle (``oracle/probes/RenderProbe.java``):

* **Exact rendered dimensions** — a mismatch is a real bug, never AA.
* **16x16 luminance grid** compared by mean-absolute cell diff (MAD) and worst
  single-cell diff (MAXDIFF). Survives Java2D vs Pillow/aggdraw sub-pixel
  differences while catching a solid-painted stroke band, an ignored stroke
  pattern, or wrong tile spacing.

Gate is wave 1408's whole-page render tolerance, ``MAD < 6.0`` /
``MAXDIFF < 60``. A solid-colour stroke of the same path is checked to score
materially OUTSIDE that gate against the pattern-stroked reference, proving the
gate detects a "stroke pattern silently fell back to a solid stroke"
regression rather than passing any content-bearing render.
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

_PAGE = 120.0  # square page.

# A two-colour cell motif: red lower-left square + blue upper-right square,
# filling the whole /BBox so the tile-step variants visibly change spacing.
_MOTIF = b"1 0 0 rg 0 0 20 20 re f\n0 0 1 rg 20 20 20 20 re f\n"


# ---------------------------------------------------------------------------
# fixture builders
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


def _tiling(bbox: float, step: float, motif: bytes) -> PDTilingPattern:
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_COLORED)
    pattern.set_tiling_type(PDTilingPattern.TILING_TYPE_CONSTANT_SPACING)
    pattern.set_b_box(PDRectangle(0.0, 0.0, bbox, bbox))
    pattern.set_x_step(step)
    pattern.set_y_step(step)
    pattern.get_cos_object().set_raw_data(motif)
    return pattern


def _put_pattern(page: PDPage, pattern: PDTilingPattern) -> PDResources:
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P1"),
        pattern.get_cos_object(),
    )
    return resources


def _build_stroke_pattern(out: Path) -> Path:
    """(a) A thick stroked rectangle outline whose stroke colour is a colored
    tiling pattern. ``/Pattern`` CS, ``SCN /P1`` on the *stroke*, then a wide
    (``18 w``) ``re S`` — the stroke band must render the pattern."""
    doc, page = _new_doc()
    # /XStep == /YStep == /BBox so this case isolates the stroke-pattern path
    # from the tile-step variants below.
    pattern = _tiling(20.0, 20.0, b"1 0 0 rg 0 0 10 10 re f\n0 0 1 rg 10 10 10 10 re f\n")
    _put_pattern(page, pattern)
    return _save(
        doc, page, b"/Pattern CS /P1 SCN 18 w 25 25 70 70 re S\n", out
    )


def _build_gapped_tiles(out: Path) -> Path:
    """(b) Tiling fill with /XStep, /YStep LARGER than the /BBox (40pt cell on
    a 56pt step) — tiles are spaced apart, background shows between them."""
    doc, page = _new_doc()
    pattern = _tiling(40.0, 56.0, _MOTIF)
    _put_pattern(page, pattern)
    return _save(doc, page, b"/Pattern cs /P1 scn 10 10 100 100 re f\n", out)


def _build_overlapping_tiles(out: Path) -> Path:
    """(c) Tiling fill with /XStep, /YStep SMALLER than the /BBox (40pt cell on
    a 28pt step) — successive cells overlap, later tiles paint over earlier."""
    doc, page = _new_doc()
    pattern = _tiling(40.0, 28.0, _MOTIF)
    _put_pattern(page, pattern)
    return _save(doc, page, b"/Pattern cs /P1 scn 10 10 100 100 re f\n", out)


def _build_solid_stroke(out: Path) -> Path:
    """Control for the (a) guard: the same wide stroked rectangle painted with
    a flat mid-grey stroke colour instead of the pattern."""
    doc, page = _new_doc()
    page.set_resources(PDResources())
    return _save(
        doc, page, b"0.5 0.5 0.5 RG 18 w 25 25 70 70 re S\n", out
    )


_BUILDERS = {
    "stroke_pattern": _build_stroke_pattern,
    "tiling_gapped": _build_gapped_tiles,
    "tiling_overlapping": _build_overlapping_tiles,
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
def test_stroke_pattern_and_tile_step_match_pdfbox(
    label: str, tmp_path: Path
) -> None:
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
        f"(maxdiff={maxdiff}) — stroke pattern / tile step grossly divergent, "
        f"not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_solid_stroke_fails_pattern_tolerance(tmp_path: Path) -> None:
    """Guard the gate: a flat-colour stroke of the same rectangle scores far
    outside tolerance against the pattern-stroked PDFBox reference. Proves the
    MAD gate discriminates a real stroke pattern from a solid-stroke fallback
    (the "stroke pattern silently dropped to a solid stroke" regression that
    existed before wave 1443) rather than passing any content-bearing
    render."""
    fixture = _build_stroke_pattern(tmp_path / "stroke_pattern.pdf")
    _dims, java_grid = _oracle_signature(fixture)

    solid = _build_solid_stroke(tmp_path / "solid_stroke.pdf")
    with PDDocument.load(solid) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    solid_grid = _grid_from_image(img)

    mad, _maxdiff = _mad_maxdiff(java_grid, solid_grid)
    assert mad >= _MAD_TOLERANCE, (
        f"tolerance too loose — a solid stroke is within the MAD gate of the "
        f"pattern-stroked reference (mad={mad:.2f}); the gate would not catch "
        f"a stroke-pattern-to-solid regression"
    )
