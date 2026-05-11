"""Port of ``org.apache.pdfbox.examples.pdmodel.EmbeddedFonts`` (lines 34-76).

Embeds a TrueType font and writes Unicode text with ligatures.
"""

from __future__ import annotations


class EmbeddedFonts:
    """Mirrors ``EmbeddedFonts`` (final class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 41)."""
        del argv
        # TODO: depends on the upstream LiberationSans resource bundle —
        # ``../pdfbox/src/main/resources/.../LiberationSans-Regular.ttf``.
        # Structural stub until the resource pipe is wired.
        raise NotImplementedError(
            "EmbeddedFonts awaits the LiberationSans-Regular.ttf bundled "
            "resource.",
        )
