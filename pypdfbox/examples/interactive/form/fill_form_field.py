"""Port of ``FillFormField`` (upstream ``FillFormField.java`` lines
31-64).

Loads a template form, fills two named text fields, and saves the result.
"""

from __future__ import annotations

import contextlib
import sys

from pypdfbox.pdmodel.pd_document import PDDocument


class FillFormField:
    """Mirrors ``FillFormField`` (final, package-private constructor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/
    interactive/form/FillFormField.java`` (lines 31-64).
    """

    DEFAULT_TEMPLATE: str = (
        "src/main/resources/org/apache/pdfbox/examples/interactive/form/"
        "FillFormField.pdf"
    )
    DEFAULT_OUTPUT: str = "target/FillFormField.pdf"

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 37)."""
        argv = list(argv) if argv else []
        src = argv[0] if argv else FillFormField.DEFAULT_TEMPLATE
        dst = argv[1] if len(argv) > 1 else FillFormField.DEFAULT_OUTPUT
        FillFormField.fill(src, dst)

    @staticmethod
    def fill(src: str, dst: str) -> None:
        """Open ``src``, set ``sampleField`` /
        ``fieldsContainer.nestedSampleField`` to ``Text Entry``, save the
        result to ``dst``."""
        with PDDocument.load(src) as pdf_document:
            acro_form = pdf_document.get_document_catalog().get_acro_form()
            if acro_form is not None:
                field = acro_form.get_field("sampleField")
                if field is not None:
                    with contextlib.suppress(Exception):
                        field.set_value("Text Entry")
                field = acro_form.get_field("fieldsContainer.nestedSampleField")
                if field is not None:
                    with contextlib.suppress(Exception):
                        field.set_value("Text Entry")
            pdf_document.save(dst)


if __name__ == "__main__":  # pragma: no cover
    FillFormField.main(sys.argv[1:])
