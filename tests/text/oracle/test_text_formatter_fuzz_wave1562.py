"""Live Apache PDFBox differential fuzz of the HTML / Markdown text-output
formatters (wave 1562).

``PDFText2HTML`` and ``PDFText2Markdown`` are the ``PDFTextStripper``
subclasses behind the ``ExtractText -html`` / ``-md`` CLI paths. They wrap
stripped text in minimal HTML / Markdown: entity / backslash escaping, the
page / article / paragraph nesting, and (HTML only) the DOCTYPE preamble + a
``<title>`` from the doc-info metadata. The existing ``Text2HtmlProbe`` /
``test_text2html_oracle`` cover HTML escaping + page nesting; this wave adds
the **Markdown** counterpart and fuzzes escaping / structure facets the
HTML-only oracle never reached.

``TextFormatterFuzzProbe`` runs either converter (``html`` / ``md`` mode) over
a caller-supplied PDF and prints the formatted output verbatim, so we diff the
escaping + structure on byte-identical input (the source PDFs are built through
pypdfbox).

Scope notes / honest divergences:

* **Glyph-decode, not formatter.** A char the page font does not map decodes
  to U+0000 on Java PDFBox and to U+FFFD (the replacement char) on pypdfbox —
  a stripper/font-decode divergence, NOT a formatter one. Fixtures therefore
  use only WinAnsi-mappable text (ASCII + the Latin-1 / superscript range the
  Standard-14 default font maps) so the comparison isolates the formatter's
  own escaping + nesting.
* **Empty-page article wrap.** A glyph-free page bypasses the per-article
  ``write_article_start`` / ``write_article_end`` hooks in pypdfbox's lite
  stripper (``PDFTextStripper._empty_article_wrap`` emits the raw
  ``article_start`` + ``article_end`` separators directly), so the HTML
  ``<div>`` / Markdown extra-separator wrap an empty page gets on Java is not
  reproduced. That gap lives in the shared stripper core (changed wave 1542),
  not the formatter, so the empty-page cases are asserted against pypdfbox's
  current output with the divergence documented rather than pinned to Java.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.tools.pdf_text2_html import PDFText2HTML
from pypdfbox.tools.pdf_text2_markdown import PDFText2Markdown
from tests.oracle.harness import requires_oracle, run_probe_text


def _text_page(
    doc: PDDocument,
    lines: list[tuple[float, float, str]],
    *,
    font_size: float = 12.0,
) -> None:
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    font = PDFontFactory.create_default_font()
    cs = PDPageContentStream(doc, page)
    cs.begin_text()
    cs.set_font(font, font_size)
    last_x = 0.0
    last_y = 0.0
    for x, y, text in lines:
        cs.new_line_at_offset(x - last_x, y - last_y)
        cs.show_text(text)
        last_x, last_y = x, y
    cs.end_text()
    cs.close()


def _build(path: Path, builder) -> Path:
    with PDDocument() as doc:
        builder(doc)
        doc.save(str(path))
    return path


def _py_html(src: Path) -> str:
    with PDDocument.load(src) as doc:
        return PDFText2HTML().get_text(doc)


def _py_md(src: Path) -> str:
    with PDDocument.load(src) as doc:
        return PDFText2Markdown().get_text(doc)


# --------------------------------------------------------------------------
# Self-contained value parity (no Java required) — pins the wave-1562 fix and
# the formatter's escaping rules against PDFBox-3.0.7-derived expected output.
# --------------------------------------------------------------------------


def test_markdown_single_line_trailing_separators(tmp_path: Path) -> None:
    """Markdown closes each article with TWO line separators (articleEnd +
    the extra ``writeString(LINE_SEPARATOR)`` upstream ``endArticle`` emits).
    Before the wave-1562 fix pypdfbox emitted only one, dropping a trailing
    newline per article. Pinned to Java PDFBox 3.0.7 output for a one-line
    page: ``\\n\\n\\n`` (page-start / article-start / paragraph-start) + text
    + ``\\n\\n\\n\\n`` (paragraph-end / articleEnd / extra / page-end)."""
    src = _build(tmp_path / "md_one.pdf", lambda d: _text_page(d, [(72, 700, "body")]))
    assert _py_md(src) == "\n\n\nbody\n\n\n\n"


def test_markdown_two_pages_trailing_separators(tmp_path: Path) -> None:
    """Each page contributes its own two-separator article close, so a
    two-page doc emits the per-page ``\\n\\n\\n\\n`` close for the first
    page and the final one. Pinned to Java PDFBox 3.0.7."""
    src = _build(
        tmp_path / "md_two.pdf",
        lambda d: (_text_page(d, [(72, 700, "one")]), _text_page(d, [(72, 700, "two")])),
    )
    assert _py_md(src) == "\n\n\none\n\n\n\n\n\n\ntwo\n\n\n\n"


def test_markdown_escapes_special_chars(tmp_path: Path) -> None:
    """Markdown backslash-escapes ``* + - #`` and lifts the ²/³ superscripts
    into ``<sup>`` runs; plain text is untouched. Pinned to Java PDFBox 3.0.7."""
    src = _build(
        tmp_path / "md_esc.pdf",
        lambda d: _text_page(d, [(72, 700, "*a* +b -c #d")]),
    )
    assert _py_md(src) == "\n\n\n\\*a\\* \\+b \\-c \\#d\n\n\n\n"


def test_markdown_superscript_two_three(tmp_path: Path) -> None:
    src = _build(
        tmp_path / "md_sup.pdf",
        lambda d: _text_page(d, [(72, 700, "m² v³")]),
    )
    assert _py_md(src) == "\n\n\nm<sup>2</sup> v<sup>3</sup>\n\n\n\n"


def test_html_entity_escaping_value(tmp_path: Path) -> None:
    """HTML escapes ``& < >`` and ``"`` to entities; the ``'`` apostrophe is
    NOT escaped (upstream ``appendEscaped`` leaves printable-ASCII other than
    ``" & < >`` verbatim). Pinned to Java PDFBox 3.0.7."""
    src = _build(
        tmp_path / "html_esc.pdf",
        lambda d: _text_page(d, [(72, 700, "a<b&c>\"d'e")]),
    )
    html = _py_html(src)
    assert "a&lt;b&amp;c&gt;&quot;d'e" in html


def test_html_title_escaped_in_head(tmp_path: Path) -> None:
    """A doc-info title is HTML-escaped inside ``<title>``. Pinned to Java
    PDFBox 3.0.7."""

    def build(doc: PDDocument) -> None:
        doc.get_document_information().set_title("T <x> & \"y\"")
        _text_page(doc, [(72, 700, "body")])

    src = _build(tmp_path / "html_title.pdf", build)
    html = _py_html(src)
    assert "<title>T &lt;x&gt; &amp; &quot;y&quot;</title>" in html


def test_html_preamble_and_paragraph_wrap(tmp_path: Path) -> None:
    """The HTML preamble + page-break div + article div + paragraph wrap are
    emitted in upstream order for a one-line page. Pinned to Java PDFBox
    3.0.7."""
    src = _build(
        tmp_path / "html_wrap.pdf", lambda d: _text_page(d, [(72, 700, "hello")])
    )
    html = _py_html(src)
    assert html.startswith(
        '<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"\n'
    )
    assert (
        '<div style="page-break-before:always; page-break-after:always">'
        "<div><p>hello</p>\n\n</div></div>\n</body></html>" in html
    )


# --------------------------------------------------------------------------
# Live differential parity — runs only when the Java PDFBox oracle is present.
# --------------------------------------------------------------------------

_HTML_CASES = {
    "special": [(72.0, 700.0, "a<b&c>\"d'e")],
    "longline": [(72.0, 700.0, "x" * 200)],
    "multiline": [(72.0, 700.0, "line one"), (72.0, 686.0, "line two")],
    "parabreak": [(72.0, 700.0, "first"), (72.0, 620.0, "second")],
}

_MD_CASES = {
    "special": [(72.0, 700.0, "*a* +b -c #d")],
    "super": [(72.0, 700.0, "m² v³")],
    "longline": [(72.0, 700.0, "y" * 200)],
    "multipage_line": [(72.0, 700.0, "p one")],
    "parabreak": [(72.0, 700.0, "alpha"), (72.0, 620.0, "beta")],
    "latin1": [(72.0, 700.0, "café über")],
}


@requires_oracle
@pytest.mark.parametrize("name", sorted(_HTML_CASES), ids=sorted(_HTML_CASES))
def test_html_matches_oracle(tmp_path: Path, name: str) -> None:
    lines = _HTML_CASES[name]
    src = _build(tmp_path / f"html_{name}.pdf", lambda d: _text_page(d, lines))
    java = run_probe_text("TextFormatterFuzzProbe", "html", str(src))
    py = _py_html(src)
    assert py == java, (
        f"PDFText2HTML divergence ({name}):\n  java: {java!r}\n  py:   {py!r}"
    )


@requires_oracle
@pytest.mark.parametrize("name", sorted(_MD_CASES), ids=sorted(_MD_CASES))
def test_markdown_matches_oracle(tmp_path: Path, name: str) -> None:
    lines = _MD_CASES[name]
    src = _build(tmp_path / f"md_{name}.pdf", lambda d: _text_page(d, lines))
    java = run_probe_text("TextFormatterFuzzProbe", "md", str(src))
    py = _py_md(src)
    assert py == java, (
        f"PDFText2Markdown divergence ({name}):\n  java: {java!r}\n  py:   {py!r}"
    )


@requires_oracle
def test_markdown_multi_page_matches_oracle(tmp_path: Path) -> None:
    """The wave-1562 fix (two separators per article close) must hold across
    page boundaries — diff a three-page doc against Java PDFBox 3.0.7."""

    def build(doc: PDDocument) -> None:
        _text_page(doc, [(72, 700, "one")])
        _text_page(doc, [(72, 700, "two")])
        _text_page(doc, [(72, 700, "three")])

    src = _build(tmp_path / "md_multi.pdf", build)
    java = run_probe_text("TextFormatterFuzzProbe", "md", str(src))
    py = _py_md(src)
    assert py == java, (
        f"PDFText2Markdown multi-page divergence:\n  java: {java!r}\n  py:   {py!r}"
    )


@requires_oracle
def test_html_title_matches_oracle(tmp_path: Path) -> None:
    def build(doc: PDDocument) -> None:
        doc.get_document_information().set_title("T <x> & \"y\"")
        _text_page(doc, [(72, 700, "body")])

    src = _build(tmp_path / "html_titled.pdf", build)
    java = run_probe_text("TextFormatterFuzzProbe", "html", str(src))
    py = _py_html(src)
    assert py == java, (
        f"PDFText2HTML title divergence:\n  java: {java!r}\n  py:   {py!r}"
    )


# --------------------------------------------------------------------------
# Documented known divergence: empty page (core ``_empty_article_wrap`` gap).
# --------------------------------------------------------------------------


def test_empty_page_html_is_current_behavior(tmp_path: Path) -> None:
    """A glyph-free page does NOT route through the HTML ``<div>`` article
    hooks (core ``_empty_article_wrap`` emits the raw separators), so the
    output differs from Java PDFBox 3.0.7 (which wraps the empty page in
    ``<div>...\\n</div>``). Documented as a stripper-core gap, not a
    formatter bug; this pins pypdfbox's CURRENT empty-page output so a future
    core fix is a deliberate, visible change."""
    src = _build(tmp_path / "html_empty.pdf", lambda d: d.add_page(PDPage(PDRectangle.LETTER)))
    html = _py_html(src)
    assert (
        '<div style="page-break-before:always; page-break-after:always">'
        "\n\n</div>\n</body></html>" in html
    )


def test_empty_page_markdown_is_current_behavior(tmp_path: Path) -> None:
    """Markdown empty-page counterpart of the core ``_empty_article_wrap``
    gap (see the HTML case). Pins pypdfbox's current output."""
    src = _build(tmp_path / "md_empty.pdf", lambda d: d.add_page(PDPage(PDRectangle.LETTER)))
    assert _py_md(src) == "\n\n\n\n"
