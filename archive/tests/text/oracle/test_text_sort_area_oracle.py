"""Live Apache PDFBox differential parity tests for PDFTextStripper
sort-by-position + page-range and PDFTextStripperByArea region extraction.

Each test builds a deterministic PDF *with pypdfbox* (a Standard-14
Helvetica font, so PDFBox and pypdfbox resolve identical glyph metrics),
saves it, then runs the ``TextSortAreaProbe`` Java program (compiled
against the pinned pdfbox-app-3.0.7 jar) on the same file and compares its
output against pypdfbox's :class:`PDFTextStripper` /
:class:`PDFTextStripperByArea`. Java PDFBox is the reference.

Coverage:

  - **sort-by-position**: a page that draws its lines *out of reading
    order* in the content stream (the lower line emitted first). With
    ``set_sort_by_position(True)`` both engines re-order top-to-bottom;
    with ``(False)`` both keep content-stream order. The test asserts
    pypdfbox == PDFBox in *both* modes AND that the two modes differ
    (proving the geometric re-sort is actually exercised, not a no-op).

  - **page-range**: ``set_start_page`` / ``set_end_page`` on a 3-page
    document — the extracted slice matches PDFBox byte-for-byte.

  - **region extraction**: ``PDFTextStripperByArea.add_region`` /
    ``get_text_for_region`` over a sub-rectangle. The Java probe takes a
    ``Rectangle2D`` (top-left origin, y-down); pypdfbox takes a PDF
    user-space rect (bottom-left origin, y-up). The test translates the
    *same* geometric rectangle between the two conventions
    (``user_y = page_h - (awt_y + h)``) and asserts identical region text.

  - **boundary clipping** (high-value): a glyph whose origin sits exactly
    on a region edge. Java ``Rectangle2D.contains`` is half-open
    (``rx <= x < rx+rw``, ``ry <= y < ry+rh`` in device space); the
    y-flip into pypdfbox user space makes ``min_y`` exclusive / ``max_y``
    inclusive while x stays ``min_x`` inclusive / ``max_x`` exclusive.
    All four edges are pinned against the oracle. This is what drove the
    wave-1439 fix in ``pdf_text_stripper_by_area.process_text_position``
    (the prior code used fully-inclusive ``<=`` on both upper edges and
    thus captured glyphs PDFBox drops).

Decorated ``@requires_oracle`` so they skip cleanly without Java + the
jar. Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.text.pdf_text_stripper_by_area import PDFTextStripperByArea
from tests.oracle.harness import requires_oracle, run_probe_text

_PAGE_W = 612.0
_PAGE_H = 792.0

# Run = (x, y, text) in PDF user space (y-up). The content stream draws
# the runs in list order, so to make sort-by-position visibly differ from
# stream order we list a *lower* line before a *higher* one.
_Run = tuple[float, float, str]


def _build_doc(pages: list[list[_Run]], path: Path) -> None:
    """Build a PDF whose pages draw the given runs (in list order) using a
    Standard-14 Helvetica font, then save it to ``path``."""
    doc = PDDocument()
    try:
        font = PDFontFactory.create_default_font("Helvetica")
        for runs in pages:
            page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
            doc.add_page(page)
            cs = PDPageContentStream(doc, page)
            for x, y, txt in runs:
                cs.begin_text()
                cs.set_font(font, 12.0)
                cs.new_line_at_offset(x, y)
                cs.show_text(txt)
                cs.end_text()
            cs.close()
        doc.save(str(path))
    finally:
        doc.close()


def _unescape(s: str) -> str:
    """Reverse the probe's newline/backslash escaping."""
    return s.replace("\\r", "\r").replace("\\n", "\n").replace("\\\\", "\\")


def _split_probe(out: str, prefix: str) -> str:
    """Extract the payload of the ``<PREFIX>:...`` line from probe stdout."""
    for line in out.splitlines():
        if line.startswith(prefix + ":"):
            return _unescape(line[len(prefix) + 1 :])
    raise AssertionError(f"probe output missing {prefix}: line:\n{out}")


# Page 1 draws the SECOND visual line (lower y) before the FIRST (higher
# y) in stream order, plus a top-left and a bottom-right run for region
# extraction. Lines are spaced > one font size apart so each is its own
# line in both engines.
_OUT_OF_ORDER_PAGE: list[_Run] = [
    (72.0, 700.0, "SECOND"),       # lower line, emitted first
    (72.0, 740.0, "FIRST"),        # higher line, emitted second
    (72.0, 720.0, "TOPLEFT"),      # top-left region
    (400.0, 100.0, "BOTTOMRIGHT"),  # bottom-right region
]


@requires_oracle
def test_sort_by_position_matches_pdfbox_and_differs_unsorted(tmp_path: Path) -> None:
    """Sorted output == PDFBox sorted, unsorted == PDFBox unsorted, and
    the two differ (geometric re-sort is exercised)."""
    pdf = tmp_path / "sort.pdf"
    _build_doc([_OUT_OF_ORDER_PAGE], pdf)

    out = run_probe_text("TextSortAreaProbe", "sort", str(pdf))
    java_sorted = _split_probe(out, "SORTED")
    java_unsorted = _split_probe(out, "UNSORTED")

    doc = PDDocument.load(str(pdf))
    try:
        s = PDFTextStripper()
        s.set_sort_by_position(True)
        py_sorted = s.get_text(doc)
        u = PDFTextStripper()
        u.set_sort_by_position(False)
        py_unsorted = u.get_text(doc)
    finally:
        doc.close()

    assert py_sorted == java_sorted
    assert py_unsorted == java_unsorted
    # The page is drawn out of reading order, so the two modes MUST
    # differ — otherwise sorting was a silent no-op.
    assert py_sorted != py_unsorted
    assert java_sorted != java_unsorted
    # Spot-check the geometric re-order: sorted puts the highest line
    # first; unsorted keeps the stream-order lower line first.
    assert py_sorted.index("FIRST") < py_sorted.index("SECOND")
    assert py_unsorted.index("SECOND") < py_unsorted.index("FIRST")


@requires_oracle
def test_page_range_matches_pdfbox(tmp_path: Path) -> None:
    """``set_start_page`` / ``set_end_page`` on a 3-page document matches
    PDFBox's ``setStartPage`` / ``setEndPage`` slice."""
    pdf = tmp_path / "range.pdf"
    _build_doc(
        [
            [(72.0, 700.0, "PAGEONE")],
            [(72.0, 700.0, "PAGETWO")],
            [(72.0, 700.0, "PAGETHREE")],
        ],
        pdf,
    )

    java = _split_probe(
        run_probe_text("TextSortAreaProbe", "range", str(pdf), "2", "3"),
        "RANGE",
    )
    doc = PDDocument.load(str(pdf))
    try:
        s = PDFTextStripper()
        s.set_sort_by_position(True)
        s.set_start_page(2)
        s.set_end_page(3)
        py = s.get_text(doc)
    finally:
        doc.close()
    assert py == java
    # Sanity: page 1 is excluded.
    assert "PAGEONE" not in py
    assert "PAGETWO" in py and "PAGETHREE" in py


def _area_parity(pdf: Path, awt_rect: tuple[float, float, float, float]) -> tuple[str, str]:
    """Run the area probe with the given AWT rect and pypdfbox with the
    same rectangle translated into PDF user space; return (java, py)."""
    ax, ay, w, h = awt_rect
    java = _split_probe(
        run_probe_text(
            "TextSortAreaProbe",
            "area",
            str(pdf),
            *[str(v) for v in awt_rect],
        ),
        "AREA",
    )
    # AWT (top-left origin, y-down) -> PDF user space (bottom-left, y-up).
    user_y = _PAGE_H - (ay + h)
    doc = PDDocument.load(str(pdf))
    try:
        s = PDFTextStripperByArea()
        s.set_sort_by_position(True)
        s.add_region("r", (ax, user_y, w, h))
        s.extract_regions(doc.get_page(0))
        py = s.get_text_for_region("r")
    finally:
        doc.close()
    return java, py


@requires_oracle
def test_region_extraction_matches_pdfbox(tmp_path: Path) -> None:
    """A sub-region capturing only the top-left run matches PDFBox; the
    bottom-right run is excluded by the same geometric clip."""
    pdf = tmp_path / "area.pdf"
    _build_doc([_OUT_OF_ORDER_PAGE], pdf)

    # TOPLEFT is drawn at user (72, 720) -> flipped y = 792 - 720 = 72.
    # An AWT rect around (x≈72, y≈72) catches it; BOTTOMRIGHT (flipped
    # y≈692, x≈400) is well outside.
    java, py = _area_parity(pdf, (50.0, 60.0, 250.0, 40.0))
    assert py == java
    assert "TOPLEFT" in py
    assert "BOTTOMRIGHT" not in py


@requires_oracle
def test_region_bottom_right_matches_pdfbox(tmp_path: Path) -> None:
    """A sub-region capturing only the bottom-right run matches PDFBox."""
    pdf = tmp_path / "area_br.pdf"
    _build_doc([_OUT_OF_ORDER_PAGE], pdf)

    # BOTTOMRIGHT at user (400, 100) -> flipped y = 692. AWT rect around it.
    java, py = _area_parity(pdf, (380.0, 680.0, 200.0, 40.0))
    assert py == java
    assert "BOTTOMRIGHT" in py
    assert "TOPLEFT" not in py


# ---------------------------------------------------------------------------
# Boundary clipping — a glyph straddling each region edge. Java
# ``Rectangle2D.contains`` is half-open; pypdfbox must reproduce the same
# inclusion/exclusion for the exact same geometric rectangle. This drove
# the wave-1439 fix (process_text_position upper bounds were inclusive).
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    ("awt_rect", "expect_glyph"),
    [
        # Single glyph "X" is drawn at user (100, 700) -> flipped (100, 92).
        # left edge: rx == glyph x  -> INSIDE (rx inclusive)
        ((100.0, 80.0, 30.0, 30.0), True),
        # right edge: rx+rw == glyph x -> OUTSIDE (right exclusive)
        ((70.0, 80.0, 30.0, 30.0), False),
        # top edge: ry == glyph flipped-y -> INSIDE (top inclusive)
        ((80.0, 92.0, 40.0, 30.0), True),
        # bottom edge: ry+rh == glyph flipped-y -> OUTSIDE (bottom exclusive)
        ((80.0, 62.0, 40.0, 30.0), False),
    ],
    ids=["left-edge-in", "right-edge-out", "top-edge-in", "bottom-edge-out"],
)
def test_region_boundary_clipping_matches_pdfbox(
    tmp_path: Path,
    awt_rect: tuple[float, float, float, float],
    expect_glyph: bool,
) -> None:
    """A glyph sitting exactly on each of the four region edges is
    included/excluded identically to Java ``Rectangle2D.contains``."""
    pdf = tmp_path / "straddle.pdf"
    _build_doc([[(100.0, 700.0, "X")]], pdf)

    java, py = _area_parity(pdf, awt_rect)
    assert py == java
    # And the parity result agrees with the half-open expectation.
    assert ("X" in py) is expect_glyph
