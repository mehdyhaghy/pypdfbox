"""Live PDFBox differential parity for the **NoRotate** annotation flag
(PDF 32000-1 §12.5.3 ``/F`` bit 5, value 16) under page ``/Rotate``
(PDFBOX-4744).

Upstream ``PageDrawer.showAnnotation`` counter-rotates a NoRotate annotation
by the page's ``/Rotate`` angle **about the rect's upper-left corner**
(``rect.lowerLeftX`` / ``rect.upperRightY``) so the appearance paints upright
while the page is rotated, pivoting at that corner. ``test_annot_rotate_
render_oracle.py`` already pins the *non*-NoRotate placement under rotation;
this module adds the orthogonal NoRotate counter-rotation surface, plus its
no-op on an unrotated page and its composition with a non-identity appearance
``/Matrix``.

Each fixture is a tiny one-page PDF built in-process via pypdfbox, rendered
through Apache PDFBox 3.0.7 (``oracle/probes/AnnotApStateProbe.java`` — page 0
at 72 dpi, emitting a 16x16 average-luminance fingerprint) and through
pypdfbox's :class:`PDFRenderer`. We gate the coarse fingerprint at
``MAD < 6`` / ``MAXDIFF < 60``, mirroring ``test_annot_rotate_render_
oracle.py`` (Pillow vs Java2D AA makes pixel-EXACT parity impossible).

The differential placement and the NoRotate-vs-control *distinctness* are
also asserted without the oracle (``test_*_pin``) so the behavioural contract
regression-tests on machines without Java.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

# Non-square media box so the 90/270 width/height swap is observable.
_PAGE_W = 200.0
_PAGE_H = 300.0

# Asymmetric shape in BBox 0..100 x 0..100 — a dark foot along the bottom plus
# a tall bar up the left edge. Asymmetry makes a wrong rotation visible.
_SHAPE = b"0 0 0 rg\n0 0 60 20 re\nf\n0 0 20 90 re\nf\n"
_BBOX = (0.0, 0.0, 100.0, 100.0)
# Rect placed off-centre; BBox is the 0..100 square so the §12.5.5 map is a
# pure translate (1x scale: rect is 100x100).
_RECT = (40.0, 50.0, 140.0, 150.0)

# /F flag bits (PDF 32000-1 Table 165): NoRotate = bit 5, value 16.
_FLAG_NO_ROTATE = 16

# A non-identity appearance /Matrix (half-scale + translate) to exercise the
# NoRotate counter-rotation composed with a /Matrix leg.
_AP_MATRIX = (0.5, 0.0, 0.0, 0.5, 50.0, 50.0)

_BLANK_THRESHOLD = 250  # cell luminance at/above this == effectively white


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
    lines = run_probe_text("AnnotApStateProbe", str(pdf), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _diff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


def _is_blank(grid: list[int]) -> bool:
    return all(v >= _BLANK_THRESHOLD for v in grid)


def _render_py(pdf: Path) -> Image.Image:
    with PDDocument.load(pdf) as doc:
        return PDFRenderer(doc).render_image_with_dpi(0, 72.0)


# ----------------------------------------------------------------- builders


def _substream(
    content: bytes,
    bbox: tuple[float, ...] = _BBOX,
    matrix: tuple[float, ...] | None = None,
) -> COSStream:
    stream = COSStream()
    stream.set_raw_data(content)
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Form"))
    bbox_arr = COSArray()
    for v in bbox:
        bbox_arr.add(COSFloat(v))
    stream.set_item(COSName.get_pdf_name("BBox"), bbox_arr)
    if matrix is not None:
        mat_arr = COSArray()
        for v in matrix:
            mat_arr.add(COSFloat(v))
        stream.set_item(COSName.get_pdf_name("Matrix"), mat_arr)
    return stream


def _fresh_doc(rotation: int) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
    page.set_rotation(rotation)
    doc.add_page(page)
    return doc, page


def _widget(
    rect: tuple[float, float, float, float],
    ap_n: object,
    *,
    no_rotate: bool = False,
) -> PDAnnotationWidget:
    widget = PDAnnotationWidget()
    widget.set_rectangle(
        PDRectangle(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
    )
    ap = PDAppearanceDictionary()
    ap.get_cos_object().set_item(COSName.get_pdf_name("N"), ap_n)
    widget.set_appearance(ap)
    if no_rotate:
        widget.get_cos_object().set_item(
            COSName.get_pdf_name("F"), COSInteger.get(_FLAG_NO_ROTATE)
        )
    return widget


def _build_square(
    path: Path,
    rotation: int,
    *,
    no_rotate: bool,
    matrix: tuple[float, ...] | None = None,
) -> None:
    """A square Widget with a direct ``/AP /N`` form stream on a page rotated
    by ``rotation`` degrees, with the NoRotate ``/F`` bit optionally set and
    an optional non-identity appearance ``/Matrix``."""
    doc, page = _fresh_doc(rotation)
    page.add_annotation(
        _widget(_RECT, _substream(_SHAPE, matrix=matrix), no_rotate=no_rotate)
    )
    doc.save(str(path))
    doc.close()


# ----------------------------------------------------------------- oracle parity

_ROTATIONS = [90, 180, 270]


@requires_oracle
@pytest.mark.parametrize("rotation", _ROTATIONS, ids=[str(r) for r in _ROTATIONS])
def test_norotate_annotation_placement_matches_pdfbox(
    rotation: int, tmp_path: Path
) -> None:
    """A NoRotate Widget on a rotated page must pivot upright about its rect's
    upper-left corner exactly as Apache PDFBox (PDFBOX-4744)."""
    pdf = tmp_path / f"norot_{rotation}.pdf"
    _build_square(pdf, rotation, no_rotate=True)

    (java_w, java_h), java_grid = _oracle_signature(pdf)
    img = _render_py(pdf)
    assert img.size == (java_w, java_h), (
        f"rotation {rotation}: rendered dimensions diverge: "
        f"pypdfbox={img.size} java={java_w}x{java_h}"
    )
    mad, maxdiff = _diff(java_grid, _grid_from_image(img))
    assert mad < _MAD_TOLERANCE, (
        f"rotation {rotation}: NoRotate annotation mean abs cell diff "
        f"{mad:.2f} >= {_MAD_TOLERANCE} (maxdiff={maxdiff}) — counter-rotation "
        f"diverges from PDFBox"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"rotation {rotation}: NoRotate worst cell diff {maxdiff} >= "
        f"{_MAXDIFF_TOLERANCE} (mad={mad:.2f})"
    )


@requires_oracle
@pytest.mark.parametrize("rotation", [90, 270], ids=["90", "270"])
def test_norotate_with_appearance_matrix_matches_pdfbox(
    rotation: int, tmp_path: Path
) -> None:
    """NoRotate composed with a non-identity appearance ``/Matrix`` must still
    match PDFBox under rotation."""
    pdf = tmp_path / f"norot_mat_{rotation}.pdf"
    _build_square(pdf, rotation, no_rotate=True, matrix=_AP_MATRIX)

    (java_w, java_h), java_grid = _oracle_signature(pdf)
    img = _render_py(pdf)
    assert img.size == (java_w, java_h)
    mad, maxdiff = _diff(java_grid, _grid_from_image(img))
    assert mad < _MAD_TOLERANCE and maxdiff < _MAXDIFF_TOLERANCE, (
        f"rotation {rotation}: NoRotate + /Matrix diverges from PDFBox "
        f"(MAD={mad:.2f}, MAXDIFF={maxdiff})"
    )


@requires_oracle
def test_norotate_on_unrotated_page_is_noop_matches_pdfbox(tmp_path: Path) -> None:
    """NoRotate on a page with ``/Rotate 0`` is a no-op — must match PDFBox's
    plain placement (the counter-rotation angle is zero)."""
    pdf = tmp_path / "norot_unrotated.pdf"
    _build_square(pdf, 0, no_rotate=True)

    (java_w, java_h), java_grid = _oracle_signature(pdf)
    img = _render_py(pdf)
    assert img.size == (java_w, java_h)
    assert not _is_blank(java_grid), "oracle precondition: annotation must paint"
    mad, maxdiff = _diff(java_grid, _grid_from_image(img))
    assert mad < _MAD_TOLERANCE and maxdiff < _MAXDIFF_TOLERANCE, (
        f"NoRotate-on-unrotated diverges from PDFBox (MAD={mad:.2f}, "
        f"MAXDIFF={maxdiff})"
    )


# ----------------------------------------------------------------- oracle-free pins


@pytest.mark.parametrize("rotation", _ROTATIONS, ids=[str(r) for r in _ROTATIONS])
def test_norotate_distinct_from_control_pin(rotation: int, tmp_path: Path) -> None:
    """Oracle-free contract: on a rotated page the NoRotate counter-rotation
    must produce a *different* image than the same annotation without the flag
    (proving the counter-rotation is actually applied), and both must paint."""
    plain = tmp_path / f"plain_{rotation}.pdf"
    norot = tmp_path / f"norot_{rotation}.pdf"
    _build_square(plain, rotation, no_rotate=False)
    _build_square(norot, rotation, no_rotate=True)

    plain_grid = _grid_from_image(_render_py(plain))
    norot_grid = _grid_from_image(_render_py(norot))

    assert not _is_blank(plain_grid), f"rotation {rotation}: control must paint"
    assert not _is_blank(norot_grid), f"rotation {rotation}: NoRotate must paint"
    _mad, maxdiff = _diff(plain_grid, norot_grid)
    assert maxdiff >= _MAXDIFF_TOLERANCE, (
        f"rotation {rotation}: NoRotate produced the same image as the control "
        f"(maxdiff={maxdiff}) — counter-rotation was not applied"
    )


def test_norotate_on_unrotated_page_matches_control_pin(tmp_path: Path) -> None:
    """Oracle-free contract: with ``/Rotate 0`` the NoRotate flag is a no-op —
    its render must be identical to the same annotation without the flag."""
    plain = tmp_path / "plain_0.pdf"
    norot = tmp_path / "norot_0.pdf"
    _build_square(plain, 0, no_rotate=False)
    _build_square(norot, 0, no_rotate=True)

    plain_grid = _grid_from_image(_render_py(plain))
    norot_grid = _grid_from_image(_render_py(norot))
    assert plain_grid == norot_grid, (
        "NoRotate on an unrotated page must be a no-op (identical render)"
    )
