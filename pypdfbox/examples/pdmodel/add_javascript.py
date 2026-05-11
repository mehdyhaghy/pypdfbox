"""Port of ``org.apache.pdfbox.examples.pdmodel.AddJavascript`` (lines 31-74).

Adds a JavaScript open-action to a PDF document.
"""

from __future__ import annotations

import sys


class AddJavascript:
    """Mirrors ``AddJavascript`` (final, utility class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 45)."""
        argv = argv if argv is not None else []
        if len(argv) != 2:
            AddJavascript.usage()
            return
        # TODO: PDActionJavaScript binding is not yet ported into the
        # pypdfbox public API surface — this example is a structural stub
        # until that action type lands.
        raise NotImplementedError(
            "AddJavascript requires PDActionJavaScript; port pending in "
            "pypdfbox.pdmodel.interactive.action.",
        )

    @staticmethod
    def usage() -> None:
        sys.stderr.write(
            "Usage: AddJavascript <input-pdf> <output-pdf>\n",
        )
