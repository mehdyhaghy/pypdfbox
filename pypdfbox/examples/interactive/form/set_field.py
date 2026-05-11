"""Port of ``SetField`` (upstream ``SetField.java`` lines 39-155).

Sets a single named form field to a supplied value, handling the field
type (text, combo, list, radio, checkbox).
"""

from __future__ import annotations

import contextlib
import sys

from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_document import PDDocument


class SetField:
    """Mirrors ``SetField`` (default no-arg constructor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/
    interactive/form/SetField.java`` (lines 39-155).
    """

    def __init__(self) -> None:
        pass

    def set_field(self, pdf_document: PDDocument, name: str, value: str) -> None:
        """Set the field ``name`` in ``pdf_document`` to ``value`` —
        mirrors upstream's ``setField(PDDocument, String, String)``
        (line 50)."""
        doc_catalog = pdf_document.get_document_catalog()
        acro_form = doc_catalog.get_acro_form()
        if acro_form is None:
            sys.stderr.write(f"No field found with name:{name}\n")
            return
        field = acro_form.get_field(name)
        if field is not None:
            if isinstance(field, PDCheckBox):
                if not value:
                    with contextlib.suppress(Exception):
                        field.un_check()
                else:
                    with contextlib.suppress(Exception):
                        field.check()
            elif isinstance(field, (PDComboBox, PDListBox, PDRadioButton, PDTextField)):
                with contextlib.suppress(Exception):
                    field.set_value(value)
        else:
            sys.stderr.write(f"No field found with name:{name}\n")

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 101)."""
        SetField().set_field_args(list(argv) if argv else [])

    def set_field_args(self, argv: list[str]) -> None:
        """Argument-array wrapper that delegates to :meth:`set_field` —
        promoted from upstream's private ``setField(String[])`` (line
        107)."""
        if len(argv) != 3:
            SetField.usage()
            return
        with PDDocument.load(argv[0]) as pdf:
            self.set_field(pdf, argv[1], argv[2])
            pdf.save(SetField.calculate_output_filename(argv[0]))

    @staticmethod
    def calculate_output_filename(filename: str) -> str:
        """Append ``_filled`` before the ``.pdf`` extension — mirrors
        upstream's private static ``calculateOutputFilename`` (line
        133)."""
        output = filename[:-4] if filename.lower().endswith(".pdf") else filename
        return output + "_filled.pdf"

    @staticmethod
    def usage() -> None:
        """Print the usage message — mirrors the private ``usage()``
        helper (line 151)."""
        sys.stderr.write(
            "usage: org.apache.pdfbox.examples.interactive.form.SetField "
            "<pdf-file> <field-name> <field-value>\n",
        )


if __name__ == "__main__":  # pragma: no cover
    SetField.main(sys.argv[1:])
