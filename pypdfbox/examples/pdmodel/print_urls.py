"""Port of ``org.apache.pdfbox.examples.pdmodel.PrintURLs`` (lines 41-164).

Prints URLs in a PDF along with the text of the surrounding annotation
rectangle.
"""

from __future__ import annotations

import sys
from typing import Any


class PrintURLs:
    """Mirrors ``PrintURLs`` (final, utility class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 60)."""
        argv = argv if argv is not None else []
        if len(argv) != 1:
            PrintURLs.usage()
            return
        # TODO: PDFTextStripperByArea + PDAnnotation surface required for a
        # faithful port. Structural stub for wave-1283.
        raise NotImplementedError(
            "PrintURLs requires PDFTextStripperByArea and "
            "annotation.get_action reflection; port pending.",
        )

    @staticmethod
    def get_action_uri(annot: Any) -> Any:
        """Mirrors ``getActionURI(PDAnnotation)`` (line 133)."""
        # Use duck typing — any annotation that has a ``get_action`` method
        # returning a ``PDActionURI``.
        try:
            get_action = annot.get_action
        except AttributeError:
            return None
        try:
            action = get_action()
        except Exception:  # noqa: BLE001 — mirrors broad Java catch
            return None
        from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI

        if isinstance(action, PDActionURI):
            return action
        return None

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (line 158)."""
        sys.stderr.write("usage: PrintURLs <input-file>\n")
