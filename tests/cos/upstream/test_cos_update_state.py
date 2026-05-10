"""
Contract tests for ``COSUpdateState``.

Upstream Apache PDFBox 3.0.x has no dedicated ``COSUpdateStateTest.java``;
its behavior is exercised indirectly via ``TestCOSUpdateInfo`` and the
incremental-save path. These tests pin the documented contract from
``pdfbox/src/main/java/org/apache/pdfbox/cos/COSUpdateState.java`` so the
port stays 1:1 with upstream behavior.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSDocumentState, COSName, COSObject
from pypdfbox.cos.cos_update_state import COSIncrement, COSUpdateState


def _accepting_state() -> COSDocumentState:
    state = COSDocumentState()
    state.set_parsing(False)
    return state


def test_update_state_starts_unlinked_and_not_updated() -> None:
    info = COSDictionary()
    update_state = info.get_update_state()

    assert update_state.get_origin_document_state() is None
    assert update_state.is_accepting_updates() is False
    assert update_state.is_updated() is False


def test_set_origin_document_state_links_and_marks_updated() -> None:
    state = _accepting_state()
    info = COSDictionary()

    info.get_update_state().set_origin_document_state(state)

    assert info.get_update_state().get_origin_document_state() is state
    assert info.get_update_state().is_accepting_updates() is True
    # Linking outside dereferencing path triggers update().
    assert info.get_update_state().is_updated() is True


def test_set_origin_document_state_with_none_is_noop() -> None:
    info = COSDictionary()
    info.get_update_state().set_origin_document_state(None)

    assert info.get_update_state().get_origin_document_state() is None
    assert info.get_update_state().is_updated() is False


def test_set_origin_document_state_does_not_overwrite_existing() -> None:
    first = _accepting_state()
    second = _accepting_state()
    info = COSDictionary()

    info.get_update_state().set_origin_document_state(first)
    info.get_update_state().set_origin_document_state(second)

    assert info.get_update_state().get_origin_document_state() is first


def test_dereferencing_link_does_not_set_updated() -> None:
    state = _accepting_state()
    info = COSDictionary()

    info.get_update_state().set_origin_document_state(state, dereferencing=True)

    assert info.get_update_state().get_origin_document_state() is state
    # When the link is established via dereferencing, updated stays False.
    assert info.get_update_state().is_updated() is False


def test_set_origin_propagates_to_dictionary_children() -> None:
    state = _accepting_state()
    parent = COSDictionary()
    child = COSDictionary()
    parent.set_item(COSName.A, child)

    parent.get_update_state().set_origin_document_state(state)

    assert child.get_update_state().get_origin_document_state() is state


def test_set_origin_propagates_to_array_children() -> None:
    state = _accepting_state()
    array = COSArray()
    child = COSDictionary()
    array.add(child)

    array.get_update_state().set_origin_document_state(state)

    assert child.get_update_state().get_origin_document_state() is state


def test_set_origin_propagates_through_dereferenced_object() -> None:
    state = _accepting_state()
    cos_object = COSObject(1)
    target = COSDictionary()
    cos_object.set_object(target)

    cos_object.get_update_state().set_origin_document_state(state)

    assert target.get_update_state().get_origin_document_state() is state


def test_update_no_op_until_linked() -> None:
    info = COSDictionary()

    info.get_update_state().update(True)

    assert info.get_update_state().is_updated() is False


def test_update_with_child_links_child() -> None:
    state = _accepting_state()
    parent = COSDictionary()
    parent.get_update_state().set_origin_document_state(state)

    child = COSDictionary()
    parent.get_update_state().update(True, child=child)

    assert child.get_update_state().get_origin_document_state() is state


def test_update_with_children_links_each() -> None:
    state = _accepting_state()
    parent = COSDictionary()
    parent.get_update_state().set_origin_document_state(state)

    child_a = COSDictionary()
    child_b = COSDictionary()
    parent.get_update_state().update(True, children=[child_a, None, child_b])

    assert child_a.get_update_state().get_origin_document_state() is state
    assert child_b.get_update_state().get_origin_document_state() is state


def test_dereference_child_links_without_marking_updated() -> None:
    state = _accepting_state()
    parent = COSDictionary()
    parent.get_update_state().set_origin_document_state(state)
    parent.set_needs_to_be_updated(False)

    child = COSDictionary()
    parent.get_update_state().dereference_child(child)

    assert child.get_update_state().get_origin_document_state() is state
    assert child.get_update_state().is_updated() is False


def test_dereference_child_handles_none_and_non_update_info() -> None:
    state = _accepting_state()
    parent = COSDictionary()
    parent.get_update_state().set_origin_document_state(state)

    # Should not raise.
    parent.get_update_state().dereference_child(None)
    parent.get_update_state().dereference_child(COSName.A)


def test_to_increment_returns_increment_seeded_with_update_info() -> None:
    info = COSDictionary()
    increment = info.get_update_state().to_increment()

    assert isinstance(increment, COSIncrement)
    members = list(increment)
    assert members == [info]


def test_constructor_stores_update_info_for_increment() -> None:
    target = COSDictionary()
    update_state = COSUpdateState(target)

    increment = update_state.to_increment()
    assert list(increment) == [target]
