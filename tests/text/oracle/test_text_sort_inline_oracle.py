"""Live Apache PDFBox differential parity for ``PDFTextStripper`` sort-by-
position applied to glyphs painted out of reading order *within a single
visual line* (the horizontal, intra-line re-sort case).

The companion ``test_text_sort_area_oracle.py`` already pins the *vertical*
re-sort (a lower line emitted before a higher line). This file targets the
distinct *horizontal* surface that exercises the comparator's same-baseline
X-ordering branch: two words share one baseline (identical ``y``) and the
right-hand word's ``Tj`` is emitted *before* the left-hand word's in the
content stream. With ``set_sort_by_position(True)`` the engine must re-order
them left-to-right; with ``(False)`` it preserves stream order.

Each test builds a deterministic PDF *with pypdfbox* (Standard-14 Helvetica,
so PDFBox and pypdfbox resolve identical glyph metrics), then runs the
``TextSortInlineProbe`` Java program (compiled against the pinned
pdfbox-app-3.0.7 jar) on the same file and compares its output against
pypdfbox's :class:`PDFTextStripper` in both modes. Java PDFBox is the
reference. The test also asserts the two modes differ (so the intra-line
re-sort is proven exercised, not a silent no-op).

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
# runs in list order, so to make the intra-line re-sort visibly differ from
# stream order we list the RIGHT word (higher x) before the LEFT word (lower
# x) at the SAME y — they share one baseline.
_Run = tuple[float, float, str]

# Two words on one baseline (y == 700). "RIGHT" (x = 300) is emitted first,
# "LEFT" (x = 72) second. The x-gap is wide enough that both engines treat
# them as two separate words on the same line (a word separator between them),
# not one run. The third run is a second, lower line also drawn out of x-order
# to cover the multi-line + intra-line interaction.
_OUT_OF_X_ORDER_PAGE: list[_Run] = [
    (300.0, 700.0, "RIGHT"),  # right word, emitted first
    (72.0, 700.0, "LEFT"),    # left word, emitted second (same baseline)
    (300.0, 660.0, "BETA"),   # lower line, right word, emitted first
    (72.0, 660.0, "ALPHA"),   # lower line, left word, emitted second
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


@requires_oracle
def test_inline_sort_by_position_matches_pdfbox_and_differs(tmp_path: Path) -> None:
    """Two words on one baseline painted right-then-left: sorted output ==
    PDFBox sorted (left-to-right), unsorted == PDFBox unsorted (stream
    order), and the two modes differ — proving the intra-line X re-sort
    is exercised."""
    pdf = tmp_path / "inline_sort.pdf"
    _build_doc(_OUT_OF_X_ORDER_PAGE, pdf)

    out = run_probe_text("TextSortInlineProbe", str(pdf))
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
    # The words on each line are drawn right-then-left, so the two modes
    # MUST differ — otherwise the intra-line re-sort was a silent no-op.
    assert py_sorted != py_unsorted
    assert java_sorted != java_unsorted
    # Spot-check the geometric re-order on the top line: sorted puts the
    # left word first; unsorted keeps the stream-order right word first.
    assert py_sorted.index("LEFT") < py_sorted.index("RIGHT")
    assert py_unsorted.index("RIGHT") < py_unsorted.index("LEFT")
    # Lower line mirrors the same intra-line reorder.
    assert py_sorted.index("ALPHA") < py_sorted.index("BETA")
    assert py_unsorted.index("BETA") < py_unsorted.index("ALPHA")
