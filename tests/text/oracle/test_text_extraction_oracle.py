"""Live Apache PDFBox differential parity tests for text extraction.

Each test runs a Java PDFBox "probe" (``oracle/probes/*.java``, compiled
against the pinned pdfbox-app-3.0.7 jar) on a fixture and compares its
stdout against pypdfbox's :class:`PDFTextStripper` /
:class:`PDFTextStripperByArea` on the same input. Java PDFBox is the
reference for text extraction — where pypdfbox diverged, the production
code was fixed (see ``CHANGES.md`` / ``HISTORY.md``); the few remaining
divergences are rooted outside ``pypdfbox/text/`` (the lite extractor's
flat text-state machine does not apply the page CTM / ``cm`` operator,
so producers that fold the point size into ``Tm`` and position each line
with ``cm`` are mis-scaled) and are ``xfail``-ed with a precise reason
rather than weakened.

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
def test_text_area_empty_region_is_empty() -> None:
    """A region that contains no glyphs yields ``""`` (no stray trailing
    separator) — matches Java's empty ``StringWriter`` for an unmatched
    region."""
    fixture = _FIXTURES / "pdfwriter" / "unencrypted.pdf"
    doc = PDDocument.load(str(fixture))
    try:
        stripper = PDFTextStripperByArea()
        stripper.add_region("nowhere", (-100.0, -100.0, 1.0, 1.0))
        stripper.extract_regions(doc.get_page(0))
        assert stripper.get_text_for_region("nowhere") == ""
    finally:
        doc.close()


# ---- Documented cross-module divergences (xfail with a precise reason) ----
#
# The lite text stripper's ``_extract_positions`` runs a flat text-state
# machine that intentionally ignores the page CTM / ``cm`` operator and
# reports the bare ``Tf`` operand as the glyph size (see the comment block
# at ``pdf_text_stripper.py::_extract_positions``). Producers that fold the
# real point size into the ``Tm`` scale (``14 0 0 14 … Tm`` with ``1 Tf``)
# AND position each line with a per-line ``cm`` translation therefore land
# every glyph at the same (collapsed) Y with size 1.0, defeating the
# line-break heuristic. Fixing this needs a graphics-state/CTM stack, which
# lives in the content-stream engine (owned elsewhere), not in
# ``pypdfbox/text/``. We xfail these rather than weaken the comparison so
# the parity gap stays visible and flips to a pass once the engine grows
# CTM tracking.


@requires_oracle
@pytest.mark.xfail(
    reason="lite text-state machine ignores the per-line `cm` (CTM) operator; "
    "BidiSample.pdf positions every line via `cm` with a `1 Tf` / Tm-scaled "
    "size, so all glyphs collapse to one line. Root cause is in the content-"
    "stream engine (CTM/graphics-state stack), outside pypdfbox/text/. "
    "BiDi reordering itself is ported (wave 1387).",
    strict=True,
)
def test_bidi_sample_line_layout_matches_pdfbox() -> None:
    fixture = _FIXTURES / "text" / "BidiSample.pdf"
    java = run_probe_text("TextExtractProbe", str(fixture))
    py = _py_text(fixture)
    assert py == java


@requires_oracle
@pytest.mark.xfail(
    reason="lite text-state machine reports the `Tf` operand (1.0) as the glyph "
    "size and ignores the Tm scale, so the word-gap / space-width heuristic "
    "operates on the wrong baseline for eu-001.pdf (real size folded into "
    "`13.98 … Tm`). Effective-size scaling is entangled with the size-1.0 "
    "line-break calibration and is tracked as a content-stream-engine "
    "follow-up, not a pypdfbox/text/ fix.",
    strict=True,
)
def test_eu001_word_spacing_matches_pdfbox() -> None:
    fixture = _FIXTURES / "text" / "input" / "eu-001.pdf"
    java = run_probe_text("TextExtractProbe", str(fixture))
    py = _py_text(fixture)
    assert py == java


@requires_oracle
@pytest.mark.xfail(
    reason="PDFBOX-3110-poems-beads.pdf uses the same per-line `cm` producer "
    "pattern as BidiSample plus article-thread (/B beads) ordering; the lite "
    "extractor's bead/CTM handling does not reproduce Java's reading order. "
    "Root cause spans the content-stream engine, outside pypdfbox/text/.",
    strict=True,
)
def test_poems_beads_order_matches_pdfbox() -> None:
    fixture = _FIXTURES / "pdfwriter" / "PDFBOX-3110-poems-beads.pdf"
    java = run_probe_text("TextExtractProbe", str(fixture))
    py = _py_text(fixture)
    assert py == java
