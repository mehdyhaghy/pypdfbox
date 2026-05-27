"""Live PDFBox differential parity for Type 1 (function-based) shading.

Companion to ``test_mesh_shading_oracle.py`` (Types 4-7) and
``test_shading_extend_oracle.py`` (axial / radial extend). This module
covers the one remaining shading family: **Type 1 — function-based**
(PDF 32000-1 §8.7.4.5.2).

A ``/ShadingType 1`` shading colours each point ``(x, y)`` of its
``/Domain`` rectangle by evaluating a 2-input / N-output ``/Function``
after the optional ``/Matrix`` maps the domain into pattern user space.
It is painted by the ``sh`` operator inside a clip. The per-pixel function
evaluation plus the domain / matrix coordinate mapping is what we pin
against Apache PDFBox here.

Two fixtures, each a 100x100 page carrying one Type 1 shading whose
``/Function`` is a Type 4 PostScript calculator producing a radial-ish RGB
field ``f(x, y) = (d, 1-d, 0)`` where ``d = sqrt(x^2 + y^2)`` over the unit
domain ``[0 1 0 1]``:

* **identity_matrix** — no ``/Matrix``; the content stream applies
  ``100 0 0 100 0 0 cm`` so the unit domain spans the page. Exercises the
  domain→device mapping through the CTM only.
* **scale_matrix** — a non-identity shading ``/Matrix [100 0 0 100 0 0]``
  maps the unit domain onto the page directly (no ``cm``). Exercises the
  shading-matrix inversion path. Renders identically to the first case,
  which is the point: ``/Matrix`` must be honoured, not ignored.

Each fixture is rendered through Apache PDFBox (``oracle/probes/
RenderProbe.java``) and through pypdfbox at 72 DPI, then compared on the
shared render fingerprint:

* **Exact page dimensions** — a mismatch is a real bug (scale / media-box).
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared
  by mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF).

Measured against PDFBox 3.0.7 both cases land at MAD ~0.3 / MAXDIFF ~1 —
the two engines evaluate the calculator + domain mapping identically; the
residual is anti-aliasing on the curved colour bands.

The whole-page render gate ``MAD < 6`` / ``MAXDIFF < 60`` applies. The
guard test proves a *solid* fill of the same box at the field's mean
luminance (the failure mode if the function is never evaluated — flat
colour, no per-pixel gradient) scores MAD ~15, well outside tolerance, so
the gate genuinely discriminates an evaluated gradient from a flat fill.
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
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60
_PAGE = 100.0

# Type 4 PostScript calculator, 2-in -> 3-out. Stack on entry: x y.
#   dup mul       -> x (y*y)
#   exch dup mul  -> (y*y) (x*x)
#   add sqrt      -> d = sqrt(x^2 + y^2)
#   dup 1 exch sub 0 -> d (1-d) 0
# Emits the RGB triple (d, 1-d, 0); d is clamped into /Range [0,1].
_PS_FUNCTION = b"{ dup mul exch dup mul add sqrt dup 1 exch sub 0 }"


def _floats(*vals: float) -> COSArray:
    arr = COSArray()
    for v in vals:
        arr.add(COSFloat(v))
    return arr


def _new_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    return doc, page


def _type4_function() -> COSStream:
    fn = COSStream()
    fn.set_int(COSName.get_pdf_name("FunctionType"), 4)
    fn.set_item(COSName.get_pdf_name("Domain"), _floats(0, 1, 0, 1))
    fn.set_item(COSName.get_pdf_name("Range"), _floats(0, 1, 0, 1, 0, 1))
    fn.set_raw_data(_PS_FUNCTION)
    return fn


def _base_shading(matrix: COSArray | None) -> COSStream:
    sh = COSStream()
    sh.set_int(COSName.get_pdf_name("ShadingType"), 1)
    sh.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    sh.set_item(COSName.get_pdf_name("Domain"), _floats(0, 1, 0, 1))
    if matrix is not None:
        sh.set_item(COSName.get_pdf_name("Matrix"), matrix)
    sh.set_item(COSName.get_pdf_name("Function"), _type4_function())
    return sh


def _save(doc: PDDocument, page: PDPage, sh: COSStream, content: bytes, out: Path) -> Path:
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"), COSName.get_pdf_name("Sh0"), sh
    )
    contents = COSStream()
    contents.set_raw_data(content)
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    doc.save(str(out))
    doc.close()
    return out


def _build_identity_matrix(out: Path) -> Path:
    """No /Matrix; the content stream's ``cm`` scales the unit domain onto
    the clipped 100x100 box."""
    doc, page = _new_doc()
    sh = _base_shading(matrix=None)
    content = b"q 0 0 100 100 re W n 100 0 0 100 0 0 cm /Sh0 sh Q\n"
    return _save(doc, page, sh, content, out)


def _build_scale_matrix(out: Path) -> Path:
    """Non-identity shading /Matrix [100 0 0 100 0 0] maps the unit domain
    onto the page; no ``cm`` in the content stream. Must render the same as
    the identity case (the /Matrix is what does the scaling)."""
    doc, page = _new_doc()
    sh = _base_shading(matrix=_floats(100, 0, 0, 100, 0, 0))
    content = b"q 0 0 100 100 re W n /Sh0 sh Q\n"
    return _save(doc, page, sh, content, out)


_BUILDERS = {
    "identity_matrix": _build_identity_matrix,
    "scale_matrix": _build_scale_matrix,
}


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


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_function_shading_matches_pdfbox(label: str, tmp_path: Path) -> None:
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

    # (b) Perceptual grid parity — catches a blank region (shading dropped),
    #     a flat fill (function not evaluated), domain mapping wrong, or a
    #     /Matrix that was ignored (the scale_matrix case would diverge).
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — function-based field grossly divergent "
        f"(blank / flat / wrong domain / ignored matrix)"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_solid_fill_would_fail_tolerance(label: str, tmp_path: Path) -> None:
    """Guard the gate: a solid mid-grey fill of the box (the failure mode if
    the function is never evaluated — flat colour, no per-pixel gradient) is
    far outside tolerance versus PDFBox's actual function-based render. Proves
    the MAD gate discriminates an evaluated gradient from a flat fill."""
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
    _dims, java_grid = _oracle_signature(fixture)
    # The mean luminance of the function field; a solid fill at that value is
    # the strongest possible flat impostor and still fails the gate.
    mean_lum = round(sum(java_grid) / len(java_grid))
    solid = [mean_lum] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, solid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: tolerance too loose — a solid fill at the field mean "
        f"({mean_lum}) passes the MAD gate ({mad:.2f})"
    )
