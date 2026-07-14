"""``DecompressObjectstreams`` class port.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/DecompressObjectstreams.java
    (lines 42-97)

Loads a PDF and saves it back uncompressed (no object streams), useful
for hand-debugging files in a text editor.
"""
from __future__ import annotations

import argparse
import contextlib
from pathlib import Path

from pypdfbox.cos import COSDocument
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.pd_document import PDDocument


@contextlib.contextmanager
def _open_doc(infile, password=None):  # noqa: ANN001
    """Open ``infile`` and yield a :class:`PDDocument`. See
    :func:`pypdfbox.tools.extract_text._open_doc`."""
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


class DecompressObjectstreams:
    def __init__(self) -> None:
        self.usage_help_requested: bool = False
        self.infile: Path | None = None
        self.outfile: Path | None = None

    def call(self) -> int:
        if self.infile is None:
            raise OSError("infile is required")
        try:
            with _open_doc(self.infile) as doc:
                # overwrite inputfile if no outputfile was specified
                outfile = self.outfile if self.outfile is not None else self.infile
                # NO_COMPRESSION, like upstream — the whole point of this
                # tool is an output without object streams; the default
                # compressed save would immediately re-pack them.
                from pypdfbox.pdfwriter.compress import CompressParameters

                doc.save(outfile, CompressParameters.NO_COMPRESSION)
        except OSError as ioe:
            import sys
            sys.stderr.write(
                f"Error processing file [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        return 0

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="DecompressObjectstreams",
            description="Decompresses object streams in a PDF file.",
        )
        parser.add_argument("-i", "--input", dest="infile", required=True)
        parser.add_argument("-o", "--output", dest="outfile", default=None)
        ns = parser.parse_args(args)
        runner = DecompressObjectstreams()
        runner.infile = Path(ns.infile)
        runner.outfile = Path(ns.outfile) if ns.outfile else None
        return runner.call()


if __name__ == "__main__":
    import sys
    sys.exit(DecompressObjectstreams.main(sys.argv[1:]))
