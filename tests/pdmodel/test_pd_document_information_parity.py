"""Parity tests for PDDocumentInformation upstream-named accessors.

Mirrors the surface of ``org.apache.pdfbox.pdmodel.PDDocumentInformation``
to catch regressions in the camelCase -> snake_case alias layer for the
standard /Info dictionary keys.
"""
from __future__ import annotations

import datetime as _dt

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel import PDDocumentInformation


# ---------- title ----------


def test_title_round_trip() -> None:
    info = PDDocumentInformation()
    assert info.get_title() is None
    info.set_title("My Doc")
    assert info.get_title() == "My Doc"
    info.set_title(None)
    assert info.get_title() is None


# ---------- author ----------


def test_author_round_trip() -> None:
    info = PDDocumentInformation()
    assert info.get_author() is None
    info.set_author("Jane Doe")
    assert info.get_author() == "Jane Doe"
    info.set_author(None)
    assert info.get_author() is None


# ---------- subject / keywords ----------


def test_subject_round_trip() -> None:
    info = PDDocumentInformation()
    info.set_subject("Topic")
    assert info.get_subject() == "Topic"


def test_keywords_round_trip() -> None:
    info = PDDocumentInformation()
    info.set_keywords("alpha, beta")
    assert info.get_keywords() == "alpha, beta"


# ---------- creator / producer ----------


def test_creator_round_trip() -> None:
    info = PDDocumentInformation()
    info.set_creator("WordProcessor 3.0")
    assert info.get_creator() == "WordProcessor 3.0"


def test_producer_round_trip() -> None:
    info = PDDocumentInformation()
    info.set_producer("pypdfbox")
    assert info.get_producer() == "pypdfbox"


# ---------- creation date ----------


def test_creation_date_returns_datetime_when_set_as_pdf_date_string() -> None:
    """Storing the value as a raw PDF date literal still returns a
    ``datetime`` from ``get_creation_date()``."""
    raw = COSDictionary()
    raw.set_item(
        COSName.get_pdf_name("CreationDate"),
        COSString("D:20240601123045Z00'00'"),
    )
    info = PDDocumentInformation(raw)
    parsed = info.get_creation_date()
    assert isinstance(parsed, _dt.datetime)
    assert parsed == _dt.datetime(
        2024, 6, 1, 12, 30, 45, tzinfo=_dt.timezone.utc
    )


def test_creation_date_set_then_get() -> None:
    info = PDDocumentInformation()
    when = _dt.datetime(2025, 11, 15, 9, 0, 0, tzinfo=_dt.timezone.utc)
    info.set_creation_date(when)
    assert info.get_creation_date() == when


# ---------- modification date ----------


def test_modification_date_round_trip() -> None:
    info = PDDocumentInformation()
    when = _dt.datetime(2026, 1, 31, 23, 59, 0, tzinfo=_dt.timezone.utc)
    info.set_modification_date(when)
    assert info.get_modification_date() == when


# ---------- trapped ----------


@pytest.mark.parametrize("value", ["True", "False", "Unknown"])
def test_trapped_accepts_each_valid_value(value: str) -> None:
    info = PDDocumentInformation()
    info.set_trapped(value)
    assert info.get_trapped() == value


def test_trapped_clear_with_none() -> None:
    info = PDDocumentInformation()
    info.set_trapped("True")
    info.set_trapped(None)
    assert info.get_trapped() is None


def test_trapped_rejects_invalid_value() -> None:
    info = PDDocumentInformation()
    with pytest.raises(ValueError):
        info.set_trapped("Maybe")


# ---------- custom metadata ----------


def test_get_custom_metadata_value_unknown_key_returns_none() -> None:
    info = PDDocumentInformation()
    assert info.get_custom_metadata_value("NonExistent") is None


def test_set_custom_metadata_value_round_trip() -> None:
    info = PDDocumentInformation()
    info.set_custom_metadata_value("Company", "ACME")
    assert info.get_custom_metadata_value("Company") == "ACME"
    # Clearing via None.
    info.set_custom_metadata_value("Company", None)
    assert info.get_custom_metadata_value("Company") is None


def test_set_custom_metadata_value_appears_in_metadata_keys() -> None:
    info = PDDocumentInformation()
    info.set_custom_metadata_value("Department", "Eng")
    keys = info.get_metadata_keys()
    assert "Department" in keys
