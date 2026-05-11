"""Port of ``org.apache.pdfbox.examples.pdmodel.SuperimposePage`` (lines 36-98).

Superimposes a page from a source PDF onto a fresh page in a new PDF using
``LayerUtility``.
"""

from __future__ import annotations

import sys


class SuperimposePage:
    """Mirrors ``SuperimposePage`` (final class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 43)."""
        argv = argv if argv is not None else []
        if len(argv) != 2:
            sys.stderr.write(
                "usage: SuperimposePage <source-pdf> <dest-pdf>\n",
            )
            raise SystemExit(1)
        # TODO: requires LayerUtility.import_page_as_form and
        # content_stream.draw_form binding on the examples surface.
        raise NotImplementedError(
            "SuperimposePage awaits LayerUtility.import_page_as_form / "
            "PDPageContentStream.draw_form exposure.",
        )
