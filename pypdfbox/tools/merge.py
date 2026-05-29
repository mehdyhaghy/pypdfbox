"""
``pypdfbox merge -i a.pdf -i b.pdf -o out.pdf`` — concatenate PDFs.

The ``-i/--input`` flag is repeatable, one input per flag, mirroring upstream
``org.apache.pdfbox.tools.PDFMerger``'s picocli synopsis
(``-i=<infile> [-i=<infile>]...``). The upstream picocli tool *rejects* a single
``-i`` gobbling several inputs (``-i a b c`` → usage error); we additionally
accept that space-separated form for convenience, so both ``-i a -i b`` and
``-i a b`` resolve to the same ordered input list.

Mirrors upstream ``org.apache.pdfbox.tools.PDFMerger``, which delegates the
real work to ``org.apache.pdfbox.multipdf.PDFMergerUtility``. This module
is a thin wrapper that registers a CLI subparser and routes the inputs /
output through :class:`pypdfbox.multipdf.PDFMergerUtility` — the merge
itself (page-tree concatenation, ``/AcroForm`` field uniquification,
``/Names`` / ``/Dests`` / ``/Outlines`` / ``/PageLabels`` / ``/Metadata``
reconciliation, structure-tree merging) lives in the utility, identical
to upstream behaviour.

Wave 1374 unified this CLI with :class:`PDFMergerUtility`. Previously the
CLI carried its own ``#2``-suffix dedup for name-tree collisions (named
destinations, embedded files, JS); upstream ``PDFMergerUtility`` lets the
duplicates ride in the flat ``/Names`` array. We follow upstream now so
``pypdfbox merge`` and the public ``PDFMergerUtility`` API produce the
same output.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pypdfbox.multipdf.pdf_merger_utility import PDFMergerUtility


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "merge",
        help="concatenate input PDFs into one output",
        description="Concatenate every page of every input PDF, in CLI order, "
        "into a single output PDF. Delegates to PDFMergerUtility for "
        "upstream-faithful catalog reconciliation (page tree, "
        "/AcroForm, /Names, /Dests, /Outlines, /PageLabels, /Metadata, "
        "/StructTreeRoot).",
    )
    p.add_argument(
        "-i", "--input", dest="inputs", action="append", nargs="+",
        required=True, metavar="INFILE",
        help="a PDF file to merge; repeat -i for each input (two or more)",
    )
    p.add_argument(
        "-o", "--output", required=True, metavar="OUTFILE",
        help="output PDF path",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    # ``action="append"`` + ``nargs="+"`` yields a list-of-lists (one inner list
    # per ``-i`` flag); flatten to the ordered flat input list. This accepts both
    # upstream's repeatable ``-i a -i b`` form and the ``-i a b`` shorthand.
    inputs: list[str] = [path for group in args.inputs for path in group]
    if len(inputs) < 2:
        print("merge: need at least two input files", flush=True)
        return 2
    output = Path(args.output)
    for raw in inputs:
        if not Path(raw).is_file():
            print(f"merge: {raw}: not a file", flush=True)
            return 4

    merger = PDFMergerUtility()
    for raw in inputs:
        merger.add_source(raw)
    merger.set_destination_file_name(str(output))
    try:
        merger.merge_documents()
    except OSError as exc:
        # Mirror upstream PDFMerger's user-visible error format:
        #   "Error merging documents [<ExcClass>]: <message>"
        # and its exit code (4).
        print(
            f"Error merging documents [{type(exc).__name__}]: {exc}",
            flush=True,
        )
        return 4
    return 0
