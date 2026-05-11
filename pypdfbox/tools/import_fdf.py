"""``ImportFDF`` class port — imports FDF form data into a PDF.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/ImportFDF.java
    (lines 41-125)
"""
from __future__ import annotations

import argparse
import contextlib
from pathlib import Path

from pypdfbox.loader import Loader


class ImportFDF:
    def __init__(self) -> None:
        self.infile: Path | None = None
        self.outfile: Path | None = None
        self.fdffile: Path | None = None

    def import_fdf(self, pdf_document, fdf_document) -> None:  # noqa: ANN001 — mirror upstream sig
        """Mirror of ``ImportFDF.importFDF(PDDocument, FDFDocument)``."""
        doc_catalog = pdf_document.get_document_catalog()
        acro_form = doc_catalog.get_acro_form()
        if acro_form is None:
            return
        acro_form.set_cache_fields(True)
        acro_form.import_fdf(fdf_document)
        # TODO this can be removed when we create appearance streams
        acro_form.set_need_appearances(True)

    def call(self) -> int:
        if self.infile is None or self.fdffile is None:
            raise OSError("infile and fdffile are required")
        importer = ImportFDF()
        try:
            with Loader.load_pdf(self.infile) as pdf:
                fdf = Loader.load_fdf(self.fdffile)
                try:
                    importer.import_fdf(pdf, fdf)
                    if self.outfile is None:
                        self.outfile = self.infile
                    pdf.save(self.outfile)
                finally:
                    with contextlib.suppress(Exception):
                        fdf.close()
        except OSError as ioe:
            import sys
            sys.stderr.write(
                f"Error importing FDF data [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        return 0

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="importfdf",
            description="Imports AcroForm form data from FDF",
        )
        parser.add_argument("-i", "--input", dest="infile", required=True)
        parser.add_argument("-o", "--output", dest="outfile", default=None)
        parser.add_argument("--data", dest="fdffile", required=True)
        ns = parser.parse_args(args)
        runner = ImportFDF()
        runner.infile = Path(ns.infile)
        runner.outfile = Path(ns.outfile) if ns.outfile else None
        runner.fdffile = Path(ns.fdffile)
        return runner.call()


if __name__ == "__main__":
    import sys
    sys.exit(ImportFDF.main(sys.argv[1:]))
