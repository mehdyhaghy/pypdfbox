"""``PDFMerger`` class port — mirrors ``org.apache.pdfbox.tools.PDFMerger``.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/PDFMerger.java (lines 38-93)

The upstream class is a picocli ``Callable<Integer>`` wrapping
``PDFMergerUtility``. We keep the class name + ``call`` contract identical
and provide a stdlib-``argparse``-based ``main(args)`` entry point so the
class is invokable standalone for parity.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pypdfbox.multipdf.pdf_merger_utility import PDFMergerUtility


class PDFMerger:
    """Concatenate input PDFs into a single output PDF.

    Mirrors upstream ``PDFMerger`` exactly: ``call()`` returns 0 on
    success, 4 on I/O error (``OSError``). Inputs / outputs are exposed
    via attributes so callers may drive the class without the CLI.
    """

    def __init__(self) -> None:
        # Mirrors upstream private fields infiles / outfile.
        self.infiles: list[Path] = []
        self.outfile: Path | None = None

    # --- picocli `Callable.call()` mirror ------------------------------
    def call(self) -> int:
        """Run the merge. Returns 0 on success, 4 on I/O error."""
        merger = PDFMergerUtility()
        try:
            for infile in self.infiles:
                merger.add_source(str(Path(infile).resolve()))
            if self.outfile is None:
                raise OSError("outfile is required")
            merger.set_destination_file_name(str(Path(self.outfile).resolve()))
            merger.merge_documents()
        except OSError as ioe:
            # Upstream prints to System.err; we route the string the same way
            # but keep stderr noise out of the public method body.
            import sys
            sys.stderr.write(
                f"Error merging documents [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        return 0

    # --- entry point ----------------------------------------------------
    @staticmethod
    def main(args: list[str] | None = None) -> int:
        """Standalone CLI entry point.

        Mirrors upstream ``PDFMerger.main(String[] args)``.
        """
        parser = argparse.ArgumentParser(
            prog="merge", description="Merges multiple PDF documents into one"
        )
        parser.add_argument(
            "-i", "--input", dest="infiles", required=True, nargs="+",
            help="the PDF files to merge",
        )
        parser.add_argument(
            "-o", "--output", dest="outfile", required=True,
            help="the merged PDF file",
        )
        ns = parser.parse_args(args)
        merger = PDFMerger()
        merger.infiles = [Path(p) for p in ns.infiles]
        merger.outfile = Path(ns.outfile)
        return merger.call()


if __name__ == "__main__":
    import sys
    sys.exit(PDFMerger.main(sys.argv[1:]))
