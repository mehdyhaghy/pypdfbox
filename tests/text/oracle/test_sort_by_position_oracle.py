"""Live Apache PDFBox differential parity for ``PDFTextStripper`` sort-by-
position applied to a TWO-COLUMN layout whose show-text operators are
emitted out of visual reading order.

The companion ``test_text_sort_area_oracle.py`` pins the *vertical* re-sort
(a lower line emitted before a higher line) and
``test_text_sort_inline_oracle.py`` pins the *intra-line* X re-sort (two
words on one baseline emitted right-then-left). This file targets the
distinct *multi-column reading-order reconstruction* surface: a page is laid
out as two columns, the RIGHT column's lines are emitted in the content
stream BEFORE the LEFT column's, and within each column the lines are drawn
bottom-to-top. With ``set_sort_by_position(True)`` the engine must
reconstruct the visual reading order (left column top-to-bottom, then right
column top-to-bottom); with ``(False)`` it preserves content-stream order.

This stresses the ``TextPositionComparator`` cross-line / cross-column branch
(grouping runs by baseline / vertical overlap, then ordering left-to-right by
X, falling back to top-to-bottom by Y for vertically disjoint runs) far more
than the single-line cases do — a two-column page produces many runs whose
relative order depends on the comparator's transitivity.

Each test builds a deterministic PDF *with pypdfbox* (Standard-14 Helvetica,
so PDFBox and pypdfbox resolve identical glyph metrics), then runs the
``SortByPositionProbe`` Java program (compiled against the pinned
pdfbox-app-3.0.7 jar) on the same file and compares its output against
pypdfbox's :class:`PDFTextStripper` in both modes. Java PDFBox is the
reference. The test also asserts the two modes differ (so the re-sort is
proven exercised, not a silent no-op).

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_PAGE_W = 612.0
_PAGE_H = 792.0

# Run = (x, y, text) in PDF user space (y-up). The content stream draws the
# runs in list order.
_Run = tuple[float, float, str]

# Two columns. LEFT column at x=72, RIGHT column at x=350 (a wide gap so both
# engines treat the columns as separate words on each shared baseline). Each
# column has three lines, spaced > one font size apart so each is its own
# line. The RIGHT column is emitted FIRST (out of reading order), and within
# each column the BOTTOM line is emitted before the TOP line — so stream
# order is the full reverse of the visual reading order on both axes.
_LEFT_X = 72.0
_RIGHT_X = 350.0
_Y_TOP = 700.0
_Y_MID = 660.0
_Y_BOT = 620.0

_TWO_COLUMN_PAGE: list[_Run] = [
    # RIGHT column, bottom-to-top, emitted first.
    (_RIGHT_X, _Y_BOT, "Rthree"),
    (_RIGHT_X, _Y_MID, "Rtwo"),
    (_RIGHT_X, _Y_TOP, "Rone"),
    # LEFT column, bottom-to-top, emitted second.
    (_LEFT_X, _Y_BOT, "Lthree"),
    (_LEFT_X, _Y_MID, "Ltwo"),
    (_LEFT_X, _Y_TOP, "Lone"),
]


def _build_doc(runs: list[_Run], path: Path) -> None:
    """Build a single-page PDF drawing ``runs`` (in list order) with a
    Standard-14 Helvetica font, then save it to ``path``."""
    doc = PDDocument()
    try:
        font = PDFontFactory.create_default_font("Helvetica")
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


def _extract_both_modes(pdf: Path) -> tuple[str, str]:
    """Return (sorted, unsorted) pypdfbox extraction for the document."""
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
    return py_sorted, py_unsorted


@requires_oracle
def test_two_column_sort_by_position_matches_pdfbox_and_differs(
    tmp_path: Path,
) -> None:
    """A two-column page whose right column is emitted before the left and
    whose lines are drawn bottom-to-top: sorted output == PDFBox sorted,
    unsorted == PDFBox unsorted, and the two modes differ (proving the
    multi-column re-sort is exercised)."""
    pdf = tmp_path / "two_column.pdf"
    _build_doc(_TWO_COLUMN_PAGE, pdf)

    out = run_probe_text("SortByPositionProbe", str(pdf))
    java_sorted = _split_probe(out, "SORTED")
    java_unsorted = _split_probe(out, "UNSORTED")

    py_sorted, py_unsorted = _extract_both_modes(pdf)

    assert py_sorted == java_sorted
    assert py_unsorted == java_unsorted
    # The page is drawn out of reading order on both axes, so the two modes
    # MUST differ — otherwise sorting was a silent no-op.
    assert py_sorted != py_unsorted
    assert java_sorted != java_unsorted


@requires_oracle
def test_two_column_sort_reading_order_is_left_column_first(
    tmp_path: Path,
) -> None:
    """The sorted reading order reconstructs left-column top-to-bottom,
    then right-column top-to-bottom — matching PDFBox row-by-row pairing of
    the two columns sharing each baseline."""
    pdf = tmp_path / "two_column_order.pdf"
    _build_doc(_TWO_COLUMN_PAGE, pdf)

    java_sorted = _split_probe(
        run_probe_text("SortByPositionProbe", str(pdf)), "SORTED"
    )
    py_sorted, _ = _extract_both_modes(pdf)

    assert py_sorted == java_sorted
    # Each baseline is shared by a left + right run; the comparator orders
    # them left-then-right, and the three baselines top-to-bottom. So the
    # full sorted reading order pairs the columns row by row.
    for tag in ("Lone", "Ltwo", "Lthree", "Rone", "Rtwo", "Rthree"):
        assert tag in py_sorted
    # Top row before middle row before bottom row.
    assert py_sorted.index("Lone") < py_sorted.index("Ltwo") < py_sorted.index("Lthree")
    assert py_sorted.index("Rone") < py_sorted.index("Rtwo") < py_sorted.index("Rthree")
    # On each shared baseline the left run precedes the right run.
    assert py_sorted.index("Lone") < py_sorted.index("Rone")
    assert py_sorted.index("Ltwo") < py_sorted.index("Rtwo")
    assert py_sorted.index("Lthree") < py_sorted.index("Rthree")
