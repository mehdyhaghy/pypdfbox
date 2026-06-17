"""Live Apache PDFBox differential parity for separator-token placement.

The default ``PDFTextStripper`` separators (word=``" "``, line=``"\\n"``,
pageEnd=``"\\n"``, page/paragraph start=``""``) all render as plain
whitespace, so a separator inserted in the wrong place is invisible in a
default-config diff: a stray space looks like an intended one. This probe
overrides every separator with a unique sentinel token so the *exact*
insertion point of each word break, line break, page break, and paragraph
break becomes observable, then asserts pypdfbox's :class:`PDFTextStripper`
places them identically to Java PDFBox 3.0.7.

``with_outline.pdf`` is a 6-page document that already matches Java
byte-for-byte under the default config (see
``test_text_extraction_oracle.py``); running it through the
sentinel-separator config additionally pins the *placement* of every
word / line / page break — i.e. that those hooks fire at the same
boundaries in both engines, not merely that whitespace happens to coincide.

The *paragraph* delimiter (``setParagraphStart`` / ``setParagraphEnd``)
now matches byte-for-byte too. Upstream wraps every visual line of this
fixture in a paragraph because its ``isParagraphSeparation`` indent test
fires on the stair-stepped left margin of the bookmark headings ("First
level 1" / "First level 2" / … each indented further). Wave 1492 ported
that classifier faithfully into the lite stripper's ``_emit_group``:
``lastLineStartPosition`` tracking, the indent prong measured against the
previous *line start* (not the immediately-previous glyph), and the
hanging-indent / list-item paragraph detection
(``PDFTextStripper.java:1611-1683``). All four separator families —
word / line / page / paragraph — are now at full placement parity and
asserted positively below.

``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font import PDFontFactory, Standard14Fonts
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
_FIXTURE = _FIXTURES / "pdmodel" / "with_outline.pdf"


def _build_pdf(content: bytes, path: str) -> None:
    """Build a one-page Letter-ish PDF whose content is exactly ``content``.

    The ``/F1`` token is rewritten to the embedded Helvetica font key.
    """
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 400, 400))
        doc.add_page(page)
        font = PDFontFactory.create_default_font(
            Standard14Fonts.FontName.HELVETICA.value
        )
        resources = page.get_or_create_resources()
        font_key = resources.add(font)
        page.set_resources(resources)
        rewritten = content.replace(
            b"/F1", b"/" + font_key.get_name().encode("ascii")
        )
        stream = COSStream()
        with stream.create_output_stream() as out:
            out.write(rewritten)
        page.set_contents(stream)
        doc.save(path)
    finally:
        doc.close()


def _py_text_with_sentinels(path: Path) -> str:
    doc = PDDocument.load(str(path))
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(True)
        stripper.set_word_separator("|W|")
        stripper.set_line_separator("|L|\n")
        stripper.set_page_start("<<PAGE>>")
        stripper.set_page_end("<</PAGE>>\n")
        stripper.set_paragraph_start("[P]")
        stripper.set_paragraph_end("[/P]")
        return stripper.get_text(doc)
    finally:
        doc.close()


def _strip_paragraph_tokens(text: str) -> str:
    """Remove the paragraph sentinels, leaving word/line/page placement."""
    return text.replace("[P]", "").replace("[/P]", "")


@requires_oracle
def test_word_line_page_separator_placement_matches_pdfbox() -> None:
    """Every word / line / page separator lands at the same boundary as
    Java PDFBox when overridden to a distinctive sentinel token (paragraph
    tokens excluded — see module docstring + the paragraph xfail below)."""
    java = run_probe_text("TextSeparatorProbe", str(_FIXTURE))
    py = _py_text_with_sentinels(_FIXTURE)
    assert _strip_paragraph_tokens(py) == _strip_paragraph_tokens(java)


@requires_oracle
def test_page_sentinels_fire_once_per_page() -> None:
    """The page-start / page-end sentinels fire exactly once per extracted
    page in both engines (6-page fixture)."""
    java = run_probe_text("TextSeparatorProbe", str(_FIXTURE))
    py = _py_text_with_sentinels(_FIXTURE)
    assert py.count("<<PAGE>>") == java.count("<<PAGE>>")
    assert py.count("<</PAGE>>") == java.count("<</PAGE>>")
    assert py.count("<<PAGE>>") == 6


@requires_oracle
def test_paragraph_token_placement_matches_pdfbox() -> None:
    """Paragraph-token placement now matches Java byte-for-byte.

    Wave 1492 ported upstream's ``isParagraphSeparation``
    (PDFTextStripper.java:1611-1683) into the lite stripper's
    ``_emit_group``: the indent prong is measured against the previous
    *line start* (``lastLineStartPosition``) rather than the
    immediately-previous glyph, and the hanging-indent / list-item prongs
    are wired in. On ``with_outline.pdf`` upstream wraps each
    further-indented bookmark heading in a ``[P]…[/P]`` pair; the lite
    stripper now emits the identical bracketing, so the full sentinel
    stream — word / line / page / paragraph — matches exactly.
    """
    java = run_probe_text("TextSeparatorProbe", str(_FIXTURE))
    py = _py_text_with_sentinels(_FIXTURE)
    assert py == java


# ---------------------------------------------------------------------------
# Synthetic fixtures exercising the list-item and hanging-indent prongs of
# upstream's isParagraphSeparation (PDFTextStripper.java:1611-1683) directly.
# ---------------------------------------------------------------------------

# A numbered list. Each item starts at the same left margin (x=40) one line
# below the last (Td uses text-space line stepping). Upstream's list-item
# prong: when a line lines up with the previous *paragraph-start* line
# (within 1/4 char) and both match the same list-item regex, the new line is
# itself a paragraph start. So every "N." item opens a fresh [P].
_LIST_ITEMS = (
    b"BT /F1 14 Tf 40 360 Td (1. First item) Tj "
    b"0 -20 Td (2. Second item) Tj "
    b"0 -20 Td (3. Third item) Tj ET"
)

# A hanging indent: the marker line "* Bullet text" sits at x=40 and is a
# paragraph start; its wrapped continuation "wraps here" is indented to x=58
# (> indentThreshold*space past the line start), so upstream flags it a
# hanging indent rather than a new paragraph (it stays inside the same [P]).
_HANGING_INDENT = (
    b"BT /F1 14 Tf 40 360 Td (Bullet text that) Tj "
    b"18 -18 Td (wraps here indented) Tj "
    b"-18 -18 Td (Next paragraph flush) Tj ET"
)


@requires_oracle
def test_list_item_paragraph_placement_matches_pdfbox() -> None:
    """A numbered list: upstream opens a new ``[P]`` at each list item via
    the list-item prong of ``isParagraphSeparation`` (lines line up with the
    previous paragraph start and share a list-item regex). The lite stripper
    now reproduces the identical paragraph-token placement."""
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "list.pdf")
        _build_pdf(_LIST_ITEMS, path)
        java = run_probe_text("TextSeparatorProbe", path)
        py = _py_text_with_sentinels(Path(path))
        assert py == java


@requires_oracle
def test_hanging_indent_paragraph_placement_matches_pdfbox() -> None:
    """A hanging-indent block: the wrapped continuation line is indented
    under a paragraph start, so upstream flags it ``isHangingIndent`` and
    keeps it in the same ``[P]`` rather than opening a new one. The lite
    stripper now reproduces the identical paragraph-token placement."""
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "hanging.pdf")
        _build_pdf(_HANGING_INDENT, path)
        java = run_probe_text("TextSeparatorProbe", path)
        py = _py_text_with_sentinels(Path(path))
        assert py == java
