"""Live PDFBox differential parity for *uncolored* tiling-pattern fills
(``/PaintType 2``, PDF 32000-1 §8.7.3.1 / §8.7.3.3).

Companion to ``test_spaced_tiling_oracle.py`` (spaced PaintType-1 colored
tiling) and ``test_pattern_render_oracle.py`` / ``test_pattern_fill_oracle.py``
(packed PaintType-1 colored tiling). This module pins the orthogonal case
none of those touch: a tiling pattern whose content stream carries **NO
colour** — the fill colour is supplied externally by the ``scn`` operands.

An uncolored tiling pattern is set via a ``/Pattern`` colour space whose
*underlying* colour space is ``/DeviceRGB`` (``[/Pattern /DeviceRGB]``). The
page does ``/PCS cs r g b /P0 scn ... f``: the three leading numbers are the
*tint* the pattern paints with (routed through the underlying DeviceRGB), and
``/P0`` selects the uncolored tile. The cell motif here is a 16pt square inset
in a 20pt /BBox cell, drawn with a bare ``re f`` (no ``rg`` / ``g`` / ``sc``),
so the painted colour is *only* whatever the tint resolves to.

Unlike the companion oracles (Python-built fixture rendered through
``RenderProbe``), the Java side here is ``UncoloredTilingProbe``, which
synthesises the *same* uncolored-tiling PDF inside Apache PDFBox and renders
it from identical parameters — a tight differential for (a) routing the scn
tint through the underlying colour space and (b) painting an uncolored cell in
that tint.

Both engines emit the shared render fingerprint:

* **Exact page dimensions** — a mismatch is a real bug (scale / media-box).
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared by
  mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF).

The gate is wave 1408's whole-page render tolerance, ``MAD < 6`` /
``MAXDIFF < 60``. A guard test proves the gate is tint-sensitive: the same
pattern set with a *different* scn colour (blue vs red) produces a materially
different raster (an uncolored tile that ignored the tint — painting a fixed
colour, e.g. black — would render identically for every scn colour and so
fail the guard).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.pattern import PDTilingPattern
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_PAGE = 120.0  # square page; fill region is the inner 100x100 box at (10, 10).
_BBOX = 20.0   # cell /BBox edge; packed lattice (XStep == YStep == /BBox).
# Uncolored cell motif: a 16pt square inset in the 20pt /BBox, NO colour op —
# the colour comes solely from the scn tint. Must match UncoloredTilingProbe.
_MOTIF = b"2 2 16 16 re f\n"

# scn tints per case, in DeviceRGB [0,1]. Must match the probe args exactly.
_TINTS = {
    "red": (1.0, 0.0, 0.0),
    "blue": (0.0, 0.0, 1.0),
}


# ---------------------------------------------------------------------------
# fixture builder — synthesise the uncolored-tiling PDF via the pypdfbox API
# ---------------------------------------------------------------------------


def _new_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    return doc, page


def _fmt(value: float) -> str:
    return str(int(value)) if value == int(value) else repr(value)


def _build_uncolored(
    out: Path, *, tint: tuple[float, float, float]
) -> Path:
    """PaintType-2 (uncolored) tiling fill: the cell is shape-only and the
    page sets a ``[/Pattern /DeviceRGB]`` colour space, supplying ``tint`` as
    the leading scn components. The square cell is painted in the tint."""
    doc, page = _new_doc()
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_UNCOLORED)
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
    # Uncolored Pattern colour space: [ /Pattern /DeviceRGB ], registered
    # under /ColorSpace as /PCS (mirrors UncoloredTilingProbe.java).
    pattern_cs = COSArray()
    pattern_cs.add(COSName.get_pdf_name("Pattern"))
    pattern_cs.add(COSName.get_pdf_name("DeviceRGB"))
    cs_dict = COSDictionary()
    cs_dict.set_item(COSName.get_pdf_name("PCS"), pattern_cs)
    resources.get_cos_object().set_item(
        COSName.get_pdf_name("ColorSpace"), cs_dict
    )

    r, g, b = tint
    content = (
        f"/PCS cs {_fmt(r)} {_fmt(g)} {_fmt(b)} /P0 scn "
        "10 10 100 100 re f\n"
    ).encode("ascii")
    stream = COSStream()
    stream.set_raw_data(content)
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


# ---------------------------------------------------------------------------
# fingerprint helpers — must mirror UncoloredTilingProbe.java's cell mapping
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


def _oracle_signature(tint: tuple[float, float, float]) -> tuple[
    tuple[int, int], list[int]
]:
    args = [_fmt(component) for component in tint]
    lines = run_probe_text("UncoloredTilingProbe", *args).splitlines()
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
@pytest.mark.parametrize("case", list(_TINTS), ids=list(_TINTS))
def test_uncolored_tiling_matches_pdfbox(case: str, tmp_path: Path) -> None:
    """The uncolored (PaintType 2) tiling fill must match Java PDFBox's
    render of the same fixture within the 16x16 fingerprint gate — proving
    the scn tint is routed through the underlying DeviceRGB and the cell is
    painted in that tint, not a fixed colour."""
    tint = _TINTS[case]
    fixture = _build_uncolored(tmp_path / f"{case}.pdf", tint=tint)
    (java_w, java_h), java_grid = _oracle_signature(tint)
    (py_w, py_h), py_grid = _pypdfbox_grid(fixture)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{case}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity — catches a dropped tint, a tint resolved
    #     through the wrong colour space, or an uncolored cell painted in a
    #     fixed colour instead of the scn tint.
    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{case}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — uncolored tile mis-painted (tint dropped / "
        f"wrong CS / fixed colour), not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{case}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_uncolored_tiling_is_tint_sensitive(tmp_path: Path) -> None:
    """Guard the gate: the SAME uncolored pattern set with two different scn
    colours (red vs blue) must produce materially different rasters. An
    uncolored tile that ignored the scn tint (painting a fixed colour, e.g.
    black or the cell's own — there is none) would render identically for
    every scn colour, so the red and blue grids would coincide and this MAD
    would be ~0. We assert it is well past the gate."""
    red = _build_uncolored(tmp_path / "red.pdf", tint=_TINTS["red"])
    blue = _build_uncolored(tmp_path / "blue.pdf", tint=_TINTS["blue"])
    _rdims, red_grid = _pypdfbox_grid(red)
    _bdims, blue_grid = _pypdfbox_grid(blue)
    mad, _maxdiff = _mad_maxdiff(red_grid, blue_grid)
    assert mad >= _MAD_TOLERANCE, (
        "uncolored tiling is not tint-sensitive: red and blue scn colours "
        f"produced near-identical rasters (mad={mad:.2f}); the scn tint is "
        "being dropped, so the gate could not catch an ignored tint"
    )
