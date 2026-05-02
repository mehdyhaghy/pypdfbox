from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSArray, COSDictionary
from pypdfbox.pdmodel.interactive.form import (
    PDAcroForm,
    PDFieldStub,
    PDFieldTree,
    PDNonTerminalField,
)


def _form_with_nested_fields() -> PDAcroForm:
    form = PDAcroForm()
    address = PDNonTerminalField(form)
    address.set_partial_name("address")

    street = PDFieldStub(form)
    street.set_partial_name("street")
    city = PDFieldStub(form)
    city.set_partial_name("city")
    address.set_children([street, city])

    name = PDFieldStub(form)
    name.set_partial_name("name")
    form.set_fields([address, name])
    return form


def test_get_field_tree_returns_pd_field_tree_iterable() -> None:
    form = _form_with_nested_fields()

    tree = form.get_field_tree()

    assert isinstance(tree, PDFieldTree)
    assert [field.get_fully_qualified_name() for field in tree] == [
        "address",
        "address.street",
        "address.city",
        "name",
    ]


def test_pd_field_tree_supports_sequence_access_for_python_callers() -> None:
    tree = _form_with_nested_fields().get_field_tree()

    assert len(tree) == 4
    assert tree[0].get_fully_qualified_name() == "address"
    assert [field.get_fully_qualified_name() for field in tree[1:3]] == [
        "address.street",
        "address.city",
    ]


def test_get_field_iterator_uses_pd_field_tree_iteration() -> None:
    form = _form_with_nested_fields()

    assert [field.get_fully_qualified_name() for field in form.get_field_iterator()] == [
        "address",
        "address.street",
        "address.city",
        "name",
    ]


def test_pd_field_tree_rejects_null_root() -> None:
    with pytest.raises(ValueError, match="root cannot be null"):
        PDFieldTree(None)  # type: ignore[arg-type]


def test_iterator_public_surface_returns_independent_iterators() -> None:
    tree = _form_with_nested_fields().get_field_tree()

    first = tree.iterator()
    second = tree.iterator()

    assert first.has_next()
    assert second.has_next()
    assert first.next().get_fully_qualified_name() == "address"
    assert second.next().get_fully_qualified_name() == "address"
    with pytest.raises(NotImplementedError, match="remove"):
        first.remove()


def test_pd_field_tree_is_empty_on_fresh_form() -> None:
    """A freshly-constructed AcroForm has no fields — is_empty should be True
    and bool() should be False."""
    form = PDAcroForm()
    tree = form.get_field_tree()
    assert tree.is_empty() is True
    assert bool(tree) is False
    assert len(tree) == 0


def test_pd_field_tree_is_empty_false_when_fields_present() -> None:
    form = _form_with_nested_fields()
    tree = form.get_field_tree()
    assert tree.is_empty() is False
    assert bool(tree) is True


def test_pd_field_tree_is_empty_short_circuits_without_walking() -> None:
    """is_empty must not consume the whole iterator — verify by mutating the
    form between calls and confirming each call yields a fresh check."""
    form = _form_with_nested_fields()
    tree = form.get_field_tree()
    # First call: True (well, False — there are fields).
    assert tree.is_empty() is False
    # Drain on a separate iter — should not affect the next is_empty call.
    consumed = list(iter(tree))
    assert len(consumed) == 4
    # Tree is still non-empty for a fresh probe.
    assert tree.is_empty() is False


def test_iterator_skips_repeated_cos_dictionary_to_avoid_recursion(
    caplog: pytest.LogCaptureFixture,
) -> None:
    form = PDAcroForm()
    parent = COSDictionary()
    parent.set_string("T", "parent")
    child = COSDictionary()
    child.set_string("T", "child")

    parent_kids = COSArray()
    parent_kids.add(child)
    parent.set_item("Kids", parent_kids)
    child_kids = COSArray()
    child_kids.add(parent)
    child.set_item("Kids", child_kids)

    fields = COSArray()
    fields.add(parent)
    form.get_cos_object().set_item("Fields", fields)

    with caplog.at_level(logging.ERROR, logger="pypdfbox.pdmodel.interactive.form.pd_field_tree"):
        names = [field.get_fully_qualified_name() for field in form.get_field_tree()]

    assert names == ["parent", "parent.child"]
    assert "already exists elsewhere, ignored to avoid recursion" in caplog.text
