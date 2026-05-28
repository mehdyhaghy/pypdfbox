"""Live Apache PDFBox differential parity for *vertical writing-mode* text
extraction (WMode 1).

Surface: ``PDFTextStripper.getText()`` on a page whose glyphs are painted with
a Type0 font using a vertical CMap (``/Identity-V``). Apache PDFBox consults
``CMap.getWMode()`` and advances each glyph DOWN the page via the vertical
displacement vector, so consecutive glyphs land on successive baselines: the
line-break heuristic then emits **one glyph per line** (top-to-bottom within a
column, right-to-left across columns). On ``show_text("ABC")`` Java emits
``"A\\nB\\nC\\n"``.

pypdfbox's *lite* text-state machine (``pdf_text_stripper.py``) is
horizontal-only: it decodes the whole show-text run as one string, emits it as
a single ``TextPosition`` at one origin, and advances the text cursor solely
along the text matrix's horizontal axis ``(tm_a, tm_b)`` — it never reads the
font's encoding-CMap WMode nor steps the cursor by the vertical displacement
vector. So the same run extracts as ``"ABC\\n"`` — all glyphs collapsed onto
one logical line.

This is a deferred layout feature (per-glyph vertical positioning + the
top-to-bottom / right-to-left column reading order), the same class as the
multi-column-table and article-bead reading-order xfails in
``test_text_extraction_oracle.py``. The parity assertion is a ``strict``
``xfail`` so it flips to a hard failure the day vertical mode is implemented;
the companion pin (``test_*_current_divergence_pinned``) locks BOTH engines'
present output so neither side drifts silently. See ``DEFERRED.md``.

Decorated ``@requires_oracle`` — skips cleanly without Java + the jar; this is a
developer-machine parity check, not a hard CI gate. Hand-written.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

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


def _py_text(pdf_path: Path) -> str:
    doc = PDDocument.load(str(pdf_path))
    try:
        return PDFTextStripper().get_text(doc)
    finally:
        # try/finally so a Windows file lock is always released.
        doc.close()


@requires_oracle
def test_vertical_writing_mode_current_divergence_pinned(tmp_path: Path) -> None:
    """Pin BOTH engines' present output on a vertical-mode page.

    Java steps each glyph down its column → one glyph per line; the lite
    stripper advances horizontally only → all glyphs on one line. This pins
    the exact strings so neither side drifts before the feature lands.
    """
    pdf_path = tmp_path / "vertical_abc.pdf"
    pdf_path.write_bytes(_build_vertical_pdf())
    java = run_probe_text("VerticalTextStripProbe", str(pdf_path))
    py = _py_text(pdf_path)
    # Java: vertical reading order → one glyph per line, top-to-bottom.
    assert java == "A\nB\nC\n"
    # pypdfbox (lite, horizontal-only): the whole run on one line.
    assert py == "ABC\n"
    assert java != py


@requires_oracle
@pytest.mark.xfail(
    reason="Vertical writing mode (WMode 1) reading order is a deferred layout "
    "feature. The lite text-state machine is horizontal-only: it emits each "
    "show-text run as one TextPosition and advances the cursor along the text "
    "matrix's horizontal axis only, ignoring the encoding CMap's WMode and the "
    "vertical displacement vector. Java steps each glyph down its column "
    "(one glyph per line, top-to-bottom within a column, right-to-left across "
    "columns), extracting 'A\\nB\\nC\\n' where pypdfbox extracts 'ABC\\n'. "
    "Same class as the multi-column-table / article-bead reading-order xfails. "
    "See DEFERRED.md.",
    strict=True,
)
def test_vertical_writing_mode_matches_pdfbox(tmp_path: Path) -> None:
    pdf_path = tmp_path / "vertical_abc.pdf"
    pdf_path.write_bytes(_build_vertical_pdf())
    java = run_probe_text("VerticalTextStripProbe", str(pdf_path))
    py = _py_text(pdf_path)
    assert py == java
