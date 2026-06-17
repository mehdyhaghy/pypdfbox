"""Live Apache PDFBox parity for the ``OverlayPDF`` CLI tool
(``org.apache.pdfbox.tools.OverlayPDF`` vs pypdfbox's
``pypdfbox.tools.overlay_pdf.OverlayPDF``).

OverlayPDF stamps overlay PDFs onto a base document. The load-bearing parity
claim is the *stacking selection* — which overlay file lands on which page when
several selectors are supplied at once. Upstream resolves, per page:

* first page  → ``-first`` overlay (wins over odd/even/default);
* last page   → ``-last`` overlay (wins over odd/even/default);
* odd pages   → ``-odd`` overlay;
* even pages  → ``-even`` overlay;
* otherwise   → ``-default`` overlay.

Because ``PDFTextStripper`` emits the overlay glyph run ahead of the base-page
glyph run, the per-page extracted text string encodes exactly which overlay
landed where (e.g. ``"FIRSTBASE1"`` = the FIRST overlay on base page 1).

The test drives the real upstream CLI through ``OverlayToolProbe`` and compares
its per-page text against pypdfbox's ``OverlayPDF`` CLI output run over the same
inputs. Both sides reload pypdfbox-built PDFs through the same stripper, so any
glyph-spacing artifact is identical on both sides — the comparison is
Java-text == Python-text, not against a hardcoded literal.
"""

from __future__ import annotations

import json
from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.tools.overlay_pdf import OverlayPDF
from tests.oracle.harness import requires_oracle, run_probe_text


def _build(
    path: Path, messages: list[str], *, offset: tuple[int, int] = (72, 700)
) -> None:
    """Build a PDF with one page per message. ``offset`` places the text so a
    base page (at the default 72,700) and an overlay page (at a distinct
    position) do NOT collide in PDFTextStripper output — overlapping glyph
    advances at the same X would otherwise inject phantom spaces / dropped
    characters into the concatenated string, an artifact unrelated to the
    overlay tool's stacking behaviour under test here."""
    doc = PDDocument()
    try:
        for message in messages:
            page = PDPage(PDRectangle.LETTER)
            doc.add_page(page)
            font = PDFontFactory.create_default_font()
            cs = PDPageContentStream(doc, page)
            cs.begin_text()
            cs.set_font(font, 12)
            cs.new_line_at_offset(offset[0], offset[1])
            cs.show_text(message)
            cs.end_text()
            cs.close()
        doc.save(str(path))
    finally:
        doc.close()


def _page_text(path: Path) -> list[str]:
    doc = PDDocument.load(path)
    try:
        stripper = PDFTextStripper()
        out: list[str] = []
        for i in range(doc.get_number_of_pages()):
            stripper.set_start_page(i + 1)
            stripper.set_end_page(i + 1)
            out.append(stripper.get_text(doc).strip())
        return out
    finally:
        doc.close()


@requires_oracle
def test_overlay_default_matches_pdfbox(tmp_path: Path) -> None:
    """A single ``-default`` overlay stamped onto every page of a 3-page base:
    upstream and pypdfbox must produce the same per-page text."""
    base = tmp_path / "base.pdf"
    over = tmp_path / "over.pdf"
    _build(base, ["BASE1", "BASE2", "BASE3"])
    _build(over, ["WATERMARK"], offset=(72, 740))

    java_out = tmp_path / "jout.pdf"
    java = json.loads(
        run_probe_text(
            "OverlayToolProbe", str(java_out), str(base), "-default", str(over)
        )
    )
    assert java["exitCode"] == 0

    py_out = tmp_path / "pyout.pdf"
    rc = OverlayPDF.main(
        ["-i", str(base), "-default", str(over), "-o", str(py_out)]
    )
    assert rc == 0
    py_text = _page_text(py_out)

    assert py_text == java["text"], (
        f"default-overlay text divergence:\n"
        f"  pypdfbox: {py_text}\n  PDFBox:   {java['text']}"
    )
    assert len(py_text) == 3


@requires_oracle
def test_overlay_first_last_odd_even_stacking_matches_pdfbox(
    tmp_path: Path,
) -> None:
    """All four selectors supplied at once over a 3-page base: page 1 should get
    FIRST (winning over ODD), page 2 EVEN, page 3 LAST (winning over ODD).
    Upstream and pypdfbox must agree page-for-page."""
    base = tmp_path / "base.pdf"
    _build(base, ["BASE1", "BASE2", "BASE3"])
    selectors: list[str] = []
    for flag, msg in (
        ("-odd", "ODD"),
        ("-even", "EVEN"),
        ("-first", "FIRST"),
        ("-last", "LAST"),
    ):
        ov = tmp_path / f"{msg.lower()}.pdf"
        _build(ov, [msg], offset=(72, 740))
        selectors += [flag, str(ov)]

    java_out = tmp_path / "jmix.pdf"
    java = json.loads(
        run_probe_text("OverlayToolProbe", str(java_out), str(base), *selectors)
    )
    assert java["exitCode"] == 0

    py_out = tmp_path / "pymix.pdf"
    rc = OverlayPDF.main(["-i", str(base), *selectors, "-o", str(py_out)])
    assert rc == 0
    py_text = _page_text(py_out)

    assert py_text == java["text"], (
        f"first/last/odd/even stacking divergence:\n"
        f"  pypdfbox: {py_text}\n  PDFBox:   {java['text']}"
    )
    assert len(py_text) == 3
    # The winning overlay per page is encoded in the leading token; assert the
    # precedence holds (first/last beat odd) independent of glyph-spacing noise.
    assert py_text[0].startswith("FIRST")
    assert py_text[1].startswith("EVEN")
    assert py_text[2].startswith("LAST")
