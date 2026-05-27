"""Live PDFBox differential parity for axial/radial shading edge cases.

Companion to ``test_pattern_render_oracle.py`` (axial / radial *basics*) and
``test_mesh_shading_oracle.py`` (mesh shadings). This module pins the
**``/Extend`` / ``/Domain`` / degenerate-geometry** edge of the Type 2 (axial)
and Type 3 (radial) shading paint path in ``pypdfbox.rendering`` against
Apache PDFBox 3.0.7:

* **axial ``/Extend``** — ``[true true]`` paints the beyond-axis region with
  the endpoint colours; ``[false false]`` leaves it unpainted (page white).
  Both fixtures clip the ``sh`` to the full page so the region *past* the axis
  endpoints is visible — that is exactly where the two cases must diverge.
* **axial ``/Domain [0.2 0.8]``** — the gradient is sampled only over the
  inner 60% of the colour function; the axis-position→domain remap must match.
* **radial nested circles + ``/Extend [true true]``** — a small start circle
  inside a large end circle gives the classic *cone* fill; extend paints the
  cone's interior (start colour) and exterior (end colour).
* **radial zero-radius start circle** — ``r0 == 0`` (a point) growing to a
  disc; the quadratic-root / radius-non-negative branch must pick the right
  root so the centre is the start colour.

Each fixture fills a 100x100 page with one ``/Sh0 sh`` shading, is rendered
through Apache PDFBox (``oracle/probes/RenderProbe.java``) and through pypdfbox
at 72 DPI, then compared on the render oracle's fingerprint:

* **Exact page dimensions** — a mismatch is a real bug (scale / media-box),
  never an anti-aliasing artefact.
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared by
  mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF).

The gate is the whole-page render gate ``MAD < 6`` / ``MAXDIFF < 60``. A
dedicated guard (``test_extend_false_differs_from_true``) asserts the
``[false false]`` axial render differs *materially* from ``[true true]`` —
proving extend is honoured per-flag, not always-extended or never-extended.
A documented benign source of sub-tolerance diff is gradient sampling: pypdfbox
lerps a 256-entry pre-evaluated colour ramp where PDFBox evaluates a per-axis
colour table, leaving a small uniform offset on smooth gradients.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.shading import PDShadingType2, PDShadingType3
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_PAGE = 100.0


# ---------------------------------------------------------------------------
# fixture builders — synthesise shading PDFs via the pypdfbox API
# ---------------------------------------------------------------------------


def _new_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    return doc, page


def _coords(*vals: float) -> COSArray:
    arr = COSArray()
    for v in vals:
        arr.add(COSFloat(v))
    return arr


def _exp_function(c0: list[float], c1: list[float], n: float = 1.0) -> COSStream:
    """Minimal Type 2 (exponential interpolation) function over [0, 1]."""
    fn = COSStream()
    fn.set_int(COSName.get_pdf_name("FunctionType"), 2)
    fn.set_item(COSName.get_pdf_name("Domain"), _coords(0.0, 1.0))
    a0 = COSArray()
    for v in c0:
        a0.add(COSFloat(v))
    fn.set_item(COSName.get_pdf_name("C0"), a0)
    a1 = COSArray()
    for v in c1:
        a1.add(COSFloat(v))
    fn.set_item(COSName.get_pdf_name("C1"), a1)
    fn.set_int(COSName.get_pdf_name("N"), int(n) if n == int(n) else n)
    return fn


def _save(doc: PDDocument, page: PDPage, shading: PDShadingType2 | PDShadingType3,
          content: bytes, out: Path) -> Path:
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"),
        COSName.get_pdf_name("Sh0"),
        shading.get_cos_object(),
    )
    stream = COSStream()
    stream.set_raw_data(content)
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


def _build_axial(out: Path, *, extend: tuple[bool, bool]) -> Path:
    """Axial gradient on a *short* horizontal axis (x 30..70) over the full
    100x100 page. Beyond the axis (x<30 / x>70) ``/Extend`` decides whether the
    endpoint colour is painted (true) or the region stays page-white (false).
    Blue (C0) -> yellow (C1)."""
    doc, page = _new_doc()
    sh = PDShadingType2()
    sh.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    sh.set_coords(_coords(30.0, 0.0, 70.0, 0.0))
    sh.set_domain(_coords(0.0, 1.0))
    sh.set_function(_exp_function([0.0, 0.0, 1.0], [1.0, 1.0, 0.0]))
    sh.set_extend(extend[0], extend[1])
    # Clip to the full page so the beyond-axis region is visible.
    return _save(doc, page, sh, b"0 0 100 100 re W n /Sh0 sh\n", out)


def _build_axial_extend_true(out: Path) -> Path:
    return _build_axial(out, extend=(True, True))


def _build_axial_extend_false(out: Path) -> Path:
    return _build_axial(out, extend=(False, False))


def _build_axial_domain(out: Path) -> Path:
    """Axial gradient over a long axis with ``/Domain [0.2 0.8]`` — only the
    inner 60% of the colour function is sampled. Extend true so the whole page
    is painted; the remap of axis-position -> domain must match PDFBox."""
    doc, page = _new_doc()
    sh = PDShadingType2()
    sh.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    sh.set_coords(_coords(10.0, 0.0, 90.0, 0.0))
    sh.set_domain(_coords(0.2, 0.8))
    sh.set_function(_exp_function([0.0, 0.0, 1.0], [1.0, 1.0, 0.0]))
    sh.set_extend(True, True)
    return _save(doc, page, sh, b"0 0 100 100 re W n /Sh0 sh\n", out)


def _build_radial_cone(out: Path) -> Path:
    """Radial gradient: a small start circle (r0=10) nested inside a large end
    circle (r1=60), both roughly centred. Extend [true true] -> a cone fill
    where the inner disc is the start colour and the outer ring the end
    colour. Yellow (C0) -> red (C1)."""
    doc, page = _new_doc()
    sh = PDShadingType3()
    sh.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    sh.set_coords(_coords(50.0, 50.0, 10.0, 50.0, 50.0, 60.0))
    sh.set_domain([0.0, 1.0])
    sh.set_function(_exp_function([1.0, 1.0, 0.0], [1.0, 0.0, 0.0]))
    sh.set_extend(True, True)
    return _save(doc, page, sh, b"0 0 100 100 re W n /Sh0 sh\n", out)


def _build_radial_zero_start(out: Path) -> Path:
    """Radial gradient with a zero-radius start circle (r0=0) — a point at the
    centre growing to a disc (r1=50). Extend [false true]. The centre must be
    the start colour. White (C0) -> blue (C1)."""
    doc, page = _new_doc()
    sh = PDShadingType3()
    sh.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    sh.set_coords(_coords(50.0, 50.0, 0.0, 50.0, 50.0, 50.0))
    sh.set_domain([0.0, 1.0])
    sh.set_function(_exp_function([1.0, 1.0, 1.0], [0.0, 0.0, 1.0]))
    sh.set_extend(False, True)
    return _save(doc, page, sh, b"0 0 100 100 re W n /Sh0 sh\n", out)


_BUILDERS = {
    "axial_extend_true": _build_axial_extend_true,
    "axial_extend_false": _build_axial_extend_false,
    "axial_domain_0208": _build_axial_domain,
    "radial_cone_nested": _build_radial_cone,
    "radial_zero_start": _build_radial_zero_start,
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


def _pypdfbox_grid(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    return img.size, _grid_from_image(img)


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_shading_edge_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
    (java_w, java_h), java_grid = _oracle_signature(fixture)
    (py_w, py_h), py_grid = _pypdfbox_grid(fixture)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity — catches extend ignored (always / never),
    #     a wrong domain remap, or wrong radial cone/cylinder geometry.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — shading region grossly divergent (extend "
        f"ignored / wrong domain / wrong geometry), not just AA / sampling"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond AA / sampling"
    )


@requires_oracle
def test_extend_false_differs_from_true(tmp_path: Path) -> None:
    """Guard: ``/Extend [false false]`` must differ *materially* from
    ``[true true]`` on the same short-axis axial gradient. This proves extend
    is honoured per-flag — a renderer that always-extends (or never-extends)
    would produce near-identical grids for the two cases and fail this gate.
    The two cases differ only in the beyond-axis regions (x<30 / x>70), which
    is roughly the outer ~40% of the page width, so the MAD between them is
    large."""
    true_fix = _build_axial_extend_true(tmp_path / "true.pdf")
    false_fix = _build_axial_extend_false(tmp_path / "false.pdf")
    _t_dims, true_grid = _pypdfbox_grid(true_fix)
    _f_dims, false_grid = _pypdfbox_grid(false_fix)
    diffs = [abs(a - b) for a, b in zip(true_grid, false_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad > 10.0, (
        f"extend [false false] vs [true true] differ by only MAD {mad:.2f} — "
        f"extend appears ignored (always-extend or never-extend)"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_blank_shading_render_would_fail_tolerance(
    label: str, tmp_path: Path
) -> None:
    """Guard the gate: a blank-white render of each painted fixture is far
    outside tolerance versus PDFBox's actual render — so the MAD gate
    discriminates a correct shading from a blank / dropped one. The
    ``extend_false`` fixture deliberately leaves the beyond-axis region white,
    so a smaller (but still > gate) divergence is expected there."""
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
    _dims, java_grid = _oracle_signature(fixture)
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: tolerance too loose — a blank render passes the MAD gate"
    )
