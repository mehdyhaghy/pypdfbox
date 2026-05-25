"""``ImportXFDF`` class port — imports XFDF form data into a PDF.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/ImportXFDF.java
    (lines 42-119)
"""
from __future__ import annotations

import argparse
import contextlib
from pathlib import Path

from pypdfbox.loader import Loader


class ImportXFDF:
    def __init__(self) -> None:
        self.infile: Path | None = None
        self.outfile: Path | None = None
        self.xfdffile: Path | None = None

    def import_fdf(self, pdf_document, fdf_document) -> None:  # noqa: ANN001
        """Mirror of ``ImportXFDF.importFDF(PDDocument, FDFDocument)``.

        Note: upstream sets ``cacheFields`` then calls ``importFDF`` —
        no ``setNeedAppearances`` here (vs. plain ImportFDF).
        """
        doc_catalog = pdf_document.get_document_catalog()
        acro_form = doc_catalog.get_acro_form()
        if acro_form is None:
            return
        acro_form.set_cache_fields(True)
        acro_form.import_fdf(fdf_document)

    def call(self) -> int:
        if self.infile is None or self.xfdffile is None:
            raise OSError("infile and xfdffile are required")
        importer = ImportXFDF()
        try:
            with Loader.load_pdf(self.infile) as pdf:
                fdf = Loader.load_xfdf(self.xfdffile)
                try:
                    importer.import_fdf(pdf, fdf)
                    if self.outfile is None:
                        self.outfile = self.infile
                    pdf.save(self.outfile)
                finally:
                    if fdf is not None:  # pragma: no branch
                        # Defensive: the with-statement above guarantees
                        # fdf was opened (or an exception bubbled out
                        # before this finally ran); the False arm has
                        # no live caller.
                        with contextlib.suppress(Exception):
                            fdf.close()
        except OSError as ioe:
            import sys
            sys.stderr.write(
                f"Error importing XFDF data [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        return 0

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="importxfdf",
            description="Imports AcroForm form data from XFDF",
        )
        parser.add_argument("-i", "--input", dest="infile", required=True)
        parser.add_argument("-o", "--output", dest="outfile", default=None)
        parser.add_argument("--data", dest="xfdffile", required=True)
        ns = parser.parse_args(args)
        runner = ImportXFDF()
        runner.infile = Path(ns.infile)
        runner.outfile = Path(ns.outfile) if ns.outfile else None
        runner.xfdffile = Path(ns.xfdffile)
        return runner.call()


if __name__ == "__main__":
    import sys
    sys.exit(ImportXFDF.main(sys.argv[1:]))
