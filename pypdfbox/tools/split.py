"""
``pypdfbox split -i in.pdf [-split N] [-startPage X -endPage Y]
[-outputPrefix prefix]`` — break a PDF into per-N-page output files.

Mirrors upstream ``org.apache.pdfbox.tools.PDFSplit``, which uses
``org.apache.pdfbox.multipdf.Splitter``. Same caveat as ``merge``: cluster
#1 ships a naive splitter that copies page COS dictionaries into fresh
output documents without remapping cross-document references. Suitable
for the common case (split each page into its own file) but won't preserve
named-destination links or struct-tree owners that pointed at sibling
pages.

Default behaviour matches upstream: when neither ``-split`` nor a page
range is given, split every page into its own file.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "split",
        help="split a PDF into per-N-page output files (naive — see docstring)",
        description="Split a PDF into multiple output files. Default chunk size "
        "is 1 page; use -split N to bundle N pages per output. -startPage / "
        "-endPage select a 1-based inclusive page range to split (rest of "
        "the document is ignored).",
    )
    p.add_argument(
        "-i", "--input", dest="input", required=True, metavar="INFILE",
        help="PDF file to split",
    )
    p.add_argument(
        "-split", dest="split", type=int, default=1, metavar="N",
        help="split after this many pages (default 1)",
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
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    src_path = Path(args.input)
    if not src_path.is_file():
        print(f"split: {src_path}: not a file", flush=True)
        return 4
    if args.split < 1:
        print(f"split: -split must be >= 1 (got {args.split})", flush=True)
        return 2

    prefix = args.output_prefix or src_path.with_suffix("").name
    out_dir = src_path.parent

    with PDDocument.load(src_path) as doc:
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

        # Collect the source pages once — the iterator is forward-only and
        # we slice it into chunks below.
        pages = list(doc.get_pages())
        # 1-based -> 0-based slice for the in-range section.
        in_range = pages[start - 1 : end]

        chunk_size = args.split
        for chunk_index in range(0, len(in_range), chunk_size):
            chunk = in_range[chunk_index : chunk_index + chunk_size]
            out_doc = PDDocument()
            try:
                for page in chunk:
                    out_doc.add_page(PDPage(page.get_cos_object()))
                # Upstream numbers from 1 (output-1.pdf, output-2.pdf, ...).
                ordinal = (chunk_index // chunk_size) + 1
                out_path = out_dir / f"{prefix}-{ordinal}.pdf"
                out_doc.save(out_path)
                print(str(out_path))
            finally:
                out_doc.close()
    return 0
