"""``ExtractXMP`` class port — extracts XMP metadata from PDF / page.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/ExtractXMP.java
    (lines 41-139)
"""
from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

from pypdfbox.cos import COSDocument
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.pd_document import PDDocument


@contextlib.contextmanager
def _open_doc(infile, password):  # noqa: ANN001
    """Open ``infile`` and yield a :class:`PDDocument`.

    See :func:`pypdfbox.tools.extract_text._open_doc` for the rationale —
    a shared helper to bridge ``Loader.load_pdf`` (returns COSDocument)
    and the test-shim pattern (returns a context manager yielding
    PDDocument).
    """
    result = Loader.load_pdf(infile, password)
    if isinstance(result, COSDocument):
        pd = PDDocument(result)
        try:
            yield pd
        finally:
            pd.close()
        return
    with result as doc:
        yield doc


class ExtractXMP:
    def __init__(self) -> None:
        self.page: int = 0
        self.password: str = ""
        self.to_console: bool = False
        self.infile: Path | None = None
        self.outfile: Path | None = None

    def call(self) -> int:
        if self.infile is None:
            raise OSError("infile is required")
        if self.outfile is None:
            self.outfile = Path(self.infile).resolve().with_suffix(".xml")
        try:
            with _open_doc(self.infile, self.password) as document:
                catalog = document.get_document_catalog()
                meta = None
                if self.page == 0:
                    meta = catalog.get_metadata()
                else:
                    if self.page > document.get_number_of_pages():
                        sys.stderr.write(f"Page {self.page} doesn't exist\n")
                        return 1
                    page = document.get_page(self.page - 1)
                    meta = page.get_metadata()
                if meta is None:
                    sys.stderr.write("No XMP metadata available\n")
                    return 1
                payload = meta.to_byte_array()
                if self.to_console:
                    sys.stdout.buffer.write(payload)
                    sys.stdout.flush()
                else:
                    Path(self.outfile).write_bytes(payload)
        except OSError as ioe:
            sys.stderr.write(
                f"Error extracting text for document [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        return 0

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="extractxmp",
            description="Extracts the xmp stream from a PDF document",
        )
        parser.add_argument("-page", type=int, default=0)
        parser.add_argument("-password", default="")
        parser.add_argument("-console", action="store_true", dest="console")
        parser.add_argument("-i", "--input", dest="infile", required=True)
        parser.add_argument("-o", "--output", dest="outfile", default=None)
        ns = parser.parse_args(args)
        runner = ExtractXMP()
        runner.page = ns.page
        runner.password = ns.password
        runner.to_console = ns.console
        runner.infile = Path(ns.infile)
        runner.outfile = Path(ns.outfile) if ns.outfile else None
        return runner.call()


if __name__ == "__main__":  # pragma: no cover — module-as-script entrypoint
    sys.exit(ExtractXMP.main(sys.argv[1:]))
