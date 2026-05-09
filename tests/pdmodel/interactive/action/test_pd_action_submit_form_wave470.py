from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.pd_action_submit_form import (
    PDActionSubmitForm,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_F = COSName.get_pdf_name("F")
_FIELDS = COSName.get_pdf_name("Fields")
_FLAGS = COSName.get_pdf_name("Flags")
_FT = COSName.get_pdf_name("FT")
_S = COSName.get_pdf_name("S")
_T = COSName.get_pdf_name("T")


def test_wave470_file_predicates_and_clear_keep_malformed_file_entry_observable() -> None:
    action = PDActionSubmitForm()
    action.get_cos_object().set_item(_F, COSName.get_pdf_name("NotAFileSpec"))

    assert action.has_file() is True
    with pytest.raises(OSError, match="Unknown file specification"):
        action.get_file()
    assert action.get_url() is None

    action.clear_file()
    assert action.has_file() is False
    assert action.get_cos_object().get_dictionary_object(_F) is None


def test_wave470_set_file_accepts_bytes_url_and_raw_cos_value() -> None:
    action = PDActionSubmitForm()

    action.set_file(b"https://example.com/post")
    assert action.get_url() == "https://example.com/post"
    assert isinstance(action.get_cos_object().get_dictionary_object(_F), COSString)

    raw = COSDictionary()
    raw.set_string("F", "submit.fdf")
    action.set_file(raw)
    assert action.get_cos_object().get_dictionary_object(_F) is raw
    assert action.get_url() == "submit.fdf"


def test_wave470_set_url_overwrites_complex_file_spec_with_simple_string() -> None:
    action = PDActionSubmitForm()
    file_spec = PDComplexFileSpecification()
    file_spec.set_file("old.fdf")
    action.set_file(file_spec)

    action.set_url("https://example.com/new")

    raw = action.get_cos_object().get_dictionary_object(_F)
    assert isinstance(raw, COSString)
    assert action.get_file() is not None
    assert action.get_url() == "https://example.com/new"


def test_wave470_field_array_helpers_append_and_clear() -> None:
    action = PDActionSubmitForm()
    action.add_field(COSString("customer.email"))

    form = PDAcroForm()
    text_dict = COSDictionary()
    text_dict.set_item(_FT, COSName.get_pdf_name("Tx"))
    text_dict.set_string(_T, "customer.name")
    text_field = PDTextField(form, text_dict, None)
    action.add_field(text_field)

    raw_fields = action.get_cos_fields()
    assert isinstance(raw_fields, COSArray)
    assert action.has_fields() is True
    assert raw_fields.size() == 2
    assert raw_fields.get_object(0).get_string() == "customer.email"
    assert raw_fields.get_object(1) is text_dict

    typed_fields = action.get_fields()
    assert typed_fields is not None
    assert len(typed_fields) == 1
    assert isinstance(typed_fields[0], PDTextField)
    assert typed_fields[0].get_partial_name() == "customer.name"

    action.clear_fields()
    assert action.has_fields() is False
    assert action.get_fields() is None


def test_wave470_set_fields_rejects_non_cos_entries() -> None:
    action = PDActionSubmitForm()

    with pytest.raises(TypeError, match="PDField or COSBase"):
        action.set_fields(["customer.name"])  # type: ignore[list-item]


def test_wave470_add_field_rejects_non_cos_entries() -> None:
    action = PDActionSubmitForm()

    with pytest.raises(TypeError, match="PDField or COSBase"):
        action.add_field("customer.name")  # type: ignore[arg-type]


def test_wave470_non_array_fields_reports_absent_without_removing_raw_value() -> None:
    action = PDActionSubmitForm()
    action.get_cos_object().set_string(_FIELDS, "customer.name")

    assert action.get_fields() is None
    assert action.get_cos_fields() is None
    assert action.has_fields() is False
    assert action.get_cos_object().get_dictionary_object(_FIELDS) is not None


def test_wave470_flag_mask_helpers_preserve_unrelated_bits() -> None:
    action = PDActionSubmitForm()
    mask = (
        PDActionSubmitForm.FLAG_INCLUDE_EXCLUDE
        | PDActionSubmitForm.FLAG_GET_METHOD
        | PDActionSubmitForm.FLAG_EMBED_FORM
    )

    assert action.has_flags() is False
    action.set_flag(mask, True)
    assert action.has_flags() is True
    assert action.has_flag(mask) is True
    assert action.is_include() is True
    assert action.is_get_method() is True
    assert action.is_embed_form() is True

    action.set_flag(PDActionSubmitForm.FLAG_GET_METHOD, False)
    assert action.has_flag(mask) is False
    assert action.is_include() is True
    assert action.is_get_method() is False
    assert action.is_embed_form() is True

    action.clear_flags()
    assert action.get_flags() == 0
    assert action.has_flags() is True
    assert action.get_cos_object().get_int(_FLAGS, -1) == 0


def test_wave470_include_overload_sets_and_returns_current_value() -> None:
    action = PDActionSubmitForm()

    assert action.is_include(True) is True
    assert action.get_flags() == PDActionSubmitForm.FLAG_INCLUDE_EXCLUDE
    assert action.is_include(False) is False
    assert action.get_flags() == 0


def test_wave470_is_valid_reflects_wrapped_subtype() -> None:
    assert PDActionSubmitForm().is_valid() is True

    raw = COSDictionary()
    raw.set_name(_S, "ResetForm")
    assert PDActionSubmitForm(raw).is_valid() is False
