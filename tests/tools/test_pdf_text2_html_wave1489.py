"""Wave 1489 byte-structure tests for ``pypdfbox.tools.pdf_text2_html``.

These pin the HTML-document structure that ``PDFText2HTML`` (a
``PDFTextStripper`` subclass) wraps stripped text in, end-to-end through a
real ``get_text`` walk over PDFs built by pypdfbox itself. The companion
oracle module (``tests/tools/oracle/test_text2html_oracle.py``) asserts the
same outputs are byte-identical to Apache PDFBox 3.0.7; this module asserts
the structure stands on its own without requiring a live JVM.

Pinned contracts (verified byte-for-byte against the upstream
``Text2HtmlProbe`` oracle):

* the fixed ``<!DOCTYPE>`` / ``<head>`` / ``<title>`` / ``<body>`` preamble;
* the per-page ``page-break`` ``<div>`` wrapper enclosing a per-article
  ``<div>`` enclosing a per-paragraph ``<p>``;
* ``startArticle`` emits ``<div>`` directly (no leading article separator),
  and ``endArticle`` emits the article-end separator then ``</div>``;
* entity escaping of ``< > &`` in body text and of the metadata title;
* non-ASCII characters escaped as ``&#NNN;`` named-decimal entities.
"""

from __future__ import annotations

import re
from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.tools.pdf_text2_html import PDFText2HTML, _escape

_PREAMBLE = (
    '<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"\n'
    '"http://www.w3.org/TR/html4/loose.dtd">\n'
    "<html><head><title>{title}</title>\n"
    '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">\n'
    "</head>\n<body>\n"
)
_PAGE_OPEN = '<div style="page-break-before:always; page-break-after:always">'


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


def _to_html(path: Path) -> str:
    with PDDocument.load(path) as doc:
        return PDFText2HTML().get_text(doc)


# --------------------------------------------------------------------------
# escape helper (matches upstream appendEscaped byte-for-byte)
# --------------------------------------------------------------------------
def test_escape_html_metacharacters() -> None:
    assert _escape("a<b&c>d") == "a&lt;b&amp;c&gt;d"


def test_escape_double_quote_and_controls() -> None:
    # 34 -> &quot;, tab(9)/control(1) -> &#N; (below ASCII 32), >126 -> &#N;
    assert _escape('q"u\to') == "q&quot;u&#9;o"


def test_escape_non_ascii_named_decimal_entity() -> None:
    assert _escape("é") == "&#233;"
    assert PDFText2HTML.escape("€") == "&#8364;"


# --------------------------------------------------------------------------
# full-document structure
# --------------------------------------------------------------------------
def test_single_line_page_structure(tmp_path: Path) -> None:
    src = tmp_path / "simple.pdf"
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "a<b&c>d")])
        doc.save(str(src))

    html = _to_html(src)
    expected = (
        _PREAMBLE.format(title="")
        + _PAGE_OPEN
        + "<div><p>a&lt;b&amp;c&gt;d</p>\n\n</div>"
        + "</div>\n"
        + "</body></html>"
    )
    assert html == expected


def test_article_div_wraps_paragraph(tmp_path: Path) -> None:
    """startArticle must emit ``<div>`` directly (no leading separator) and
    endArticle must emit the article-end separator then ``</div>``."""
    src = tmp_path / "simple.pdf"
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "body")])
        doc.save(str(src))

    html = _to_html(src)
    # page-open is immediately followed by the article <div>, no '\n' between.
    assert _PAGE_OPEN + "<div><p>" in html
    # the </p> line, then the article-end separator, then </div></div>.
    assert "</p>\n\n</div></div>\n</body></html>" in html


def test_multi_page_emits_two_page_divs(tmp_path: Path) -> None:
    src = tmp_path / "multipage.pdf"
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "page one text")])
        _text_page(doc, [(72, 700, "page two text")])
        doc.save(str(src))

    html = _to_html(src)
    assert html.count(_PAGE_OPEN) == 2
    assert "<p>page one text</p>" in html
    assert "<p>page two text</p>" in html
    # both page divs are siblings under <body>, each with its own article div.
    assert html.count("<div><p>") == 2


def test_title_from_metadata_is_escaped(tmp_path: Path) -> None:
    src = tmp_path / "title.pdf"
    with PDDocument() as doc:
        doc.get_document_information().set_title("My <Title> & More")
        _text_page(doc, [(72, 700, "body text")])
        doc.save(str(src))

    html = _to_html(src)
    title = re.search(r"<title>(.*?)</title>", html).group(1)
    assert title == "My &lt;Title&gt; &amp; More"


def test_title_control_chars_escaped_as_entities(tmp_path: Path) -> None:
    src = tmp_path / "esc.pdf"
    with PDDocument() as doc:
        doc.get_document_information().set_title('q"u o\tt e<>&~')
        _text_page(doc, [(72, 700, "x")])
        doc.save(str(src))

    html = _to_html(src)
    title = re.search(r"<title>(.*?)</title>", html).group(1)
    assert title == "q&quot;u o&#9;t e&lt;&gt;&amp;~"


def test_lines_in_same_paragraph_separated_by_line_separator(
    tmp_path: Path,
) -> None:
    """Two vertically-close lines stay in one ``<p>`` joined by the line
    separator (no intervening ``</p><p>``)."""
    src = tmp_path / "multiline.pdf"
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "line one"), (72, 686, "line two")])
        doc.save(str(src))

    html = _to_html(src)
    assert "<p>line one\nline two</p>" in html
    assert html.count("<p>") == 1
