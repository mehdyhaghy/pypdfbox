"""Live PDFBox differential parity for form-XObject ``Do`` rendering —
the ``/Matrix`` concatenation + ``/BBox`` clip path (PDF 32000-1 §8.10.1).

When a content stream invokes ``/Do`` on a form XObject the renderer must,
per §8.10.1: (1) save the graphics state, (2) concatenate the form's
``/Matrix`` onto the CTM, (3) intersect the current clip with the form's
``/BBox`` *transformed by that matrix*, (4) switch to the form's
``/Resources``, (5) execute the form's content stream, (6) restore. The
two parity hazards this surface guards against:

* **Dropped /Matrix concatenation** — a renderer that runs the form's
  content stream against the bare CTM paints the form's geometry at the
  wrong scale / position, moving large luminance blocks far past the gate.
* **Missing /BBox clip** — a form whose content paints outside its /BBox
  must have that surplus clipped away. The ``matrix_scale_translate``
  fixture's /BBox deliberately crops the painted rect, so a renderer that
  forgets the clip leaves a coloured block where the oracle shows page
  background.

Pixel-EXACT parity is impossible (Pillow vs Java2D AA — see ``CHANGES.md`` /
``test_render_oracle.py``), so we compare the proven coarse fingerprint:
exact rendered dimensions plus a 16x16 average-luminance grid, gated at
``MAD < 6`` / ``MAXDIFF < 60`` against ``oracle/probes/FormXObjectProbe.java``
(72 DPI render — identical luminance math to ``RenderProbe`` /
``ImageMaskProbe``).

Fixtures are tiny one-page PDFs synthesised in-memory via pypdfbox's own
COS + content-stream API (no committed binaries). Each builds a form
XObject with an explicit ``/Matrix`` and ``/BBox``, attaches it under the
page's ``/Resources/XObject`` and invokes it with a single ``/F0 Do``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as the other rendering oracles — comfortably above the AA
# ceiling yet well below the gross-failure floor (a dropped /Matrix or an
# un-applied /BBox clip both diverge far past this).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 120  # media-box side, pt


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``FormXObjectProbe.java`` (integer-division of pixel coord over image
    size, clamped to the last cell). Matches PIL's "L" Rec.601 weights."""
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


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    """Run FormXObjectProbe on page 0 and parse its (dims, 16x16 grid)."""
    lines = run_probe_text("FormXObjectProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _make_form_stream(
    content: bytes,
    bbox: tuple[float, float, float, float],
    matrix: tuple[float, float, float, float, float, float],
) -> COSStream:
    """Build a ``/Subtype /Form`` stream with explicit /BBox + /Matrix."""
    stream = COSStream()
    stream.set_raw_data(content)
    cos = stream
    cos.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    cos.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form"))
    cos.set_int(COSName.get_pdf_name("FormType"), 1)
    bbox_arr = COSArray()
    for v in bbox:
        bbox_arr.add(COSFloat(float(v)))
    cos.set_item(COSName.get_pdf_name("BBox"), bbox_arr)
    matrix_arr = COSArray()
    for v in matrix:
        matrix_arr.add(COSFloat(float(v)))
    cos.set_item(COSName.get_pdf_name("Matrix"), matrix_arr)
    return stream


def _attach_form_and_save(
    path: Path, form_stream: COSStream, page_prefix: bytes = b""
) -> None:
    """One-page doc whose content fills a backdrop then invokes ``/F0 Do``."""
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _MB, _MB))
    doc.add_page(page)

    contents = COSStream()
    contents.set_raw_data(page_prefix + b"/F0 Do\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        form_stream,
    )
    doc.save(str(path))
    doc.close()


def _build_matrix_scale_translate_fixture(path: Path) -> None:
    """Form whose /Matrix scales x2 and translates, and whose /BBox clips
    the painted content.

    Form-space content: a green rect at (0,0)-(40,40). The /Matrix
    ``[2 0 0 2 20 10]`` maps it to page rect (20,10)-(100,90). The /BBox
    is set to form-space (0,0)-(25,40), which after the matrix maps to
    page (20,10)-(70,90) — so the right strip of the painted rect
    (page x 70..100) is CLIPPED away and the page backdrop shows there.

    Backdrop: a blue page fill. A renderer that drops the /Matrix paints
    the rect at half scale at the wrong origin; a renderer that skips the
    /BBox clip paints the full 40x40 (scaled to 80x80) rect with no blue
    strip on the right — both score far outside the gate.
    """
    content = b"0 1 0 rg\n0 0 40 40 re\nf\n"
    form = _make_form_stream(
        content,
        bbox=(0.0, 0.0, 25.0, 40.0),
        matrix=(2.0, 0.0, 0.0, 2.0, 20.0, 10.0),
    )
    # Page backdrop: solid blue fill behind the form.
    _attach_form_and_save(path, form, page_prefix=b"0 0 1 rg\n0 0 120 120 re\nf\n")


def _build_matrix_rotate_translate_fixture(path: Path) -> None:
    """Form whose /Matrix rotates 90 degrees and translates, BBox loose
    (does not clip). Catches a renderer that mis-orders the matrix
    concatenation (rotation about the wrong origin) — the painted block
    lands in a different quadrant.

    Form-space content: a red rect at (0,0)-(60,30). The /Matrix
    ``[0 1 -1 0 90 20]`` (cos90=0, sin90=1) rotates +90 deg then
    translates by (90,20). Corner (0,0)->(90,20); (60,0)->(90,80);
    (0,30)->(60,20). The /BBox is the full form extent so no clipping.
    """
    content = b"1 0 0 rg\n0 0 60 30 re\nf\n"
    form = _make_form_stream(
        content,
        bbox=(0.0, 0.0, 60.0, 30.0),
        matrix=(0.0, 1.0, -1.0, 0.0, 90.0, 20.0),
    )
    _attach_form_and_save(path, form, page_prefix=b"1 1 1 rg\n0 0 120 120 re\nf\n")


_BUILDERS = {
    "matrix_scale_translate": _build_matrix_scale_translate_fixture,
    "matrix_rotate_translate": _build_matrix_rotate_translate_fixture,
}


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_form_xobject_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each form-XObject /Matrix + /BBox variant must match Java PDFBox's
    render of the same fixture within the 16x16 fingerprint gate."""
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)

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

    # (b) Perceptual grid parity within tolerance.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — form /Matrix or /BBox path mis-applied, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_bbox_actually_clips_visible_content(tmp_path: Path) -> None:
    """Direct proof the /BBox clip is applied: the scale+translate fixture's
    /BBox crops the right strip of the painted green rect. The right strip
    (page x 70..100) must show the BLUE backdrop, while the left part of
    the rect (page x 30..60) must show GREEN. A renderer that skips the
    /BBox clip paints green across the whole 20..100 span (no blue strip)."""
    fixture = tmp_path / "matrix_scale_translate.pdf"
    _build_matrix_scale_translate_fixture(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    # PDF y is flipped: page y in pt → PIL row (_MB - y) at 72 DPI.
    # Sample mid-height of the rect (page y ~50 → PIL row ~70).
    row = _MB - 50
    # Inside the clipped form: page x ~45 → green-dominant.
    inside = img.getpixel((45, row))
    assert inside[1] > inside[0] + 40 and inside[1] > inside[2] + 40, (
        f"clipped form interior {inside} not green-dominant — form not painted"
    )
    # Right of the /BBox clip: page x ~85 → blue backdrop shows through.
    clipped = img.getpixel((85, row))
    assert clipped[2] > clipped[0] + 40 and clipped[2] > clipped[1] + 40, (
        f"region right of /BBox {clipped} not blue-dominant — /BBox clip ignored"
    )
