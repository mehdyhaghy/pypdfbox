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


def test_trapped_reads_cos_string_value() -> None:
    """Some real-world PDFs store /Trapped as a COSString instead of the
    spec-mandated COSName. Upstream ``getTrapped()`` reads via
    ``getNameAsString`` which accepts both — match that lenience."""
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("Trapped"), COSString("True"))
    info = PDDocumentInformation(raw)
    assert info.get_trapped() == "True"


def test_trapped_reads_cos_name_value() -> None:
    """The spec-correct COSName form still reads back."""
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("Trapped"), "Unknown")
    info = PDDocumentInformation(raw)
    assert info.get_trapped() == "Unknown"


def test_trapped_returns_none_for_unexpected_type() -> None:
    """Non-name, non-string values yield None (no exception)."""
    raw = COSDictionary()
    raw.set_int(COSName.get_pdf_name("Trapped"), 1)
    info = PDDocumentInformation(raw)
    assert info.get_trapped() is None


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


# ---------- get_metadata_keys_set / contains_property ----------


def test_get_metadata_keys_set_default_empty() -> None:
    info = PDDocumentInformation()
    assert info.get_metadata_keys_set() == set()


def test_get_metadata_keys_set_returns_set_instance() -> None:
    info = PDDocumentInformation()
    info.set_title("T")
    info.set_author("A")
    keys = info.get_metadata_keys_set()
    assert isinstance(keys, set)
    assert keys == {"Title", "Author"}


def test_get_metadata_keys_set_matches_list_form() -> None:
    info = PDDocumentInformation()
    info.set_title("T")
    info.set_creator("C")
    info.set_custom_metadata_value("Department", "Eng")
    assert info.get_metadata_keys_set() == set(info.get_metadata_keys())


def test_contains_property_default_false() -> None:
    info = PDDocumentInformation()
    assert info.contains_property("Title") is False
    assert info.contains_property("NonExistent") is False


def test_contains_property_true_after_set() -> None:
    info = PDDocumentInformation()
    info.set_title("My Doc")
    assert info.contains_property("Title") is True
    info.set_title(None)
    assert info.contains_property("Title") is False


def test_contains_property_works_for_custom_keys() -> None:
    info = PDDocumentInformation()
    info.set_custom_metadata_value("Company", "ACME")
    assert info.contains_property("Company") is True
    info.set_custom_metadata_value("Company", None)
    assert info.contains_property("Company") is False


# ---------- STANDARD_KEYS / get_custom_metadata_keys ----------


def test_standard_keys_contains_all_spec_keys() -> None:
    """The class-level constant must mirror PDF 32000-1:2008 §14.3.3."""
    assert PDDocumentInformation.STANDARD_KEYS == frozenset(
        {
            "Title",
            "Author",
            "Subject",
            "Keywords",
            "Creator",
            "Producer",
            "CreationDate",
            "ModDate",
            "Trapped",
        }
    )


def test_standard_keys_is_immutable() -> None:
    assert isinstance(PDDocumentInformation.STANDARD_KEYS, frozenset)


def test_get_custom_metadata_keys_default_empty() -> None:
    info = PDDocumentInformation()
    assert info.get_custom_metadata_keys() == []


def test_get_custom_metadata_keys_excludes_standard_entries() -> None:
    """Setting only standard fields yields no custom keys."""
    info = PDDocumentInformation()
    info.set_title("T")
    info.set_author("A")
    info.set_creator("C")
    info.set_producer("P")
    assert info.get_custom_metadata_keys() == []


def test_get_custom_metadata_keys_returns_only_non_standard_sorted() -> None:
    info = PDDocumentInformation()
    info.set_title("T")
    info.set_custom_metadata_value("Department", "Eng")
    info.set_custom_metadata_value("Company", "ACME")
    info.set_custom_metadata_value("BatchId", "42")
    # Sorted ASCII order, standard keys filtered out.
    assert info.get_custom_metadata_keys() == [
        "BatchId",
        "Company",
        "Department",
    ]


# ---------- is_empty / __len__ / __contains__ ----------


def test_is_empty_default_true() -> None:
    info = PDDocumentInformation()
    assert info.is_empty() is True


def test_is_empty_false_after_set() -> None:
    info = PDDocumentInformation()
    info.set_title("T")
    assert info.is_empty() is False
    info.set_title(None)
    assert info.is_empty() is True


def test_len_reports_entry_count() -> None:
    info = PDDocumentInformation()
    assert len(info) == 0
    info.set_title("T")
    assert len(info) == 1
    info.set_author("A")
    info.set_custom_metadata_value("Company", "ACME")
    assert len(info) == 3


def test_dunder_contains_with_string() -> None:
    info = PDDocumentInformation()
    info.set_title("T")
    assert "Title" in info
    assert "Author" not in info


def test_dunder_contains_with_cos_name() -> None:
    info = PDDocumentInformation()
    info.set_creator("C")
    assert COSName.get_pdf_name("Creator") in info
    assert COSName.get_pdf_name("Producer") not in info


def test_dunder_contains_with_non_string_returns_false() -> None:
    info = PDDocumentInformation()
    info.set_title("T")
    assert (123 in info) is False
    assert (None in info) is False
