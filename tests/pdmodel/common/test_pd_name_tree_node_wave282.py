"""Wave 282 name-tree common behavior tests."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSNull, COSString
from pypdfbox.pdmodel.common.pd_string_name_tree_node import PDStringNameTreeNode

_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_NAMES = COSName.get_pdf_name("Names")
_LIMITS = COSName.get_pdf_name("Limits")


def test_child_name_mutation_refreshes_parent_limits() -> None:
    first = PDStringNameTreeNode()
    first.set_names({"alpha": "A"})
    second = PDStringNameTreeNode()
    second.set_names({"zulu": "Z"})

    parent = PDStringNameTreeNode()
    parent.set_kids([first, second])
    root = PDStringNameTreeNode()
    root.set_kids([parent])

    assert parent.get_lower_limit() == "alpha"
    assert parent.get_upper_limit() == "zulu"
    assert root.get_lower_limit() is None

    first.set_names({"mike": "M"})

    assert first.get_lower_limit() == "mike"
    assert parent.get_lower_limit() == "mike"
    assert parent.get_upper_limit() == "zulu"


def test_clear_names_alias_removes_leaf_entries_and_refreshes_parent_limits() -> None:
    first = PDStringNameTreeNode()
    first.set_names({"alpha": "A"})
    second = PDStringNameTreeNode()
    second.set_names({"zulu": "Z"})
    parent = PDStringNameTreeNode()
    parent.set_kids([first, second])
    root = PDStringNameTreeNode()
    root.set_kids([parent])

    first.clear_names()

    assert first.has_names() is False
    assert first.has_limits() is False
    assert first.get_cos_object().get_dictionary_object(_NAMES) is None
    assert parent.get_lower_limit() is None
    assert parent.get_upper_limit() == "zulu"
    assert root.get_lower_limit() is None


def test_clear_kids_alias_removes_intermediate_entries() -> None:
    leaf = PDStringNameTreeNode()
    leaf.set_names({"alpha": "A"})
    parent = PDStringNameTreeNode()
    parent.set_kids([leaf])

    parent.clear_kids()

    assert parent.has_kids() is False
    assert parent.get_cos_object().get_dictionary_object(_KIDS) is None
    assert parent.get_cos_object().get_dictionary_object(_LIMITS) is None


def test_null_name_tree_value_is_rejected_with_clear_error() -> None:
    tree = PDStringNameTreeNode()
    names = COSArray()
    names.add(COSString("alpha"))
    names.add(COSNull.NULL)
    tree.get_cos_object().set_item(_NAMES, names)

    # Per Wave 1360, ``_read_names_array`` no longer rejects ``COSNull``
    # value slots in the base class — the embedded-files name tree
    # subclass tolerates them per upstream
    # ``TestEmbeddedFiles#testNullEmbeddedFile``. The string-typed
    # subclass still rejects non-string values inside
    # ``convert_cos_to_value`` with a message naming the expected type.
    with pytest.raises(OSError, match="COSString"):
        tree.get_names()
