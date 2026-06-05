"""Live Apache PDFBox differential parity tests for text extraction.

Each test runs a Java PDFBox "probe" (``oracle/probes/*.java``, compiled
against the pinned pdfbox-app-3.0.7 jar) on a fixture and compares its
stdout against pypdfbox's :class:`PDFTextStripper` /
:class:`PDFTextStripperByArea` on the same input. Java PDFBox is the
reference for text extraction — where pypdfbox diverged, the production
code was fixed (see ``CHANGES.md`` / ``HISTORY.md``). Wave 1409 made the
lite extractor CTM-aware (``q`` / ``Q`` / ``cm`` graphics-state stack +
text-rendering-matrix composition), so producers that fold the point size
into ``Tm`` and position each line with ``cm`` now lay out correctly. The
few remaining divergences are deferred layout features (multi-column table
reading order; article-thread bead stitching + per-glyph width clipping)
and are ``xfail``-ed with a precise reason rather than weakened.

These tests are decorated ``@requires_oracle`` so they skip cleanly on
machines without Java + the jar; they are a developer-machine parity
check, not a hard CI gate. Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.text.pdf_text_stripper_by_area import PDFTextStripperByArea
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def _py_text(path: Path) -> str:
    """Extract text with pypdfbox's default stripper, closing the doc."""
    doc = PDDocument.load(str(path))
    try:
        return PDFTextStripper().get_text(doc)
    finally:
        # try/finally so a Windows file lock is always released.
        doc.close()


# Fixtures whose pypdfbox output matches Java PDFBox byte-for-byte. These
# lock the parity in so a future regression in the line/word/paragraph
# heuristics (or the page/article separators) is caught immediately.
_EXACT_MATCH = [
    "pdmodel/with_outline.pdf",
    "pdmodel/page_tree_multiple_levels.pdf",
    "pdfwriter/unencrypted.pdf",
    "multipdf/rot0.pdf",
    "multipdf/rot90.pdf",
    "multipdf/rot180.pdf",
    "multipdf/rot270.pdf",
    "multipdf/PDFA3A.pdf",
]


@requires_oracle
@pytest.mark.parametrize("rel", _EXACT_MATCH)
def test_text_extraction_matches_pdfbox(rel: str) -> None:
    fixture = _FIXTURES / rel
    java = run_probe_text("TextExtractProbe", str(fixture))
    py = _py_text(fixture)
    assert py == java


@requires_oracle
def test_with_outline_has_no_spurious_blank_lines() -> None:
    """Regression for the wave-1408 blank-line bug.

    ``with_outline.pdf`` triggers a paragraph separation (vertical drop)
    inside several pages. pypdfbox previously defaulted ``paragraph_end``
    to ``"\\n"`` while also emitting ``line_separator`` (``"\\n"``) at the
    same break, so every paragraph boundary produced ``"\\n\\n"`` — a
    blank line the Java oracle never emits (Java's ``paragraphEnd`` default
    is ``""``). The fix sets pypdfbox's default to ``""`` to match.
    """
    fixture = _FIXTURES / "pdmodel" / "with_outline.pdf"
    java = run_probe_text("TextExtractProbe", str(fixture))
    py = _py_text(fixture)
    assert py == java
    # No double-newline (blank line) anywhere except the document's own
    # trailing terminator handling.
    assert "\n\n" not in py
    assert py.count("\n") == java.count("\n")


@requires_oracle
def test_text_area_region_matches_pdfbox() -> None:
    """``PDFTextStripperByArea`` over a full-page region matches Java.

    The ``TextAreaProbe`` uses Java's ``Rectangle2D`` (origin top-left,
    y-down); pypdfbox's ``add_region`` consumes a PDF user-space rect
    (origin bottom-left, y-up). A full-page ``(0, 0, w, h)`` rectangle
    selects the same glyphs in either convention, so it is the clean
    cross-implementation comparison point (sub-region coordinate-flip
    parity is exercised in ``tests/text/upstream``).
    """
    fixture = _FIXTURES / "pdfwriter" / "unencrypted.pdf"
    rect = (0.0, 0.0, 700.0, 900.0)
    java = run_probe_text("TextAreaProbe", str(fixture), *[str(v) for v in rect])

    doc = PDDocument.load(str(fixture))
    try:
        stripper = PDFTextStripperByArea()
        stripper.set_sort_by_position(True)
        stripper.add_region("r", rect)
        stripper.extract_regions(doc.get_page(0))
        py = stripper.get_text_for_region("r")
    finally:
        doc.close()
    assert py == java


@requires_oracle
def test_text_area_empty_region_matches_pdfbox() -> None:
    """A region that is extracted but captures no glyphs yields the page
    line separator (``"\\n"``), not the empty string.

    Java's ``PDFTextStripperByArea`` runs the standard ``writePage`` loop
    once per registered region whether or not the region matched anything,
    so its per-region ``StringWriter`` always ends in one line separator.
    Verified against the live PDFBox oracle (wave 1439 corrected pypdfbox,
    which previously suppressed the trailing separator for empty regions).
    Note the region must sit *within* a contents-bearing page — a page
    with no ``/Contents`` skips ``writePage`` and yields ``""`` in both
    engines (see ``test_pdf_text_stripper_by_area`` blank-page case)."""
    fixture = _FIXTURES / "pdfwriter" / "unencrypted.pdf"
    # AWT rect far off the page → matches no glyph but is still extracted.
    java = run_probe_text(
        "TextSortAreaProbe", "area", str(fixture), "-100", "-100", "1", "1"
    )
    java_text = java.split("AREA:", 1)[1].split("\n", 1)[0].replace("\\n", "\n")
    doc = PDDocument.load(str(fixture))
    try:
        stripper = PDFTextStripperByArea()
        stripper.set_sort_by_position(True)
        stripper.add_region("nowhere", (-100.0, -100.0, 1.0, 1.0))
        stripper.extract_regions(doc.get_page(0))
        py = stripper.get_text_for_region("nowhere")
    finally:
        doc.close()
    assert py == java_text
    assert py == "\n"


# ---- CTM-aware extraction (wave 1409) ----
#
# The lite text stripper now tracks the page CTM via a graphics-state
# stack (``q`` / ``Q`` / ``cm``) and composes it with the text matrix to
# recover the device-space glyph origin and the *effective* font size
# (``Tf`` operand scaled by the text-rendering matrix), mirroring upstream
# ``PDFStreamEngine.showText`` / ``TextPosition``. Producers that fold the
# point size into ``Tm`` (``14 0 0 14 … Tm`` with a ``1 Tf``) and position
# each line with a per-line ``cm`` translation — which previously collapsed
# every glyph onto one baseline at size 1.0 — now lay out correctly. See
# ``pdf_text_stripper.py::_text_rendering_matrix``.


@requires_oracle
def test_bidi_sample_line_layout_matches_pdfbox() -> None:
    """BidiSample.pdf positions every line via a per-line ``cm`` with a
    ``1 Tf`` / Tm-scaled size. With CTM-aware emission the line layout,
    effective sizes, and BiDi reordering (ported wave 1387) all match
    Java byte-for-byte."""
    fixture = _FIXTURES / "text" / "BidiSample.pdf"
    java = run_probe_text("TextExtractProbe", str(fixture))
    py = _py_text(fixture)
    assert py == java


@requires_oracle
def test_eu001_word_spacing_matches_pdfbox() -> None:
    """eu-001.pdf is a wide threshold table whose value cells sit on a
    slightly different baseline than their (wrapped) row label (Y-delta <
    glyph height). Wave 1489 ported upstream ``writePage``'s running
    vertical-span ``overlap`` line grouping (``maxYForLine`` /
    ``maxHeightForLine``) plus a real per-font glyph height
    (``computeFontHeight``), so label+values group onto one logical line
    exactly as Java does — byte-for-byte parity."""
    fixture = _FIXTURES / "text" / "input" / "eu-001.pdf"
    java = run_probe_text("TextExtractProbe", str(fixture))
    py = _py_text(fixture)
    assert py == java


@requires_oracle
@pytest.mark.xfail(
    reason="CTM-aware emission (wave 1409) fixes the per-line `cm` size/baseline "
    "(same producer pattern as BidiSample), but PDFBOX-3110-poems-beads.pdf "
    "additionally relies on article-thread (/B bead) reading order: Java "
    "stitches the two bead columns so a column's last line continues onto the "
    "next column's first line, and clips glyphs to bead rectangles using true "
    "per-glyph widths. The lite extractor's bead bucketing + average-advance "
    "width estimate do not reproduce that stitch/clip. Article-thread reading "
    "order and per-glyph metrics are deferred features, not the CTM root cause.",
    strict=True,
)
def test_poems_beads_order_matches_pdfbox() -> None:
    fixture = _FIXTURES / "pdfwriter" / "PDFBOX-3110-poems-beads.pdf"
    java = run_probe_text("TextExtractProbe", str(fixture))
    py = _py_text(fixture)
    assert py == java
