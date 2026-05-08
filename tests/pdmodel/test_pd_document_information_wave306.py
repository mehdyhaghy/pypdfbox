"""Wave 306 — PDDocumentInformation low-level string setter parity."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel import PDDocumentInformation


def test_set_property_string_value_writes_raw_string_wave306() -> None:
    info = PDDocumentInformation()

    info.set_property_string_value("Company", "ACME")

    raw = info.get_cos_object().get_dictionary_object("Company")
    assert isinstance(raw, COSString)
    assert info.get_property_string_value("Company") == "ACME"
    assert info.get_custom_metadata_value("Company") == "ACME"


def test_set_property_string_value_none_removes_entry_wave306() -> None:
    info = PDDocumentInformation()
    info.set_property_string_value("Company", "ACME")

    info.set_property_string_value("Company", None)

    assert info.has_property("Company") is False
    assert info.get_property_string_value("Company") is None


def test_set_property_string_value_replaces_malformed_value_wave306() -> None:
    raw = COSDictionary()
    raw.set_item("Company", COSInteger.get(306))
    info = PDDocumentInformation(raw)

    assert info.has_property("Company") is True
    assert info.get_property_string_value("Company") is None

    info.set_property_string_value("Company", "Engineering")

    assert info.get_property_string_value("Company") == "Engineering"


def test_set_property_string_value_accepts_cosname_key_wave306() -> None:
    info = PDDocumentInformation()
    title = COSName.get_pdf_name("Title")

    info.set_property_string_value(title.get_name(), "Report")

    assert info.get_title() == "Report"
