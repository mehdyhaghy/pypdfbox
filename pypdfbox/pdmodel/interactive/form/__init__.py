from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .appearance_generator_helper import AppearanceGeneratorHelper
    from .appearance_style import AppearanceStyle
    from .builder import Builder
    from .field_iterator import FieldIterator
    from .field_utils import FieldUtils
    from .key_value import KeyValue
    from .paragraph import (
        Line,
        Paragraph,
    )
    from .pd_acro_form import PDAcroForm
    from .pd_appearance_generator import PDAppearanceGenerator
    from .pd_button import PDButton
    from .pd_check_box import PDCheckBox
    from .pd_choice import PDChoice
    from .pd_combo_box import PDComboBox
    from .pd_field import PDField
    from .pd_field_factory import PDFieldFactory
    from .pd_field_tree import PDFieldTree
    from .pd_list_box import PDListBox
    from .pd_non_terminal_field import PDNonTerminalField
    from .pd_push_button import PDPushButton
    from .pd_radio_button import PDRadioButton
    from .pd_signature_field import PDSignatureField
    from .pd_terminal_field import (
        PDFieldStub,
        PDTerminalField,
    )
    from .pd_text_field import PDTextField
    from .pd_variable_text import PDVariableText
    from .pd_xfa_resource import PDXFAResource
    from .plain_text import PlainText
    from .plain_text_formatter import PlainTextFormatter
    from .scripting_handler import ScriptingHandler
    from .text_align import TextAlign
    from .word import Word

__getattr__, __dir__ = _attach(
    __name__,
    {
        "AppearanceGeneratorHelper": ".appearance_generator_helper",
        "AppearanceStyle": ".appearance_style",
        "Builder": ".builder",
        "FieldIterator": ".field_iterator",
        "FieldUtils": ".field_utils",
        "KeyValue": ".key_value",
        "Line": ".paragraph",
        "Paragraph": ".paragraph",
        "PDAcroForm": ".pd_acro_form",
        "PDAppearanceGenerator": ".pd_appearance_generator",
        "PDButton": ".pd_button",
        "PDCheckBox": ".pd_check_box",
        "PDChoice": ".pd_choice",
        "PDComboBox": ".pd_combo_box",
        "PDField": ".pd_field",
        "PDFieldFactory": ".pd_field_factory",
        "PDFieldTree": ".pd_field_tree",
        "PDListBox": ".pd_list_box",
        "PDNonTerminalField": ".pd_non_terminal_field",
        "PDPushButton": ".pd_push_button",
        "PDRadioButton": ".pd_radio_button",
        "PDSignatureField": ".pd_signature_field",
        "PDFieldStub": ".pd_terminal_field",
        "PDTerminalField": ".pd_terminal_field",
        "PDTextField": ".pd_text_field",
        "PDVariableText": ".pd_variable_text",
        "PDXFAResource": ".pd_xfa_resource",
        "PlainText": ".plain_text",
        "PlainTextFormatter": ".plain_text_formatter",
        "ScriptingHandler": ".scripting_handler",
        "TextAlign": ".text_align",
        "Word": ".word",
    },
)

__all__ = [
    "AppearanceGeneratorHelper",
    "AppearanceStyle",
    "Builder",
    "FieldIterator",
    "FieldUtils",
    "KeyValue",
    "Line",
    "PDAcroForm",
    "PDAppearanceGenerator",
    "PDButton",
    "PDCheckBox",
    "PDChoice",
    "PDComboBox",
    "PDField",
    "PDFieldFactory",
    "PDFieldStub",
    "PDFieldTree",
    "PDListBox",
    "PDNonTerminalField",
    "PDPushButton",
    "PDRadioButton",
    "PDSignatureField",
    "PDTerminalField",
    "PDTextField",
    "PDVariableText",
    "PDXFAResource",
    "Paragraph",
    "PlainText",
    "PlainTextFormatter",
    "ScriptingHandler",
    "TextAlign",
    "Word",
]
