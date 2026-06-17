"""Live PDFBox differential parity for annotation appearance rendering under
**page rotation** composed with **visibility flags** (PDF 32000-1 §7.7.3.3
page ``/Rotate`` + §12.5.5 ``/BBox`` → ``/Rect`` placement + §12.5.3 ``/F``
visibility flags).

Two orthogonal surfaces are already pinned elsewhere and are NOT re-tested
here:

* ``test_annot_ap_state_oracle.py`` — ``/AS`` substream selection on an
  *upright* page (rotation 0).
* ``test_annotation_flag_render_oracle.py`` — ``/F`` Hidden / NoView / Print
  gates on an *upright* page.

The fresh angle this module pins is the **composition** of page ``/Rotate``
with the annotation pipeline: the §12.5.5 transform that maps an appearance's
``/BBox`` (after its ``/Matrix``) onto the annotation ``/Rect`` is built in
default user space, and must then be composed with the page-rotation device
CTM exactly as Apache PDFBox does (``PageDrawer.showAnnotation`` →
``PDFStreamEngine.processAnnotation`` painted into a graphics device whose base
transform already carries the page rotation). Concretely we pin:

* A square Widget with a direct ``/AP /N`` form stream lands in the correct
  rotated pixel position for ``/Rotate`` 90 / 180 / 270 — and the rendered
  image dimensions swap width/height for 90 / 270.
* The Hidden ``/F`` bit still suppresses the annotation under rotation (a
  rotated page must not resurrect a hidden annotation).
* An ``/AS``-selected substream paints the correct shape under rotation.

Plus three oracle-confirmed edge cases that need no rotation but were not
previously pinned in the rendering tree:

* A subdictionary ``/AP /N`` with **no** ``/AS`` paints nothing (upstream
  ``getNormalAppearanceStream`` returns null for a state dict without ``/AS``).
* An ``/AS`` naming a state absent from the subdictionary paints nothing.
* An annotation whose appearance ``/BBox`` has zero width is skipped without
  raising (PDFBOX-4783 / PDFBOX-6095).

Each fixture is a tiny one-page PDF built in-process via pypdfbox. We render
through Apache PDFBox 3.0.7 (``oracle/probes/AnnotApStateProbe.java`` — it
renders page 0 of an arbitrary PDF at 72 dpi and emits the same 16x16 average
luminance fingerprint the paired pytest computes) and through pypdfbox's
:class:`PDFRenderer`. Pixel-EXACT parity is impossible (Pillow vs Java2D AA —
see ``CHANGES.md``); we gate the coarse fingerprint at ``MAD < 6`` /
``MAXDIFF < 60``, mirroring ``test_annot_ap_state_oracle.py``.

The blank-vs-painted and dimension-swap assertions are *also* exercised
without the oracle (``test_*_pin``) so the behavioural contract is regression
tested on machines without Java.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
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

# /F flag bits (PDF 32000-1 Table 165): Invisible=bit1(1), Hidden=bit2(2),
# NoView=bit6(32).
_FLAG_HIDDEN = 2

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


def _substream(content: bytes, bbox: tuple[float, ...] = _BBOX) -> COSStream:
    """A ``/Subtype /Form`` appearance substream drawing ``content`` with the
    given ``/BBox`` (identity ``/Matrix``)."""
    stream = COSStream()
    stream.set_raw_data(content)
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Form"))
    bbox_arr = COSArray()
    for v in bbox:
        bbox_arr.add(COSFloat(v))
    stream.set_item(COSName.get_pdf_name("BBox"), bbox_arr)
    return stream


def _fresh_doc(
    rotation: int, page_size: tuple[float, float] = (_PAGE_W, _PAGE_H)
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, page_size[0], page_size[1]))
    page.set_rotation(rotation)
    doc.add_page(page)
    return doc, page


def _widget(rect: tuple[float, float, float, float], ap_n: object) -> PDAnnotationWidget:
    widget = PDAnnotationWidget()
    widget.set_rectangle(
        PDRectangle(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
    )
    ap = PDAppearanceDictionary()
    ap.get_cos_object().set_item(COSName.get_pdf_name("N"), ap_n)
    widget.set_appearance(ap)
    return widget


def _build_rotated_square(path: Path, rotation: int) -> None:
    """A square Widget with a direct ``/AP /N`` form stream on a page rotated
    by ``rotation`` degrees."""
    doc, page = _fresh_doc(rotation)
    page.add_annotation(_widget(_RECT, _substream(_SHAPE)))
    doc.save(str(path))
    doc.close()


def _build_rotated_hidden(path: Path, rotation: int) -> None:
    """As above but with the Hidden ``/F`` bit set — must paint nothing."""
    doc, page = _fresh_doc(rotation)
    widget = _widget(_RECT, _substream(_SHAPE))
    widget.get_cos_object().set_item(
        COSName.get_pdf_name("F"), COSInteger.get(_FLAG_HIDDEN)
    )
    page.add_annotation(widget)
    doc.save(str(path))
    doc.close()


def _build_rotated_as_state(path: Path, rotation: int) -> None:
    """A state-subdictionary ``/AP /N`` whose ``/AS = /On`` selects a distinct
    substream, on a rotated page."""
    doc, page = _fresh_doc(rotation)
    sub = COSDictionary()
    sub.set_item(
        COSName.get_pdf_name("On"), _substream(b"0 0 0 rg\n0 0 70 70 re\nf\n")
    )
    sub.set_item(
        COSName.get_pdf_name("Off"), _substream(b"0 0 0 rg\n80 80 20 20 re\nf\n")
    )
    widget = _widget(_RECT, sub)
    widget.set_appearance_state("On")
    page.add_annotation(widget)
    doc.save(str(path))
    doc.close()


def _build_subdict_no_as(path: Path) -> None:
    """A subdictionary ``/AP /N`` with NO ``/AS`` — paints nothing."""
    doc, page = _fresh_doc(0, (200.0, 200.0))
    sub = COSDictionary()
    sub.set_item(
        COSName.get_pdf_name("On"), _substream(b"0 0 0 rg\n0 0 70 70 re\nf\n")
    )
    sub.set_item(
        COSName.get_pdf_name("Off"), _substream(b"0 0 0 rg\n80 80 20 20 re\nf\n")
    )
    page.add_annotation(_widget((40.0, 40.0, 140.0, 140.0), sub))
    doc.save(str(path))
    doc.close()


def _build_as_unknown_state(path: Path) -> None:
    """``/AS`` naming a state absent from the subdictionary — paints nothing."""
    doc, page = _fresh_doc(0, (200.0, 200.0))
    sub = COSDictionary()
    sub.set_item(
        COSName.get_pdf_name("On"), _substream(b"0 0 0 rg\n0 0 70 70 re\nf\n")
    )
    widget = _widget((40.0, 40.0, 140.0, 140.0), sub)
    widget.set_appearance_state("Bogus")
    page.add_annotation(widget)
    doc.save(str(path))
    doc.close()


def _build_zero_bbox(path: Path) -> None:
    """A direct ``/AP /N`` whose ``/BBox`` has zero width — skipped silently."""
    doc, page = _fresh_doc(0, (200.0, 200.0))
    page.add_annotation(
        _widget(
            (40.0, 40.0, 140.0, 140.0),
            _substream(_SHAPE, bbox=(0.0, 0.0, 0.0, 100.0)),
        )
    )
    doc.save(str(path))
    doc.close()


# ----------------------------------------------------------------- oracle parity

_ROTATIONS = [90, 180, 270]


@requires_oracle
@pytest.mark.parametrize("rotation", _ROTATIONS, ids=[str(r) for r in _ROTATIONS])
def test_rotated_annotation_placement_matches_pdfbox(
    rotation: int, tmp_path: Path
) -> None:
    """A square Widget's ``/AP /N`` must land in the same rotated pixel
    position as Apache PDFBox, with matching (swapped for 90/270) image
    dimensions, within the AA fingerprint gate."""
    pdf = tmp_path / f"rot_{rotation}.pdf"
    _build_rotated_square(pdf, rotation)

    (java_w, java_h), java_grid = _oracle_signature(pdf)
    img = _render_py(pdf)
    py_w, py_h = img.size

    assert (py_w, py_h) == (java_w, java_h), (
        f"rotation {rotation}: rendered dimensions diverge: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )
    mad, maxdiff = _diff(java_grid, _grid_from_image(img))
    assert mad < _MAD_TOLERANCE, (
        f"rotation {rotation}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — annotation placement diverges under rotation"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"rotation {rotation}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("rotation", _ROTATIONS, ids=[str(r) for r in _ROTATIONS])
def test_rotated_hidden_annotation_suppressed_matches_pdfbox(
    rotation: int, tmp_path: Path
) -> None:
    """The Hidden ``/F`` bit must still suppress the annotation under page
    rotation — both renderers produce a blank page."""
    pdf = tmp_path / f"rot_{rotation}_hidden.pdf"
    _build_rotated_hidden(pdf, rotation)

    _dims, java_grid = _oracle_signature(pdf)
    py_grid = _grid_from_image(_render_py(pdf))

    assert _is_blank(java_grid), "oracle precondition: hidden annot must be blank"
    mad, maxdiff = _diff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE and maxdiff < _MAXDIFF_TOLERANCE, (
        f"rotation {rotation}: hidden annot diverges (MAD={mad:.2f}, "
        f"MAXDIFF={maxdiff}) — Hidden flag not honoured under rotation"
    )


@requires_oracle
@pytest.mark.parametrize("rotation", [90, 270], ids=["90", "270"])
def test_rotated_as_state_matches_pdfbox(rotation: int, tmp_path: Path) -> None:
    """An ``/AS``-selected substream paints the correct shape under rotation,
    matching PDFBox within the AA gate."""
    pdf = tmp_path / f"rot_{rotation}_as.pdf"
    _build_rotated_as_state(pdf, rotation)

    (java_w, java_h), java_grid = _oracle_signature(pdf)
    img = _render_py(pdf)
    assert img.size == (java_w, java_h)
    mad, maxdiff = _diff(java_grid, _grid_from_image(img))
    assert mad < _MAD_TOLERANCE and maxdiff < _MAXDIFF_TOLERANCE, (
        f"rotation {rotation}: /AS substream diverges under rotation "
        f"(MAD={mad:.2f}, MAXDIFF={maxdiff})"
    )


@requires_oracle
@pytest.mark.parametrize(
    ("label", "builder"),
    [
        ("subdict_no_as", _build_subdict_no_as),
        ("as_unknown_state", _build_as_unknown_state),
        ("zero_bbox", _build_zero_bbox),
    ],
    ids=["subdict_no_as", "as_unknown_state", "zero_bbox"],
)
def test_appearance_edge_cases_match_pdfbox(
    label: str, builder, tmp_path: Path
) -> None:
    """Subdictionary-without-/AS, /AS-naming-a-missing-state, and zero-width
    /BBox all paint nothing in PDFBox — pypdfbox must agree (and not raise)."""
    pdf = tmp_path / f"{label}.pdf"
    builder(pdf)

    _dims, java_grid = _oracle_signature(pdf)
    py_grid = _grid_from_image(_render_py(pdf))

    assert _is_blank(java_grid), f"{label}: oracle precondition — must be blank"
    mad, maxdiff = _diff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE and maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: diverges from PDFBox blank render "
        f"(MAD={mad:.2f}, MAXDIFF={maxdiff})"
    )


# ----------------------------------------------------------------- oracle-free pins


@pytest.mark.parametrize("rotation", _ROTATIONS, ids=[str(r) for r in _ROTATIONS])
def test_rotated_annotation_dimension_swap_pin(rotation: int, tmp_path: Path) -> None:
    """Oracle-free contract: rendering a 200x300 page at 72 dpi swaps the
    output dimensions for 90/270 and keeps them for 180, and the annotation
    actually paints (non-blank)."""
    pdf = tmp_path / f"rot_{rotation}.pdf"
    _build_rotated_square(pdf, rotation)
    img = _render_py(pdf)
    expected = (300, 200) if rotation in (90, 270) else (200, 300)
    assert img.size == expected, (
        f"rotation {rotation}: expected {expected}, got {img.size}"
    )
    assert not _is_blank(_grid_from_image(img)), (
        f"rotation {rotation}: annotation should paint, page is blank"
    )


@pytest.mark.parametrize("rotation", _ROTATIONS, ids=[str(r) for r in _ROTATIONS])
def test_rotated_hidden_annotation_blank_pin(rotation: int, tmp_path: Path) -> None:
    """Oracle-free contract: a Hidden annotation paints nothing regardless of
    page rotation."""
    pdf = tmp_path / f"rot_{rotation}_hidden.pdf"
    _build_rotated_hidden(pdf, rotation)
    assert _is_blank(_grid_from_image(_render_py(pdf))), (
        f"rotation {rotation}: hidden annotation must not paint"
    )


@pytest.mark.parametrize(
    ("label", "builder"),
    [
        ("subdict_no_as", _build_subdict_no_as),
        ("as_unknown_state", _build_as_unknown_state),
        ("zero_bbox", _build_zero_bbox),
    ],
    ids=["subdict_no_as", "as_unknown_state", "zero_bbox"],
)
def test_appearance_edge_cases_blank_pin(label: str, builder, tmp_path: Path) -> None:
    """Oracle-free contract: each appearance edge case paints nothing and does
    not raise."""
    pdf = tmp_path / f"{label}.pdf"
    builder(pdf)
    assert _is_blank(_grid_from_image(_render_py(pdf))), (
        f"{label}: must paint nothing"
    )
