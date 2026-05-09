"""Wave 283 — PDDocumentInformation metadata accessor edge cases."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel import PDDocumentInformation


def test_standard_string_accessors_ignore_malformed_cos_names_wave283() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("Title"), "NotAString")
    raw.set_name(COSName.get_pdf_name("Author"), "AlsoNotAString")

    info = PDDocumentInformation(raw)

    assert info.has_title() is True
    assert info.has_author() is True
    assert info.get_title() is None
    assert info.get_author() is None


def test_property_string_value_does_not_coerce_cos_name_wave283() -> None:
    raw = COSDictionary()
    raw.set_name("Company", "ACME")
    raw.set_item("Department", COSString("Engineering"))

    info = PDDocumentInformation(raw)

    assert info.contains_property("Company") is True
    assert info.has_property("Company") is True
    assert info.get_property_string_value("Company") is None
    assert info.get_property_string_value("Department") == "Engineering"


def test_date_accessors_ignore_non_string_cos_values_wave283() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("CreationDate"), "D:20240101000000Z")
    raw.set_int(COSName.get_pdf_name("ModDate"), 20240101)

    info = PDDocumentInformation(raw)

    assert info.has_creation_date() is True
    assert info.has_modification_date() is True
    assert info.get_creation_date() is None
    assert info.get_modification_date() is None


def test_custom_metadata_has_and_clear_helpers_wave283() -> None:
    info = PDDocumentInformation()

    assert info.has_custom_metadata_value("Company") is False

    info.set_custom_metadata_value("Company", "ACME")
    assert info.has_custom_metadata_value("Company") is True
    assert info.get_custom_metadata_value("Company") == "ACME"

    info.clear_custom_metadata_value("Company")
    assert info.has_custom_metadata_value("Company") is False
    assert info.get_custom_metadata_value("Company") is None


def test_clear_property_removes_standard_and_custom_keys_wave283() -> None:
    info = PDDocumentInformation()
    info.set_title("Report")
    info.set_custom_metadata_value("Company", "ACME")

    info.clear_property("Title")
    info.clear_property("Company")

    assert info.has_title() is False
    assert info.has_property("Title") is False
    assert info.contains_property("Company") is False
    assert info.is_empty() is True


def test_to_dict_includes_name_values_but_skips_non_string_values_wave283() -> None:
    raw = COSDictionary()
    raw.set_item("Title", COSString("Report"))
    raw.set_name("Author", "MalformedName")
    raw.set_item("Build", COSInteger.get(283))

    info = PDDocumentInformation(raw)

    assert info.to_dict() == {"Title": "Report", "Author": "MalformedName"}
