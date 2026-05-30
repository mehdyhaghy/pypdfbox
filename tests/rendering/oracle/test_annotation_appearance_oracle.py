"""Live PDFBox differential parity for the §12.5.5 appearance→/Rect map when
the appearance ``/BBox`` is NOT anchored at the origin.

``test_annotation_appearance_transform_oracle.py`` already pins the PDF 32000-1
§12.5.5 ``/BBox``-after-``/Matrix`` → ``/Rect`` placement for appearances whose
``/BBox`` starts at ``(0, 0)`` (identity / 90°-rotation / aspect-fit). For an
origin-anchored BBox the §12.5.5 "translate the transformed box lower-left to
the rect origin" leg degenerates: ``tb_x``/``tb_y`` are ~0 so the translate
contribution ``-tb_x * sx`` / ``-tb_y * sy`` vanishes. A renderer could drop
that subtraction entirely and still pass every origin-anchored case.

This file exercises the orthogonal, genuinely-load-bearing permutation: an
appearance whose ``/BBox`` is **offset from the origin** (lower-left far from
``(0, 0)``), so the transformed-box origin ``(tb_x, tb_y)`` is non-zero and the
``-tb_x * sx`` / ``-tb_y * sy`` translate legs of the fit matrix
``A = T(rect.ll) · S(rect.w/tb.w, rect.h/tb.h) · T(-tb.x, -tb.y)`` actually do
work. Cases:

(a) ``offset_identity`` — identity ``/Matrix``, ``/BBox`` = ``(40,40,140,140)``
    (a 100×100 square shifted up-and-right of the origin) mapped onto a
    100×100 ``/Rect``. A renderer that forgot ``-tb_x``/``-tb_y`` would shift
    the painted block by 40pt in both axes — way off inside the rect.
(b) ``offset_rotate`` — the same offset ``/BBox`` under a 90° rotation about
    its own centre, mapped into a wide non-square ``/Rect``. The transformed
    box origin is non-zero *and* the content is rotated, so both the offset
    cancellation and the rotate-before-translate order (PDFBOX-3083 /
    wave-1391) must be right.

We render each through Apache PDFBox 3.0.7 (``oracle/probes/RenderProbe.java``)
and through pypdfbox's :class:`PDFRenderer`, comparing the coarse 16×16
average-luminance grid. Tolerance mirrors the sibling transform test:
``MAD < 6.0`` / ``MAXDIFF < 60`` — above the AA ceiling, below any
placement / scale / orientation failure floor.

A guard test confirms the gate discriminates: rendering the offset appearance
with the ``-tb_x``/``-tb_y`` cancellation *deliberately dropped* (the painted
block left at its raw BBox offset) scores far over the gate against PDFBox's
correctly-fitted reference.
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

# Asymmetric appearance content, drawn relative to the BBox lower-left. The
# block hugs the BBox lower-left corner (0..60 in BBox-local terms) plus a thin
# bar up the left edge, so a flip / wrong rotation / wrong offset is visible in
# the downsampled grid. Emitted with a BBox-origin offset baked into the
# coordinates so the marks sit inside the offset BBox.
_BBOX_OFFSET = 40.0
_BX = _BBOX_OFFSET


def _shape_at(ox: float, oy: float) -> bytes:
    """The asymmetric mark (corner block + left-edge bar), translated so its
    lower-left sits at ``(ox, oy)`` in appearance space."""
    return (
        f"0 0 0 rg\n"
        f"{ox} {oy} 60 60 re\nf\n"
        f"{ox} {oy} 10 100 re\nf\n"
    ).encode("utf-8")


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
    content: bytes,
    bbox: tuple[float, float, float, float],
    matrix: tuple[float, float, float, float, float, float] | None,
) -> PDAppearanceStream:
    stream = COSStream()
    stream.set_raw_data(content)
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


# 90° CCW rotation about the offset BBox centre (90, 90) for a 40..140 square.
_C = math.cos(math.pi / 2.0)
_S = math.sin(math.pi / 2.0)
_CENTRE = _BX + 50.0  # 90.0
_ROT_ABOUT_CENTRE = (
    _C,
    _S,
    -_S,
    _C,
    _CENTRE - _CENTRE * _C + _CENTRE * _S,
    _CENTRE - _CENTRE * _S - _CENTRE * _C,
)


# (a) offset_identity — identity /Matrix, BBox offset to (40,40,140,140),
# mapped onto a centred 100x100 /Rect.
def _build_offset_identity(path: Path) -> None:
    doc, page = _make_doc()
    appearance = _build_appearance(
        content=_shape_at(_BX, _BX),
        bbox=(_BX, _BX, _BX + 100.0, _BX + 100.0),
        matrix=None,
    )
    _add_stamp(page, rect=(50.0, 50.0, 150.0, 150.0), appearance=appearance)
    _save(path, doc)


# (b) offset_rotate — offset BBox rotated 90° about its own centre, mapped into
# a wide non-square /Rect (forces non-uniform scale-to-fit on the rotated,
# offset transformed box).
def _build_offset_rotate(path: Path) -> None:
    doc, page = _make_doc()
    appearance = _build_appearance(
        content=_shape_at(_BX, _BX),
        bbox=(_BX, _BX, _BX + 100.0, _BX + 100.0),
        matrix=_ROT_ABOUT_CENTRE,
    )
    _add_stamp(page, rect=(20.0, 60.0, 180.0, 140.0), appearance=appearance)
    _save(path, doc)


_BUILDERS = {
    "offset_identity": _build_offset_identity,
    "offset_rotate": _build_offset_rotate,
}


# Guard: paint the offset appearance's marks at their raw BBox coordinates as
# page content — no §12.5.5 translate-to-rect at all. For offset_identity the
# correct map translates the transformed box (40..140) onto the rect (50..150),
# a net shift; raw placement leaves the marks at 40..100 — a clear divergence.
def _build_raw_offset(path: Path) -> None:
    doc, page = _make_doc()
    contents = COSStream()
    contents.set_raw_data(_shape_at(_BX, _BX))
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    _save(path, doc)


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_annotation_offset_bbox_appearance_matches_pdfbox(
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
        f"(maxdiff={maxdiff}) — offset-BBox→/Rect map diverges, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_offset_cancellation_blows_past_gate(tmp_path: Path) -> None:
    """Guard: leaving the offset appearance at its raw BBox coordinates (no
    §12.5.5 ``-tb_x``/``-tb_y`` translate) scores far over the gate against
    PDFBox's correctly-fitted ``offset_identity`` reference. Proves the
    transformed-box-origin cancellation is genuinely exercised — a renderer
    that dropped it would let this pass."""
    mapped = tmp_path / "offset_identity.pdf"
    raw = tmp_path / "raw_offset.pdf"
    _build_offset_identity(mapped)
    _build_raw_offset(raw)

    _dims, java_mapped_grid = _oracle_signature(mapped)
    py_raw_grid = _grid_from_image(_render_py(raw))
    mad, maxdiff = _diff(java_mapped_grid, py_raw_grid)
    assert mad >= _MAD_TOLERANCE and maxdiff >= _MAXDIFF_TOLERANCE, (
        f"Offset-cancellation gate too loose: raw-BBox placement passes "
        f"(MAD={mad:.2f}, MAXDIFF={maxdiff})"
    )
