"""Live PDFBox differential parity for annotation ``/F`` flag *render gating*.

Surface under test: ``pypdfbox.rendering`` (``PdfRenderer._render_annotation`` /
``_annotation_should_skip``) plus the ``/F`` flag accessors on
``pypdfbox.pdmodel.interactive.annotation.PDAnnotation``.

PDF 32000-1 §12.5.3 / Table 165: when rasterising a page for screen
(``renderImage`` => ``RenderDestination.VIEW``) Apache PDFBox's
``PageDrawer.showAnnotation`` consults ``shouldSkipAnnotation`` and DROPS an
annotation whose ``/F`` carries:

* the **Hidden** bit (bit 2, value 2)  — never displayed, any destination;
* the **NoView** bit (bit 6, value 32) — skipped for the View/Export (screen)
  destination, which is exactly what ``renderImage`` targets.

The **Print** bit (bit 3, value 4) is irrelevant for screen rendering: a
Print-only annotation (Print set, NoView clear) still shows on screen. An
annotation with no flags always paints. This gate is distinct from the
annotation ``/OC`` optional-content gate (wave 1441,
``tests/pdmodel/interactive/annotation/oracle/test_annotation_oc_oracle.py``):
here the suppression is driven by the ``/F`` flag bits, not OCG membership.

Each case BUILDS a one-page PDF via pypdfbox carrying a single filled-square
markup annotation with a Normal Appearance (``/AP /N`` via
``construct_appearances``) and a specific ``/F`` value, saves it ONCE to
``tmp_path``, then renders the same bytes through BOTH the Java oracle
(``RenderProbe.java`` at 72 DPI, default render state = screen/View) and
pypdfbox at 72 DPI. Pixel-EXACT parity is impossible (Pillow vs Java2D AA), so
we compare the same coarse fingerprint as the rest of the render oracle suite:
exact dimensions plus a 16x16 average-luminance grid, gated at ``MAD < 6`` /
``MAXDIFF < 60``.

Cases:

* ``hidden``    — ``/F`` = 2  (Hidden)       => must NOT paint (blank page).
* ``no_view``   — ``/F`` = 32 (NoView)       => must NOT paint on screen.
* ``print_only``— ``/F`` = 4  (Print)        => MUST paint (Print irrelevant
                                                  for screen).
* ``no_flags``  — ``/F`` = 0                 => paints.

The flip guard (``test_hidden_flag_off_diverges``) re-renders the ``hidden``
geometry with the Hidden bit cleared and asserts the result is *materially
different* from the Hidden reference — proving the ``/F`` gate is actually
evaluated during rendering, not that every annotation is dropped (or every
annotation painted) regardless.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel.interactive.annotation import PDAnnotationSquare
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as the rest of the render oracle suite — well above the AA ceiling
# (a correct /F-flag render scores MAD ~0) yet far below a gross failure (a
# Hidden/NoView annotation still painted, or a Print-only annotation dropped,
# blows a whole band of cells' luminance).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 200  # media-box side, pt

# /F flag bit values (PDF 32000-1 Table 165).
_FLAG_HIDDEN = 2
_FLAG_PRINT = 4
_FLAG_NO_VIEW = 32


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``RenderProbe.java``."""
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
    """Run RenderProbe on page 0 and parse its (dims, 16x16 grid)."""
    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


# ----------------------------------------------------------------- builders


def _make_square(rect: PDRectangle) -> PDAnnotationSquare:
    """A filled-square markup annotation with a Normal Appearance — a solid
    black interior with a black stroke, so it paints a strongly non-white block
    (suppressing it shifts whole cells from ~0 luminance to 255)."""
    square = PDAnnotationSquare()
    square.set_rectangle(rect)
    square.set_color([0.0, 0.0, 0.0])
    square.set_interior_color([0.0, 0.0, 0.0])
    return square


def _build_flag(path: Path, flags: int) -> None:
    """One filled-square annotation centred on the page, carrying the given
    ``/F`` value. It always has a Normal Appearance, so the only thing that can
    suppress it is the ``/F``-flag render gate."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)

    square = _make_square(PDRectangle(40, 40, 160, 160))
    square.construct_appearances(doc)
    square.set_annotation_flags(flags)
    page.add_annotation(square)

    doc.save(str(path))
    doc.close()


# label -> /F value; expected_painted documented in the test below.
_FLAG_CASES = {
    "hidden": _FLAG_HIDDEN,
    "no_view": _FLAG_NO_VIEW,
    "print_only": _FLAG_PRINT,
    "no_flags": 0,
}


@requires_oracle
@pytest.mark.parametrize("label", list(_FLAG_CASES), ids=list(_FLAG_CASES))
def test_annotation_flag_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """For each ``/F`` case the pypdfbox screen render matches Apache PDFBox
    within the AA gate. Hidden / NoView must be suppressed; Print-only and
    no-flags must paint — a divergence in either direction blows the gate."""
    fixture = tmp_path / f"annot_flag_{label}.pdf"
    _build_flag(fixture, _FLAG_CASES[label])

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

    # (b) Perceptual grid parity. A Hidden/NoView annotation still painted (or a
    # Print-only/no-flags annotation dropped) lands far outside this gate.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — /F-flag render gate diverges from PDFBox, not AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_hidden_flag_off_diverges(tmp_path: Path) -> None:
    """Guard the gate: the SAME geometry with the Hidden bit cleared must render
    *materially different* from the Hidden reference. Proves the ``/F`` gate is
    actually evaluated (the Hidden annotation is suppressed, the unflagged one
    paints), not that everything is dropped — or painted — regardless.
    pypdfbox-vs-pypdfbox so the guard is independent of the Java oracle."""
    hidden_pdf = tmp_path / "annot_flag_hidden.pdf"
    shown_pdf = tmp_path / "annot_flag_shown.pdf"
    _build_flag(hidden_pdf, _FLAG_HIDDEN)
    _build_flag(shown_pdf, 0)

    with PDDocument.load(hidden_pdf) as doc:
        hidden_grid = _grid_from_image(
            PDFRenderer(doc).render_image_with_dpi(0, 72.0)
        )
    with PDDocument.load(shown_pdf) as doc:
        shown_grid = _grid_from_image(
            PDFRenderer(doc).render_image_with_dpi(0, 72.0)
        )

    diffs = [abs(a - b) for a, b in zip(hidden_grid, shown_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    # The 120x120-pt black square is ~36% of the page; suppressing it shifts a
    # large band of cells from ~0 (black) to 255 (white), so the MAD is large.
    assert mad >= _MAD_TOLERANCE, (
        "/F Hidden gate not evaluated: clearing the Hidden bit produced a render "
        f"indistinguishable from the Hidden reference (MAD {mad:.2f})"
    )
