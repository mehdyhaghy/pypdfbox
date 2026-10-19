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


def test_deep_array_chain_links_without_recursion_error() -> None:
    """PDFBOX-6200: a 5000-deep nested ``COSArray`` chain links iteratively."""
    deepest = COSArray()
    root = deepest
    for _ in range(5000):
        parent = COSArray()
        parent.add(root)
        root = parent
    state = _accepting_state()

    root.get_update_state().set_origin_document_state(state)

    assert deepest.get_update_state().get_origin_document_state() is state
    assert root.is_needs_to_be_updated()
    assert deepest.is_needs_to_be_updated()


def test_deep_chain_dereferencing_links_without_marking_updated() -> None:
    deepest = COSDictionary()
    root: COSDictionary = deepest
    for _ in range(5000):
        parent = COSDictionary()
        parent.set_item(COSName.get_pdf_name("Next"), root)
        root = parent
    holder = COSDictionary()
    holder.get_update_state().set_origin_document_state(_accepting_state())

    holder.get_update_state().dereference_child(root)

    assert deepest.get_update_state().get_origin_document_state() is not None
    assert not root.is_needs_to_be_updated()
    assert not deepest.is_needs_to_be_updated()


def test_cyclic_structure_terminates() -> None:
    a = COSDictionary()
    b = COSArray()
    a.set_item(COSName.get_pdf_name("B"), b)
    b.add(a)
    state = _accepting_state()

    a.get_update_state().set_origin_document_state(state)

    assert b.get_update_state().get_origin_document_state() is state
    assert a.is_needs_to_be_updated()
    assert b.is_needs_to_be_updated()


def test_already_linked_subtree_is_not_revisited() -> None:
    first = _accepting_state()
    second = _accepting_state()
    child = COSDictionary()
    grandchild = COSDictionary()
    child.set_item(COSName.get_pdf_name("G"), grandchild)
    child.get_update_state().set_origin_document_state(first)
    root = COSArray()
    root.add(child)

    root.get_update_state().set_origin_document_state(second)

    assert root.get_update_state().get_origin_document_state() is second
    assert child.get_update_state().get_origin_document_state() is first
    assert grandchild.get_update_state().get_origin_document_state() is first


def test_unloaded_object_target_is_not_linked() -> None:
    target = COSDictionary()
    loaded: list[int] = []

    def loader(_obj: COSObject) -> COSDictionary:
        loaded.append(1)
        return target

    ref = COSObject(7, loader=loader)
    ref.get_update_state().set_origin_document_state(_accepting_state())

    assert loaded == []
    assert target.get_update_state().get_origin_document_state() is None
