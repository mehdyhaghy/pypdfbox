from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.pd_action_submit_form import (
    PDActionSubmitForm,
)

_F = COSName.get_pdf_name("F")
_FIELDS = COSName.get_pdf_name("Fields")
_FLAGS = COSName.get_pdf_name("Flags")


def test_wave648_url_and_file_helpers_remove_and_ignore_malformed_f_values() -> None:
    action = PDActionSubmitForm()
    action.set_url("https://example.test/post")

    assert action.has_file() is True
    assert action.get_url() == "https://example.test/post"

    action.set_url(None)

    assert action.has_file() is False
    assert action.get_file() is None
    assert action.get_url() is None

    action.set_file(COSInteger.get(42))
    assert action.has_file() is True
    with pytest.raises(OSError, match="Unknown file specification"):
        action.get_file()
    assert action.get_url() is None

    action.clear_file()
    assert action.get_cos_object().get_dictionary_object(_F) is None


def test_wave648_complex_file_spec_url_round_trips_through_f_dictionary() -> None:
    file_spec = PDComplexFileSpecification()
    file_spec.set_file("https://example.test/complex.fdf")
    action = PDActionSubmitForm()

    action.set_file(file_spec)

    assert action.get_cos_object().get_dictionary_object(_F) is file_spec.get_cos_object()
    assert action.get_url() == "https://example.test/complex.fdf"
    assert action.get_file().get_cos_object() is file_spec.get_cos_object()


def test_wave648_fields_presence_requires_array_and_clear_removes_slot() -> None:
    action = PDActionSubmitForm()

    action.get_cos_object().set_item(_FIELDS, COSString("customer.email"))
    assert action.has_fields() is False
    assert action.get_fields() is None
    assert action.get_cos_fields() is None

    fields = COSArray()
    fields.add(COSString("customer.email"))
    action.set_fields(fields)

    assert action.has_fields() is True
    assert action.get_cos_fields() is fields
    assert action.get_fields() == []

    action.clear_fields()
    assert action.has_fields() is False
    assert action.get_cos_object().get_dictionary_object(_FIELDS) is None


def test_wave648_set_and_add_fields_reject_non_cos_entries() -> None:
    action = PDActionSubmitForm()

    with pytest.raises(TypeError, match="set_fields entries"):
        action.set_fields(["customer.email"])  # type: ignore[list-item]

    with pytest.raises(TypeError, match="add_field expects"):
        action.add_field("customer.email")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("mask", "getter_name", "setter_name"),
    [
        (
            PDActionSubmitForm.FLAG_INCLUDE_NO_VALUE_FIELDS,
            "is_include_no_value_fields",
            "set_include_no_value_fields",
        ),
        (PDActionSubmitForm.FLAG_EXPORT_FORMAT, "is_export_format", "set_export_format"),
        (PDActionSubmitForm.FLAG_GET_METHOD, "is_get_method", "set_get_method"),
        (PDActionSubmitForm.FLAG_XFDF, "is_xfdf", "set_xfdf"),
        (PDActionSubmitForm.FLAG_EMBED_FORM, "is_embed_form", "set_embed_form"),
    ],
)
def test_wave648_remaining_named_flags_round_trip(
    mask: int, getter_name: str, setter_name: str
) -> None:
    action = PDActionSubmitForm()
    getter = getattr(action, getter_name)
    setter = getattr(action, setter_name)

    setter(True)
    assert getter() is True
    assert action.has_flag(mask) is True

    setter(False)
    assert getter() is False
    assert action.get_flags() == 0


def test_wave648_include_overload_clear_flags_and_has_flags_presence() -> None:
    action = PDActionSubmitForm()

    assert action.has_flags() is False
    assert action.is_include(True) is True
    assert action.has_flags() is True
    assert action.get_cos_object().get_dictionary_object(_FLAGS) is not None

    assert action.is_include(False) is False
    assert action.get_flags() == 0

    action.set_flags(
        PDActionSubmitForm.FLAG_INCLUDE_EXCLUDE | PDActionSubmitForm.FLAG_XFDF
    )
    action.clear_flags()

    assert action.has_flags() is True
    assert action.get_flags() == 0
