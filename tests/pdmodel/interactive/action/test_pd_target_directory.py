from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.interactive.action.pd_target_directory import (
    PDTargetDirectory,
)


def test_default_fresh_target_directory() -> None:
    td = PDTargetDirectory()
    assert td.get_relationship() == "C"
    assert td.get_target_filename() is None
    assert td.get_named_destination() is None
    assert td.get_page_number() is None
    assert td.get_annotation_number() is None
    assert td.get_target() is None
    assert isinstance(td.get_cos_object(), COSDictionary)


def test_round_trip_all_fields() -> None:
    td = PDTargetDirectory()
    td.set_relationship("P")
    td.set_target_filename("attachment.pdf")
    td.set_page_number(5)
    td.set_annotation_number(0)

    assert td.get_relationship() == "P"
    assert td.get_target_filename() == "attachment.pdf"
    assert td.get_page_number() == 5
    assert td.get_annotation_number() == 0


def test_recursive_target_directory() -> None:
    parent = PDTargetDirectory()
    child = PDTargetDirectory()
    child.set_target_filename("nested.pdf")

    parent.set_target(child)

    fetched = parent.get_target()
    assert fetched is not None
    assert isinstance(fetched, PDTargetDirectory)
    assert fetched.get_cos_object() is child.get_cos_object()
    assert fetched.get_target_filename() == "nested.pdf"


def test_set_relationship_rejects_invalid() -> None:
    td = PDTargetDirectory()
    with pytest.raises(ValueError):
        td.set_relationship("X")


def test_clearing_optional_entries() -> None:
    td = PDTargetDirectory()
    td.set_target_filename("foo.pdf")
    td.set_page_number(2)
    td.set_annotation_number(3)

    td.set_target_filename(None)
    td.set_page_number(None)
    td.set_annotation_number(None)

    assert td.get_target_filename() is None
    assert td.get_page_number() is None
    assert td.get_annotation_number() is None


def test_wrap_existing_dictionary_no_defaults() -> None:
    raw = COSDictionary()
    td = PDTargetDirectory(raw)
    assert td.get_cos_object() is raw
    assert td.get_relationship() is None


def test_named_destination_round_trip_uses_p_string_form() -> None:
    """``/P`` may carry a named-destination string per PDF 32000-1 Table 202."""
    td = PDTargetDirectory()
    td.set_named_destination("Chapter1")
    assert td.get_named_destination() == "Chapter1"
    # The string form does not surface as an integer page number.
    assert td.get_page_number() is None


def test_page_number_does_not_alias_named_destination() -> None:
    """Setting ``/P`` as int should not be readable via the string accessor."""
    td = PDTargetDirectory()
    td.set_page_number(7)
    assert td.get_page_number() == 7
    assert td.get_named_destination() is None


def test_set_named_destination_none_clears_p() -> None:
    td = PDTargetDirectory()
    td.set_named_destination("Nested")
    assert td.get_named_destination() == "Nested"
    td.set_named_destination(None)
    assert td.get_named_destination() is None
    assert td.get_page_number() is None


# ---------------------------------------------------------------- /A string form


def test_annotation_name_round_trip_string_form_of_a() -> None:
    """``/A`` may carry an annotation ``/NM`` string per PDF 32000-1 Table 202."""
    td = PDTargetDirectory()
    td.set_annotation_name("AnnotNM-1")
    assert td.get_annotation_name() == "AnnotNM-1"
    # The string form does not surface as an integer index.
    assert td.get_annotation_number() is None
    assert td.get_annotation_index() is None


def test_annotation_index_does_not_alias_annotation_name() -> None:
    """Setting ``/A`` as int should not be readable via the string accessor."""
    td = PDTargetDirectory()
    td.set_annotation_number(4)
    assert td.get_annotation_number() == 4
    assert td.get_annotation_name() is None


def test_set_annotation_name_none_clears_a() -> None:
    td = PDTargetDirectory()
    td.set_annotation_name("AnnotNM-1")
    assert td.get_annotation_name() == "AnnotNM-1"
    td.set_annotation_name(None)
    assert td.get_annotation_name() is None
    assert td.get_annotation_number() is None


# ---------------------------------------------------------------- spec-named aliases


def test_get_filename_alias_matches_target_filename() -> None:
    """``get_filename`` mirrors upstream PDFBox name; aliases
    ``get_target_filename``."""
    td = PDTargetDirectory()
    td.set_target_filename("attached.pdf")
    assert td.get_filename() == "attached.pdf"
    assert td.get_filename() == td.get_target_filename()


def test_set_filename_alias_writes_n_entry() -> None:
    """``set_filename`` mirrors upstream PDFBox name; aliases
    ``set_target_filename``."""
    td = PDTargetDirectory()
    td.set_filename("a.pdf")
    assert td.get_target_filename() == "a.pdf"
    td.set_filename(None)
    assert td.get_target_filename() is None


def test_get_target_directory_alias_matches_get_target() -> None:
    """``get_target_directory`` mirrors upstream PDFBox name; aliases
    ``get_target``."""
    parent = PDTargetDirectory()
    child = PDTargetDirectory()
    child.set_target_filename("nested.pdf")
    parent.set_target(child)

    via_legacy = parent.get_target()
    via_spec = parent.get_target_directory()
    assert via_legacy is not None
    assert via_spec is not None
    # Same backing dictionary either way.
    assert via_spec.get_cos_object() is via_legacy.get_cos_object()


def test_set_target_directory_alias_writes_t_entry() -> None:
    """``set_target_directory`` mirrors upstream PDFBox name; aliases
    ``set_target``."""
    parent = PDTargetDirectory()
    child = PDTargetDirectory()
    child.set_target_filename("nested.pdf")
    parent.set_target_directory(child)

    fetched = parent.get_target()
    assert fetched is not None
    assert fetched.get_target_filename() == "nested.pdf"

    parent.set_target_directory(None)
    assert parent.get_target() is None


def test_annotation_index_alias_matches_annotation_number() -> None:
    """``get_annotation_index`` / ``set_annotation_index`` mirror upstream
    PDFBox names; alias ``get_annotation_number`` / ``set_annotation_number``."""
    td = PDTargetDirectory()
    td.set_annotation_index(3)
    assert td.get_annotation_index() == 3
    assert td.get_annotation_number() == 3

    td.set_annotation_index(None)
    assert td.get_annotation_index() is None
    assert td.get_annotation_number() is None
