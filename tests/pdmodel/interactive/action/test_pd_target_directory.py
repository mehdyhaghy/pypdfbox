from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.interactive.action.pd_target_directory import (
    PDTargetDirectory,
)


def test_default_fresh_target_directory() -> None:
    td = PDTargetDirectory()
    assert td.get_relationship() == "C"
    assert td.get_named_destination() is None
    assert td.get_page_number() is None
    assert td.get_annotation_number() is None
    assert td.get_target() is None
    assert isinstance(td.get_cos_object(), COSDictionary)


def test_round_trip_all_fields() -> None:
    td = PDTargetDirectory()
    td.set_relationship("P")
    td.set_named_destination("Chapter1")
    td.set_page_number(5)
    td.set_annotation_number(0)

    assert td.get_relationship() == "P"
    assert td.get_named_destination() == "Chapter1"
    assert td.get_page_number() == 5
    assert td.get_annotation_number() == 0


def test_recursive_target_directory() -> None:
    parent = PDTargetDirectory()
    child = PDTargetDirectory()
    child.set_named_destination("Nested")

    parent.set_target(child)

    fetched = parent.get_target()
    assert fetched is not None
    assert isinstance(fetched, PDTargetDirectory)
    assert fetched.get_cos_object() is child.get_cos_object()
    assert fetched.get_named_destination() == "Nested"


def test_set_relationship_rejects_invalid() -> None:
    td = PDTargetDirectory()
    with pytest.raises(ValueError):
        td.set_relationship("X")


def test_clearing_optional_entries() -> None:
    td = PDTargetDirectory()
    td.set_named_destination("foo")
    td.set_page_number(2)
    td.set_annotation_number(3)

    td.set_named_destination(None)
    td.set_page_number(None)
    td.set_annotation_number(None)

    assert td.get_named_destination() is None
    assert td.get_page_number() is None
    assert td.get_annotation_number() is None


def test_set_target_none_removes_entry() -> None:
    parent = PDTargetDirectory()
    child = PDTargetDirectory()
    parent.set_target(child)
    assert parent.get_target() is not None
    parent.set_target(None)
    assert parent.get_target() is None


def test_wrap_existing_dictionary_no_defaults() -> None:
    raw = COSDictionary()
    td = PDTargetDirectory(raw)
    assert td.get_cos_object() is raw
    assert td.get_relationship() is None
