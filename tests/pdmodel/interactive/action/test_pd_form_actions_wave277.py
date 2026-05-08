"""Wave 277 coverage for form actions: ResetForm, SubmitForm, and
ImportData field/file/flag conveniences, defaults, COS round-trips, and
malformed shape handling."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action import (
    PDActionImportData,
    PDActionResetForm,
    PDActionSubmitForm,
)
from pypdfbox.pdmodel.interactive.action.pd_action import PDAction

_F: COSName = COSName.get_pdf_name("F")
_FIELDS: COSName = COSName.get_pdf_name("Fields")
_FLAGS: COSName = COSName.get_pdf_name("Flags")
_S: COSName = COSName.get_pdf_name("S")


def test_reset_form_field_names_skip_non_string_entries_and_round_trip_raw_array() -> None:
    action = PDActionResetForm()
    field_dict = COSDictionary()
    fields = COSArray([COSString("billing.name"), field_dict, COSString("email")])

    action.set_fields(fields)

    assert action.get_fields() is fields
    assert action.has_fields() is True
    assert action.get_field_names() == ["billing.name", "email"]

    action.clear_fields()
    assert action.get_fields() is None
    assert action.get_field_names() == []


def test_reset_form_defaults_and_malformed_fields_shape() -> None:
    action = PDActionResetForm()

    assert action.get_flags() == 0
    assert action.has_flags() is False
    assert action.has_fields() is False
    assert action.is_empty() is True

    action.get_cos_object().set_string(_FIELDS, "not-an-array")

    assert action.get_fields() is None
    assert action.get_field_names() == []
    assert action.has_fields() is False
    assert action.is_empty() is True


def test_submit_form_file_helpers_clear_and_tolerate_malformed_url_shape() -> None:
    action = PDActionSubmitForm()
    malformed_file_spec = COSArray([COSString("not-a-file-spec")])

    action.set_file(malformed_file_spec)

    assert action.has_file() is True
    assert action.get_url() is None
    with pytest.raises(OSError, match="Unknown file specification"):
        action.get_file()

    action.clear_file()
    assert action.has_file() is False
    assert action.get_file() is None
    assert action.get_url() is None


def test_submit_form_field_helpers_clear_and_tolerate_malformed_shape() -> None:
    action = PDActionSubmitForm()
    fields = COSArray([COSString("field.one"), COSString("field.two")])

    action.set_fields(fields)
    assert action.get_cos_fields() is fields
    assert action.has_fields() is True

    action.get_cos_object().set_string(_FIELDS, "not-an-array")
    assert action.get_cos_fields() is None
    assert action.get_fields() is None
    assert action.has_fields() is False

    action.clear_fields()
    assert action.get_cos_object().get_dictionary_object(_FIELDS) is None
    assert action.has_fields() is False


def test_submit_form_flags_presence_defaults_and_clear_semantics() -> None:
    action = PDActionSubmitForm()

    assert action.get_flags() == 0
    assert action.has_flags() is False

    action.set_flags(0)
    assert action.get_flags() == 0
    assert action.has_flags() is True

    action.set_flags(PDActionSubmitForm.FLAG_GET_METHOD | PDActionSubmitForm.FLAG_XFDF)
    assert action.has_flag(PDActionSubmitForm.FLAG_GET_METHOD)
    assert action.has_flag(PDActionSubmitForm.FLAG_XFDF)

    action.clear_flags()
    assert action.get_flags() == 0
    assert action.has_flags() is True
    assert action.get_cos_object().get_int(_FLAGS, -1) == 0


def test_submit_form_is_valid_and_cos_create_round_trip() -> None:
    action = PDActionSubmitForm()
    action.set_url("https://example.com/submit")
    action.set_fields(COSArray([COSString("field.name")]))
    action.set_flags(PDActionSubmitForm.FLAG_SUBMIT_PDF)

    raw = action.get_cos_object()
    recreated = PDAction.create(raw)

    assert action.is_valid() is True
    assert isinstance(recreated, PDActionSubmitForm)
    assert recreated.is_valid() is True
    assert recreated.get_url() == "https://example.com/submit"
    assert recreated.get_cos_fields() is raw.get_dictionary_object(_FIELDS)
    assert recreated.get_flags() == PDActionSubmitForm.FLAG_SUBMIT_PDF

    bare = PDActionSubmitForm(COSDictionary())
    assert bare.is_valid() is False


def test_import_data_clear_file_and_malformed_string_convenience_shape() -> None:
    action = PDActionImportData()
    malformed_file_spec = COSArray([COSString("not-a-file-spec")])

    action.set_file(malformed_file_spec)

    assert action.has_file() is True
    assert action.get_file_path() is None
    assert action.get_url() is None
    with pytest.raises(OSError, match="Unknown file specification"):
        action.get_file()

    action.clear_file()
    assert action.has_file() is False
    assert action.get_file() is None
    assert action.get_file_path() is None
    assert action.get_url() is None


def test_import_data_is_valid_for_existing_dict_and_create_round_trip() -> None:
    raw = COSDictionary()
    raw.set_item(_S, COSName.get_pdf_name("ImportData"))
    raw.set_string(_F, "payload.xfdf")

    action = PDActionImportData(raw)
    recreated = PDAction.create(raw)

    assert action.is_valid() is True
    assert action.get_file_path() == "payload.xfdf"
    assert isinstance(recreated, PDActionImportData)
    assert recreated.is_valid() is True
    assert recreated.get_file_path() == "payload.xfdf"

