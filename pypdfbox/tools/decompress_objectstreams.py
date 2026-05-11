"""``DecompressObjectstreams`` class port.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/DecompressObjectstreams.java
    (lines 42-97)

Loads a PDF and saves it back uncompressed (no object streams), useful
for hand-debugging files in a text editor.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pypdfbox.loader import Loader


class DecompressObjectstreams:
    def __init__(self) -> None:
        self.usage_help_requested: bool = False
        self.infile: Path | None = None
        self.outfile: Path | None = None

    def call(self) -> int:
        if self.infile is None:
            raise OSError("infile is required")
        try:
            with Loader.load_pdf(self.infile) as doc:
                # overwrite inputfile if no outputfile was specified
                outfile = self.outfile if self.outfile is not None else self.infile
                # CompressParameters.NO_COMPRESSION → no-op object-stream behaviour.
                doc.save(outfile)
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
