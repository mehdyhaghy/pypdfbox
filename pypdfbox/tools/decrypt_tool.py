"""``Decrypt`` class port — wraps the existing ``pypdfbox.tools.decrypt``
functional CLI in the upstream ``Callable`` shape.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/Decrypt.java

Module is named ``decrypt_tool`` to avoid colliding with the existing
``pypdfbox/tools/decrypt.py`` argparse subcommand module.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pypdfbox.tools.decrypt import decrypt_pdf


class Decrypt:
    def __init__(self) -> None:
        self.password: str = ""
        self.key_store: Path | None = None
        self.alias: str | None = None
        self.infile: Path | None = None
        self.outfile: Path | None = None

    def call(self) -> int:
        if self.infile is None:
            raise OSError("infile is required")
        out = self.outfile if self.outfile is not None else self.infile
        try:
            decrypt_pdf(self.infile, out, password=self.password or "")
        except OSError as ioe:
            sys.stderr.write(
                f"Error decrypting document [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        return 0

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="decrypt", description="Decrypts a PDF document",
        )
        parser.add_argument("-password", default="")
        parser.add_argument("-keyStore", dest="keyStore", default=None)
        parser.add_argument("-alias", default=None)
        parser.add_argument("-i", "--input", dest="infile", required=True)
        parser.add_argument("-o", "--output", dest="outfile", default=None)
        ns = parser.parse_args(args)
        runner = Decrypt()
        runner.password = ns.password
        runner.key_store = Path(ns.keyStore) if ns.keyStore else None
        runner.alias = ns.alias
        runner.infile = Path(ns.infile)
        runner.outfile = Path(ns.outfile) if ns.outfile else None
        return runner.call()


if __name__ == "__main__":
    sys.exit(Decrypt.main(sys.argv[1:]))
