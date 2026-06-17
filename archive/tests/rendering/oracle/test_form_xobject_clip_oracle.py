"""Live PDFBox differential parity for form XObject ``/BBox`` clipping + ``/Matrix``.

When a form XObject is painted via ``Do`` the renderer must (PDF 32000-1
§8.10.1):

1. concatenate the form's ``/Matrix`` onto the CTM, then
2. clip to the form's ``/BBox`` (transformed by that matrix) — content the
   form draws *outside* the BBox must not paint.

Nested form XObjects compound this: the outer form's BBox clip stays active
while the inner form is processed, so the inner form's paint is doubly
clipped (outer BBox ∩ inner BBox).

This file renders small PDFs through Apache PDFBox 3.0.7 (via
``oracle/probes/RenderProbe.java``) and through pypdfbox's
:class:`PDFRenderer`, comparing the coarse 16x16 average-luminance
fingerprint. pypdfbox rasterises with skia-python while PDFBox uses
Java2D/AWT, so anti-aliasing differs at the sub-pixel level; the fingerprint
survives AA but catches the gross failures this surface is prone to:

* a ``/BBox`` clip that is ignored lets the form's oversized fill bleed into
  cells PDFBox leaves white;
* a ``/Matrix`` that is *not* concatenated renders the form's content at the
  wrong position / scale (and clips the wrong region);
* a nested ``/BBox`` clip that isn't compounded paints the inner form's
  overflow that the outer BBox should have removed.

Cases (all built in-process, 200x200pt page, rendered at 72 DPI):

(a) ``bbox_clip``   — a form whose content fills the whole page but whose
    ``/BBox`` is a centred 50..150 square; only that square may paint.
(b) ``matrix_bbox`` — a form with a scale(0.5)+translate ``/Matrix`` and a
    full-form-space ``/BBox``; the clip must follow the *transformed* BBox,
    so the painted region is the lower-left quadrant.
(c) ``nested``      — an inner form (oversized fill, big BBox) painted inside
    an outer form whose ``/BBox`` is a centred square; the outer BBox clips
    the inner overflow.

Tolerance mirrors ``test_clipping_oracle.py``: gate at ``MAD < 6.0`` and
``MAXDIFF < 60`` — above the AA ceiling, well below any clip/matrix failure
floor. Three guard tests confirm the gate discriminates: an *un-clipped*
(oversized-BBox) form, a form with the ``/Matrix`` dropped, and a nested form
whose outer BBox is oversized — each scores far over the gate against the
correctly-clipped PDFBox reference.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60
_PAGE = 200.0

# A form whose content fills a region far larger than any sane /BBox: paint
# the whole 0..200 page black. Whatever shows is purely the BBox clip's doing.
_FULL_FILL = b"0 0 0 rg\n0 0 200 200 re\nf\n"


# --------------------------------------------------------------------------
# fingerprint helpers (must match RenderProbe.java's cell mapping exactly)
# --------------------------------------------------------------------------


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
        round(total[i] / count[i]) if count[i] else 255 for i in range(_GRID * _GRID)
    ]


def _oracle_signature(pdf: Path) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text("RenderProbe", str(pdf), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _diff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


def _render_py(pdf: Path) -> Image.Image:
    with PDDocument.load(pdf) as doc:
        return PDFRenderer(doc).render_image_with_dpi(0, 72.0)


# --------------------------------------------------------------------------
# PDF builders
# --------------------------------------------------------------------------


def _make_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    return doc, page


def _matrix_array(values: tuple[float, float, float, float, float, float]) -> COSArray:
    arr = COSArray()
    for v in values:
        arr.add(COSFloat(v))
    return arr


def _make_form(
    content: bytes,
    bbox: tuple[float, float, float, float],
    matrix: tuple[float, float, float, float, float, float] | None = None,
    resources: PDResources | None = None,
) -> PDFormXObject:
    stream = COSStream()
    stream.set_raw_data(content)
    form = PDFormXObject(stream)
    form.set_b_box(PDRectangle(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]))
    if matrix is not None:
        form.get_cos_object().set_item(
            COSName.get_pdf_name("Matrix"), _matrix_array(matrix)
        )
    if resources is not None:
        form.set_resources(resources)
    return form


def _save_with_form(
    path: Path, page: PDPage, doc: PDDocument, form: PDFormXObject, page_ops: bytes
) -> None:
    resources = PDResources()
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Fm0"),
        form.get_cos_object(),
    )
    page.set_resources(resources)
    contents = COSStream()
    contents.set_raw_data(page_ops)
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    doc.save(str(path))
    doc.close()


# (a) BBox clip — content fills the page, BBox is a centred 50..150 square.
def _build_bbox_clip(path: Path) -> None:
    doc, page = _make_doc()
    form = _make_form(_FULL_FILL, bbox=(50.0, 50.0, 150.0, 150.0))
    _save_with_form(path, page, doc, form, b"/Fm0 Do\n")


# Guard (a): the same form but with an oversized /BBox (0..200) — the
# oversized fill bleeds across the whole page, no clip removes it.
def _build_bbox_noclip(path: Path) -> None:
    doc, page = _make_doc()
    form = _make_form(_FULL_FILL, bbox=(0.0, 0.0, 200.0, 200.0))
    _save_with_form(path, page, doc, form, b"/Fm0 Do\n")


# (b) Matrix + BBox — scale 0.5 + no translate. The form draws a full-form-
# space fill (0..200) and the BBox is the full form space (0..200); after the
# 0.5 scale the painted+clipped region is the lower-left 0..100 quadrant.
_MATRIX_HALF = (0.5, 0.0, 0.0, 0.5, 0.0, 0.0)


def _build_matrix_bbox(path: Path) -> None:
    doc, page = _make_doc()
    form = _make_form(
        _FULL_FILL, bbox=(0.0, 0.0, 200.0, 200.0), matrix=_MATRIX_HALF
    )
    _save_with_form(path, page, doc, form, b"/Fm0 Do\n")


# Guard (b): identical form + BBox but with the /Matrix dropped — the form
# paints at full scale across the whole page instead of the lower-left
# quadrant.
def _build_matrix_dropped(path: Path) -> None:
    doc, page = _make_doc()
    form = _make_form(_FULL_FILL, bbox=(0.0, 0.0, 200.0, 200.0))
    _save_with_form(path, page, doc, form, b"/Fm0 Do\n")


# (c) Nested — an inner form (oversized fill, big BBox) painted inside an
# outer form whose /BBox is the centred 50..150 square. The outer BBox must
# clip the inner form's overflow.
def _build_nested(path: Path) -> None:
    doc, page = _make_doc()
    inner = _make_form(_FULL_FILL, bbox=(0.0, 0.0, 200.0, 200.0))
    inner_res = PDResources()
    inner_res.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Inner"),
        inner.get_cos_object(),
    )
    outer = _make_form(
        b"/Inner Do\n",
        bbox=(50.0, 50.0, 150.0, 150.0),
        resources=inner_res,
    )
    _save_with_form(path, page, doc, outer, b"/Fm0 Do\n")


# Guard (c): same nesting but the *outer* form's /BBox is oversized (0..200) —
# the inner overflow is no longer clipped to the centred square.
def _build_nested_noclip(path: Path) -> None:
    doc, page = _make_doc()
    inner = _make_form(_FULL_FILL, bbox=(0.0, 0.0, 200.0, 200.0))
    inner_res = PDResources()
    inner_res.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Inner"),
        inner.get_cos_object(),
    )
    outer = _make_form(
        b"/Inner Do\n",
        bbox=(0.0, 0.0, 200.0, 200.0),
        resources=inner_res,
    )
    _save_with_form(path, page, doc, outer, b"/Fm0 Do\n")


_BUILDERS = {
    "bbox_clip": _build_bbox_clip,
    "matrix_bbox": _build_matrix_bbox,
    "nested": _build_nested,
}


# --------------------------------------------------------------------------
# differential tests
# --------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_form_xobject_bbox_matrix_match_pdfbox(label: str, tmp_path: Path) -> None:
    pdf = tmp_path / f"{label}.pdf"
    _BUILDERS[label](pdf)

    (java_w, java_h), java_grid = _oracle_signature(pdf)
    img = _render_py(pdf)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    mad, maxdiff = _diff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — form BBox/Matrix clip diverges, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_oversized_bbox_blows_past_clip_gate(tmp_path: Path) -> None:
    """Guard: a form with an *oversized* /BBox (the full page) lets its
    oversized fill bleed everywhere, scoring far over the gate against
    PDFBox's correctly BBox-clipped reference. Proves the /BBox clip in
    ``bbox_clip`` is genuinely exercised (a no-op clip would let this pass)."""
    clipped = tmp_path / "bbox_clip.pdf"
    noclip = tmp_path / "bbox_noclip.pdf"
    _build_bbox_clip(clipped)
    _build_bbox_noclip(noclip)

    _dims, java_clipped_grid = _oracle_signature(clipped)
    py_noclip_grid = _grid_from_image(_render_py(noclip))
    mad, maxdiff = _diff(java_clipped_grid, py_noclip_grid)
    assert mad >= _MAD_TOLERANCE and maxdiff >= _MAXDIFF_TOLERANCE, (
        f"BBox-clip gate too loose: an oversized-BBox form passes "
        f"(MAD={mad:.2f}, MAXDIFF={maxdiff})"
    )


@requires_oracle
def test_dropped_matrix_blows_past_gate(tmp_path: Path) -> None:
    """Guard: the same form + BBox with the /Matrix dropped paints at full
    scale across the page instead of the matrix-transformed lower-left
    quadrant, scoring far over the gate against PDFBox's matrix-honouring
    reference. Proves the /Matrix concatenation in ``matrix_bbox`` is
    genuinely exercised."""
    with_matrix = tmp_path / "matrix_bbox.pdf"
    without_matrix = tmp_path / "matrix_dropped.pdf"
    _build_matrix_bbox(with_matrix)
    _build_matrix_dropped(without_matrix)

    _dims, java_matrix_grid = _oracle_signature(with_matrix)
    py_dropped_grid = _grid_from_image(_render_py(without_matrix))
    mad, maxdiff = _diff(java_matrix_grid, py_dropped_grid)
    assert mad >= _MAD_TOLERANCE and maxdiff >= _MAXDIFF_TOLERANCE, (
        f"Matrix gate too loose: a form with the /Matrix dropped passes "
        f"(MAD={mad:.2f}, MAXDIFF={maxdiff})"
    )


@requires_oracle
def test_nested_oversized_outer_bbox_blows_past_gate(tmp_path: Path) -> None:
    """Guard: the nested form with an *oversized* outer /BBox lets the inner
    form's overflow paint everywhere, scoring far over the gate against
    PDFBox's compounded-clip reference. Proves the outer BBox clip in
    ``nested`` genuinely compounds onto the inner form."""
    clipped = tmp_path / "nested.pdf"
    noclip = tmp_path / "nested_noclip.pdf"
    _build_nested(clipped)
    _build_nested_noclip(noclip)

    _dims, java_clipped_grid = _oracle_signature(clipped)
    py_noclip_grid = _grid_from_image(_render_py(noclip))
    mad, maxdiff = _diff(java_clipped_grid, py_noclip_grid)
    assert mad >= _MAD_TOLERANCE and maxdiff >= _MAXDIFF_TOLERANCE, (
        f"Nested-BBox-clip gate too loose: an oversized outer /BBox passes "
        f"(MAD={mad:.2f}, MAXDIFF={maxdiff})"
    )
