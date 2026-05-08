from __future__ import annotations

import datetime as _dt

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel import PDDocument, PDDocumentInformation
from pypdfbox.pdmodel.pd_document_information import _parse_pdf_date


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
    when = _dt.datetime(2024, 6, 1, 12, 30, 45, tzinfo=_dt.UTC)
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
    when = _dt.datetime(2020, 1, 1, tzinfo=_dt.UTC)
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


# ---------- _parse_pdf_date lenient-mode regression tests ----------


def test_parse_date_strict_full_format() -> None:
    """Canonical D:YYYYMMDDHHmmSSOHH'mm' still parses (regression)."""
    assert _parse_pdf_date("D:20230101120000Z00'00'") == _dt.datetime(
        2023, 1, 1, 12, 0, 0, tzinfo=_dt.UTC
    )


def test_parse_date_missing_d_prefix() -> None:
    """Many writers omit the leading 'D:' marker."""
    assert _parse_pdf_date("20230101120000Z00'00'") == _dt.datetime(
        2023, 1, 1, 12, 0, 0, tzinfo=_dt.UTC
    )


def test_parse_date_truncated_to_year_month() -> None:
    assert _parse_pdf_date("D:202301") == _dt.datetime(
        2023, 1, 1, 0, 0, 0, tzinfo=_dt.UTC
    )


def test_parse_date_truncated_to_year_month_day() -> None:
    assert _parse_pdf_date("D:20230101") == _dt.datetime(
        2023, 1, 1, 0, 0, 0, tzinfo=_dt.UTC
    )


def test_parse_date_truncated_to_hour() -> None:
    assert _parse_pdf_date("D:2023010112") == _dt.datetime(
        2023, 1, 1, 12, 0, 0, tzinfo=_dt.UTC
    )


def test_parse_date_full_time_without_timezone() -> None:
    """No Z and no offset — assume UTC."""
    assert _parse_pdf_date("D:20230101120000") == _dt.datetime(
        2023, 1, 1, 12, 0, 0, tzinfo=_dt.UTC
    )


def test_parse_date_bare_z_without_offset() -> None:
    assert _parse_pdf_date("D:20230101120000Z") == _dt.datetime(
        2023, 1, 1, 12, 0, 0, tzinfo=_dt.UTC
    )


def test_parse_date_compact_timezone_no_apostrophes() -> None:
    expected = _dt.datetime(
        2023, 1, 1, 12, 0, 0, tzinfo=_dt.timezone(_dt.timedelta(hours=5, minutes=30))
    )
    assert _parse_pdf_date("D:20230101120000+0530") == expected


def test_parse_date_apostrophe_timezone_form() -> None:
    expected = _dt.datetime(
        2023, 1, 1, 12, 0, 0, tzinfo=_dt.timezone(_dt.timedelta(hours=5, minutes=30))
    )
    assert _parse_pdf_date("D:20230101120000+05'30'") == expected


def test_parse_date_negative_offset_compact() -> None:
    expected = _dt.datetime(
        2023, 1, 1, 12, 0, 0, tzinfo=_dt.timezone(_dt.timedelta(hours=-8))
    )
    assert _parse_pdf_date("D:20230101120000-0800") == expected


def test_parse_date_strips_whitespace() -> None:
    assert _parse_pdf_date("  D:20230101120000Z  ") == _dt.datetime(
        2023, 1, 1, 12, 0, 0, tzinfo=_dt.UTC
    )


def test_parse_date_clamps_leap_second() -> None:
    """Time HHmm60 — clamp to HHmm59 (Python datetime has no leap-second
    representation; upstream PDFBox silently truncates as well)."""
    assert _parse_pdf_date("D:20230101235960Z") == _dt.datetime(
        2023, 1, 1, 23, 59, 59, tzinfo=_dt.UTC
    )


@pytest.mark.parametrize(
    "garbage",
    [
        "",
        "   ",
        "hello world",
        "D:abc",
        "not a date",
        "D:",
    ],
)
def test_parse_date_returns_none_for_garbage(garbage: str) -> None:
    assert _parse_pdf_date(garbage) is None


def test_round_trip_via_info_dict_with_lenient_string() -> None:
    """Reading a CreationDate stored without the 'D:' prefix still works."""
    raw = COSDictionary()
    raw.set_item(
        COSName.get_pdf_name("CreationDate"), COSString("20230101120000Z00'00'")
    )
    info = PDDocumentInformation(raw)
    parsed = info.get_creation_date()
    assert parsed == _dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=_dt.UTC)
