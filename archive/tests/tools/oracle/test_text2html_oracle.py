"""Live Apache PDFBox parity for ``org.apache.pdfbox.tools.PDFText2HTML``
vs pypdfbox's ``pypdfbox.tools.pdf_text2_html.PDFText2HTML``.

``PDFText2HTML`` is the ``PDFTextStripper`` subclass behind the
``ExtractText -html`` CLI path: it wraps stripped text in minimal HTML
(DOCTYPE / head / title / body, a per-page page-break ``<div>``, a
per-article ``<div>``, a per-paragraph ``<p>``, ``<b>``/``<i>`` font-state
tags, and entity escaping). The ``Text2HtmlProbe`` Java probe constructs
``PDFText2HTML`` and prints ``getText(doc)`` verbatim — exactly the bytes
the CLI emits.

The source PDFs are built through pypdfbox so the input bytes are identical
on both sides; only the produced HTML is compared. Fixtures are scoped to
the converter's own logic (preamble + page/article/paragraph nesting +
escaping + metadata title) and to single-line / same-paragraph layouts, so
the comparison does not depend on the underlying stripper's mid-page
paragraph-separation cadence (a separate, stripper-rooted surface).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.tools.pdf_text2_html import PDFText2HTML
from tests.oracle.harness import requires_oracle, run_probe_text


def _text_page(
    doc: PDDocument, lines: list[tuple[float, float, str]]
) -> None:
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    font = PDFontFactory.create_default_font()
    cs = PDPageContentStream(doc, page)
    cs.begin_text()
    cs.set_font(font, 12)
    last_x = 0.0
    last_y = 0.0
    for x, y, text in lines:
        cs.new_line_at_offset(x - last_x, y - last_y)
        cs.show_text(text)
        last_x, last_y = x, y
    cs.end_text()
    cs.close()


def _py_html(src: Path) -> str:
    with PDDocument.load(src) as doc:
        return PDFText2HTML().get_text(doc)


@requires_oracle
def test_text2html_entity_escaping_matches_pdfbox(tmp_path: Path) -> None:
    src = tmp_path / "simple.pdf"
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "a<b&c>d")])
        doc.save(str(src))

    java = run_probe_text("Text2HtmlProbe", str(src))
    py = _py_html(src)

    assert py == java, f"PDFText2HTML escape divergence:\n  java: {java!r}\n  py:   {py!r}"
    assert "a&lt;b&amp;c&gt;d" in py


@requires_oracle
def test_text2html_page_article_paragraph_nesting_matches_pdfbox(
    tmp_path: Path,
) -> None:
    src = tmp_path / "multipage.pdf"
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "page one text")])
        _text_page(doc, [(72, 700, "page two text")])
        doc.save(str(src))

    java = run_probe_text("Text2HtmlProbe", str(src))
    py = _py_html(src)

    assert py == java, (
        "PDFText2HTML page/article nesting divergence:\n"
        f"  java: {java!r}\n  py:   {py!r}"
    )


@requires_oracle
def test_text2html_same_paragraph_lines_match_pdfbox(tmp_path: Path) -> None:
    src = tmp_path / "multiline.pdf"
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "line one"), (72, 686, "line two")])
        doc.save(str(src))

    java = run_probe_text("Text2HtmlProbe", str(src))
    py = _py_html(src)

    assert py == java, (
        "PDFText2HTML same-paragraph divergence:\n"
        f"  java: {java!r}\n  py:   {py!r}"
    )


@requires_oracle
def test_text2html_mid_page_paragraph_break_matches_pdfbox(
    tmp_path: Path,
) -> None:
    """A mid-page paragraph break (a vertical drop larger than
    ``drop_threshold`` × line height) now emits the separator tokens in
    upstream order — ``writeLineSeparator → writeParagraphEnd →
    writeParagraphStart`` — so PDFText2HTML produces ``\\n</p>\\n<p>``
    rather than the previously-emitted ``</p>\\n\\n<p>`` (wave 1490
    reorder of ``_emit_group``). Two lines 60 user-space units apart at
    12pt (drop ≈ 60 > 2.5 × 12 = 30) cross the drop threshold so the
    paragraph separator fires between them; this pins the corrected
    ordering byte-for-byte against Java PDFBox 3.0.7."""
    src = tmp_path / "para_break.pdf"
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "first paragraph"), (72, 640, "second paragraph")])
        doc.save(str(src))

    java = run_probe_text("Text2HtmlProbe", str(src))
    py = _py_html(src)

    assert py == java, (
        "PDFText2HTML mid-page paragraph-break divergence:\n"
        f"  java: {java!r}\n  py:   {py!r}"
    )


@requires_oracle
def test_text2html_metadata_title_escaping_matches_pdfbox(
    tmp_path: Path,
) -> None:
    src = tmp_path / "title.pdf"
    with PDDocument() as doc:
        doc.get_document_information().set_title("My <Title> & More")
        _text_page(doc, [(72, 700, "body text")])
        doc.save(str(src))

    java = run_probe_text("Text2HtmlProbe", str(src))
    py = _py_html(src)

    assert py == java, (
        "PDFText2HTML title divergence:\n"
        f"  java: {java!r}\n  py:   {py!r}"
    )
    assert "<title>My &lt;Title&gt; &amp; More</title>" in py
