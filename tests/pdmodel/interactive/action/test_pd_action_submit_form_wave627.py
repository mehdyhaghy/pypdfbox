from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.pd_action_submit_form import (
    PDActionSubmitForm,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_field import PDField

_F = COSName.get_pdf_name("F")
_FIELDS = COSName.get_pdf_name("Fields")
_FLAGS = COSName.get_pdf_name("Flags")
_FT = COSName.get_pdf_name("FT")
_S = COSName.get_pdf_name("S")
_T = COSName.get_pdf_name("T")


def test_wave627_constructor_sets_subtype_only_for_fresh_action() -> None:
    fresh = PDActionSubmitForm()
    wrapped_dict = COSDictionary()
    wrapped = PDActionSubmitForm(wrapped_dict)

    assert fresh.get_cos_object().get_name(_S) == "SubmitForm"
    assert wrapped.get_cos_object() is wrapped_dict
    assert wrapped.get_cos_object().get_dictionary_object(_S) is None
    assert wrapped.is_valid() is False


def test_wave627_set_file_accepts_raw_cos_string_without_reencoding() -> None:
    raw = COSString("https://example.test/submit.fdf")
    action = PDActionSubmitForm()

    action.set_file(raw)

    assert action.get_cos_object().get_dictionary_object(_F) is raw
    assert action.get_url() == "https://example.test/submit.fdf"
    file_spec = action.get_file()
    assert isinstance(file_spec, PDSimpleFileSpecification)
    assert file_spec.get_file() == "https://example.test/submit.fdf"


def test_wave627_set_fields_accepts_mixed_raw_cos_entries_and_filters_typed_view() -> None:
    button_dict = COSDictionary()
    button_dict.set_item(_FT, COSName.get_pdf_name("Btn"))
    button_dict.set_string(_T, "confirm")
    field_name = COSString("customer.email")
    not_a_field = COSDictionary()

    action = PDActionSubmitForm()
    action.set_fields([field_name, button_dict, not_a_field])

    raw = action.get_cos_fields()
    assert isinstance(raw, COSArray)
    assert raw.size() == 3
    assert raw.get_object(0) is field_name
    assert raw.get_object(1) is button_dict
    assert raw.get_object(2) is not_a_field

    typed = action.get_fields()
    assert typed is not None
    assert len(typed) == 1
    assert isinstance(typed[0], PDCheckBox)
    assert typed[0].get_partial_name() == "confirm"


def test_wave627_add_field_accepts_generic_pd_field_underlying_dictionary() -> None:
    field_dict = COSDictionary()
    field_dict.set_string(_T, "generic")
    field = PDField.from_dictionary(form=PDAcroForm(), field=field_dict)
    assert field is not None

    action = PDActionSubmitForm()
    action.add_field(field)

    raw = action.get_cos_fields()
    assert isinstance(raw, COSArray)
    assert raw.size() == 1
    assert raw.get_object(0) is field_dict


def test_wave627_flag_helpers_accept_zero_mask_as_vacuously_present() -> None:
    action = PDActionSubmitForm()

    assert action.has_flag(0) is True
    action.set_flags(PDActionSubmitForm.FLAG_XFDF)
    action.set_flag(0, False)

    assert action.get_flags() == PDActionSubmitForm.FLAG_XFDF
    assert action.get_cos_object().get_dictionary_object(_FLAGS) is not None


def test_wave627_get_url_returns_none_for_complex_file_spec_without_file() -> None:
    action = PDActionSubmitForm()
    action.get_cos_object().set_item(_F, COSDictionary())

    assert action.get_url() is None
    file_spec = action.get_file()
    assert isinstance(file_spec, PDComplexFileSpecification)
    assert file_spec.get_file() is None
