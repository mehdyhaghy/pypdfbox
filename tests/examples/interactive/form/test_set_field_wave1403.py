"""Wave 1403 branch round-out for ``set_field``.

Closes ``48->exit``: a located field that is neither a ``PDCheckBox`` nor one
of ``(PDComboBox, PDListBox, PDRadioButton, PDTextField)`` (e.g. a
``PDPushButton``) takes the False arc of the second ``isinstance`` check, so
``set_field`` returns without mutating any value.
"""

from __future__ import annotations

from pypdfbox.examples.interactive.form.set_field import SetField
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.pd_document import PDDocument


def test_set_field_ignores_unsupported_field_type() -> None:
    """A push button matches neither branch → 48->exit (no-op return)."""
    with PDDocument() as doc:
        acro = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(acro)
        button = PDPushButton(acro)
        button.set_partial_name("Submit")
        acro.set_fields([*acro.get_fields(), button])

        # Should complete without raising and without altering the button.
        SetField().set_field(doc, "Submit", "ignored")
        located = acro.get_field("Submit")
        assert isinstance(located, PDPushButton)
