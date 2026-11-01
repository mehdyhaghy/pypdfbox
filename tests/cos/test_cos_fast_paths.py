"""Behavior pins for the COS container / update-state fast paths.

The fast paths skip update-state work while no origin document state is
linked, dispatch on exact classes, and replace ``ABCMeta`` on ``COSBase``
with an equivalent ``__abstractmethods__`` computation. These tests pin the
observable behavior each shortcut must preserve.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
)
from pypdfbox.cos.cos_document_state import COSDocumentState


def _accepting_state() -> COSDocumentState:
    state = COSDocumentState()
    state.set_parsing(False)
    return state


# ---------- COSBase abstract-method enforcement without ABCMeta ----------


def test_cos_base_is_not_instantiable() -> None:
    with pytest.raises(TypeError, match="abstract method 'accept'"):
        COSBase()  # type: ignore[abstract]


def test_subclass_without_accept_is_not_instantiable() -> None:
    class Missing(COSBase):
        pass

    assert Missing.__abstractmethods__ == frozenset({"accept"})
    with pytest.raises(TypeError):
        Missing()  # type: ignore[abstract]


def test_subclass_with_accept_is_instantiable() -> None:
    class Concrete(COSBase):
        def accept(self, visitor: Any) -> Any:
            return visitor

    assert Concrete.__abstractmethods__ == frozenset()
    assert Concrete().accept(7) == 7


def test_new_abstract_method_on_subclass_is_enforced() -> None:
    class Middle(COSBase):
        def accept(self, visitor: Any) -> Any:
            return None

        @abstractmethod
        def extra(self) -> None: ...

    class Leaf(Middle):
        def extra(self) -> None:
            return None

    with pytest.raises(TypeError, match="extra"):
        Middle()  # type: ignore[abstract]
    assert isinstance(Leaf(), COSBase)


def test_concrete_cos_types_have_no_abstract_methods() -> None:
    for cls in (COSArray, COSDictionary, COSStream, COSObject, COSName, COSInteger):
        assert cls.__abstractmethods__ == frozenset()


# ---------- update-state shortcuts ----------


def test_unlinked_set_item_neither_links_nor_marks() -> None:
    parent = COSDictionary()
    child = COSDictionary()
    parent.set_item("Child", child)
    assert parent.get_update_state().get_origin_document_state() is None
    assert child.get_update_state().get_origin_document_state() is None
    assert not parent.is_needs_to_be_updated()


def test_linked_set_item_marks_and_links_child_subtree() -> None:
    state = _accepting_state()
    parent = COSDictionary()
    parent.get_update_state().set_origin_document_state(state, dereferencing=True)
    assert not parent.is_needs_to_be_updated()

    child = COSDictionary()
    grandchild = COSArray()
    child.set_item("A", grandchild)
    parent.set_item("Child", child)

    assert parent.is_needs_to_be_updated()
    for base in (child, grandchild):
        assert base.get_update_state().get_origin_document_state() is state
        assert base.is_needs_to_be_updated()


def test_linked_quiet_set_links_without_marking() -> None:
    state = _accepting_state()
    parent = COSDictionary()
    parent.get_update_state().set_origin_document_state(state, dereferencing=True)
    child = COSDictionary()
    parent._set_item_quiet("Child", child)
    assert not parent.is_needs_to_be_updated()
    assert child.get_update_state().get_origin_document_state() is state
    assert not child.is_needs_to_be_updated()


def test_linked_array_mutators_mark() -> None:
    state = _accepting_state()
    array = COSArray()
    array.get_update_state().set_origin_document_state(state, dereferencing=True)
    array.add(COSInteger.get(1))
    assert array.is_needs_to_be_updated()
    array.set_needs_to_be_updated(False)
    array.remove_at(0)
    assert array.is_needs_to_be_updated()


def test_linked_remove_item_marks_only_when_present() -> None:
    state = _accepting_state()
    d = COSDictionary()
    d.set_int("K", 1)
    d.get_update_state().set_origin_document_state(state, dereferencing=True)
    d.remove_item("Missing")
    assert not d.is_needs_to_be_updated()
    d.remove_item("K")
    assert d.is_needs_to_be_updated()


def test_traversal_stops_at_linked_reference_but_walks_dereferenced_ones() -> None:
    state = _accepting_state()
    other = COSDictionary()
    linked_ref = COSObject(1, 0, resolved=other)
    # Link only the reference itself, the way ``COSDocument`` links a pool
    # placeholder.
    linked_ref.get_update_state()._origin_document_state = state
    other_child = COSArray()
    other.set_item("X", other_child)  # ``other`` is still unlinked

    inner = COSDictionary()
    fresh_ref = COSObject(2, 0, resolved=inner)

    root = COSDictionary()
    root.set_item("Linked", linked_ref)
    root.set_item("Fresh", fresh_ref)
    root.get_update_state().set_origin_document_state(state)

    # An already linked reference skips its whole subtree.
    assert other.get_update_state().get_origin_document_state() is None
    assert other_child.get_update_state().get_origin_document_state() is None
    # A fresh, dereferenced reference is walked into and marked.
    assert fresh_ref.get_update_state().get_origin_document_state() is state
    assert inner.get_update_state().get_origin_document_state() is state
    assert inner.is_needs_to_be_updated()


def test_traversal_uses_get_update_state_for_unknown_types() -> None:
    state = _accepting_state()

    class Tracked(COSDictionary):
        pass

    custom = Tracked()
    nested = COSArray()
    custom.set_item("N", nested)
    root = COSArray([custom, COSInteger.get(3), COSNull.NULL])
    root.get_update_state().set_origin_document_state(state)
    assert custom.get_update_state().get_origin_document_state() is state
    assert nested.get_update_state().get_origin_document_state() is state


# ---------- getter shortcuts ----------


def test_get_dictionary_object_resolution_rules() -> None:
    target = COSInteger.get(5)
    d = COSDictionary()
    d.set_item("Ref", COSObject(3, 0, resolved=target))
    d.set_item("Null", COSNull.NULL)
    d.set_item("Dangling", COSObject(4, 0))
    d.set_item(COSName.get_pdf_name("B"), COSInteger.get(9))

    assert d.get_dictionary_object("Ref") is target
    assert d.get_dictionary_object("Null") is None
    assert d.get_dictionary_object("Dangling") is None
    assert d.get_dictionary_object("Missing") is None
    assert d.get_dictionary_object("Missing", "B") is COSInteger.get(9)
    assert d.get_dictionary_object("Null", "B") is COSInteger.get(9)
    sentinel = COSInteger.get(77)
    assert d.get_dictionary_object("Missing", sentinel) is sentinel
    with pytest.raises(TypeError):
        d.get_dictionary_object(3)  # type: ignore[arg-type]


def test_getitem_and_contains_with_names_and_strings() -> None:
    d = COSDictionary()
    d.set_int("K", 1)
    assert d["K"] is d[COSName.get_pdf_name("K")]
    assert "K" in d
    assert COSName.get_pdf_name("K") in d
    assert 5 not in d
    with pytest.raises(KeyError) as info:
        d["Missing"]
    assert info.value.args == ("Missing",)


def test_array_get_object_resolution_rules() -> None:
    target = COSDictionary()
    array = COSArray([COSObject(1, 0, resolved=target), COSNull.NULL, COSObject(2, 0)])
    assert array.get_object(0) is target
    assert array.get_object(1) is None
    assert array.get_object(2) is None
    with pytest.raises(IndexError):
        array.get_object(-1)
    with pytest.raises(IndexError):
        array.get(-1)
