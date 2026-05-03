"""Wave 267 round-out: PDAnnotationInk predicates / convenience helpers.

Covers:
- ``has_ink_list`` predicate (present vs absent vs malformed)
- ``is_empty`` (absent / empty array / non-empty / non-array entry)
- ``clear_ink_list`` (in-place when present; install empty array when absent)
- Interaction with the existing typed accessors.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_ink import (
    PDAnnotationInk,
)

_INK_LIST_NAME = COSName.get_pdf_name("InkList")


# ---------- has_ink_list ----------


def test_has_ink_list_default_false() -> None:
    assert PDAnnotationInk().has_ink_list() is False


def test_has_ink_list_true_after_set() -> None:
    ann = PDAnnotationInk()
    ann.set_ink_paths([[1.0, 2.0]])
    assert ann.has_ink_list() is True


def test_has_ink_list_true_for_empty_array() -> None:
    """Empty ``/InkList`` still counts as present — distinguishes
    "never drawn" from "drawn then cleared"."""
    ann = PDAnnotationInk()
    ann.get_cos_object().set_item(_INK_LIST_NAME, COSArray())
    assert ann.has_ink_list() is True


def test_has_ink_list_true_for_non_array_entry() -> None:
    """Predicate reports presence regardless of malformed contents."""
    ann = PDAnnotationInk()
    ann.get_cos_object().set_item(_INK_LIST_NAME, COSFloat(0.0))
    assert ann.has_ink_list() is True


def test_has_ink_list_false_after_clear_to_none() -> None:
    ann = PDAnnotationInk()
    ann.set_ink_paths([[1.0, 2.0]])
    ann.set_ink_paths(None)
    assert ann.has_ink_list() is False


# ---------- is_empty ----------


def test_is_empty_default_true() -> None:
    assert PDAnnotationInk().is_empty() is True


def test_is_empty_true_for_explicit_empty_array() -> None:
    ann = PDAnnotationInk()
    ann.get_cos_object().set_item(_INK_LIST_NAME, COSArray())
    assert ann.is_empty() is True


def test_is_empty_false_when_paths_present() -> None:
    ann = PDAnnotationInk()
    ann.set_ink_paths([[1.0, 2.0, 3.0, 4.0]])
    assert ann.is_empty() is False


def test_is_empty_true_for_non_array_entry() -> None:
    """Malformed (non-COSArray) entry reports empty — matches the
    upstream-mirror ``get_ink_paths`` returning ``[]`` for the same."""
    ann = PDAnnotationInk()
    ann.get_cos_object().set_item(_INK_LIST_NAME, COSFloat(0.0))
    assert ann.is_empty() is True


def test_is_empty_false_with_inner_empty_path() -> None:
    """A path of zero points still counts as one path — not empty."""
    ann = PDAnnotationInk()
    outer = COSArray()
    outer.add(COSArray())  # one zero-coord path
    ann.get_cos_object().set_item(_INK_LIST_NAME, outer)
    assert ann.is_empty() is False


# ---------- clear_ink_list ----------


def test_clear_ink_list_when_absent_installs_empty_array() -> None:
    ann = PDAnnotationInk()
    assert ann.has_ink_list() is False
    ann.clear_ink_list()
    assert ann.has_ink_list() is True
    assert ann.is_empty() is True
    assert ann.path_count() == 0


def test_clear_ink_list_mutates_in_place() -> None:
    """Existing ``COSArray`` reference must remain valid after clear —
    important for callers that already cached the inner array."""
    ann = PDAnnotationInk()
    ann.set_ink_paths([[1.0, 2.0], [3.0, 4.0]])
    raw_before = ann.get_cos_object().get_dictionary_object(_INK_LIST_NAME)
    assert isinstance(raw_before, COSArray)
    ann.clear_ink_list()
    raw_after = ann.get_cos_object().get_dictionary_object(_INK_LIST_NAME)
    assert raw_after is raw_before
    assert raw_after.size() == 0


def test_clear_ink_list_when_non_array_replaces_with_empty_array() -> None:
    ann = PDAnnotationInk()
    ann.get_cos_object().set_item(_INK_LIST_NAME, COSFloat(7.0))
    ann.clear_ink_list()
    raw = ann.get_cos_object().get_dictionary_object(_INK_LIST_NAME)
    assert isinstance(raw, COSArray)
    assert raw.size() == 0


def test_clear_then_get_ink_paths_returns_empty_list() -> None:
    ann = PDAnnotationInk()
    ann.set_ink_paths([[1.0, 2.0, 3.0, 4.0]])
    ann.clear_ink_list()
    assert ann.get_ink_paths() == []


def test_clear_distinct_from_set_none() -> None:
    """``clear_ink_list`` keeps the entry; ``set_ink_paths(None)``
    removes it. Both leave ``is_empty()`` true but ``has_ink_list``
    differs."""
    a = PDAnnotationInk()
    a.set_ink_paths([[0.0, 0.0]])
    a.clear_ink_list()
    assert a.is_empty() is True
    assert a.has_ink_list() is True

    b = PDAnnotationInk()
    b.set_ink_paths([[0.0, 0.0]])
    b.set_ink_paths(None)
    assert b.is_empty() is True
    assert b.has_ink_list() is False
