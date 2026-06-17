"""Live Apache PDFBox differential parity for
``PDFTextStripper.setShouldSeparateByBeads`` over a page that actually
carries thread beads (articles) — the previously-uncovered branch.

Earlier waves pinned the ``setShouldSeparateByBeads`` flag round-trip on a
*bead-free* page (see ``test_pdf_text_stripper_setters_wave1370.py``, whose
comment notes "no beads on the test pages"). This file targets the
load-bearing case: a two-column page whose ``/B`` array declares ONE bead
per column. The show-text operators are emitted RIGHT column first, then
LEFT, so the content-stream order differs from the visual reading order on
both axes.

With ``set_sort_by_position(True)``:

* ``set_should_separate_by_beads(True)`` (the upstream default) groups the
  text by article — the whole LEFT column (top-to-bottom) then the whole
  RIGHT column. Upstream wraps each article in ``startArticle`` /
  ``endArticle`` whose default markers are "", so the two columns
  concatenate with NO separator between them
  (``LeftTop\\nLeftBotRightTop\\nRightBot``).
* ``set_should_separate_by_beads(False)`` ignores the beads, so the
  geometric sort interleaves both columns per shared baseline
  (``LeftTop RightTop\\nLeftBot RightBot``).

The two modes MUST differ, proving bead bucketing is exercised, and BOTH
must match Java PDFBox byte-for-byte. Wave 1483 fixed a divergence where the
lite stripper injected a hard line separator between bead buckets; upstream
emits the (empty by default) article markers instead.

The PDF is built with pypdfbox (Standard-14 Helvetica, so PDFBox and
pypdfbox resolve identical glyph metrics), then the ``BeadSeparationProbe``
(compiled against the pinned pdfbox-app-3.0.7 jar) runs on the same file.
Java PDFBox is the reference.

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.interactive.pagenavigation import PDThreadBead
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_PAGE_W = 612.0
_PAGE_H = 792.0

# (x, y, text) in PDF user space (y-up); the content stream draws the runs
# in list order — RIGHT column first, then LEFT.
_RUNS: list[tuple[float, float, str]] = [
    (350.0, 700.0, "RightTop"),
    (350.0, 650.0, "RightBot"),
    (72.0, 700.0, "LeftTop"),
    (72.0, 650.0, "LeftBot"),
]

# Bead 0 covers the LEFT column, bead 1 the RIGHT column (PDF bottom-up
# coordinates). The bead-chain order (left, then right) drives the article
# reading order.
_LEFT_BEAD = (60.0, 600.0, 200.0, 760.0)
_RIGHT_BEAD = (340.0, 600.0, 500.0, 760.0)


def _build_doc(path: Path) -> None:
    doc = PDDocument()
    try:
        font = PDFontFactory.create_default_font("Helvetica")
        page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
        doc.add_page(page)
        cs = PDPageContentStream(doc, page)
        for x, y, txt in _RUNS:
            cs.begin_text()
            cs.set_font(font, 12.0)
            cs.new_line_at_offset(x, y)
            cs.show_text(txt)
            cs.end_text()
        cs.close()
        left = PDThreadBead()
        left.set_rectangle(PDRectangle(*_LEFT_BEAD))
        right = PDThreadBead()
        right.set_rectangle(PDRectangle(*_RIGHT_BEAD))
        page.set_thread_beads([left, right])
        doc.save(str(path))
    finally:
        doc.close()


def _unescape(s: str) -> str:
    return s.replace("\\r", "\r").replace("\\n", "\n").replace("\\\\", "\\")


def _split_probe(out: str, prefix: str) -> str:
    for line in out.splitlines():
        if line.startswith(prefix + ":"):
            return _unescape(line[len(prefix) + 1 :])
    raise AssertionError(f"probe output missing {prefix}: line:\n{out}")


def _py_text(pdf: Path, separate: bool, add_more_formatting: bool = False) -> str:
    doc = PDDocument.load(str(pdf))
    try:
        s = PDFTextStripper()
        s.set_sort_by_position(True)
        s.set_should_separate_by_beads(separate)
        s.set_add_more_formatting(add_more_formatting)
        return s.get_text(doc)
    finally:
        doc.close()


# --- regression: the expected strings, oracle-confirmed (pass WITHOUT java) -

_EXPECTED_BEADS_ON = "LeftTop\nLeftBotRightTop\nRightBot\n"
_EXPECTED_BEADS_OFF = "LeftTop RightTop\nLeftBot RightBot\n"


def test_beads_on_groups_by_article_no_separator(tmp_path: Path) -> None:
    """Bead-separation ON groups text by article; the two articles
    concatenate with no separator (default empty article markers)."""
    pdf = tmp_path / "beads.pdf"
    _build_doc(pdf)
    assert _py_text(pdf, separate=True) == _EXPECTED_BEADS_ON


def test_beads_off_interleaves_columns_by_baseline(tmp_path: Path) -> None:
    """Bead-separation OFF lets the geometric sort interleave both columns
    on each shared baseline."""
    pdf = tmp_path / "beads.pdf"
    _build_doc(pdf)
    assert _py_text(pdf, separate=False) == _EXPECTED_BEADS_OFF


def test_bead_modes_differ(tmp_path: Path) -> None:
    """The two modes must differ — proving bead bucketing is exercised."""
    pdf = tmp_path / "beads.pdf"
    _build_doc(pdf)
    assert _py_text(pdf, separate=True) != _py_text(pdf, separate=False)


# --- live differential (skips without java + jar) --------------------------


@requires_oracle
def test_beads_on_matches_pdfbox(tmp_path: Path) -> None:
    pdf = tmp_path / "beads.pdf"
    _build_doc(pdf)
    out = run_probe_text("BeadSeparationProbe", str(pdf))
    java_on = _split_probe(out, "BEADS_ON")
    assert _py_text(pdf, separate=True) == java_on
    assert java_on == _EXPECTED_BEADS_ON


@requires_oracle
def test_beads_off_matches_pdfbox(tmp_path: Path) -> None:
    pdf = tmp_path / "beads.pdf"
    _build_doc(pdf)
    out = run_probe_text("BeadSeparationProbe", str(pdf))
    java_off = _split_probe(out, "BEADS_OFF")
    assert _py_text(pdf, separate=False) == java_off
    assert java_off == _EXPECTED_BEADS_OFF


@requires_oracle
def test_bead_modes_differ_in_pdfbox(tmp_path: Path) -> None:
    pdf = tmp_path / "beads.pdf"
    _build_doc(pdf)
    out = run_probe_text("BeadSeparationProbe", str(pdf))
    assert _split_probe(out, "BEADS_ON") != _split_probe(out, "BEADS_OFF")


# --- add_more_formatting: article markers promoted to the line separator ---
#
# Upstream ``writeText`` promotes ``paragraphEnd`` / ``pageStart`` /
# ``articleStart`` / ``articleEnd`` to the line separator when
# ``setAddMoreFormatting(true)`` (PDFTextStripper.java:243-250). The
# observable consequence on a beaded page is that the two article (bead)
# buckets — concatenated directly with the default empty markers — become
# separated once the article markers carry the line separator.
#
# Byte-for-byte equality with Java under add_more_formatting is NOT asserted:
# the exact newline count between/around lines depends on upstream's
# per-paragraph ``writeParagraphStart`` / ``writeParagraphEnd`` cadence, which
# the lite stripper approximates (the documented average-advance / per-run
# layout carve-out, a deferred follow-up). We pin only the article-marker promotion
# property, which is the load-bearing add_more_formatting effect.


def test_add_more_formatting_separates_bead_buckets(tmp_path: Path) -> None:
    """With ``add_more_formatting`` the article markers carry the line
    separator, so adjacent bead buckets are split (default markers join
    them)."""
    pdf = tmp_path / "beads.pdf"
    _build_doc(pdf)
    plain = _py_text(pdf, separate=True)
    formatted = _py_text(pdf, separate=True, add_more_formatting=True)
    # Default markers join the buckets ("LeftBotRightTop"); the promoted
    # article separator breaks that join.
    assert "LeftBotRightTop" in plain
    assert "LeftBotRightTop" not in formatted
    assert "LeftBot" in formatted
    assert "RightTop" in formatted


def test_add_more_formatting_is_observable(tmp_path: Path) -> None:
    """``add_more_formatting`` changes the output (markers promoted to the
    line separator)."""
    pdf = tmp_path / "beads.pdf"
    _build_doc(pdf)
    assert _py_text(pdf, separate=True) != _py_text(
        pdf, separate=True, add_more_formatting=True
    )
