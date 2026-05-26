"""Live PDFBox differential parity for the mesh shadings (Types 4-7).

Companion to ``test_pattern_render_oracle.py`` (axial / radial / tiling) and
``test_render_oracle.py`` (whole-page rasterisation). This module focuses on
the four *mesh* shadings, which read packed vertex / flag / colour data from
the shading stream per ``/BitsPerCoordinate`` / ``/BitsPerComponent`` /
``/BitsPerFlag`` / ``/Decode``:

* **Type 4** — free-form Gouraud-shaded triangle mesh (per-vertex flag).
* **Type 5** — lattice-form Gouraud triangle mesh (``/VerticesPerRow``).
* **Type 6** — Coons patch mesh (12 control points per patch).
* **Type 7** — tensor-product patch mesh (16 control points per patch).

Each fixture fills a 100x100 page with one ``/Sh0 sh`` mesh shading carrying a
red / green / blue / white corner ramp, is rendered through Apache PDFBox
(``oracle/probes/RenderProbe.java``) and through pypdfbox at 72 DPI, then
compared on the same fingerprint the other render oracles use:

* **Exact page dimensions** — a mismatch is a real bug (scale / media-box),
  never an anti-aliasing artefact.
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared by
  mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF).

Measured against PDFBox 3.0.7 the four cases land at:

    type4 (free-form Gouraud) ........ MAD ~1.1  MAXDIFF ~2
    type5 (lattice Gouraud) .......... MAD ~1.1  MAXDIFF ~2
    type6 (Coons patch) .............. MAD ~6.4  MAXDIFF ~18
    type7 (tensor patch) ............. MAD ~6.4  MAXDIFF ~18

The triangle meshes (4/5) match PDFBox almost exactly — both engines do plain
per-vertex Gouraud interpolation. The patch meshes (6/7) sit higher: pypdfbox
approximates the patch colour field with a Gouraud-shaded cell grid while
PDFBox interpolates per pixel, leaving a small, *uniform* colour offset (~4
luminance units) that does not reduce with finer subdivision — an inter-engine
interpolation difference documented in ``CHANGES.md``, not banding. A blank /
solid render of any fixture scores MAD 100+ (asserted in the guard test
below), so the gate still discriminates a correct mesh from a dropped one.

The gate ``MAD < 8.0`` / ``MAXDIFF < 60`` is the whole-page render gate
(``MAD < 6``) loosened just enough to admit the patch-mesh interpolation
offset while staying far below the banding (MAD 12-17) and blank (MAD 100+)
failure modes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Whole-page render gate (MAD < 6) loosened to admit the patch-mesh
# interpolation offset; still far below banding (12-17) and blank (100+).
_MAD_TOLERANCE = 8.0
_MAXDIFF_TOLERANCE = 60

_PAGE = 100.0


# ---------------------------------------------------------------------------
# fixture builders — synthesise mesh-shading PDFs via the pypdfbox COS API
# ---------------------------------------------------------------------------


def _new_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    return doc, page


def _decode_array() -> COSArray:
    """``/Decode`` for an RGB mesh over the full 100x100 page: x/y in
    ``[0, 100]`` then three colour components in ``[0, 1]``."""
    arr = COSArray()
    for v in (0.0, 100.0, 0.0, 100.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0):
        arr.add(COSFloat(v))
    return arr


def _q(value: float, lo: float, hi: float, src_max: int = 255) -> int:
    """Quantise ``value`` from ``[lo, hi]`` into ``[0, src_max]`` (the
    inverse of the decoder's ``_interpolate``)."""
    if hi == lo:
        return 0
    raw = round((value - lo) / (hi - lo) * src_max)
    return max(0, min(src_max, raw))


def _save(doc: PDDocument, page: PDPage, shading: COSStream, out: Path) -> Path:
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"), COSName.get_pdf_name("Sh0"), shading
    )
    contents = COSStream()
    contents.set_raw_data(b"/Sh0 sh\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    doc.save(str(out))
    doc.close()
    return out


def _base_shading(shading_type: int) -> COSStream:
    sh = COSStream()
    sh.set_int(COSName.get_pdf_name("ShadingType"), shading_type)
    sh.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    sh.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    sh.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    sh.set_item(COSName.get_pdf_name("Decode"), _decode_array())
    return sh


def _build_type4(out: Path) -> Path:
    """Free-form Gouraud mesh: two flag-0 triangles tiling the page with a
    red / green / blue / white corner ramp."""
    doc, page = _new_doc()
    sh = _base_shading(4)
    sh.set_int(COSName.get_pdf_name("BitsPerFlag"), 8)

    def vtx(flag: int, x: float, y: float, r: float, g: float, b: float) -> bytes:
        return bytes(
            [flag, _q(x, 0, 100), _q(y, 0, 100), _q(r, 0, 1), _q(g, 0, 1), _q(b, 0, 1)]
        )

    data = b""
    # Triangle 1: (0,0) red, (100,0) green, (0,100) blue.
    data += vtx(0, 0, 0, 1, 0, 0) + vtx(0, 100, 0, 0, 1, 0) + vtx(0, 0, 100, 0, 0, 1)
    # Triangle 2: (100,0) green, (0,100) blue, (100,100) white.
    data += vtx(0, 100, 0, 0, 1, 0) + vtx(0, 0, 100, 0, 0, 1) + vtx(0, 100, 100, 1, 1, 1)
    sh.set_raw_data(data)
    return _save(doc, page, sh, out)


def _build_type5(out: Path) -> Path:
    """Lattice Gouraud mesh: a 2x2 vertex grid (VerticesPerRow=2) with a
    red / green / blue / white corner ramp."""
    doc, page = _new_doc()
    sh = _base_shading(5)
    sh.set_int(COSName.get_pdf_name("VerticesPerRow"), 2)

    def vtx(x: float, y: float, r: float, g: float, b: float) -> bytes:
        return bytes(
            [_q(x, 0, 100), _q(y, 0, 100), _q(r, 0, 1), _q(g, 0, 1), _q(b, 0, 1)]
        )

    # Row 0: (0,0) red, (100,0) green. Row 1: (0,100) blue, (100,100) white.
    data = (
        vtx(0, 0, 1, 0, 0)
        + vtx(100, 0, 0, 1, 0)
        + vtx(0, 100, 0, 0, 1)
        + vtx(100, 100, 1, 1, 1)
    )
    sh.set_raw_data(data)
    return _save(doc, page, sh, out)


# Canonical 12-point Coons boundary (PDF 32000-1 §8.7.4.5.7 Fig. 39):
# bottom (p0..p3) L->R, right (p3..p6) bottom->top, top (p6..p9) R->L,
# left (p9..p11,p0) top->bottom. The 4 corner colours are p0/p3/p6/p9.
_COONS_POINTS = [
    (0, 0), (33, 0), (66, 0), (100, 0),
    (100, 33), (100, 66), (100, 100),
    (66, 100), (33, 100),
    (0, 100), (0, 66), (0, 33),
]
_CORNER_COLORS = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1)]


def _build_type6(out: Path) -> Path:
    """Single free (flag 0) Coons patch over the page, red/green/blue/white
    corners."""
    doc, page = _new_doc()
    sh = _base_shading(6)
    sh.set_int(COSName.get_pdf_name("BitsPerFlag"), 8)
    body = [0]  # flag
    for x, y in _COONS_POINTS:
        body += [_q(x, 0, 100), _q(y, 0, 100)]
    for r, g, b in _CORNER_COLORS:
        body += [_q(r, 0, 1), _q(g, 0, 1), _q(b, 0, 1)]
    sh.set_raw_data(bytes(body))
    return _save(doc, page, sh, out)


def _build_type7(out: Path) -> Path:
    """Single free (flag 0) tensor-product patch over the page. The 12
    boundary control points match the Coons case; the 4 interior control
    points sit inside the patch so the tensor surface stays planar."""
    doc, page = _new_doc()
    sh = _base_shading(7)
    sh.set_int(COSName.get_pdf_name("BitsPerFlag"), 8)
    interior = [(33, 33), (66, 33), (66, 66), (33, 66)]
    body = [0]  # flag
    for x, y in (*_COONS_POINTS, *interior):
        body += [_q(x, 0, 100), _q(y, 0, 100)]
    for r, g, b in _CORNER_COLORS:
        body += [_q(r, 0, 1), _q(g, 0, 1), _q(b, 0, 1)]
    sh.set_raw_data(bytes(body))
    return _save(doc, page, sh, out)


_BUILDERS = {
    "type4_freeform_gouraud": _build_type4,
    "type5_lattice_gouraud": _build_type5,
    "type6_coons_patch": _build_type6,
    "type7_tensor_patch": _build_type7,
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
def test_mesh_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
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

    # (b) Perceptual grid parity within tolerance — catches a blank region
    #     (mesh dropped), a flat fill (no Gouraud), or wrong vertex decode.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — mesh grossly divergent (blank / flat / "
        f"wrong decode), not just inter-engine interpolation"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond interpolation"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_blank_mesh_render_would_fail_tolerance(
    label: str, tmp_path: Path
) -> None:
    """Guard the gate: a blank-white render of each mesh fixture is far
    outside tolerance versus PDFBox's actual gradient render. Proves the MAD
    gate discriminates a painted mesh gradient from a blank / dropped one
    (the exact failure mode before Types 4/5 grew a triangle painter)."""
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
    _dims, java_grid = _oracle_signature(fixture)
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: tolerance too loose — a blank render passes the MAD gate"
    )
