"""
``pypdfbox extracttext -i in.pdf [-o out.txt] [-startPage N] [-endPage M]
[-password PWD] [-encoding ENC] [-sort] [-console] [-addFileName] [-append]
[-html] [-md] [-rotationMagic] [-ignoreBeads] [-debug]``
— extract plain text from a PDF.

Mirrors upstream ``org.apache.pdfbox.tools.ExtractText``. Upstream loads
the PDF (optionally with a password), checks the ``canExtractContent``
permission bit, runs ``PDFTextStripper`` page-by-page over the requested
page range, and writes the result to ``-o`` (defaulting to
``<input>.txt``) or to the console when ``-console`` is set.

Notes on flag round-out:

* ``-html`` / ``-md`` — pypdfbox does not ship a ``PDFText2HTML`` /
  ``PDFText2Markdown`` subclass. We do the simplest faithful thing the
  upstream CLI promises: extract plain text and wrap it in a minimal
  HTML / Markdown document so callers can pipe the output into a
  browser / renderer. Default output extension changes to ``.html`` /
  ``.md`` accordingly. Recorded in ``CHANGES.md``.
* ``-debug`` — upstream prints per-page timings via a JUL ``Logger``;
  pypdfbox emits a one-line ``debug:`` summary to stderr instead.
* ``-ignoreBeads`` — flips ``set_should_separate_by_beads(False)``,
  matching upstream.
* ``-alwaysNext`` — error-recovery flag for a multi-page extraction loop;
  pypdfbox's stripper already raises rather than aborting silently, so
  the equivalent is just retrying with a narrower ``-startPage``/``-endPage``
  window.
* Embedded PDF extraction mirrors upstream's one-level
  ``/Names → /EmbeddedFiles`` walk. Only the default ``/EF /F`` embedded
  file is considered, and only when its subtype is exactly
  ``application/pdf``.

Exit codes follow upstream:
  0  success
  1  permission denied or password incorrect
  4  IO error (raised as ``OSError`` and caught by ``cli.run_cli``)
"""
from __future__ import annotations

import argparse
import html as _htmlmod
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.encryption import InvalidPasswordException
from pypdfbox.text import AngleCollector, FilteredTextStripper, PDFTextStripper

_STD_ENCODING = "UTF-8"


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "extracttext",
        help="extract text from a PDF document",
        description="Extract text from a PDF document. Loads the input "
        "(optionally with a password), runs PDFTextStripper across the "
        "requested page range, and writes the result to OUTFILE "
        "(or to stdout with -console).",
    )
    p.add_argument(
        "-i", "--input", dest="input", required=True, metavar="INFILE",
        help="the PDF file to extract text from",
    )
    p.add_argument(
        "-o", "--output", dest="output", default=None, metavar="OUTFILE",
        help="the exported text file (defaults to <input>.txt)",
    )
    p.add_argument(
        "-password", "--password", dest="password", default="", metavar="PASSWORD",
        help="password for the PDF (defaults to empty string)",
    )
    p.add_argument(
        "-encoding", "--encoding", dest="encoding", default=_STD_ENCODING,
        metavar="ENCODING",
        help="output text encoding (default: UTF-8)",
    )
    p.add_argument(
        "-startPage", "--startPage", dest="start_page", type=int, default=1,
        metavar="N",
        help="the first page to extract (1-based, inclusive; default 1)",
    )
    p.add_argument(
        "-endPage", "--endPage", dest="end_page", type=int, default=sys.maxsize,
        metavar="M",
        help="the last page to extract (1-based, inclusive; default last page)",
    )
    p.add_argument(
        "-sort", "--sort", dest="sort", action="store_true",
        help="sort text by position before writing",
    )
    p.add_argument(
        "-console", "--console", dest="to_console", action="store_true",
        help="send text to stdout instead of a file",
    )
    p.add_argument(
        "-addFileName", "--addFileName", dest="add_file_name",
        action="store_true",
        help="prepend a 'PDF file: <path>' line to the output",
    )
    p.add_argument(
        "-append", "--append", dest="append", action="store_true",
        help="append to the output file instead of overwriting it",
    )
    p.add_argument(
        "-rotationMagic", "--rotationMagic", dest="rotation_magic",
        action="store_true",
        help=(
            "analyse each page for rotated/skewed text and emit the runs "
            "for each rotation in turn (uses FilteredTextStripper)"
        ),
    )
    p.add_argument(
        "-html", "--html", dest="html", action="store_true",
        help="wrap the extracted text in a minimal HTML document",
    )
    p.add_argument(
        "-md", "--md", dest="md", action="store_true",
        help="wrap the extracted text in a minimal Markdown document",
    )
    p.add_argument(
        "-ignoreBeads", "--ignoreBeads", dest="ignore_beads",
        action="store_true",
        help=(
            "disable article-bead separation (equivalent to upstream's "
            "setShouldSeparateByBeads(false))"
        ),
    )
    p.add_argument(
        "-debug", "--debug", dest="debug", action="store_true",
        help="print extraction timing to stderr",
    )
    p.set_defaults(func=run)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _default_output(infile: Path, *, html: bool = False, md: bool = False) -> Path:
    """Mirror upstream ``FilenameUtils.removeExtension(infile) + ".txt"``.

    When ``-html`` or ``-md`` is set the upstream CLI swaps the default
    extension to ``.html`` / ``.md``; we follow that.
    """
    if html:
        return infile.with_suffix(".html")
    if md:
        return infile.with_suffix(".md")
    return infile.with_suffix(".txt")


def _wrap_html(body: str) -> str:
    """Minimal HTML wrapper. Mirrors upstream ``PDFText2HTML`` only at the
    structural level — head + body + ``<pre>`` to preserve whitespace."""
    return (
        "<html>\n"
        "<head><meta charset=\"UTF-8\"><title>extracttext</title></head>\n"
        "<body>\n"
        f"<pre>{_htmlmod.escape(body)}</pre>\n"
        "</body>\n"
        "</html>\n"
    )


def _wrap_md(body: str) -> str:
    """Minimal Markdown wrapper — fence the extracted text so newlines
    survive untouched."""
    return f"```\n{body}\n```\n"


@contextmanager
def _open_writer(
    *, to_console: bool, outfile: Path | None, encoding: str, append: bool,
) -> Iterator[IO[str]]:
    """Yield a writer matching upstream's ``createOutputWriter``.

    On ``-console`` we write to ``sys.stdout`` and explicitly do not
    close it, matching upstream's PrintWriter override.
    """
    if to_console:
        yield sys.stdout
        return
    assert outfile is not None  # narrowed by run()
    mode = "a" if append else "w"
    with open(outfile, mode, encoding=encoding) as fh:
        yield fh


def extract_text(
    document: PDDocument,
    output: IO[str],
    *,
    start_page: int = 1,
    end_page: int = sys.maxsize,
    sort: bool = False,
    rotation_magic: bool = False,
    ignore_beads: bool = False,
) -> None:
    """Run ``PDFTextStripper`` over ``document`` and write the resulting
    text into ``output`` (any file-like object with a ``.write(str)``).

    Mirrors the body of upstream ``ExtractText.extractPages`` plus the
    ``setSortByPosition`` / ``setStartPage`` / ``setEndPage`` calls from
    ``call``. Page bounds are clamped to ``[1, document.page_count]``,
    matching upstream's ``Math.min(endPage, getNumberOfPages())``.

    When ``rotation_magic`` is set, each page is first scanned by an
    :class:`~pypdfbox.text.AngleCollector` to discover the rotations
    actually used; then a :class:`~pypdfbox.text.FilteredTextStripper`
    runs once per discovered angle, emitting only text whose text matrix
    matches that rotation. Output preserves the upstream ordering: angle
    0 first, then 90, 180, 270 (rotation values are sorted ascending).
    """
    total = document.get_number_of_pages()
    first = max(1, int(start_page))
    last = min(int(end_page), total)
    if rotation_magic:
        _extract_text_rotation_magic(
            document, output, first=first, last=last, sort=bool(sort),
            ignore_beads=bool(ignore_beads),
        )
        return
    stripper = PDFTextStripper()
    stripper.set_sort_by_position(bool(sort))
    if ignore_beads:
        stripper.set_should_separate_by_beads(False)
    stripper.set_start_page(first)
    stripper.set_end_page(last)
    output.write(stripper.get_text(document))


def extract_embedded_pdfs(
    document: PDDocument,
    output: IO[str],
    *,
    sort: bool = False,
    rotation_magic: bool = False,
    ignore_beads: bool = False,
) -> None:
    """Extract top-level embedded PDFs after the main document.

    Mirrors upstream ``ExtractText``: walk catalog ``/Names /EmbeddedFiles``,
    use each file specification's default ``getEmbeddedFile()`` stream,
    require an exact ``application/pdf`` subtype match, and extract every
    page from the embedded document. This is intentionally one-level only;
    embedded PDFs inside embedded PDFs are not recursively traversed.
    """
    catalog = document.get_document_catalog()
    names = catalog.get_names()
    if names is None:
        return
    embedded_files = names.get_embedded_files()
    if embedded_files is None:
        return
    entries = embedded_files.get_names()
    if not entries:
        return

    for file_spec in entries.values():
        embedded = file_spec.get_embedded_file()
        if embedded is None or embedded.get_subtype() != "application/pdf":
            continue
        sub_doc = PDDocument.load(embedded.to_byte_array())
        try:
            extract_text(
                sub_doc,
                output,
                start_page=1,
                end_page=sys.maxsize,
                sort=sort,
                rotation_magic=rotation_magic,
                ignore_beads=ignore_beads,
            )
        finally:
            sub_doc.close()


def _extract_text_rotation_magic(
    document: PDDocument, output: IO[str], *, first: int, last: int, sort: bool,
    ignore_beads: bool = False,
) -> None:
    """Per-page rotation-aware extraction loop.

    Mirrors the ``rotationMagic`` branch of upstream
    ``ExtractText.extractPages``: for every page in ``[first, last]``,
    discover the rotations present via :class:`AngleCollector`, then run
    :class:`FilteredTextStripper` once per rotation. Upstream prepends a
    ``cm`` to the content stream to "un-rotate" the page before each
    pass; pypdfbox's lite stripper checks the text-matrix angle directly
    on emit, so the prepend dance is unnecessary.
    """
    if first > last:
        return
    for page_number in range(first, last + 1):
        collector = AngleCollector()
        collector.set_sort_by_position(sort)
        collector.set_start_page(page_number)
        collector.set_end_page(page_number)
        # Run the collector for its side effect of populating the angle
        # set; the text it returns is intentionally discarded.
        collector.get_text(document)
        angles = sorted(collector.get_angles())
        if not angles:
            # Upstream still calls ``writeText`` even when no glyphs were
            # seen so the page-start/page-end markers fire. Run a
            # zero-target stripper on the page so the output shape
            # matches the non-rotation-magic path.
            angles = [0]
        for angle in angles:
            stripper = FilteredTextStripper(target_angle=angle)
            stripper.set_sort_by_position(sort)
            if ignore_beads:
                stripper.set_should_separate_by_beads(False)
            stripper.set_start_page(page_number)
            stripper.set_end_page(page_number)
            output.write(stripper.get_text(document))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    import io as _io

    src = Path(args.input)
    if not src.is_file():
        print(f"extracttext: {src}: not a file", flush=True)
        return 4

    encoding = args.encoding or _STD_ENCODING
    html = bool(getattr(args, "html", False))
    md = bool(getattr(args, "md", False))
    if args.to_console:
        outfile: Path | None = None
    else:
        outfile = (
            Path(args.output)
            if args.output
            else _default_output(src, html=html, md=md)
        )

    try:
        doc = PDDocument.load(src, password=args.password or "")
    except InvalidPasswordException as exc:
        print(f"extracttext: {exc}", flush=True)
        return 1

    debug = bool(getattr(args, "debug", False))
    started = time.perf_counter() if debug else 0.0

    try:
        ap = doc.get_current_access_permission()
        if ap is not None and not ap.can_extract_content():
            print("extracttext: You do not have permission to extract text",
                  flush=True)
            return 1

        # When -html/-md is set we collect the body text first, then wrap.
        # Otherwise we stream straight into the output writer for parity
        # with upstream's per-page write loop.
        with _open_writer(
            to_console=args.to_console,
            outfile=outfile,
            encoding=encoding,
            append=args.append,
        ) as output:
            if html or md:
                buf = _io.StringIO()
                if args.add_file_name:
                    buf.write(f"PDF file: {src}\n")
                extract_text(
                    doc,
                    buf,
                    start_page=args.start_page,
                    end_page=args.end_page,
                    sort=args.sort,
                    rotation_magic=args.rotation_magic,
                    ignore_beads=args.ignore_beads,
                )
                extract_embedded_pdfs(
                    doc,
                    buf,
                    sort=args.sort,
                    rotation_magic=args.rotation_magic,
                    ignore_beads=args.ignore_beads,
                )
                wrapped = _wrap_html(buf.getvalue()) if html else _wrap_md(buf.getvalue())
                output.write(wrapped)
            else:
                if args.add_file_name:
                    output.write(f"PDF file: {src}\n")
                extract_text(
                    doc,
                    output,
                    start_page=args.start_page,
                    end_page=args.end_page,
                    sort=args.sort,
                    rotation_magic=args.rotation_magic,
                    ignore_beads=args.ignore_beads,
                )
                extract_embedded_pdfs(
                    doc,
                    output,
                    sort=args.sort,
                    rotation_magic=args.rotation_magic,
                    ignore_beads=args.ignore_beads,
                )
    finally:
        doc.close()
    if debug:
        elapsed = time.perf_counter() - started
        print(f"debug: extracttext finished in {elapsed:.3f}s",
              file=sys.stderr, flush=True)
    return 0
