from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSDocumentState, COSName, COSObject


def _accepting_state() -> COSDocumentState:
    state = COSDocumentState()
    state.set_parsing(False)
    return state


def test_array_updates_are_document_state_gated_and_propagate_to_children() -> None:
    state = _accepting_state()
    array = COSArray()
    child = COSDictionary()

    array.add(child)
    assert array.is_needs_to_be_updated() is False
    assert child.is_needs_to_be_updated() is False

    array.get_update_state().set_origin_document_state(state)
    array.set_needs_to_be_updated(False)
    inserted_child = COSDictionary()

    array.add(inserted_child)

    assert array.is_needs_to_be_updated() is True
    assert inserted_child.is_needs_to_be_updated() is True


def test_dereferenced_object_child_inherits_state_without_becoming_dirty() -> None:
    state = _accepting_state()
    cos_object = COSObject(1)
    child = COSDictionary()

    cos_object.get_update_state().set_origin_document_state(state)
    cos_object.set_object(child)

    assert child.get_update_state().get_origin_document_state() is state
    assert child.is_needs_to_be_updated() is False

    child.set_item(COSName.A, COSName.B)

    assert child.is_needs_to_be_updated() is True
