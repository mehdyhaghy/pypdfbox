from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.interactive.form import (
    PDAcroForm,
    PDFieldStub,
    PDNonTerminalField,
)


def test_acro_form_round_trips_top_level_fields() -> None:
    form = PDAcroForm()
    stub = PDFieldStub(form, COSDictionary(), None)
    stub.set_partial_name("name")
    form.set_fields([stub])

    fields = form.get_fields()
    assert len(fields) == 1
    assert isinstance(fields[0], PDFieldStub)
    assert fields[0].get_cos_object() is stub.get_cos_object()
    assert fields[0].get_partial_name() == "name"


def test_field_partial_alternate_and_mapping_names_round_trip() -> None:
    form = PDAcroForm()
    stub = PDFieldStub(form)
    stub.set_partial_name("first_name")
    stub.set_alternate_field_name("First Name")
    stub.set_mapping_name("firstName")

    assert stub.get_partial_name() == "first_name"
    assert stub.get_alternate_field_name() == "First Name"
    assert stub.get_mapping_name() == "firstName"


def test_fully_qualified_name_concatenates_with_dot() -> None:
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.set_partial_name("address")
    child = PDFieldStub(form)
    child.set_partial_name("street")
    parent.set_children([child])

    children = parent.get_children()
    assert len(children) == 1
    assert children[0].get_fully_qualified_name() == "address.street"


def test_field_flags_and_read_only_round_trip() -> None:
    form = PDAcroForm()
    stub = PDFieldStub(form)
    assert stub.get_field_flags() == 0
    assert stub.is_read_only() is False

    stub.set_field_flags(0b101)  # bit 0 (read-only) + bit 2 (no-export)
    assert stub.get_field_flags() == 0b101
    assert stub.is_read_only() is True
    assert stub.is_no_export() is True
    assert stub.is_required() is False

    stub.set_read_only(False)
    assert stub.is_read_only() is False
    assert stub.is_no_export() is True


def test_signatures_exist_and_need_appearances_round_trip() -> None:
    form = PDAcroForm()
    assert form.is_signatures_exist() is False
    assert form.is_appendonly() is False
    assert form.is_need_appearances() is False

    form.set_signatures_exist(True)
    form.set_appendonly(True)
    form.set_need_appearances(True)

    assert form.is_signatures_exist() is True
    assert form.is_appendonly() is True
    assert form.is_need_appearances() is True

    form.set_signatures_exist(False)
    assert form.is_signatures_exist() is False
    assert form.is_appendonly() is True


def test_get_field_by_fully_qualified_name() -> None:
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.set_partial_name("address")
    child = PDFieldStub(form)
    child.set_partial_name("street")
    parent.set_children([child])
    form.set_fields([parent])

    found = form.get_field("address.street")
    assert found is not None
    assert found.get_partial_name() == "street"
    assert form.get_field("address") is not None
    assert form.get_field("does.not.exist") is None
