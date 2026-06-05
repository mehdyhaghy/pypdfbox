"""Live Apache PDFBox differential parity for *vertical writing-mode* text
extraction (WMode 1).

Surface: ``PDFTextStripper.getText()`` on a page whose glyphs are painted with
a Type0 font using a vertical CMap (``/Identity-V``). Apache PDFBox consults
``CMap.getWMode()`` and advances each glyph DOWN the page via the vertical
displacement vector, so consecutive glyphs land on successive baselines: the
line-break heuristic then emits **one glyph per line** (top-to-bottom within a
column, right-to-left across columns). On ``show_text("ABC")`` Java emits
``"A\\nB\\nC\\n"``.

As of wave 1491 pypdfbox's lite text-state machine implements the same
behaviour: ``_emit`` detects ``font.is_vertical()`` (WMode 1 from the encoding
CMap) and delegates to ``_emit_vertical``, which emits one ``TextPosition`` per
glyph — offsetting each glyph origin by the font's position vector and stepping
the text cursor DOWN the column by the vertical displacement
``ty = w1y·fontSize + Tc (+ Tw)`` — so the line-grouping heuristic breaks a line
after every glyph. The synthetic ``/Identity-V`` page below therefore extracts
as ``"A\\nB\\nC\\n"`` on both engines.

Decorated ``@requires_oracle`` — skips cleanly without Java + the jar; this is a
developer-machine parity check, not a hard CI gate. Hand-written.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox.pdmodel import PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_TTF = (
    Path(__file__).resolve().parents[3]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _build_vertical_pdf() -> bytes:
    """Build a single-page PDF painting ``"ABC"`` with a vertical
    (``/Identity-V``) Type0 font, so each glyph advances down the page."""
    doc = PDDocument()
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    with _TTF.open("rb") as fh:
        font = PDType0Font.load_vertical(doc, fh, False)
    encoded = font.encode("ABC")
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 20)
        cs.new_line_at_offset(300, 700)
        cs.show_text(encoded)
        cs.end_text()
    sink = io.BytesIO()
    doc.save(sink)
    doc.close()
    return sink.getvalue()


def _build_two_column_vertical_pdf() -> bytes:
    """Build a single-page PDF painting two vertical columns: ``"AB"`` at
    ``x=400`` and ``"CD"`` at ``x=300`` (the *later*, left-most column).

    The columns share baselines (A/C on the top row, B/D on the next), so
    Apache PDFBox emits them in content-stream order by default
    (``A\\nB\\nC\\nD\\n``) and in left-to-right-per-row order under
    ``setSortByPosition(true)`` (``C A\\nD B\\n``)."""
    doc = PDDocument()
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    with _TTF.open("rb") as fh:
        font = PDType0Font.load_vertical(doc, fh, False)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 20)
        cs.new_line_at_offset(400, 700)
        cs.show_text(font.encode("AB"))
        cs.end_text()
        cs.begin_text()
        cs.set_font(font, 20)
        cs.new_line_at_offset(300, 700)
        cs.show_text(font.encode("CD"))
        cs.end_text()
    sink = io.BytesIO()
    doc.save(sink)
    doc.close()
    return sink.getvalue()


def _py_text(pdf_path: Path, *, sort: bool = False) -> str:
    doc = PDDocument.load(str(pdf_path))
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(sort)
        return stripper.get_text(doc)
    finally:
        # try/finally so a Windows file lock is always released.
        doc.close()


@requires_oracle
def test_vertical_writing_mode_pinned(tmp_path: Path) -> None:
    """Pin both engines' output on a vertical-mode page.

    Java steps each glyph down its column → one glyph per line; as of wave
    1491 the lite stripper does the same. This pins the exact string so
    neither side drifts.
    """
    pdf_path = tmp_path / "vertical_abc.pdf"
    pdf_path.write_bytes(_build_vertical_pdf())
    java = run_probe_text("VerticalTextStripProbe", str(pdf_path))
    py = _py_text(pdf_path)
    # Both engines: vertical reading order → one glyph per line, top-to-bottom.
    assert java == "A\nB\nC\n"
    assert py == "A\nB\nC\n"
    assert java == py


@requires_oracle
def test_vertical_writing_mode_matches_pdfbox(tmp_path: Path) -> None:
    """Wave 1491: the lite stripper now reproduces Apache PDFBox's vertical
    writing-mode reading order (one glyph per line, top-to-bottom)."""
    pdf_path = tmp_path / "vertical_abc.pdf"
    pdf_path.write_bytes(_build_vertical_pdf())
    java = run_probe_text("VerticalTextStripProbe", str(pdf_path))
    py = _py_text(pdf_path)
    assert py == java


@requires_oracle
def test_vertical_two_column_default_order(tmp_path: Path) -> None:
    """Two vertical columns, default (content-stream) order: each glyph on
    its own line, columns emitted in paint order. Both engines: ``A B C D``
    one-per-line."""
    pdf_path = tmp_path / "vertical_two_col.pdf"
    pdf_path.write_bytes(_build_two_column_vertical_pdf())
    java = run_probe_text("VerticalTextStripProbe", str(pdf_path))
    py = _py_text(pdf_path)
    assert java == "A\nB\nC\nD\n"
    assert py == java


@requires_oracle
def test_vertical_two_column_sorted_order(tmp_path: Path) -> None:
    """Two vertical columns under ``setSortByPosition(true)``: the comparator
    groups the shared-baseline glyphs into rows ordered left-to-right (C at
    x=300 before A at x=400), one row per baseline — ``C A`` / ``D B``."""
    pdf_path = tmp_path / "vertical_two_col.pdf"
    pdf_path.write_bytes(_build_two_column_vertical_pdf())
    java = run_probe_text("VerticalTextStripProbe", str(pdf_path), "sort")
    py = _py_text(pdf_path, sort=True)
    assert java == "C A\nD B\n"
    assert py == java
