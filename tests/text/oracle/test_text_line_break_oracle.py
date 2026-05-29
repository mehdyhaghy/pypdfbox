"""Live Apache PDFBox differential parity for line-break (newline) insertion.

``PDFTextStripper.getText()`` inserts a *line separator* whenever the text
cursor drops to a new baseline — i.e. a ``Td`` / ``TD`` / ``T*`` (or new ``BT``
block) that moves the glyph origin down by more than the line tolerance — and
inserts NO line separator between two runs that share the same baseline (they
get a word separator or nothing). This module pins that decision against Java
PDFBox 3.0.7.

The default line separator (``"\n"``) collapses onto ordinary whitespace, so a
misplaced newline is invisible in a default-config diff. ``TextLineBreakProbe``
overrides ONLY the line separator with a distinctive ``"|L|"`` sentinel (word
separator stays the default ``" "``), making the exact insertion point of every
vertical-baseline line break observable. pypdfbox is configured identically.

Each test builds a deterministic one-page PDF *with pypdfbox* (Standard-14
Helvetica, so PDFBox and pypdfbox resolve identical glyph metrics) drawing runs
at controlled baselines, runs the probe over the same file, and asserts
pypdfbox's :class:`PDFTextStripper` places line breaks identically.

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

# Run = (x, y, text) in PDF user space (y-up).
_Run = tuple[float, float, str]


def _build_doc(runs: list[_Run], path: Path) -> None:
    """Build a one-page PDF drawing each run as its own BT…ET block with an
    absolute new_line_at_offset, then save it to ``path``. Each run therefore
    sets its own baseline, so the vertical spacing between runs is exactly the
    difference of their y coordinates."""
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


def _py_text(path: Path) -> str:
    doc = PDDocument.load(str(path))
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(True)
        stripper.set_line_separator("|L|")
        return stripper.get_text(doc)
    finally:
        doc.close()


def _java_text(path: Path) -> str:
    return run_probe_text("TextLineBreakProbe", str(path))


@requires_oracle
def test_three_line_paragraph_matches_pdfbox(tmp_path: Path) -> None:
    """Three lines, each a separate Td drop of one line height (14 pt), extract
    as three lines separated by exactly one line break each — same placement as
    Java PDFBox."""
    pdf = tmp_path / "three_lines.pdf"
    _build_doc(
        [
            (72.0, 700.0, "LineOne"),
            (72.0, 686.0, "LineTwo"),
            (72.0, 672.0, "LineThree"),
        ],
        pdf,
    )
    java = _java_text(pdf)
    py = _py_text(pdf)
    assert py == java
    # Exactly two line breaks (three lines) and no stray ones.
    assert py.count("|L|") == java.count("|L|")
    # The text content is the three runs joined by the sentinel.
    assert "LineOne|L|LineTwo|L|LineThree" in py


@requires_oracle
def test_same_baseline_runs_get_no_line_break(tmp_path: Path) -> None:
    """Two runs on the SAME baseline are NOT separated by a line break (they
    get a word separator / nothing), matching Java PDFBox."""
    pdf = tmp_path / "same_baseline.pdf"
    _build_doc(
        [
            (72.0, 700.0, "Hello"),
            (200.0, 700.0, "World"),
        ],
        pdf,
    )
    java = _java_text(pdf)
    py = _py_text(pdf)
    assert py == java
    # Both runs present, and no line break inserted between them.
    assert "Hello" in py and "World" in py
    assert "|L|" not in py


@requires_oracle
def test_mixed_same_and_new_baseline_matches_pdfbox(tmp_path: Path) -> None:
    """Two runs on baseline A (same line), then a drop to baseline B (new
    line): exactly one line break, placed before the dropped run — identical to
    Java PDFBox."""
    pdf = tmp_path / "mixed.pdf"
    _build_doc(
        [
            (72.0, 700.0, "Alpha"),
            (200.0, 700.0, "Beta"),
            (72.0, 680.0, "Gamma"),
        ],
        pdf,
    )
    java = _java_text(pdf)
    py = _py_text(pdf)
    assert py == java
    assert py.count("|L|") == java.count("|L|")
    # The drop lands before Gamma, not between Alpha and Beta.
    assert "Gamma" in py
    assert "Alpha|L|" not in py


@requires_oracle
def test_tiny_baseline_jitter_is_not_a_line_break(tmp_path: Path) -> None:
    """A sub-tolerance vertical jitter (well under half the font size) does NOT
    trigger a line break in either engine — the runs stay on one logical
    line."""
    pdf = tmp_path / "jitter.pdf"
    _build_doc(
        [
            (72.0, 700.0, "Steady"),
            (160.0, 701.0, "Asabove"),
        ],
        pdf,
    )
    java = _java_text(pdf)
    py = _py_text(pdf)
    assert py == java
    assert py.count("|L|") == java.count("|L|")
