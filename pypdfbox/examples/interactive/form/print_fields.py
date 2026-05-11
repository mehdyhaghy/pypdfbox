"""Port of ``PrintFields`` (upstream ``PrintFields.java`` lines 36-132).

Walks an AcroForm field tree and prints each field's fully qualified
name and value.
"""

from __future__ import annotations

import sys

from pypdfbox.pdmodel.interactive.form.pd_field import PDField
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.pd_document import PDDocument


class PrintFields:
    """Mirrors ``PrintFields`` (default no-arg constructor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/
    interactive/form/PrintFields.java`` (lines 36-132).
    """

    def __init__(self) -> None:
        pass

    def print_fields(self, pdf_document: PDDocument) -> None:
        """Print every field in ``pdf_document``'s AcroForm — mirrors
        upstream's ``printFields(PDDocument)`` (line 46)."""
        doc_catalog = pdf_document.get_document_catalog()
        acro_form = doc_catalog.get_acro_form()
        if acro_form is None:
            sys.stdout.write("0 top-level fields were found on the form\n")
            return
        fields = acro_form.get_fields()
        sys.stdout.write(f"{len(fields)} top-level fields were found on the form\n")
        for field in fields:
            self.process_field(field, "|--", field.get_partial_name())

    def process_field(
        self, field: PDField, level: str, parent: str | None
    ) -> None:
        """Recursive walker — promoted from upstream's private
        ``processField`` (line 60)."""
        partial_name = field.get_partial_name()
        if isinstance(field, PDNonTerminalField):
            if parent != field.get_partial_name() and partial_name is not None:
                parent = f"{parent}.{partial_name}"
            sys.stdout.write(f"{level}{parent}\n")
            for child in field.get_children():
                self.process_field(child, "|  " + level, parent)
        else:
            try:
                field_value = field.get_value_as_string()
            except Exception:  # noqa: BLE001
                field_value = ""
            out = level + str(parent)
            if partial_name is not None:
                out += f".{partial_name}"
            out += f" = {field_value},  type={type(field).__name__}"
            sys.stdout.write(out + "\n")

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 100)."""
        argv = list(argv) if argv else []
        if len(argv) != 1:
            PrintFields.usage()
            return
        with PDDocument.load(argv[0]) as pdf:
            PrintFields().print_fields(pdf)

    @staticmethod
    def usage() -> None:
        """Print the usage message — mirrors the private ``usage()``
        helper (line 128)."""
        sys.stderr.write(
            "usage: org.apache.pdfbox.examples.interactive.form.PrintFields <pdf-file>\n",
        )


if __name__ == "__main__":  # pragma: no cover
    PrintFields.main(sys.argv[1:])
