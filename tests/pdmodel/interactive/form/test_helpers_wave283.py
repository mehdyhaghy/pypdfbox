from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.form import (
    PDAcroForm,
    PDCheckBox,
    PDListBox,
    PDSignatureField,
    PDTextField,
)

_CO = COSName.get_pdf_name("CO")
_DA = COSName.get_pdf_name("DA")
_DR = COSName.get_pdf_name("DR")
_DV = COSName.get_pdf_name("DV")
_I = COSName.get_pdf_name("I")
_LOCK = COSName.get_pdf_name("Lock")
_NEED_APPEARANCES = COSName.get_pdf_name("NeedAppearances")
_OPT = COSName.get_pdf_name("Opt")
_Q = COSName.get_pdf_name("Q")
_SV = COSName.get_pdf_name("SV")
_TI = COSName.get_pdf_name("TI")
_V = COSName.get_pdf_name("V")
_XFA = COSName.get_pdf_name("XFA")


def test_acro_form_type_aware_has_and_clear_helpers() -> None:
    form = PDAcroForm()
    cos = form.get_cos_object()

    cos.set_string(_NEED_APPEARANCES, "not-a-bool")
    assert form.get_need_appearances_if_exists() is None
    assert form.has_need_appearances() is False
    form.set_need_appearances(False)
    assert form.has_need_appearances() is True
    form.clear_need_appearances()
    assert form.get_need_appearances_if_exists() is None

    cos.set_int(_DA, 3)
    assert form.get_default_appearance_if_exists() is None
    assert form.has_default_appearance() is False
    form.set_default_appearance("")
    assert form.has_default_appearance() is True
    form.clear_default_appearance()
    assert form.get_default_appearance() == ""

    cos.set_string(_Q, "not-a-number")
    assert form.get_q_if_exists() is None
    assert form.has_q() is False
    form.set_q(0)
    assert form.has_q() is True
    form.clear_q()
    assert form.get_q_if_exists() is None

    cos.set_string(_DR, "not-a-dict")
    assert form.has_default_resources() is False
    cos.set_item(_DR, COSDictionary())
    assert form.has_default_resources() is True
    form.clear_default_resources()
    assert form.has_default_resources() is False

    cos.set_item(_CO, COSArray([COSString("not-a-field")]))
    assert form.has_calc_order() is False
    form.clear_calc_order()
    assert form.has_calc_order() is False

    cos.set_item(_XFA, COSString("<xfa/>"))
    assert form.has_xfa() is True
    form.clear_xfa()
    assert form.has_xfa() is False


def test_text_field_type_aware_has_and_clear_helpers() -> None:
    field = PDTextField(PDAcroForm())
    cos = field.get_cos_object()

    cos.set_name(_V, "NameIsNotTextValue")
    assert field.has_value() is False
    field.set_value("value")
    assert field.has_value() is True
    field.clear_value()
    assert field.has_value() is False

    cos.set_item(_DV, COSArray())
    assert field.has_default_value() is False
    field.set_default_value("default")
    assert field.has_default_value() is True
    field.clear_default_value()
    assert field.has_default_value() is False

    field.set_max_len(12)
    assert field.has_max_len() is True
    field.clear_max_len()
    assert field.has_max_len() is False

    cos.set_int(_DA, 42)
    assert field.has_default_appearance() is False
    field.set_default_appearance("/Helv 12 Tf 0 g")
    assert field.has_default_appearance() is True
    field.clear_default_appearance()
    assert field.has_default_appearance() is False

    cos.set_item(_Q, COSString("not-a-number"))
    assert field.has_q() is False
    field.set_q(0)
    assert field.has_q() is True
    field.clear_q()
    assert field.has_q() is False


def test_choice_field_type_aware_has_and_clear_helpers() -> None:
    field = PDListBox(PDAcroForm())
    cos = field.get_cos_object()

    cos.set_int(_OPT, 1)
    assert field.has_options() is False
    field.set_options(["a", "b"])
    assert field.has_options() is True
    field.clear_options()
    assert field.has_options() is False

    cos.set_item(_V, COSInteger(7))
    assert field.has_value() is False
    field.set_options(["a", "b"])
    field.set_multi_select(True)
    # Use the list overload to populate /I (the str overload now clears
    # /I per upstream contract — wave 1372).
    field.set_value(["a"])
    assert field.has_value() is True
    assert field.has_selected_options_indices() is True
    field.clear_value()
    assert field.has_value() is False
    assert field.has_selected_options_indices() is False

    cos.set_item(_DV, COSInteger(7))
    assert field.has_default_value() is False
    field.set_default_value("b")
    assert field.has_default_value() is True
    field.clear_default_value()
    assert field.has_default_value() is False

    cos.set_item(_I, COSString("not-an-array"))
    assert field.has_selected_options_indices() is False
    field.set_selected_options_indices([0])
    assert field.has_selected_options_indices() is True
    field.clear_selected_options_indices()
    assert field.has_selected_options_indices() is False

    cos.set_string(_TI, "not-an-int")
    assert field.has_top_index() is False
    field.set_top_index(0)
    assert field.has_top_index() is True
    field.clear_top_index()
    assert field.has_top_index() is False


def test_button_and_signature_type_aware_has_and_clear_helpers() -> None:
    button = PDCheckBox(PDAcroForm())
    button_cos = button.get_cos_object()

    button_cos.set_item(_V, COSArray())
    assert button.has_value() is False
    # set_value is upstream-strict; this AP-less box only accepts "" / "Off".
    # The subject is the has_value/clear_value helpers, so use "Off".
    button.set_value("Off")
    assert button.has_value() is True
    button.clear_value()
    assert button.has_value() is False

    button_cos.set_item(_DV, COSArray())
    assert button.has_default_value() is False
    button.set_default_value("Off")
    assert button.has_default_value() is True
    button.clear_default_value()
    assert button.has_default_value() is False

    button_cos.set_int(_OPT, 1)
    assert button.has_export_values() is False
    button.set_export_values(["export"])
    assert button.has_export_values() is True
    button.clear_export_values()
    assert button.has_export_values() is False

    signature = PDSignatureField(PDAcroForm())
    sig_cos = signature.get_cos_object()
    sig_cos.set_string(_V, "not-a-dict")
    assert signature.has_signature() is False
    signature.set_value(COSDictionary())
    assert signature.has_signature() is True
    signature.clear_signature()
    assert signature.has_signature() is False

    sig_cos.set_string(_DV, "not-a-dict")
    assert signature.has_default_value() is False
    signature.set_default_value(COSDictionary())
    assert signature.has_default_value() is True
    signature.clear_default_value()
    assert signature.has_default_value() is False

    sig_cos.set_string(_SV, "not-a-dict")
    assert signature.has_seed_value() is False
    signature.set_seed_value(COSDictionary())
    assert signature.has_seed_value() is True
    signature.clear_seed_value()
    assert signature.has_seed_value() is False

    sig_cos.set_string(_LOCK, "not-a-dict")
    assert signature.has_lock() is False
    signature.set_lock(COSDictionary())
    assert signature.has_lock() is True
    signature.clear_lock()
    assert signature.has_lock() is False
