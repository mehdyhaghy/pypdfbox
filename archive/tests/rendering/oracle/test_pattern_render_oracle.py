"""Live PDFBox differential parity for tiling-pattern + shading-pattern fills.

Companion to ``test_render_oracle.py`` (page rasterisation parity), focused on
the pattern / shading paint path: ``pypdfbox.pdmodel.graphics.pattern`` plus the
tile / gradient paint in ``pypdfbox.rendering``. We synthesise four tiny PDFs —
each fills a 100x100 region with a different pattern type — render every one
through Apache PDFBox (``oracle/probes/RenderProbe.java``) and through pypdfbox
at 72 DPI, then compare the same tolerance-based fingerprint the render oracle
uses:

* **Exact page dimensions** — a mismatch is a real bug (wrong scale rounding,
  wrong media-box handling), never an anti-aliasing artefact.
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared by
  mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF). This
  survives AA / sub-pixel coverage differences (Java2D vs Pillow/aggdraw) but
  catches a blank region, the wrong fill colour, or a grossly mis-tiled lattice.

Pixel-exact parity is impossible (documented in ``CHANGES.md``); the gate is the
same one wave 1408 calibrated for whole-page renders, ``MAD < 6.0`` and
``MAXDIFF < 60``. Measured against PDFBox 3.0.7 the four cases land at:

    tiling (PaintType 1, coloured) ...... MAD ~4.5  MAXDIFF ~26
    tiling (PaintType 2, uncoloured) .... MAD ~3.7  MAXDIFF ~25
    axial shading (Type 2) .............. MAD ~0.8  MAXDIFF ~2
    radial shading (Type 3) ............. MAD ~0.1  MAXDIFF ~1

The tiling cases sit higher because a tile lattice has a hard 1px boundary at
the clip edge where Java2D and our integer-lattice paste round differently;
that 1px shift is amplified by the coarse 16x16 downsample (worst case for a
repeating feature). A *blank* render of any of these regions measures MAD 69+
— comfortably caught by the gate (asserted explicitly below). The average
luminance of every correct render matches PDFBox within ~1 unit, confirming the
fill colour and coverage are right and only sub-pixel placement differs.
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
from pypdfbox.pdmodel.graphics.shading import PDShadingType2, PDShadingType3
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate wave 1408 calibrated for whole-page render parity.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_PAGE = 120.0  # square page; fill region is the inner 100x100 box at (10, 10).


# ---------------------------------------------------------------------------
# fixture builders — synthesise pattern PDFs via the pypdfbox API
# ---------------------------------------------------------------------------


def _new_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    return doc, page


def _exp_function(c0: list[float], c1: list[float]) -> COSDictionary:
    """Minimal Type 2 (exponential interpolation) function over [0, 1]."""
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


def _build_colored_tiling(out: Path) -> Path:
    """PaintType 1 (coloured) tiling pattern: a 40pt cell painting a red
    square with a blue inset; cell supplies its own colours."""
    doc, page = _new_doc()
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_COLORED)
    pattern.set_tiling_type(PDTilingPattern.TILING_TYPE_CONSTANT_SPACING)
    pattern.set_b_box(PDRectangle(0.0, 0.0, 40.0, 40.0))
    pattern.set_x_step(40.0)
    pattern.set_y_step(40.0)
    pattern.get_cos_object().set_raw_data(
        b"1 0 0 rg 6 6 28 28 re f\n"
        b"0 0 1 rg 14 14 12 12 re f\n"
    )
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pattern.get_cos_object(),
    )
    return _save(
        doc, page, b"/Pattern cs /P0 scn 10 10 100 100 re f\n", out
    )


def _build_uncolored_tiling(out: Path) -> Path:
    """PaintType 2 (uncoloured) tiling pattern: a colourless 40pt cell whose
    paint colour comes from the tint set via ``scn`` over a
    ``[/Pattern /DeviceRGB]`` colour space (here a green tint)."""
    doc, page = _new_doc()
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_UNCOLORED)
    pattern.set_tiling_type(PDTilingPattern.TILING_TYPE_CONSTANT_SPACING)
    pattern.set_b_box(PDRectangle(0.0, 0.0, 40.0, 40.0))
    pattern.set_x_step(40.0)
    pattern.set_y_step(40.0)
    # Colourless content — no colour operators; the tint paints it.
    pattern.get_cos_object().set_raw_data(b"6 6 28 28 re f\n")
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pattern.get_cos_object(),
    )
    # Pattern colour space with a DeviceRGB underlying ("alternate") space.
    cs = COSArray()
    cs.add(COSName.get_pdf_name("Pattern"))
    cs.add(COSName.get_pdf_name("DeviceRGB"))
    resources.put(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("CS0"), cs
    )
    return _save(
        doc, page, b"/CS0 cs 0 0.55 0 /P0 scn 10 10 100 100 re f\n", out
    )


def _build_axial_shading(out: Path) -> Path:
    """Shading pattern (PatternType 2) wrapping a Type 2 axial shading: a
    horizontal blue->yellow gradient across the fill region."""
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
    return _save(
        doc, page, b"/Pattern cs /P0 scn 10 10 100 100 re f\n", out
    )


def _build_radial_shading(out: Path) -> Path:
    """Shading pattern (PatternType 2) wrapping a Type 3 radial shading: a
    yellow centre fading to red at the rim, centred on the fill region."""
    doc, page = _new_doc()
    shading = PDShadingType3()
    shading.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    coords = COSArray()
    for v in (60.0, 60.0, 0.0, 60.0, 60.0, 50.0):
        coords.add(COSFloat(v))
    shading.set_coords(coords)
    shading.set_domain([0.0, 1.0])
    shading.set_function(_exp_function([1.0, 1.0, 0.0], [1.0, 0.0, 0.0]))
    shading.set_extend(True, True)
    sp = PDShadingPattern()
    sp.set_shading(shading)
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        sp.get_cos_object(),
    )
    return _save(
        doc, page, b"/Pattern cs /P0 scn 10 10 100 100 re f\n", out
    )


_BUILDERS = {
    "tiling_colored": _build_colored_tiling,
    "tiling_uncolored": _build_uncolored_tiling,
    "shading_axial": _build_axial_shading,
    "shading_radial": _build_radial_shading,
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


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_pattern_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
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

    # (b) Perceptual grid parity within tolerance — catches a blank region,
    #     the wrong fill colour, or a grossly mis-tiled lattice.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — pattern region grossly divergent, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_blank_pattern_render_would_fail_tolerance(
    label: str, tmp_path: Path
) -> None:
    """Guard the gate: a blank-white render of each pattern fixture is far
    outside tolerance versus PDFBox's actual (content-bearing) render. Proves
    the MAD gate discriminates a correct pattern fill from a blank / dropped
    one rather than passing everything."""
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
    _dims, java_grid = _oracle_signature(fixture)
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: tolerance too loose — a blank render passes the MAD gate"
    )
