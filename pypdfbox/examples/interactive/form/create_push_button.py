"""Port of ``CreatePushButton`` (upstream ``CreatePushButton.java`` lines
42-83).

Adds a push button with a JavaScript ``app.alert`` action.

The upstream sample paints a black 100x100 image as the button's normal
appearance using ``LosslessFactory``. pypdfbox does not yet expose an
in-memory image XObject builder (``LosslessFactory`` lands with the
rendering / image cluster), so the port wires up the field, widget,
action, and appearance dictionary while leaving the appearance stream
content empty. Documented in ``CHANGES.md``.
"""

from __future__ import annotations

import sys

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


class CreatePushButton:
    """Mirrors ``CreatePushButton`` (default-package constructor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/
    interactive/form/CreatePushButton.java`` (lines 42-83).
    """

    DEFAULT_FILENAME: str = "target/PushButtonSample.pdf"

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 44)."""
        argv = list(argv) if argv else []
        out = argv[0] if argv else CreatePushButton.DEFAULT_FILENAME
        CreatePushButton.create(out)

    @staticmethod
    def create(filename: str) -> None:
        """Build a single-page document with one push button and save it
        to ``filename``."""
        with PDDocument() as doc:
            page = PDPage()
            doc.add_page(page)
            acro_form = PDAcroForm(doc)
            doc.get_document_catalog().set_acro_form(acro_form)

            push_button = PDPushButton(acro_form)
            push_button.set_partial_name("push")
            acro_form.set_fields([*acro_form.get_fields(), push_button])
            widget = push_button.get_widgets()[0]
            page.get_annotations().append(widget)
            widget.set_rectangle(PDRectangle(50, 500, 100, 100))
            widget.set_printed(True)
            widget.set_page(page)

            appearance_dictionary = PDAppearanceDictionary(COSDictionary())
            widget.set_appearance(appearance_dictionary)

            doc.save(filename)


if __name__ == "__main__":  # pragma: no cover
    CreatePushButton.main(sys.argv[1:])
