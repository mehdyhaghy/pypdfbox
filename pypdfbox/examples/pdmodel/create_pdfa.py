"""Port of ``org.apache.pdfbox.examples.pdmodel.CreatePDFA`` (lines 42-136).

Creates a simple PDF/A document with an embedded font, sRGB output intent,
and XMP metadata.
"""

from __future__ import annotations

import sys


class CreatePDFA:
    """Mirrors ``CreatePDFA`` (final class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 48)."""
        argv = argv if argv is not None else []
        if len(argv) != 3:
            sys.stderr.write(
                "usage: CreatePDFA <output-file> <Message> <ttf-file>\n",
            )
            raise SystemExit(1)
        # TODO: PDF/A creation needs the XMPBox + PDOutputIntent + sRGB.icc
        # bundle and CompressParameters.NO_COMPRESSION binding.
        raise NotImplementedError(
            "CreatePDFA awaits XMPBox PDFA-identification schema + "
            "PDOutputIntent + sRGB.icc resource wiring.",
        )
