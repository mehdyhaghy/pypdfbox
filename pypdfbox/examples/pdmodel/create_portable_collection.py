"""Port of ``org.apache.pdfbox.examples.pdmodel.CreatePortableCollection`` (lines 49-229).

Creates a portable collection ("PDF Package") with two embedded files.
"""

from __future__ import annotations

import sys


class CreatePortableCollection:
    """Mirrors ``CreatePortableCollection`` (line 49)."""

    def __init__(self) -> None:
        pass

    def do_it(self, file_: str) -> None:
        """Mirrors ``doIt(String file)`` (line 66)."""
        del file_
        # TODO: collection-schema dictionaries depend on the
        # PDComplexFileSpecification / PDEmbeddedFile pair plus the schema
        # COSName surface. Structural stub for wave-1283.
        raise NotImplementedError(
            "CreatePortableCollection awaits collection schema / "
            "embedded-file wiring.",
        )

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 209)."""
        argv = argv if argv is not None else []
        app = CreatePortableCollection()
        if len(argv) != 1:
            app.usage()
        else:
            app.do_it(argv[0])

    def usage(self) -> None:
        sys.stderr.write(
            "usage: CreatePortableCollection <output-file>\n",
        )
