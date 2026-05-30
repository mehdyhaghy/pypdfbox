"""Live Apache PDFBox parity for the ``ExtractText`` CLI's page-range + sort
surface (``org.apache.pdfbox.tools.ExtractText`` vs pypdfbox's
``pypdfbox.tools.extracttext``).

The companion stripper-level oracle (``TextExtractProbe``) pins the whole-
document ``PDFTextStripper.getText`` path. This module instead drives the
**CLI tool's** ``-startPage`` / ``-endPage`` / ``-sort`` options, exactly as a
shell invocation would. The CLI's core is ``extracttext.extract_text``, which
sets ``set_sort_by_position`` / ``set_start_page`` / ``set_end_page`` (clamping
the end page to the document page count) and writes ``PDFTextStripper.getText``
— precisely the sequence the ``ExtractTextRangeProbe`` Java probe replicates
against upstream.

The parity claim, on a controlled 5-page source whose pages carry distinct
text:

* ``-startPage 2 -endPage 3`` extracts pages 2 and 3 only — identical bytes;
* default whole-document extraction (start 1, end past the last page, so the
  clamp to ``getNumberOfPages()`` is exercised) — identical bytes;
* ``-sort`` over a page with two out-of-reading-order text runs produces the
  same position-sorted output on both sides.

The source PDF is built through pypdfbox so the input bytes are identical on
both sides of every comparison; only the extracted text is asserted.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.tools.extracttext import extract_text
from tests.oracle.harness import requires_oracle, run_probe_text


def _text_page(doc: PDDocument, lines: list[tuple[float, float, str]]) -> None:
    """Append a Letter page to ``doc`` showing each (x, y, text) run."""
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


def _build_source(path: Path) -> None:
    """Build a controlled 5-page source PDF.

    Pages 1-4 carry a single distinct line each so a page-range subset is
    unambiguous. Page 5 lays two runs out of reading order (the lower-on-page
    run is emitted first) so ``-sort`` has something to reorder.
    """
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "PAGE ONE alpha")])
        _text_page(doc, [(72, 700, "PAGE TWO bravo")])
        _text_page(doc, [(72, 700, "PAGE THREE charlie")])
        _text_page(doc, [(72, 700, "PAGE FOUR delta")])
        # Two runs, emitted bottom-then-top, far apart vertically so the
        # stripper treats them as separate lines on both sides.
        _text_page(
            doc,
            [
                (72, 400, "LOWER echo"),
                (72, 700, "UPPER foxtrot"),
            ],
        )
        doc.save(str(path))


def _py_extract(src: Path, *, start_page: int, end_page: int, sort: bool) -> str:
    """Run pypdfbox's ExtractText CLI core over ``src`` and return the text."""
    buf = io.StringIO()
    with PDDocument.load(src) as doc:
        extract_text(
            doc,
            buf,
            start_page=start_page,
            end_page=end_page,
            sort=sort,
        )
    return buf.getvalue()


@requires_oracle
def test_extract_text_page_range_matches_pdfbox(tmp_path: Path) -> None:
    src = tmp_path / "source.pdf"
    _build_source(src)

    java = run_probe_text("ExtractTextRangeProbe", str(src), "2", "3", "false")
    py = _py_extract(src, start_page=2, end_page=3, sort=False)

    assert py == java, (
        "ExtractText -startPage 2 -endPage 3 divergence:\n"
        f"  java: {java!r}\n  py:   {py!r}"
    )
    # Guard the fixture: the subset must be exactly pages 2-3.
    assert "PAGE TWO bravo" in py
    assert "PAGE THREE charlie" in py
    assert "PAGE ONE alpha" not in py
    assert "PAGE FOUR delta" not in py


@requires_oracle
def test_extract_text_whole_document_matches_pdfbox(tmp_path: Path) -> None:
    src = tmp_path / "source.pdf"
    _build_source(src)

    # endPage past the last page exercises the clamp to getNumberOfPages().
    java = run_probe_text("ExtractTextRangeProbe", str(src), "1", "999", "false")
    py = _py_extract(src, start_page=1, end_page=999, sort=False)

    assert py == java, (
        "ExtractText whole-document divergence:\n"
        f"  java: {java!r}\n  py:   {py!r}"
    )
    assert "PAGE ONE alpha" in py
    assert "UPPER foxtrot" in py


@requires_oracle
def test_extract_text_sort_matches_pdfbox(tmp_path: Path) -> None:
    src = tmp_path / "source.pdf"
    _build_source(src)

    # Page 5 only, with sort-by-position on: the upper run must precede the
    # lower run in the output regardless of content-stream emission order.
    java = run_probe_text("ExtractTextRangeProbe", str(src), "5", "5", "true")
    py = _py_extract(src, start_page=5, end_page=5, sort=True)

    assert py == java, (
        "ExtractText -sort divergence:\n"
        f"  java: {java!r}\n  py:   {py!r}"
    )
    assert py.index("UPPER foxtrot") < py.index("LOWER echo")
