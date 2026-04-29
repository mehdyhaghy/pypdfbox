from __future__ import annotations

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
