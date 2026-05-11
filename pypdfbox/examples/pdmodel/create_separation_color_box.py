"""Port of ``org.apache.pdfbox.examples.pdmodel.CreateSeparationColorBox`` (lines 39-99).

Creates a separation / spot-colour rectangle as a placeholder for "gold".
"""

from __future__ import annotations


class CreateSeparationColorBox:
    """Mirrors ``CreateSeparationColorBox`` (line 39)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 45)."""
        del argv
        # TODO: PDSeparation + PDFunctionType2 binding required for a
        # faithful port.
        raise NotImplementedError(
            "CreateSeparationColorBox awaits PDSeparation + PDFunctionType2 "
            "exposure.",
        )
