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

        from pypdfbox.loader import Loader
        from pypdfbox.pdmodel.interactive.action.pd_action_java_script import (
            PDActionJavaScript,
        )
        from pypdfbox.pdmodel.pd_document import PDDocument

        with Loader.load_pdf(argv[0]) as cos_doc:
            document = PDDocument(cos_doc)
            javascript = PDActionJavaScript(
                "app.alert( {cMsg: 'PDFBox rocks!', nIcon: 3, nType: 0, "
                "cTitle: 'PDFBox Javascript example' } );",
            )
            document.get_document_catalog().set_open_action(javascript)
            if document.is_encrypted():
                raise OSError(
                    "Encrypted documents are not supported for this example",
                )
            document.save(argv[1])

    @staticmethod
    def usage() -> None:
        sys.stderr.write(
            "Usage: AddJavascript <input-pdf> <output-pdf>\n",
        )
