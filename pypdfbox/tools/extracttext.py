"""
``pypdfbox extracttext -i in.pdf [-o out.txt] [-startPage N] [-endPage M]
[-password PWD] [-encoding ENC] [-sort] [-console] [-addFileName] [-append]``
— extract plain text from a PDF.

Mirrors upstream ``org.apache.pdfbox.tools.ExtractText``. Upstream loads
the PDF (optionally with a password), checks the ``canExtractContent``
permission bit, runs ``PDFTextStripper`` page-by-page over the requested
page range, and writes the result to ``-o`` (defaulting to
``<input>.txt``) or to the console when ``-console`` is set.

Skipped flags (require subsystems pypdfbox does not yet ship):

* ``-html``  — needs ``PDFText2HTML``.
* ``-md``    — needs ``PDFText2Markdown``.
* ``-rotationMagic`` — needs the AngleCollector / FilteredTextStripper
  cluster.
* ``-debug`` — upstream uses it to log timings; we leave that to callers.
* ``-alwaysNext`` — error-recovery flag for a multi-page extraction loop;
  pypdfbox's stripper already raises rather than aborting silently, so
  the equivalent is just retrying with a narrower ``-startPage``/``-endPage``
  window.
* ``-ignoreBeads`` — flips ``setShouldSeparateByBeads(false)``; cheap to
  add later but currently no-op since article-thread sorting isn't
  exposed in the pypdfbox stripper output.

Embedded-PDF extraction (the ``/Names → /EmbeddedFiles`` walk in
upstream's ``call``) is not implemented; pypdfbox does not yet expose a
``PDDocumentNameDictionary`` facade rich enough to enumerate embedded
files.

Exit codes follow upstream:
  0  success
  1  permission denied or password incorrect
  4  IO error (raised as ``OSError`` and caught by ``cli.run_cli``)
"""
from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Iterator, TextIO

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.encryption import PDInvalidPasswordException
from pypdfbox.text import PDFTextStripper

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
    p.set_defaults(func=run)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _default_output(infile: Path) -> Path:
    """Mirror upstream ``FilenameUtils.removeExtension(infile) + ".txt"``."""
    return infile.with_suffix(".txt")


@contextmanager
def _open_writer(
    *, to_console: bool, outfile: Path | None, encoding: str, append: bool,
) -> Iterator[TextIO | IO[str]]:
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
    output,
    *,
    start_page: int = 1,
    end_page: int = sys.maxsize,
    sort: bool = False,
) -> None:
    """Run ``PDFTextStripper`` over ``document`` and write the resulting
    text into ``output`` (any file-like object with a ``.write(str)``).

    Mirrors the body of upstream ``ExtractText.extractPages`` plus the
    ``setSortByPosition`` / ``setStartPage`` / ``setEndPage`` calls from
    ``call``. Page bounds are clamped to ``[1, document.page_count]``,
    matching upstream's ``Math.min(endPage, getNumberOfPages())``.
    """
    stripper = PDFTextStripper()
    stripper.set_sort_by_position(bool(sort))
    total = document.get_number_of_pages()
    first = max(1, int(start_page))
    last = min(int(end_page), total)
    stripper.set_start_page(first)
    stripper.set_end_page(last)
    output.write(stripper.get_text(document))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"extracttext: {src}: not a file", flush=True)
        return 4

    encoding = args.encoding or _STD_ENCODING
    if args.to_console:
        outfile: Path | None = None
    else:
        outfile = Path(args.output) if args.output else _default_output(src)

    try:
        doc = PDDocument.load(src, password=args.password or "")
    except PDInvalidPasswordException as exc:
        print(f"extracttext: {exc}", flush=True)
        return 1

    try:
        ap = doc.get_current_access_permission()
        if ap is not None and not ap.can_extract_content():
            print("extracttext: You do not have permission to extract text",
                  flush=True)
            return 1

        with _open_writer(
            to_console=args.to_console,
            outfile=outfile,
            encoding=encoding,
            append=args.append,
        ) as output:
            if args.add_file_name:
                output.write(f"PDF file: {src}\n")
            extract_text(
                doc,
                output,
                start_page=args.start_page,
                end_page=args.end_page,
                sort=args.sort,
            )
    finally:
        doc.close()
    return 0
