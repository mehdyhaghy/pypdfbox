"""Port of ``org.apache.pdfbox.examples.pdmodel.EmbeddedFiles`` (lines 44-147).

Creates a PDF with an embedded text file attachment.
"""

from __future__ import annotations

import sys


class EmbeddedFiles:
    """Mirrors ``EmbeddedFiles`` (line 44)."""

    def __init__(self) -> None:
        pass

    def do_it(self, file_: str) -> None:
        """Mirrors ``doIt(String file)`` (line 60)."""
        del file_
        # TODO: PDComplexFileSpecification + PDEmbeddedFile + name-tree wiring
        # required for a faithful port.
        raise NotImplementedError(
            "EmbeddedFiles awaits PDComplexFileSpecification + "
            "PDEmbeddedFile bindings.",
        )

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 127)."""
        argv = argv if argv is not None else []
        app = EmbeddedFiles()
        if len(argv) != 1:
            app.usage()
        else:
            app.do_it(argv[0])

    def usage(self) -> None:
        sys.stderr.write("usage: EmbeddedFiles <output-file>\n")
