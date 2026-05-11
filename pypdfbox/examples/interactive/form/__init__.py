"""Ports of ``org.apache.pdfbox.examples.interactive.form`` form-field
demos — AcroForm field creation, filling, editing, and removal.

Each module mirrors a single upstream class one-to-one (class name
preserved, method names ``camelCase -> snake_case``)."""

from pypdfbox.examples.interactive.form.add_border_to_field import AddBorderToField
from pypdfbox.examples.interactive.form.create_check_box import CreateCheckBox
from pypdfbox.examples.interactive.form.create_multi_widgets_form import (
    CreateMultiWidgetsForm,
)
from pypdfbox.examples.interactive.form.create_push_button import CreatePushButton
from pypdfbox.examples.interactive.form.create_radio_buttons import CreateRadioButtons
from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.create_simple_form_with_embedded_font import (
    CreateSimpleFormWithEmbeddedFont,
)
from pypdfbox.examples.interactive.form.determine_text_fits_field import (
    DetermineTextFitsField,
)
from pypdfbox.examples.interactive.form.field_remover import FieldRemover
from pypdfbox.examples.interactive.form.field_triggers import FieldTriggers
from pypdfbox.examples.interactive.form.fill_form_field import FillFormField
from pypdfbox.examples.interactive.form.print_fields import PrintFields
from pypdfbox.examples.interactive.form.set_field import SetField
from pypdfbox.examples.interactive.form.update_field_on_document_open import (
    UpdateFieldOnDocumentOpen,
)

__all__ = [
    "AddBorderToField",
    "CreateCheckBox",
    "CreateMultiWidgetsForm",
    "CreatePushButton",
    "CreateRadioButtons",
    "CreateSimpleForm",
    "CreateSimpleFormWithEmbeddedFont",
    "DetermineTextFitsField",
    "FieldRemover",
    "FieldTriggers",
    "FillFormField",
    "PrintFields",
    "SetField",
    "UpdateFieldOnDocumentOpen",
]
