"""
``pypdfbox split -i in.pdf [-split N] [-startPage X -endPage Y]
[-outputPrefix prefix] [-password PWD]`` — break a PDF into per-N-page
output files.

Mirrors upstream ``org.apache.pdfbox.tools.PDFSplit``, which delegates to
``org.apache.pdfbox.multipdf.Splitter``. We do the same — see
``pypdfbox.multipdf.splitter.Splitter`` for the per-chunk behaviour and
the structure-tree cloning deviation noted in ``CHANGES.md``.

Default behaviour matches upstream:

* When neither ``-split`` nor a page range is given, split every page
  into its own file (split-at-page = 1).
* When only a page range is given (``-startPage`` and/or ``-endPage``)
  with no explicit ``-split``, the entire range is emitted as a single
  output file. This matches PDFBox's ``setSplitAtPage(numberOfPages)``
  fallback when start/end are present but split is unset.
* When ``-split N`` is given (with or without a range), the range is
  chunked at every ``N`` pages.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel import PDDocument


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "split",
        help="split a PDF into per-N-page output files",
        description="Split a PDF into multiple output files. Default chunk size "
        "is 1 page; use -split N to bundle N pages per output. -startPage / "
        "-endPage select a 1-based inclusive page range to split (rest of "
        "the document is ignored). When a range is supplied without -split, "
        "the entire range is emitted as a single output file (upstream "
        "parity).",
    )
    p.add_argument(
        "-i", "--input", dest="input", required=True, metavar="INFILE",
        help="PDF file to split",
    )
    p.add_argument(
        "-split", dest="split", type=int, default=-1, metavar="N",
        help="split after this many pages (default 1, if startPage and "
        "endPage are unset)",
    )
    p.add_argument(
        "-startPage", dest="start_page", type=int, default=-1,
        metavar="N", help="1-based first page to include (default 1)",
    )
    p.add_argument(
        "-endPage", dest="end_page", type=int, default=-1,
        metavar="N", help="1-based last page to include (default last)",
    )
    p.add_argument(
        "-outputPrefix", dest="output_prefix", default=None,
        metavar="PREFIX",
        help="filename prefix for split files (default: input stem)",
    )
    p.add_argument(
        "-password", "--password", dest="password", default=None,
        metavar="PASSWORD",
        help="password to decrypt the document",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    src_path = Path(args.input)
    if not src_path.is_file():
        print(f"split: {src_path}: not a file", flush=True)
        return 4
    # ``-split == -1`` is the upstream sentinel meaning "not supplied"; any
    # other non-positive value is a user error.
    if args.split != -1 and args.split < 1:
        print(f"split: -split must be >= 1 (got {args.split})", flush=True)
        return 2
    if args.start_page != -1 and args.start_page < 1:
        print(
            f"split: -startPage must be >= 1 (got {args.start_page})",
            flush=True,
        )
        return 2
    if args.end_page != -1 and args.end_page < 1:
        print(
            f"split: -endPage must be >= 1 (got {args.end_page})",
            flush=True,
        )
        return 2

    prefix = args.output_prefix or src_path.with_suffix("").name
    out_dir = src_path.parent

    with PDDocument.load(src_path, password=args.password) as doc:
        total = doc.get_number_of_pages()
        # Resolve 1-based inclusive range, defaulting to the full document.
        start = args.start_page if args.start_page > 0 else 1
        end = args.end_page if args.end_page > 0 else total
        if start > end or start > total:
            print(
                f"split: empty page range ({start}..{end}) for {total}-page "
                "document",
                flush=True,
            )
            return 2
        end = min(end, total)

        # Upstream PDFSplit logic (PDFSplit.java#call):
        #   if startPage != -1 and split == -1: setSplitAtPage(numberOfPages)
        #   if endPage   != -1 and split == -1: setSplitAtPage(endPage)
        #   if split     != -1:                 setSplitAtPage(split)
        #   else if no range:                   setSplitAtPage(1)
        # The net effect: a bare range with no explicit -split becomes a
        # single-output split.
        start_end_set = args.start_page != -1 or args.end_page != -1
        if args.split != -1:
            split_at = args.split
        elif start_end_set:
            # Use endPage if set, else numberOfPages — both are >= range
            # length, so the range emerges as one chunk either way.
            split_at = args.end_page if args.end_page != -1 else total
        else:
            split_at = 1

        splitter = Splitter()
        splitter.set_split_at_page(split_at)
        splitter.set_start_page(start)
        splitter.set_end_page(end)
        chunks = splitter.split(doc)
        for ordinal, out_doc in enumerate(chunks, start=1):
            try:
                out_path = out_dir / f"{prefix}-{ordinal}.pdf"
                out_doc.save(out_path)
                print(str(out_path))
            finally:
                out_doc.close()
    return 0
