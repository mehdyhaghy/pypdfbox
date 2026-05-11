"""``PDFSplit`` class port — mirrors ``org.apache.pdfbox.tools.PDFSplit``.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/PDFSplit.java (lines 42-156)

A picocli ``Callable<Integer>`` that wraps ``Splitter``. Splits a PDF
into N-page chunks (or a single-page-per-file default) and writes the
output files with the configured prefix.
"""
from __future__ import annotations

import argparse
import contextlib
from pathlib import Path

from pypdfbox.loader import Loader
from pypdfbox.multipdf.splitter import Splitter


class PDFSplit:
    """Split a PDF document into multiple smaller PDFs.

    Mirrors upstream behavior:
      - default split-at-page is 1
      - if ``-startPage`` set, also set ``splitAtPage`` to number_of_pages
      - if ``-endPage`` set, also set ``splitAtPage`` to ``endPage``
      - explicit ``-split`` always wins
    """

    def __init__(self) -> None:
        self.password: str | None = None
        self.split: int = -1
        self.start_page: int = -1
        self.end_page: int = -1
        self.output_prefix: str | None = None
        self.infile: Path | None = None

    def call(self) -> int:
        if self.infile is None:
            raise OSError("infile is required")
        splitter = Splitter()
        if self.output_prefix is None:
            self.output_prefix = str(Path(self.infile).resolve().with_suffix(""))
        documents: list = []
        try:
            with Loader.load_pdf(self.infile, self.password) as document:
                start_end_page_set = False
                if self.start_page != -1:
                    splitter.set_start_page(self.start_page)
                    start_end_page_set = True
                    if self.split == -1:
                        splitter.set_split_at_page(document.get_number_of_pages())
                if self.end_page != -1:
                    splitter.set_end_page(self.end_page)
                    start_end_page_set = True
                    if self.split == -1:
                        splitter.set_split_at_page(self.end_page)
                if self.split != -1:
                    splitter.set_split_at_page(self.split)
                else:
                    if not start_end_page_set:
                        splitter.set_split_at_page(1)
                documents = splitter.split(document)
                for i, doc in enumerate(documents):
                    doc.save(f"{self.output_prefix}-{i + 1}.pdf")
        except OSError as ioe:
            import sys
            sys.stderr.write(
                f"Error splitting document [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        finally:
            for doc in documents:
                with contextlib.suppress(Exception):
                    doc.close()
        return 0

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="pdfsplit",
            description="Splits a PDF document into number of new documents",
        )
        parser.add_argument("-password", default=None)
        parser.add_argument("-split", type=int, default=-1)
        parser.add_argument("-startPage", dest="startPage", type=int, default=-1)
        parser.add_argument("-endPage", dest="endPage", type=int, default=-1)
        parser.add_argument(
            "-outputPrefix", dest="outputPrefix", default=None,
        )
        parser.add_argument("-i", "--input", dest="infile", required=True)
        ns = parser.parse_args(args)
        runner = PDFSplit()
        runner.password = ns.password
        runner.split = ns.split
        runner.start_page = ns.startPage
        runner.end_page = ns.endPage
        runner.output_prefix = ns.outputPrefix
        runner.infile = Path(ns.infile)
        return runner.call()


if __name__ == "__main__":
    import sys
    sys.exit(PDFSplit.main(sys.argv[1:]))
