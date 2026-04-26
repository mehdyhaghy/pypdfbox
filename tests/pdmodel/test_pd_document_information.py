from __future__ import annotations

import datetime as _dt

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel import PDDocument, PDDocumentInformation


def test_default_construction_yields_empty_dict() -> None:
    info = PDDocumentInformation()
    assert info.get_cos_object().is_empty()
    assert info.get_title() is None
    assert info.get_author() is None


def test_round_trip_simple_fields() -> None:
    info = PDDocumentInformation()
    info.set_title("Hello")
    info.set_author("Bob")
    info.set_subject("Topic")
    info.set_keywords("a, b")
    info.set_creator("WordProcessor")
    info.set_producer("pypdfbox")
    assert info.get_title() == "Hello"
    assert info.get_author() == "Bob"
    assert info.get_subject() == "Topic"
    assert info.get_keywords() == "a, b"
    assert info.get_creator() == "WordProcessor"
    assert info.get_producer() == "pypdfbox"


def test_setting_none_clears_field() -> None:
    info = PDDocumentInformation()
    info.set_title("Hello")
    info.set_title(None)
    assert info.get_title() is None
    # The /Title key should also be removed from the underlying dict.
    assert not info.get_cos_object().contains_key(COSName.get_pdf_name("Title"))


def test_creation_date_round_trip_utc() -> None:
    info = PDDocumentInformation()
    when = _dt.datetime(2024, 6, 1, 12, 30, 45, tzinfo=_dt.timezone.utc)
    info.set_creation_date(when)
    parsed = info.get_creation_date()
    assert parsed == when
    # The raw value should be a PDF date string.
    raw = info.get_property_string_value("CreationDate")
    assert raw is not None
    assert raw.startswith("D:20240601123045")


def test_creation_date_round_trip_offset() -> None:
    info = PDDocumentInformation()
    when = _dt.datetime(
        2024, 6, 1, 12, 30, 45, tzinfo=_dt.timezone(_dt.timedelta(hours=-5))
    )
    info.set_creation_date(when)
    parsed = info.get_creation_date()
    assert parsed == when


def test_modification_date_round_trip() -> None:
    info = PDDocumentInformation()
    when = _dt.datetime(2020, 1, 1, tzinfo=_dt.timezone.utc)
    info.set_modification_date(when)
    assert info.get_modification_date() == when
    info.set_modification_date(None)
    assert info.get_modification_date() is None


def test_parse_external_date_string() -> None:
    """Read a /CreationDate set as a raw PDF date literal (ASCII)."""
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("CreationDate"), COSString("D:20080819181502"))
    info = PDDocumentInformation(raw)
    parsed = info.get_creation_date()
    assert parsed is not None
    assert parsed.year == 2008
    assert parsed.month == 8
    assert parsed.day == 19
    assert parsed.hour == 18
    assert parsed.minute == 15
    assert parsed.second == 2


def test_trapped_validation() -> None:
    info = PDDocumentInformation()
    info.set_trapped("True")
    assert info.get_trapped() == "True"
    info.set_trapped("False")
    assert info.get_trapped() == "False"
    info.set_trapped("Unknown")
    assert info.get_trapped() == "Unknown"
    info.set_trapped(None)
    assert info.get_trapped() is None
    with pytest.raises(ValueError):
        info.set_trapped("Maybe")


def test_metadata_keys_lists_all_entries() -> None:
    info = PDDocumentInformation()
    info.set_title("T")
    info.set_author("A")
    info.set_custom_metadata_value("Company", "ACME")
    keys = info.get_metadata_keys()
    assert "Title" in keys
    assert "Author" in keys
    assert "Company" in keys


def test_custom_metadata_round_trip() -> None:
    info = PDDocumentInformation()
    info.set_custom_metadata_value("Company", "ACME")
    assert info.get_custom_metadata_value("Company") == "ACME"
    # Unknown key returns None.
    assert info.get_custom_metadata_value("Missing") is None


def test_pddocument_get_document_information_creates_wrapper() -> None:
    """Round-trip via PDDocument: setting on the wrapper is visible on the
    trailer's /Info dict."""
    doc = PDDocument()
    info = doc.get_document_information()
    info.set_title("Round-trip")
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    info_dict = trailer.get_dictionary_object(COSName.INFO)  # type: ignore[attr-defined]
    assert isinstance(info_dict, COSDictionary)
    assert info_dict.get_string(COSName.get_pdf_name("Title")) == "Round-trip"


def test_set_document_information_replaces_trailer_entry() -> None:
    doc = PDDocument()
    new_info = PDDocumentInformation()
    new_info.set_author("Alice")
    doc.set_document_information(new_info)
    fetched = doc.get_document_information()
    assert fetched.get_cos_object() is new_info.get_cos_object()
    assert fetched.get_author() == "Alice"
