"""Live PDFBox differential parity for *shading-pattern* (``/PatternType 2``)
fills — the sub-cases the two companion files don't reach.

``test_pattern_render_oracle.py`` and ``test_pattern_fill_oracle.py`` already
anchor an axial / radial shading pattern used to fill a **rectangle** at an
**identity** pattern ``/Matrix``. Both of those coincidences (rectangular path,
identity matrix, fill issued at the page base CTM) make the shading's pattern
space line up exactly with the current user space, so they exercise neither the
pattern ``/Matrix`` transform nor a non-rectangular clip.

This file fills the gap with three shading-pattern fills:

* **shading_nonrect** — an axial shading pattern filling a **non-rectangular
  path** (a triangle). Confirms the shading is clipped to the filled path's
  interior, not just its bounding box.
* **shading_matrix** — an axial shading pattern carrying a non-identity
  ``/Matrix`` (a 1.6x scale + translate). The gradient axis is given in pattern
  space; the ``/Matrix`` maps pattern space into the page's *initial* user
  space (PDF 32000-1 §8.7.3.1), so honouring it shifts and stretches the
  gradient relative to the same coords-with-identity-matrix render.
* **shading_matrix_rotate** — the same with a rotation in the ``/Matrix`` so the
  gradient axis is no longer page-aligned, stressing the off-diagonal terms.

A shading pattern's space is ``patternMatrix x initialPageCTM`` — it ignores the
CTM in force when the path is filled. A renderer that maps the shading through
the *current* CTM (correct for the ``sh`` operator) instead of the pattern
matrix produces a visibly different gradient; that was the wave-1470 bug this
file pins (see ``CHANGES.md``).

Method mirrors ``test_pattern_render_oracle.py`` (probe
``oracle/probes/RenderProbe.java``): exact rendered dimensions plus a 16x16
luminance grid compared by mean-absolute cell diff (MAD) and worst-cell diff
(MAXDIFF), under wave 1408's whole-page gate ``MAD < 6.0`` / ``MAXDIFF < 60``.
A *matrix-ignored* guard renders each matrix fixture's gradient at identity and
confirms it scores materially worse against the real (matrix-honouring) PDFBox
reference, so the gate would catch a "/Matrix silently dropped" regression.
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
from pypdfbox.pdmodel.graphics.pattern import PDShadingPattern
from pypdfbox.pdmodel.graphics.shading import PDShadingType2
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_PAGE = 120.0  # square page; fill region is the inner 100x100 box at (10, 10).


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


def _axial_pattern(
    coords: tuple[float, float, float, float],
    c0: list[float],
    c1: list[float],
    matrix: list[float] | None,
) -> PDShadingPattern:
    """A PatternType-2 shading pattern over a Type-2 axial shading."""
    shading = PDShadingType2()
    shading.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    coords_arr = COSArray()
    for v in coords:
        coords_arr.add(COSFloat(v))
    shading.set_coords(coords_arr)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    shading.set_domain(domain)
    shading.set_function(_exp_function(c0, c1))
    extend = COSArray()
    extend.add(COSBoolean.get(True))
    extend.add(COSBoolean.get(True))
    shading.set_extend(extend)
    sp = PDShadingPattern()
    sp.set_shading(shading)
    if matrix is not None:
        sp.set_matrix(matrix)
    return sp


def _with_pattern(
    out: Path, pattern: PDShadingPattern, content: bytes
) -> Path:
    doc, page = _new_doc()
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pattern.get_cos_object(),
    )
    return _save(doc, page, content, out)


def _build_nonrect(out: Path) -> Path:
    """(a) Axial shading pattern filling a non-rectangular (triangle) path."""
    pattern = _axial_pattern(
        (10.0, 0.0, 110.0, 0.0), [0.0, 0.0, 1.0], [1.0, 1.0, 0.0], None
    )
    # A triangle: (10,10) -> (110,10) -> (60,110), filled with the pattern.
    content = (
        b"/Pattern cs /P0 scn\n"
        b"10 10 m 110 10 l 60 110 l h f\n"
    )
    return _with_pattern(out, pattern, content)


def _build_matrix(out: Path) -> Path:
    """(b) Axial shading pattern with a 1.6x scale + (20, 15) translate
    ``/Matrix``. The axis is given in pattern space and the matrix maps it
    into page space, so the gradient is stretched and shifted."""
    pattern = _axial_pattern(
        (0.0, 0.0, 60.0, 0.0), [0.0, 0.0, 1.0], [1.0, 1.0, 0.0],
        [1.6, 0.0, 0.0, 1.6, 20.0, 15.0],
    )
    return _with_pattern(
        out, pattern, b"/Pattern cs /P0 scn 10 10 100 100 re f\n"
    )


def _build_matrix_rotate(out: Path) -> Path:
    """(c) Axial shading pattern whose ``/Matrix`` rotates the axis ~30deg so
    the off-diagonal terms matter, plus a translate to keep it on the page."""
    import math

    c, s = math.cos(math.radians(30.0)), math.sin(math.radians(30.0))
    pattern = _axial_pattern(
        (0.0, 0.0, 100.0, 0.0), [1.0, 0.0, 0.0], [0.0, 1.0, 1.0],
        [c, s, -s, c, 20.0, 10.0],
    )
    return _with_pattern(
        out, pattern, b"/Pattern cs /P0 scn 10 10 100 100 re f\n"
    )


_BUILDERS = {
    "shading_nonrect": _build_nonrect,
    "shading_matrix": _build_matrix,
    "shading_matrix_rotate": _build_matrix_rotate,
}

# Identity-matrix variants of the matrix fixtures — the render a renderer that
# *ignored* the pattern /Matrix would produce. Used by the guard test.
_IDENTITY_VARIANTS = {
    "shading_matrix": lambda out: _with_pattern(
        out,
        _axial_pattern(
            (0.0, 0.0, 60.0, 0.0), [0.0, 0.0, 1.0], [1.0, 1.0, 0.0], None
        ),
        b"/Pattern cs /P0 scn 10 10 100 100 re f\n",
    ),
    "shading_matrix_rotate": lambda out: _with_pattern(
        out,
        _axial_pattern(
            (0.0, 0.0, 100.0, 0.0), [1.0, 0.0, 0.0], [0.0, 1.0, 1.0], None
        ),
        b"/Pattern cs /P0 scn 10 10 100 100 re f\n",
    ),
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


def _render_grid(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    return img.size, _grid_from_image(img)


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_shading_pattern_fill_matches_pdfbox(
    label: str, tmp_path: Path
) -> None:
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
    (java_w, java_h), java_grid = _oracle_signature(fixture)

    (py_w, py_h), py_grid = _render_grid(fixture)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — shading pattern fill grossly divergent"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize(
    "label", list(_IDENTITY_VARIANTS), ids=list(_IDENTITY_VARIANTS)
)
def test_matrix_ignored_fails_pattern_tolerance(
    label: str, tmp_path: Path
) -> None:
    """Guard the gate: rendering the gradient with the pattern ``/Matrix``
    dropped (identity) scores far outside tolerance against the real
    matrix-honouring PDFBox reference. Proves the gate would catch a
    "/Matrix silently ignored" regression in the shading-pattern fill."""
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
    _dims, java_grid = _oracle_signature(fixture)

    ident = _IDENTITY_VARIANTS[label](tmp_path / f"{label}_identity.pdf")
    _ident_dims, ident_grid = _render_grid(ident)

    mad, _maxdiff = _mad_maxdiff(java_grid, ident_grid)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: tolerance too loose — an identity-matrix gradient is "
        f"within the MAD gate of the matrix reference (mad={mad:.2f}); the "
        f"gate would not catch a /Matrix-ignored regression"
    )
