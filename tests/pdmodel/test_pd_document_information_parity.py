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
from pypdfbox.pdmodel.pd_document_information import (
    TRAPPED_FALSE,
    TRAPPED_TRUE,
    TRAPPED_UNKNOWN,
)


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


# ---------- /Trapped value constants ----------


def test_trapped_constants_module_level_match_spec() -> None:
    """PDF 32000-1:2008 §14.11.6 names: ``True`` / ``False`` / ``Unknown``."""
    assert TRAPPED_TRUE == "True"
    assert TRAPPED_FALSE == "False"
    assert TRAPPED_UNKNOWN == "Unknown"


def test_trapped_constants_class_level_alias_module_level() -> None:
    assert PDDocumentInformation.TRAPPED_TRUE == TRAPPED_TRUE
    assert PDDocumentInformation.TRAPPED_FALSE == TRAPPED_FALSE
    assert PDDocumentInformation.TRAPPED_UNKNOWN == TRAPPED_UNKNOWN


def test_set_trapped_accepts_module_constants() -> None:
    info = PDDocumentInformation()
    info.set_trapped(TRAPPED_TRUE)
    assert info.get_trapped() == "True"
    info.set_trapped(TRAPPED_FALSE)
    assert info.get_trapped() == "False"
    info.set_trapped(TRAPPED_UNKNOWN)
    assert info.get_trapped() == "Unknown"


def test_set_trapped_accepts_class_constants() -> None:
    info = PDDocumentInformation()
    info.set_trapped(PDDocumentInformation.TRAPPED_TRUE)
    assert info.get_trapped() == "True"


# ---------- is_trapped() tri-state predicate ----------


def test_is_trapped_default_none_when_absent() -> None:
    info = PDDocumentInformation()
    assert info.is_trapped() is None


def test_is_trapped_true() -> None:
    info = PDDocumentInformation()
    info.set_trapped("True")
    assert info.is_trapped() is True


def test_is_trapped_false() -> None:
    info = PDDocumentInformation()
    info.set_trapped("False")
    assert info.is_trapped() is False


def test_is_trapped_unknown_returns_none() -> None:
    """Spec semantic — ``Unknown`` means "we don't know", maps to ``None``."""
    info = PDDocumentInformation()
    info.set_trapped("Unknown")
    assert info.is_trapped() is None


def test_is_trapped_unexpected_type_returns_none() -> None:
    raw = COSDictionary()
    raw.set_int(COSName.get_pdf_name("Trapped"), 1)
    info = PDDocumentInformation(raw)
    assert info.is_trapped() is None


def test_is_trapped_reads_cos_string_storage() -> None:
    """Real-world PDFs storing /Trapped as COSString still produce True/False."""
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("Trapped"), COSString("True"))
    info = PDDocumentInformation(raw)
    assert info.is_trapped() is True


# ---------- has_* predicate helpers ----------


def test_has_title_default_false() -> None:
    info = PDDocumentInformation()
    assert info.has_title() is False


def test_has_title_true_after_set_then_false_after_clear() -> None:
    info = PDDocumentInformation()
    info.set_title("T")
    assert info.has_title() is True
    info.set_title(None)
    assert info.has_title() is False


def test_has_author_default_false() -> None:
    assert PDDocumentInformation().has_author() is False


def test_has_author_round_trip() -> None:
    info = PDDocumentInformation()
    info.set_author("A")
    assert info.has_author() is True
    info.set_author(None)
    assert info.has_author() is False


def test_has_subject_round_trip() -> None:
    info = PDDocumentInformation()
    assert info.has_subject() is False
    info.set_subject("S")
    assert info.has_subject() is True


def test_has_keywords_round_trip() -> None:
    info = PDDocumentInformation()
    assert info.has_keywords() is False
    info.set_keywords("k")
    assert info.has_keywords() is True


def test_has_creator_round_trip() -> None:
    info = PDDocumentInformation()
    assert info.has_creator() is False
    info.set_creator("C")
    assert info.has_creator() is True


def test_has_producer_round_trip() -> None:
    info = PDDocumentInformation()
    assert info.has_producer() is False
    info.set_producer("P")
    assert info.has_producer() is True


def test_has_creation_date_round_trip() -> None:
    info = PDDocumentInformation()
    assert info.has_creation_date() is False
    info.set_creation_date(_dt.datetime(2024, 1, 1, tzinfo=_dt.timezone.utc))
    assert info.has_creation_date() is True
    info.set_creation_date(None)
    assert info.has_creation_date() is False


def test_has_modification_date_round_trip() -> None:
    info = PDDocumentInformation()
    assert info.has_modification_date() is False
    info.set_modification_date(_dt.datetime(2024, 1, 1, tzinfo=_dt.timezone.utc))
    assert info.has_modification_date() is True
    info.set_modification_date(None)
    assert info.has_modification_date() is False


def test_has_trapped_round_trip() -> None:
    info = PDDocumentInformation()
    assert info.has_trapped() is False
    info.set_trapped("True")
    assert info.has_trapped() is True
    info.set_trapped(None)
    assert info.has_trapped() is False


# ---------- get_standard_metadata_keys ----------


def test_get_standard_metadata_keys_default_empty() -> None:
    info = PDDocumentInformation()
    assert info.get_standard_metadata_keys() == []


def test_get_standard_metadata_keys_only_returns_spec_keys() -> None:
    info = PDDocumentInformation()
    info.set_title("T")
    info.set_author("A")
    info.set_custom_metadata_value("Company", "ACME")
    info.set_custom_metadata_value("BatchId", "42")
    # Standard keys only — sorted, custom keys filtered out.
    assert info.get_standard_metadata_keys() == ["Author", "Title"]


def test_get_standard_metadata_keys_partitions_full_keyset() -> None:
    """Standard ∪ custom == all metadata keys, with no overlap."""
    info = PDDocumentInformation()
    info.set_title("T")
    info.set_creator("C")
    info.set_custom_metadata_value("Company", "ACME")
    standard = set(info.get_standard_metadata_keys())
    custom = set(info.get_custom_metadata_keys())
    assert standard.isdisjoint(custom)
    assert standard | custom == info.get_metadata_keys_set()


# ---------- clear() ----------


def test_clear_removes_all_entries() -> None:
    info = PDDocumentInformation()
    info.set_title("T")
    info.set_custom_metadata_value("Company", "ACME")
    info.set_creation_date(_dt.datetime(2024, 1, 1, tzinfo=_dt.timezone.utc))
    assert not info.is_empty()
    info.clear()
    assert info.is_empty()
    assert info.get_title() is None
    assert info.get_custom_metadata_value("Company") is None


def test_clear_preserves_underlying_dict_identity() -> None:
    """Clearing must not swap out the dict — references on the trailer stay
    valid."""
    info = PDDocumentInformation()
    raw = info.get_cos_object()
    info.set_title("T")
    info.clear()
    assert info.get_cos_object() is raw


# ---------- copy_from() ----------


def test_copy_from_copies_all_entries() -> None:
    src = PDDocumentInformation()
    src.set_title("Title")
    src.set_author("Author")
    src.set_custom_metadata_value("Company", "ACME")

    dst = PDDocumentInformation()
    dst.copy_from(src)
    assert dst.get_title() == "Title"
    assert dst.get_author() == "Author"
    assert dst.get_custom_metadata_value("Company") == "ACME"


def test_copy_from_overwrites_colliding_keys() -> None:
    src = PDDocumentInformation()
    src.set_title("New")

    dst = PDDocumentInformation()
    dst.set_title("Old")
    dst.set_author("Existing")
    dst.copy_from(src)

    # Title overwritten, Author preserved.
    assert dst.get_title() == "New"
    assert dst.get_author() == "Existing"


def test_copy_from_does_not_alias_dictionaries() -> None:
    """copy_from must not link the two wrappers' dictionaries; modifying
    one should not affect the other."""
    src = PDDocumentInformation()
    src.set_title("T")
    dst = PDDocumentInformation()
    dst.copy_from(src)
    src.set_title("Changed")
    assert dst.get_title() == "T"


def test_copy_from_empty_source_leaves_destination_intact() -> None:
    src = PDDocumentInformation()
    dst = PDDocumentInformation()
    dst.set_title("Keep")
    dst.copy_from(src)
    assert dst.get_title() == "Keep"


# ---------- module __all__ exports ----------


def test_module_exports_trapped_constants() -> None:
    from pypdfbox.pdmodel import pd_document_information as mod

    assert "TRAPPED_TRUE" in mod.__all__
    assert "TRAPPED_FALSE" in mod.__all__
    assert "TRAPPED_UNKNOWN" in mod.__all__
