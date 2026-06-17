"""Live Apache PDFBox parity for ``setAddMoreFormatting(true)`` cadence.

``addMoreFormatting`` promotes ``paragraphEnd`` / ``pageStart`` /
``articleStart`` / ``articleEnd`` to the line separator
(PDFTextStripper.java:244-250 in ``writeText``), so every structural
boundary — page start, article wrap, and each paragraph end — becomes a
visible newline. This pins the exact per-page / per-paragraph newline
cadence of the lite stripper against Java PDFBox 3.0.7.

The source PDFs are built through pypdfbox so the input bytes are
identical on both sides; only the extracted text is compared. Fixtures
are scoped to layouts the lite stripper reproduces at full parity:
single-line pages, same-paragraph multi-line bodies, and mid-page
paragraph-drop breaks (a vertical drop beyond ``drop_threshold`` × line
height). Indent / hanging-indent / list-item paragraph detection is a
deferred layout feature (see ``test_text_separator_oracle.py`` xfail) and
is deliberately not exercised here.

``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
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


def _py_add_more_formatting(src: Path) -> str:
    with PDDocument.load(src) as doc:
        stripper = PDFTextStripper()
        stripper.set_add_more_formatting(True)
        return stripper.get_text(doc)


@requires_oracle
def test_add_more_formatting_single_line_matches_pdfbox(tmp_path: Path) -> None:
    src = tmp_path / "single.pdf"
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "only line")])
        doc.save(str(src))

    java = run_probe_text("AddMoreFormattingProbe", str(src))
    py = _py_add_more_formatting(src)
    assert py == java, (
        f"add_more_formatting single-line divergence:\n  java: {java!r}\n  py:   {py!r}"
    )


@requires_oracle
def test_add_more_formatting_same_paragraph_matches_pdfbox(tmp_path: Path) -> None:
    src = tmp_path / "samepara.pdf"
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "line one"), (72, 686, "line two")])
        doc.save(str(src))

    java = run_probe_text("AddMoreFormattingProbe", str(src))
    py = _py_add_more_formatting(src)
    assert py == java, (
        f"add_more_formatting same-paragraph divergence:\n  java: {java!r}\n  py:   {py!r}"
    )


@requires_oracle
def test_add_more_formatting_paragraph_break_matches_pdfbox(tmp_path: Path) -> None:
    src = tmp_path / "parabreak.pdf"
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "first paragraph"), (72, 640, "second paragraph")])
        doc.save(str(src))

    java = run_probe_text("AddMoreFormattingProbe", str(src))
    py = _py_add_more_formatting(src)
    assert py == java, (
        f"add_more_formatting paragraph-break divergence:\n  java: {java!r}\n  py:   {py!r}"
    )


@requires_oracle
def test_add_more_formatting_multipage_matches_pdfbox(tmp_path: Path) -> None:
    src = tmp_path / "multipage.pdf"
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "page one body")])
        _text_page(doc, [(72, 700, "page two body")])
        doc.save(str(src))

    java = run_probe_text("AddMoreFormattingProbe", str(src))
    py = _py_add_more_formatting(src)
    assert py == java, (
        f"add_more_formatting multipage divergence:\n  java: {java!r}\n  py:   {py!r}"
    )
