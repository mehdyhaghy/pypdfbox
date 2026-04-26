"""
``pypdfbox merge -i a.pdf b.pdf -o out.pdf`` — concatenate PDFs.

Mirrors upstream ``org.apache.pdfbox.tools.PDFMerger``, which delegates the
real work to ``org.apache.pdfbox.multipdf.PDFMergerUtility``. That utility
performs deep ``cloneForNewDocument`` graph copying so cross-document
references (named destinations, link annotations, structure trees, fonts,
XObjects) are remapped into the merged output.

**Cluster #1 limitation.** ``cloneForNewDocument`` is heavy and not yet
ported. This implementation does a *naive* concatenation: each input
document is loaded, every page is appended (by COS dictionary reference)
to a fresh output document, then the result is saved. Cross-document
references therefore are NOT remapped — link annotations pointing into
their source document, named destinations, structure-tree owners, and any
other graph that referenced the source page may break or dangle. Resources
embedded directly under each page (``/Resources`` inheritable attribute)
survive because pages keep their own dictionaries.

Once the multipdf cluster lands, this module switches over to
``PDFMergerUtility``. The CLI surface is intentionally identical so callers
do not have to change.

Add this caveat to ``CHANGES.md`` when the multipdf cluster is queued:

    > tools/merge.py: cluster #1 ships naive page-list concatenation. Cross-
    > document refs (links, named dests, struct tree) are not remapped.
    > Replaced by PDFMergerUtility once the multipdf cluster lands.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "merge",
        help="concatenate input PDFs into one output (naive — see docstring)",
        description="Concatenate every page of every input PDF, in CLI order, "
        "into a single output PDF. Cross-document references (link "
        "annotations, named destinations, struct tree) are NOT remapped — "
        "this is a cluster-#1 limitation pending the multipdf cluster.",
    )
    p.add_argument(
        "-i", "--input", dest="inputs", nargs="+", required=True,
        metavar="INFILE", help="PDF files to merge (two or more)",
    )
    p.add_argument(
        "-o", "--output", required=True, metavar="OUTFILE",
        help="output PDF path",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    inputs: list[str] = list(args.inputs)
    if len(inputs) < 2:
        print("merge: need at least two input files", flush=True)
        return 2
    output = Path(args.output)
    for raw in inputs:
        if not Path(raw).is_file():
            print(f"merge: {raw}: not a file", flush=True)
            return 4

    out_doc = PDDocument()
    # Keep input documents open until the save completes — pages still
    # reference their original COSStream contents (which are tied to the
    # source ``RandomAccessRead``).
    open_sources: list[PDDocument] = []
    try:
        for raw in inputs:
            src = PDDocument.load(raw)
            open_sources.append(src)
            for page in src.get_pages():
                # ``add_page`` calls into PDPageTree.add which re-parents the
                # page dict under the output's /Pages root (mutates the
                # page's /Parent pointer). That's fine for naive merge; the
                # source PDDocument is discarded after save.
                out_doc.add_page(PDPage(page.get_cos_object()))
        out_doc.save(output)
    finally:
        out_doc.close()
        for src in open_sources:
            src.close()
    return 0
