from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action import PDFormFieldAdditionalActions
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_field import PDField
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_AA = COSName.get_pdf_name("AA")
_FT = COSName.get_pdf_name("FT")
_KIDS = COSName.get_pdf_name("Kids")
_PARENT = COSName.get_pdf_name("Parent")
_T = COSName.get_pdf_name("T")


def test_set_parent_none_clears_parent_entry() -> None:
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    child = PDTextField(form)

    child.set_parent(parent)
    assert child.get_parent() is parent
    assert child.get_cos_object().get_dictionary_object(_PARENT) is parent.get_cos_object()

    child.set_parent(None)

    assert child.get_parent() is None
    assert child.get_cos_object().get_dictionary_object(_PARENT) is None


def test_fully_qualified_name_handles_empty_parent_or_child_name() -> None:
    form = PDAcroForm()
    unnamed_parent = PDNonTerminalField(form)
    named_child = PDTextField(form, parent=unnamed_parent)
    named_child.set_partial_name("leaf")

    assert named_child.get_fully_qualified_name() == "leaf"

    named_parent = PDNonTerminalField(form)
    named_parent.set_partial_name("root")
    unnamed_child = PDTextField(form, parent=named_parent)

    assert unnamed_child.get_fully_qualified_name() == "root"


def test_base_set_actions_accepts_wrapper_and_none_removes_entry() -> None:
    field = PDField(PDAcroForm())
    actions = PDFormFieldAdditionalActions()

    field.set_actions(actions)

    assert field.has_actions()
    assert field.get_cos_object().get_dictionary_object(_AA) is actions.get_cos_object()

    field.set_actions(None)

    assert not field.has_actions()
    assert field.get_cos_object().get_dictionary_object(_AA) is None


def test_base_field_is_terminal_is_abstract() -> None:
    with pytest.raises(NotImplementedError):
        PDField(PDAcroForm()).is_terminal()


def test_find_kid_skips_non_dictionary_kids_and_breaks_after_match() -> None:
    form = PDAcroForm()
    parent = PDNonTerminalField(form)

    matching_child = COSDictionary()
    matching_child.set_string(_T, "leaf")
    matching_child.set_item(_FT, COSName.get_pdf_name("Tx"))
    ignored_child = COSDictionary()
    ignored_child.set_string(_T, "other")
    ignored_child.set_item(_FT, COSName.get_pdf_name("Tx"))
    parent.get_cos_object().set_item(
        _KIDS,
        COSArray([COSString("not a dictionary"), matching_child, ignored_child]),
    )

    found = parent.find_kid(["leaf"], 0)

    assert found is not None
    assert found.get_cos_object() is matching_child


def test_find_kid_recurses_through_non_terminal_child() -> None:
    form = PDAcroForm()
    root = PDNonTerminalField(form)

    branch = COSDictionary()
    branch.set_string(_T, "branch")
    leaf = COSDictionary()
    leaf.set_string(_T, "leaf")
    leaf.set_item(_FT, COSName.get_pdf_name("Tx"))
    branch.set_item(_KIDS, COSArray([leaf]))
    root.get_cos_object().set_item(_KIDS, COSArray([branch]))

    found = root.find_kid(["branch", "leaf"], 0)

    assert found is not None
    assert found.get_fully_qualified_name() == "branch.leaf"
    assert found.get_cos_object() is leaf


def test_repr_delegates_to_string_representation() -> None:
    field = PDTextField(PDAcroForm())
    field.set_partial_name("display")

    assert repr(field) == str(field)
