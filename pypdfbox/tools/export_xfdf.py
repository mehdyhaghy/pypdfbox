"""``ExportXFDF`` class port — exports AcroForm fields as XFDF.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/ExportXFDF.java
    (lines 41-106)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pypdfbox.loader import Loader


class ExportXFDF:
    def __init__(self) -> None:
        self.infile: Path | None = None
        self.outfile: Path | None = None

    def call(self) -> int:
        if self.infile is None:
            raise OSError("infile is required")
        try:
            with Loader.load_pdf(self.infile) as pdf:
                form = pdf.get_document_catalog().get_acro_form()
                if form is None:
                    import sys
                    sys.stderr.write("Error: This PDF does not contain a form.\n")
                else:
                    if self.outfile is None:
                        self.outfile = Path(self.infile).resolve().with_suffix(".xfdf")
                    try:
                        fdf = form.export_fdf()
                    except (AttributeError, NotImplementedError) as exc:
                        raise OSError(f"export_fdf unsupported: {exc}") from exc
                    fdf.save_xfdf(str(self.outfile))
        except OSError as ioe:
            import sys
            sys.stderr.write(
                f"Error exporting XFDF data [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        return 0

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="exportxfdf",
            description="Exports AcroForm form data to XFDF",
        )
        parser.add_argument("-i", "--input", dest="infile", required=True)
        parser.add_argument("-o", "--output", dest="outfile", required=True)
        ns = parser.parse_args(args)
        runner = ExportXFDF()
        runner.infile = Path(ns.infile)
        runner.outfile = Path(ns.outfile)
        return runner.call()


if __name__ == "__main__":
    import sys
    sys.exit(ExportXFDF.main(sys.argv[1:]))
