"""Port of ``org.apache.pdfbox.examples.pdmodel.EmbeddedVerticalFonts`` (lines 32-102).

Renders Japanese text in horizontal and vertical layouts with and without
the ``vrt2`` / ``vert`` GSUB features.
"""

from __future__ import annotations


class EmbeddedVerticalFonts:
    """Mirrors ``EmbeddedVerticalFonts`` (line 32)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 38)."""
        del argv
        # TODO: depends on the IPA Gothic font (``ipag.ttf``), which is not
        # bundled.
        raise NotImplementedError(
            "EmbeddedVerticalFonts depends on ipag.ttf, not bundled.",
        )
