"""Live PDFBox differential parity for the annotation appearance → /Rect map.

When a renderer paints an annotation's Normal Appearance (``/AP /N``) form
XObject it must apply the PDF 32000-1 §12.5.5 algorithm (the
``PDFStreamEngine.processAnnotation`` path upstream):

1. transform the appearance ``/BBox`` by the appearance ``/Matrix`` and take
   the axis-aligned bounds of the four transformed corners (the *transformed
   appearance box*);
2. derive an affine matrix ``A`` that maps that transformed box onto the
   annotation ``/Rect`` — translate its lower-left to the rect origin then
   scale-to-fit ``rect.w / tb.w`` × ``rect.h / tb.h``;
3. render the appearance through ``A ∘ Matrix`` (matrix applied first), clipped
   to the raw ``/BBox``.

A non-identity ``/Matrix`` (rotation / scale) makes the transformed box differ
from the raw ``/BBox``; a ``/Rect`` whose size / aspect differs from the
transformed box forces the scale-to-fit. Both must still land the appearance
in the right place, size, and orientation inside ``/Rect``.

This file builds small PDFs in-process via pypdfbox — a ``/Subtype /Stamp``
annotation drawing a recognisable *asymmetric* shape (a filled block hugging
the appearance-space lower-left plus a thin vertical bar up the left edge, so a
flip / wrong rotation / wrong scale is visible in the 16×16 fingerprint) — and
renders each through Apache PDFBox 3.0.7 (``oracle/probes/RenderProbe.java``)
and through pypdfbox's :class:`PDFRenderer`, comparing the coarse 16×16
average-luminance grid.

Cases (all on a 200×200pt page, rendered at 72 DPI):

(a) ``identity``   — ``/Matrix`` identity, ``/BBox`` == ``/Rect`` (a centred
    100×100 square). The §12.5.5 map is the identity translate; baseline.
(b) ``matrix_rot`` — ``/Matrix`` rotates the appearance 90° CCW about the
    BBox centre and the ``/Rect`` is a non-square (wide) rectangle, so the
    transformed box must be scaled non-uniformly into ``/Rect``.
(c) ``aspect_fit`` — identity ``/Matrix`` but a square ``/BBox`` mapped into a
    tall narrow ``/Rect`` — pure non-uniform scale-to-fit, no rotation.

Tolerance mirrors ``test_form_xobject_clip_oracle.py``: gate at ``MAD < 6.0``
and ``MAXDIFF < 60`` — above the AA ceiling, well below any placement /
scale / orientation failure floor.

Guard tests confirm the gate discriminates: rendering the same appearance
*without* the §12.5.5 fit (the raw ``/BBox`` placement — appearance painted at
its own BBox coordinates, /Matrix and rect-fit ignored) scores far over the
gate against PDFBox's correctly-mapped reference.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_rubber_stamp import (
    PDAnnotationRubberStamp,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60
_PAGE = 200.0

# Asymmetric appearance content, drawn in appearance (BBox) space 0..100 ×
# 0..100. A filled black block hugging the lower-left 0..60 × 0..60 plus a thin
# black bar up the full left edge (0..10 × 0..100). The block-in-one-corner +
# left-edge bar makes a horizontal flip, a 90° rotation, and a wrong aspect all
# visible in the downsampled grid (the dark mass is NOT centred or symmetric).
_SHAPE = b"0 0 0 rg\n0 0 60 60 re\nf\n0 0 10 100 re\nf\n"


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


def _build_appearance(
    bbox: tuple[float, float, float, float],
    matrix: tuple[float, float, float, float, float, float] | None,
) -> PDAppearanceStream:
    """A /Subtype /Form appearance stream drawing :data:`_SHAPE`, with the
    given ``/BBox`` and (optional) ``/Matrix``."""
    stream = COSStream()
    stream.set_raw_data(_SHAPE)
    appearance = PDAppearanceStream(stream)
    appearance.set_b_box(
        PDRectangle(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
    )
    if matrix is not None:
        appearance.get_cos_object().set_item(
            COSName.get_pdf_name("Matrix"), _matrix_array(matrix)
        )
    return appearance


def _add_stamp(
    page: PDPage,
    rect: tuple[float, float, float, float],
    appearance: PDAppearanceStream,
) -> None:
    stamp = PDAnnotationRubberStamp()
    stamp.set_rectangle(
        PDRectangle(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
    )
    ap = PDAppearanceDictionary()
    ap.set_normal_appearance(appearance)
    stamp.set_appearance(ap)
    page.add_annotation(stamp)


def _save(path: Path, doc: PDDocument) -> None:
    doc.save(str(path))
    doc.close()


# A 90° CCW rotation about the BBox centre (50,50) of a 0..100 square:
#   R(90) = [0 1 -1 0 0 0]; conjugated by translate(±50,±50) to keep the
#   transformed box anchored at the same centre. Net matrix maps the square
#   onto itself rotated, so its transformed-bbox bounds are still 0..100 but
#   the *content* is rotated — the dark corner block moves to a new quadrant.
_C = math.cos(math.pi / 2.0)
_S = math.sin(math.pi / 2.0)
_ROT_ABOUT_CENTRE = (
    _C,
    _S,
    -_S,
    _C,
    50.0 - 50.0 * _C + 50.0 * _S,
    50.0 - 50.0 * _S - 50.0 * _C,
)


# (a) identity — /Matrix identity, /BBox == /Rect (centred 100x100 square).
def _build_identity(path: Path) -> None:
    doc, page = _make_doc()
    appearance = _build_appearance(bbox=(0.0, 0.0, 100.0, 100.0), matrix=None)
    _add_stamp(page, rect=(50.0, 50.0, 150.0, 150.0), appearance=appearance)
    _save(path, doc)


# (b) matrix_rot — appearance rotated 90° about its centre, mapped into a wide
# non-square /Rect (forces non-uniform scale-to-fit on top of the rotation).
def _build_matrix_rot(path: Path) -> None:
    doc, page = _make_doc()
    appearance = _build_appearance(
        bbox=(0.0, 0.0, 100.0, 100.0), matrix=_ROT_ABOUT_CENTRE
    )
    _add_stamp(page, rect=(20.0, 60.0, 180.0, 140.0), appearance=appearance)
    _save(path, doc)


# (c) aspect_fit — identity /Matrix, square /BBox mapped into a tall narrow
# /Rect (pure non-uniform scale-to-fit, no rotation).
def _build_aspect_fit(path: Path) -> None:
    doc, page = _make_doc()
    appearance = _build_appearance(bbox=(0.0, 0.0, 100.0, 100.0), matrix=None)
    _add_stamp(page, rect=(70.0, 20.0, 130.0, 180.0), appearance=appearance)
    _save(path, doc)


_BUILDERS = {
    "identity": _build_identity,
    "matrix_rot": _build_matrix_rot,
    "aspect_fit": _build_aspect_fit,
}


# --------------------------------------------------------------------------
# Guard builders — appearance painted at its RAW /BBox coordinates onto the
# page directly (no §12.5.5 fit, /Matrix and /Rect ignored). This is what a
# renderer that skipped the BBox→Rect mapping would produce. Built as a plain
# page content stream so the bytes land at appearance space == page space.
# --------------------------------------------------------------------------


def _build_raw_identity(path: Path) -> None:
    """Paint :data:`_SHAPE` at its raw BBox coordinates as page content — no
    appearance transform applied at all. For the identity case the §12.5.5 map
    only translates the BBox (0..100) to the rect (50..150); raw placement
    leaves it at 0..100 — a clear shift."""
    doc, page = _make_doc()
    contents = COSStream()
    contents.set_raw_data(_SHAPE)
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    _save(path, doc)


# --------------------------------------------------------------------------
# differential tests
# --------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_annotation_appearance_transform_matches_pdfbox(
    label: str, tmp_path: Path
) -> None:
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
        f"(maxdiff={maxdiff}) — appearance→/Rect map diverges, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_raw_bbox_placement_blows_past_gate(tmp_path: Path) -> None:
    """Guard: painting the appearance at its raw /BBox coordinates (no
    §12.5.5 translate-to-rect) scores far over the gate against PDFBox's
    correctly-mapped ``identity`` reference. Proves the BBox→Rect fit is
    genuinely exercised — a no-op map would let this pass."""
    mapped = tmp_path / "identity.pdf"
    raw = tmp_path / "raw_identity.pdf"
    _build_identity(mapped)
    _build_raw_identity(raw)

    _dims, java_mapped_grid = _oracle_signature(mapped)
    py_raw_grid = _grid_from_image(_render_py(raw))
    mad, maxdiff = _diff(java_mapped_grid, py_raw_grid)
    assert mad >= _MAD_TOLERANCE and maxdiff >= _MAXDIFF_TOLERANCE, (
        f"Appearance-fit gate too loose: raw-BBox placement passes "
        f"(MAD={mad:.2f}, MAXDIFF={maxdiff})"
    )


@requires_oracle
def test_rotation_distinguished_from_unrotated(tmp_path: Path) -> None:
    """Guard: the asymmetric shape under the 90° appearance /Matrix is
    materially different from the same shape rendered *without* the rotation.
    Compares PDFBox's rotated reference against pypdfbox rendering the
    identity (unrotated) appearance in the same wide /Rect — they must
    diverge far over the gate, proving the /Matrix rotation actually moves the
    dark block (a renderer that dropped the /Matrix would score near zero)."""
    rotated = tmp_path / "matrix_rot.pdf"
    unrotated = tmp_path / "matrix_rot_dropped.pdf"
    _build_matrix_rot(rotated)
    # Same /Rect, same /BBox, but /Matrix dropped — the dark corner block
    # stays in the unrotated quadrant.
    doc, page = _make_doc()
    appearance = _build_appearance(bbox=(0.0, 0.0, 100.0, 100.0), matrix=None)
    _add_stamp(page, rect=(20.0, 60.0, 180.0, 140.0), appearance=appearance)
    _save(unrotated, doc)

    _dims, java_rotated_grid = _oracle_signature(rotated)
    py_unrotated_grid = _grid_from_image(_render_py(unrotated))
    mad, maxdiff = _diff(java_rotated_grid, py_unrotated_grid)
    assert mad >= _MAD_TOLERANCE and maxdiff >= _MAXDIFF_TOLERANCE, (
        f"Rotation gate too loose: dropping the appearance /Matrix passes "
        f"(MAD={mad:.2f}, MAXDIFF={maxdiff})"
    )
