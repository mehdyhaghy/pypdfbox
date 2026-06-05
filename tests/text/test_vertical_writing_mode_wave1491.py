"""Model-layer pins for vertical writing-mode (WMode 1) text extraction.

Wave 1491 taught the lite ``PDFTextStripper`` to consume the encoding CMap's
WMode. When the active font is vertical (``/Identity-V`` etc.), ``_emit``
delegates to ``_emit_vertical``, which emits one ``TextPosition`` per glyph,
offsets each glyph origin by the font's position vector, and steps the text
cursor DOWN the column by the vertical displacement vector. The line-grouping
heuristic then breaks a line after every glyph, so a vertical run extracts as
one glyph per line (top-to-bottom within a column).

These tests pin that behaviour purely against the pypdfbox model layer (no Java
oracle): they build a synthetic ``/Identity-V`` Type0 font with the bundled
Liberation TTF, save + reload the page, and assert the extracted string and the
per-glyph TextPosition geometry. Hand-written.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox.pdmodel import PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper

_TTF = (
    Path(__file__).resolve().parents[2]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _vertical_pdf(text: str, x: float = 300.0, y: float = 700.0) -> bytes:
    doc = PDDocument()
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    with _TTF.open("rb") as fh:
        font = PDType0Font.load_vertical(doc, fh, False)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 20)
        cs.new_line_at_offset(x, y)
        cs.show_text(font.encode(text))
        cs.end_text()
    sink = io.BytesIO()
    doc.save(sink)
    doc.close()
    return sink.getvalue()


def test_vertical_run_extracts_one_glyph_per_line(tmp_path: Path) -> None:
    pdf = tmp_path / "v.pdf"
    pdf.write_bytes(_vertical_pdf("ABC"))
    doc = PDDocument.load(str(pdf))
    try:
        assert PDFTextStripper().get_text(doc) == "A\nB\nC\n"
    finally:
        doc.close()


def test_horizontal_run_unaffected(tmp_path: Path) -> None:
    """A horizontal (``/Identity-H``) Type0 font must stay on one line — the
    vertical branch is gated on ``font.is_vertical()``."""
    doc = PDDocument()
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    with _TTF.open("rb") as fh:
        font = PDType0Font.load(doc, fh, True)
    assert not font.is_vertical()
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 20)
        cs.new_line_at_offset(100, 700)
        cs.show_text(font.encode("ABC"))
        cs.end_text()
    sink = io.BytesIO()
    doc.save(sink)
    doc.close()
    pdf = tmp_path / "h.pdf"
    pdf.write_bytes(sink.getvalue())
    doc2 = PDDocument.load(str(pdf))
    try:
        assert PDFTextStripper().get_text(doc2) == "ABC\n"
    finally:
        doc2.close()


def test_vertical_positions_step_down_the_column(tmp_path: Path) -> None:
    """Each emitted ``TextPosition`` is a single glyph whose origin steps DOWN
    the page (decreasing user-space Y) by the vertical displacement
    (``|w1y|·fontSize = 1.0·20 = 20`` user-space units per glyph)."""
    pdf = tmp_path / "v.pdf"
    pdf.write_bytes(_vertical_pdf("ABC"))
    # ``process_page`` binds the active page so the font (and its WMode) is
    # resolved; it stashes the per-article TextPositions for introspection.
    doc = PDDocument.load(str(pdf))
    try:
        page = next(iter(doc.get_pages()))
        stripper = PDFTextStripper()
        stripper.process_page(page)
        positions = stripper.get_characters_by_article()[0]
    finally:
        doc.close()
    assert [p.text for p in positions] == ["A", "B", "C"]
    ys = [p.y for p in positions]
    # Strictly decreasing — glyphs march down the page.
    assert ys[0] > ys[1] > ys[2]
    # Step ~ 20 user-space units (1.0 em vertical displacement × 20pt).
    assert abs((ys[0] - ys[1]) - 20.0) < 0.5
    assert abs((ys[1] - ys[2]) - 20.0) < 0.5
