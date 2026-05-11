"""Port of ``UpdateFieldOnDocumentOpen`` (upstream
``UpdateFieldOnDocumentOpen.java`` lines 36-64).

Loads a simple form, attaches a JavaScript open-action that fills the
``SampleField`` with the current date, and saves the result.
"""

from __future__ import annotations

import contextlib
import sys

from pypdfbox.pdmodel.pd_document import PDDocument


class UpdateFieldOnDocumentOpen:
    """Mirrors ``UpdateFieldOnDocumentOpen`` (final, package-private ctor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/
    interactive/form/UpdateFieldOnDocumentOpen.java`` (lines 36-64).
    """

    DEFAULT_INPUT: str = "target/SimpleForm.pdf"
    DEFAULT_OUTPUT: str = "target/UpdateFieldOnDocumentOpen.pdf"

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 42)."""
        argv = list(argv) if argv else []
        src = argv[0] if argv else UpdateFieldOnDocumentOpen.DEFAULT_INPUT
        dst = argv[1] if len(argv) > 1 else UpdateFieldOnDocumentOpen.DEFAULT_OUTPUT
        UpdateFieldOnDocumentOpen.attach_open_action(src, dst)

    @staticmethod
    def attach_open_action(src: str, dst: str) -> None:
        """Open ``src``, wire a JavaScript open-action that sets
        ``SampleField`` to today's date, and save to ``dst``. Promoted
        from the upstream inline ``main`` body."""
        try:
            from pypdfbox.pdmodel.interactive.action.pd_action_javascript import (
                PDActionJavaScript,
            )
        except ImportError:
            PDActionJavaScript = None  # type: ignore[assignment]

        java_script = (
            "var now = util.printd('yyyy-mm-dd', new Date());"
            "var oField = this.getField('SampleField');"
            "oField.value = now;"
        )

        with PDDocument.load(src) as document:
            if PDActionJavaScript is not None:
                js_action = PDActionJavaScript()
                js_action.set_action(java_script)
                with contextlib.suppress(Exception):
                    document.get_document_catalog().set_open_action(js_action)
            document.save(dst)


if __name__ == "__main__":  # pragma: no cover
    UpdateFieldOnDocumentOpen.main(sys.argv[1:])
