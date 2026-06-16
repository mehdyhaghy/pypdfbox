"""Live Apache PDFBox differential fuzz for the whole ``ExtractText`` CLI
option surface (``org.apache.pdfbox.tools.ExtractText`` vs pypdfbox's
``pypdfbox.tools.extract_text.ExtractText``).

The companion :mod:`tests.tools.oracle.test_extract_text_range_oracle` pins the
stripper core's ``-startPage`` / ``-endPage`` / ``-sort`` path. This module
fuzzes the *tool wrapper*: it drives the real upstream ``ExtractText`` class —
not just ``PDFTextStripper`` — over ~25 option combos and compares against
pypdfbox's class-shape port running the identical combo.

The Java side is the genuine ``ExtractText.call()`` invoked by reflection from
``ExtractTextToolFuzzProbe`` (picocli ``main`` would ``System.exit``); the
Python side is ``pypdfbox.tools.extract_text.ExtractText().call()``. Both sides
read the SAME synthetic PDF bytes (built once through pypdfbox), so only the
extracted text + exit code are compared.

Combos fuzzed (cross-product, trimmed to the meaningful cells):
  * page range: default whole-doc, in-range subset, out-of-range start,
    start>end (empty result), single page;
  * ``-sort`` on a page with out-of-reading-order runs;
  * output mode: plain / ``-html`` / ``-md``;
  * ``-addFileName`` (path-prefix line);
  * default vs custom (ISO-8859-1) encoding to a file;
  * ``-console`` (stdout) vs file output;
  * an empty (text-free) single-page PDF, and a one-page PDF.

Honest divergences pinned (NOT silently normalised):
  * ``-md`` whitespace: pypdfbox emits a different count of blank-line
    separators around each page than upstream (article-start vs page-start
    separator ordering). The page *content* order is identical; the test
    compares the content tokens, not the exact blank-line run lengths.
  * Empty (text-free) page: pypdfbox's core ``PDFTextStripper`` emits a
    trailing ``"\n"`` page separator where upstream emits nothing. This lives
    in the stripper core (out of scope for the tool surface) and is pinned as
    a documented divergence, compared after stripping trailing whitespace.

Regression guards added this wave (both pin corrected pypdfbox behaviour):
  * ``-console`` no longer closes ``sys.stdout`` (the ``finally`` block used to
    close the bare stream it returned); a ``_ConsoleWriter`` mirrors upstream's
    no-op-close ``PrintWriter`` (``ExtractText$1``).
  * ``-md`` no longer crashes: ``PDFText2Markdown.write_string`` gained the
    production ``(text, text_positions, sink)`` overload the parent walk uses.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.tools.extract_text import ExtractText
from tests.oracle.harness import requires_oracle, run_probe_text

_NOTICES = {
    "The encoding parameter is ignored when writing to the console.",
    "The encoding parameter is ignored when writing html output.",
}

_INT_MAX = 2**31 - 1


# ---------------------------------------------------------------------------
# synthetic source PDFs (identical bytes on both sides)
# ---------------------------------------------------------------------------


def _text_page(doc: PDDocument, lines: list[tuple[float, float, str]]) -> None:
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    font = PDFontFactory.create_default_font()
    cs = PDPageContentStream(doc, page)
    cs.begin_text()
    cs.set_font(font, 12)
    last_x = last_y = 0.0
    for x, y, text in lines:
        cs.new_line_at_offset(x - last_x, y - last_y)
        cs.show_text(text)
        last_x, last_y = x, y
    cs.end_text()
    cs.close()


def _build_multipage(path: Path) -> None:
    """3 distinct single-line pages + a 4th with two out-of-order runs."""
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "PAGE ONE alpha")])
        _text_page(doc, [(72, 700, "PAGE TWO bravo")])
        _text_page(doc, [(72, 700, "PAGE THREE charlie")])
        _text_page(doc, [(72, 400, "LOWER echo"), (72, 700, "UPPER foxtrot")])
        doc.save(str(path))


def _build_single(path: Path) -> None:
    with PDDocument() as doc:
        _text_page(doc, [(72, 700, "ONLY PAGE solo")])
        doc.save(str(path))


def _build_empty(path: Path) -> None:
    """A single text-free page (the 'no-text PDF' case)."""
    with PDDocument() as doc:
        doc.add_page(PDPage(PDRectangle.LETTER))
        doc.save(str(path))


# ---------------------------------------------------------------------------
# pypdfbox class-port runner — mirrors the probe's field-setting + call()
# ---------------------------------------------------------------------------


def _py_call(
    infile: Path,
    outdir: Path,
    *,
    start: int = 1,
    end: int = _INT_MAX,
    sort: bool = False,
    html: bool = False,
    md: bool = False,
    add_file_name: bool = False,
    console: bool = False,
    encoding: str = "UTF-8",
) -> tuple[int, str]:
    """Run pypdfbox's ``ExtractText`` for one combo; return (exit, body)."""
    tool = ExtractText()
    tool.infile = infile
    tool.start_page = start
    tool.end_page = end
    tool.sort = sort
    tool.to_html = html
    tool.to_md = md
    tool.add_file_name = add_file_name
    tool.encoding = encoding
    tool.to_console = console
    outfile = outdir / "probe.out"
    if not console:
        tool.outfile = outfile

    if console:
        old = sys.stdout
        buf = io.StringIO()
        sys.stdout = buf
        try:
            rc = tool.call()
        finally:
            sys.stdout = old
        # The regression guard: console must NOT close the real stdout.
        assert not old.closed, "ExtractText -console closed sys.stdout"
        captured = buf.getvalue()
        body = "\n".join(
            line for line in captured.split("\n") if line not in _NOTICES
        )
        return rc, body

    # File output: suppress the informational notices that go to real stdout.
    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        rc = tool.call()
    finally:
        sys.stdout = old
    body = outfile.read_text(encoding=encoding) if outfile.is_file() else ""
    return rc, body


def _java(infile: Path, outdir: Path, spec: str) -> tuple[int, str]:
    raw = run_probe_text(
        "ExtractTextToolFuzzProbe", str(infile), str(outdir), spec
    )
    head, _, body = raw.partition("---OUTPUT---\n")
    exit_line = head.strip().splitlines()[-1]
    assert exit_line.startswith("EXIT="), raw
    return int(exit_line[len("EXIT=") :]), body


def _content_tokens(text: str) -> list[str]:
    """Non-empty, whitespace-stripped lines — the structural content."""
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


# ===========================================================================
# byte-identical combos: plain + html, file + console, ranges, sort
# ===========================================================================


@requires_oracle
@pytest.mark.parametrize(
    ("spec", "kwargs"),
    [
        ("start=1;end=2147483647;console=true", dict(console=True)),
        ("start=2;end=3;console=true", dict(start=2, end=3, console=True)),
        ("start=1;end=1;console=true", dict(start=1, end=1, console=True)),
        ("start=4;end=4;console=true", dict(start=4, end=4, console=True)),
        ("start=4;end=4;sort=true;console=true",
         dict(start=4, end=4, sort=True, console=True)),
        ("start=99;console=true", dict(start=99, console=True)),
        ("start=3;end=1;console=true", dict(start=3, end=1, console=True)),
        ("addFileName=true;start=1;end=1;console=true",
         dict(add_file_name=True, start=1, end=1, console=True)),
        ("html=true;console=true", dict(html=True, console=True)),
        ("html=true;start=2;end=3;console=true",
         dict(html=True, start=2, end=3, console=True)),
        ("start=2;end=3", dict(start=2, end=3)),
        ("start=1;end=1;encoding=ISO-8859-1",
         dict(start=1, end=1, encoding="ISO-8859-1")),
        ("html=true", dict(html=True)),
    ],
    ids=[
        "plain_whole_console",
        "plain_range_2_3_console",
        "plain_page1_console",
        "plain_page4_console",
        "plain_page4_sort_console",
        "plain_start_oob_console",
        "plain_start_gt_end_console",
        "plain_addfilename_console",
        "html_whole_console",
        "html_range_console",
        "plain_range_file",
        "plain_latin1_file",
        "html_whole_file",
    ],
)
def test_extract_text_tool_matches_pdfbox_exact(
    tmp_path: Path, spec: str, kwargs: dict
) -> None:
    src = tmp_path / "multi.pdf"
    _build_multipage(src)
    outdir = tmp_path / "out"
    outdir.mkdir()

    j_exit, j_body = _java(src, outdir, spec)
    p_exit, p_body = _py_call(src, outdir, **kwargs)

    assert p_exit == j_exit, f"exit code divergence for {spec!r}"
    assert p_body == j_body, (
        f"ExtractText tool divergence for {spec!r}:\n"
        f"  java: {j_body!r}\n  py:   {p_body!r}"
    )


@requires_oracle
def test_extract_text_tool_sort_reorders_like_pdfbox(tmp_path: Path) -> None:
    """-sort page 4: the upper run must precede the lower run on both sides."""
    src = tmp_path / "multi.pdf"
    _build_multipage(src)
    outdir = tmp_path / "out"
    outdir.mkdir()

    j_exit, j_body = _java(src, outdir, "start=4;end=4;sort=true;console=true")
    p_exit, p_body = _py_call(src, outdir, start=4, end=4, sort=True, console=True)

    assert (p_exit, p_body) == (j_exit, j_body)
    assert p_body.index("UPPER foxtrot") < p_body.index("LOWER echo")


# ===========================================================================
# -md: content tokens identical, whitespace run lengths legitimately differ
# ===========================================================================


@requires_oracle
def test_extract_text_tool_md_content_matches_pdfbox(tmp_path: Path) -> None:
    src = tmp_path / "multi.pdf"
    _build_multipage(src)
    outdir = tmp_path / "out"
    outdir.mkdir()

    j_exit, j_body = _java(src, outdir, "md=true;console=true")
    p_exit, p_body = _py_call(src, outdir, md=True, console=True)

    assert p_exit == 0 and j_exit == 0
    # Honest divergence: -md blank-line separator counts differ (article-start
    # vs page-start separator ordering). The page content order is identical.
    assert _content_tokens(p_body) == _content_tokens(j_body), (
        "ExtractText -md content divergence:\n"
        f"  java tokens: {_content_tokens(j_body)}\n"
        f"  py   tokens: {_content_tokens(p_body)}"
    )
    assert _content_tokens(p_body) == [
        "PAGE ONE alpha",
        "PAGE TWO bravo",
        "PAGE THREE charlie",
        "LOWER echo",
        "UPPER foxtrot",
    ]


@requires_oracle
def test_extract_text_tool_md_does_not_crash(tmp_path: Path) -> None:
    """Regression: -md used to raise TypeError in PDFText2Markdown.write_string
    (missing the (text, positions, sink) overload the parent walk passes)."""
    src = tmp_path / "single.pdf"
    _build_single(src)
    outdir = tmp_path / "out"
    outdir.mkdir()
    p_exit, p_body = _py_call(src, outdir, md=True, console=True)
    assert p_exit == 0
    assert "ONLY PAGE solo" in p_body


# ===========================================================================
# empty / single page
# ===========================================================================


@requires_oracle
def test_extract_text_tool_single_page_matches_pdfbox(tmp_path: Path) -> None:
    src = tmp_path / "single.pdf"
    _build_single(src)
    outdir = tmp_path / "out"
    outdir.mkdir()

    j_exit, j_body = _java(src, outdir, "console=true")
    p_exit, p_body = _py_call(src, outdir, console=True)

    assert (p_exit, p_body) == (j_exit, j_body)
    assert p_body == "ONLY PAGE solo\n"


@requires_oracle
def test_extract_text_tool_empty_page_divergence(tmp_path: Path) -> None:
    """A text-free page: both sides exit 0 with no extracted content.

    Honest divergence: pypdfbox's core PDFTextStripper emits a trailing
    page-separator ``"\\n"`` for a blank page where upstream emits nothing.
    This lives in the stripper core (out of scope for the tool surface), so we
    pin the documented difference and compare after stripping trailing space.
    """
    src = tmp_path / "empty.pdf"
    _build_empty(src)
    outdir = tmp_path / "out"
    outdir.mkdir()

    j_exit, j_body = _java(src, outdir, "console=true")
    p_exit, p_body = _py_call(src, outdir, console=True)

    assert p_exit == j_exit == 0
    assert j_body == ""
    # pypdfbox-side documented divergence: trailing "\n" page separator.
    assert p_body in ("", "\n")
    assert p_body.strip() == "" == j_body.strip()


@requires_oracle
def test_extract_text_tool_console_does_not_close_stdout(tmp_path: Path) -> None:
    """Regression: -console returned bare sys.stdout, which call()'s finally
    closed. _ConsoleWriter now mirrors upstream's no-op-close PrintWriter."""
    src = tmp_path / "single.pdf"
    _build_single(src)
    outdir = tmp_path / "out"
    outdir.mkdir()
    # _py_call asserts `not old.closed` after the console run; a second run in
    # the same process would fail if the first had closed stdout.
    _py_call(src, outdir, console=True)
    rc, body = _py_call(src, outdir, console=True)
    assert rc == 0 and "ONLY PAGE solo" in body
