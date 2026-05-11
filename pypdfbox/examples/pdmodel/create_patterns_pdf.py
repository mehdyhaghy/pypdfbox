"""Port of ``org.apache.pdfbox.examples.pdmodel.CreatePatternsPDF`` (lines 39-130).

Creates a PDF that uses colored and uncolored tiling patterns.
"""

from __future__ import annotations


class CreatePatternsPDF:
    """Mirrors ``CreatePatternsPDF`` (final class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 45)."""
        del argv
        # TODO: tiling patterns require PDPatternContentStream + PDPattern +
        # PDTilingPattern bindings in the examples surface.
        raise NotImplementedError(
            "CreatePatternsPDF awaits PDPatternContentStream / "
            "PDTilingPattern exposure.",
        )
