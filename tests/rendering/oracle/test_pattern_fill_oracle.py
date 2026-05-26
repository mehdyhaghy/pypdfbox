"""Live PDFBox differential parity for pattern *fills* — focused on the
sub-cases ``test_pattern_render_oracle.py`` does not exercise.

That companion file already covers a colour-supplying (PaintType 1) tiling
fill, an uncoloured (PaintType 2) tiling fill, and axial/radial shading
patterns at identity matrix. This file adds the case those miss: a **tiling
pattern with a non-identity ``/Matrix``** (a scale + translate that shifts the
lattice phase and changes the cell size in device space). It re-confirms the
PaintType 1 / PaintType 2 / axial-shading paths alongside it so the four fills
of PRD §"pattern fills in rendering" are all anchored against Apache PDFBox in
one place, and adds a *solid-fill guard*: a flat colour fill of the same region
must score materially worse against each patterned reference than the real
pattern render does — proving the gate detects a "pattern silently fell back to
a flat fill" regression rather than passing everything.

Method mirrors the render oracle (``oracle/probes/RenderProbe.java``):

* **Exact rendered dimensions** — a mismatch is a real bug, never AA.
* **16x16 luminance grid** compared by mean-absolute cell diff (MAD) and worst
  single-cell diff (MAXDIFF). Survives Java2D vs Pillow/aggdraw sub-pixel
  differences while catching a blank region, the wrong fill colour, a
  mis-tiled lattice, or an ignored ``/Matrix``.

Gate is wave 1408's whole-page render tolerance, ``MAD < 6.0`` /
``MAXDIFF < 60``. Measured against PDFBox 3.0.7 the cases land at roughly:

    tiling PaintType 1 (colour) ............. MAD ~4.5  MAXDIFF ~26
    tiling PaintType 2 (uncoloured, scn) .... MAD ~3.7  MAXDIFF ~25
    tiling PaintType 1 + scale/translate .... MAD ~3.1  MAXDIFF ~25
    axial shading pattern (Type 2) .......... MAD ~0.8  MAXDIFF ~2

The matrix case used to score MAD ~64 / MAXDIFF ~205 (the ``/Matrix`` was
ignored entirely — the lattice tiled from the canvas origin at the page CTM
scale); see ``CHANGES.md`` wave 1429.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.pattern import PDShadingPattern, PDTilingPattern
from pypdfbox.pdmodel.graphics.shading import PDShadingType2
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_PAGE = 120.0  # square page; fill region is the inner 100x100 box at (10, 10).
# 28pt-on-40pt motif: a red square with a blue inset, matching the calibrated
# tile size of the companion render oracle so the lattice rounding stays in
# tolerance under the coarse 16x16 downsample.
_MOTIF = b"1 0 0 rg 6 6 28 28 re f\n0 0 1 rg 14 14 12 12 re f\n"


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


def _exp_function(c0: list[float], c1: list[float]) -> COSDictionary:
    fn = COSDictionary()
    fn.set_int(COSName.get_pdf_name("FunctionType"), 2)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    fn.set_item(COSName.get_pdf_name("Domain"), domain)
    a0 = COSArray()
    for v in c0:
        a0.add(COSFloat(v))
    fn.set_item(COSName.get_pdf_name("C0"), a0)
    a1 = COSArray()
    for v in c1:
        a1.add(COSFloat(v))
    fn.set_item(COSName.get_pdf_name("C1"), a1)
    fn.set_int(COSName.get_pdf_name("N"), 1)
    return fn


def _save(doc: PDDocument, page: PDPage, content: bytes, out: Path) -> Path:
    stream = COSStream()
    stream.set_raw_data(content)
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


def _tiling(paint_type: int, matrix: list[float] | None) -> PDTilingPattern:
    pattern = PDTilingPattern()
    pattern.set_paint_type(paint_type)
    pattern.set_tiling_type(PDTilingPattern.TILING_TYPE_CONSTANT_SPACING)
    pattern.set_b_box(PDRectangle(0.0, 0.0, 40.0, 40.0))
    pattern.set_x_step(40.0)
    pattern.set_y_step(40.0)
    if matrix is not None:
        pattern.set_matrix(matrix)
    return pattern


def _build_colored_tiling(out: Path) -> Path:
    """(a) PaintType 1 (colour) tiling fill — cell supplies its own colours."""
    doc, page = _new_doc()
    pattern = _tiling(PDTilingPattern.PAINT_TYPE_COLORED, None)
    pattern.get_cos_object().set_raw_data(_MOTIF)
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pattern.get_cos_object(),
    )
    return _save(doc, page, b"/Pattern cs /P0 scn 10 10 100 100 re f\n", out)


def _build_uncolored_tiling(out: Path) -> Path:
    """(b) PaintType 2 (uncoloured) tiling fill — colour supplied at the use
    site via ``scn c1 c2 c3 /P0`` over a ``[/Pattern /DeviceRGB]`` space."""
    doc, page = _new_doc()
    pattern = _tiling(PDTilingPattern.PAINT_TYPE_UNCOLORED, None)
    # Colourless cell content: no colour operators — the scn tint paints it.
    pattern.get_cos_object().set_raw_data(b"6 6 28 28 re f\n")
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pattern.get_cos_object(),
    )
    cs = COSArray()
    cs.add(COSName.get_pdf_name("Pattern"))
    cs.add(COSName.get_pdf_name("DeviceRGB"))
    resources.put(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("CS0"), cs
    )
    return _save(
        doc, page, b"/CS0 cs 0 0.55 0 /P0 scn 10 10 100 100 re f\n", out
    )


def _build_matrix_tiling(out: Path) -> Path:
    """(c) PaintType 1 tiling fill with a non-identity ``/Matrix`` — a 1.5x
    scale plus a (12, 8) translate that grows the device-space cell and
    shifts the lattice phase. Exercises ``/Matrix`` handling end-to-end."""
    doc, page = _new_doc()
    pattern = _tiling(
        PDTilingPattern.PAINT_TYPE_COLORED, [1.5, 0.0, 0.0, 1.5, 12.0, 8.0]
    )
    pattern.get_cos_object().set_raw_data(_MOTIF)
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pattern.get_cos_object(),
    )
    return _save(doc, page, b"/Pattern cs /P0 scn 10 10 100 100 re f\n", out)


def _build_axial_shading(out: Path) -> Path:
    """(d) Shading pattern (PatternType 2) wrapping a Type 2 axial shading:
    a horizontal blue->yellow gradient across the fill region."""
    doc, page = _new_doc()
    shading = PDShadingType2()
    shading.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    coords = COSArray()
    for v in (10.0, 0.0, 110.0, 0.0):
        coords.add(COSFloat(v))
    shading.set_coords(coords)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    shading.set_domain(domain)
    shading.set_function(_exp_function([0.0, 0.0, 1.0], [1.0, 1.0, 0.0]))
    extend = COSArray()
    extend.add(COSBoolean.get(True))
    extend.add(COSBoolean.get(True))
    shading.set_extend(extend)
    sp = PDShadingPattern()
    sp.set_shading(shading)
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        sp.get_cos_object(),
    )
    return _save(doc, page, b"/Pattern cs /P0 scn 10 10 100 100 re f\n", out)


def _build_solid_fill(out: Path) -> Path:
    """Control: a flat mid-grey fill of the same 100x100 region. Used by the
    guard test as the "pattern fell back to a solid fill" stand-in."""
    doc, page = _new_doc()
    page.set_resources(PDResources())
    return _save(doc, page, b"0.5 0.5 0.5 rg 10 10 100 100 re f\n", out)


_BUILDERS = {
    "tiling_colored": _build_colored_tiling,
    "tiling_uncolored": _build_uncolored_tiling,
    "tiling_matrix": _build_matrix_tiling,
    "shading_axial": _build_axial_shading,
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
def test_pattern_fill_matches_pdfbox(label: str, tmp_path: Path) -> None:
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
        f"(maxdiff={maxdiff}) — pattern fill grossly divergent, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_solid_fill_fails_pattern_tolerance(
    label: str, tmp_path: Path
) -> None:
    """Guard the gate: a flat-colour fill of the same region scores far
    outside tolerance against each pattern's PDFBox reference. Proves the MAD
    gate discriminates a real pattern fill from a solid-fill fallback (the
    "pattern silently dropped to a flat fill" regression) rather than passing
    any content-bearing render."""
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
    _dims, java_grid = _oracle_signature(fixture)

    solid = _build_solid_fill(tmp_path / f"{label}_solid.pdf")
    with PDDocument.load(solid) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    solid_grid = _grid_from_image(img)

    mad, _maxdiff = _mad_maxdiff(java_grid, solid_grid)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: tolerance too loose — a solid fill is within the MAD gate "
        f"of the pattern reference (mad={mad:.2f}); the gate would not catch "
        f"a pattern-to-solid-fill regression"
    )
