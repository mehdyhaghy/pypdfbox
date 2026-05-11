"""Port of ``org.apache.pdfbox.examples.pdmodel.ShowTextWithPositioning`` (lines 41-169).

Uses ``showTextWithPositioning`` to justify text both word-by-word and
letter-by-letter.
"""

from __future__ import annotations


class ShowTextWithPositioning:
    """Mirrors ``ShowTextWithPositioning`` (line 41)."""

    FONT_SIZE: float = 20.0

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 49)."""
        del argv
        ShowTextWithPositioning.do_it(
            "Hello World, this is a test!",
            "justify-example.pdf",
        )

    @staticmethod
    def do_it(message: str, outfile: str) -> None:
        """Mirrors ``doIt(String message, String outfile)`` (line 54)."""
        del message, outfile
        # TODO: requires PDType0Font.load from resource stream +
        # PDTrueTypeFont.load with WinAnsiEncoding, plus
        # ``set_word_spacing`` and ``show_text_with_positioning`` semantics —
        # binding stub for wave-1283.
        raise NotImplementedError(
            "ShowTextWithPositioning awaits LiberationSans resource + "
            "show_text_with_positioning surface.",
        )
