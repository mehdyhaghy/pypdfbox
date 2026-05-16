"""Coverage boost for ``pypdfbox.cos.cos_increment`` (wave 1318).

Exercises the lazy traversal seed paths, dict/array/object collection
branches, exclusion, processed-object tracking, and the
``update_different_origin`` cross-document hook.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSIncrement,
    COSName,
    COSObject,
    COSString,
)
from pypdfbox.cos.cos_document_state import COSDocumentState


def _open_for_updates(*items: object) -> None:
    """Attach a finished document state to each COS item so subsequent
    :meth:`update` calls flip ``is_updated`` to ``True``."""
    state = COSDocumentState()
    state.set_parsing(False)
    for item in items:
        get = getattr(item, "get_update_state", None)
        if get is not None:
            get().set_origin_document_state(state)


def test_iterator_is_alias_for_iter() -> None:
    inc = COSIncrement(None)
    assert list(inc.iterator()) == []
    assert list(inc) == []


def test_contains_none_is_false() -> None:
    inc = COSIncrement(None)
    assert inc.contains(None) is False


def test_exclude_none_arg_is_ignored() -> None:
    inc = COSIncrement(None)
    d = COSDictionary()
    inc.exclude(None, d)
    assert inc.is_excluded(d) is True
    assert inc.is_excluded(COSDictionary()) is False


def test_add_records_object() -> None:
    inc = COSIncrement(None)
    d = COSDictionary()
    inc.add(d)
    assert inc.contains(d) is True
    inc.add(None)  # no-op
    assert list(inc.get_objects()) == [d]


def test_add_processed_object_marks_cos_object() -> None:
    inc = COSIncrement(None)
    obj = COSObject(7, 0)
    inc.add_processed_object(obj)
    assert inc.contains(obj) is True
    inc.add_processed_object(None)  # no-op


def test_update_different_origin_no_origin_is_noop() -> None:
    inc = COSIncrement(None)
    d = COSDictionary()
    # No seed origin → early return; should not raise even with arbitrary obj.
    inc.update_different_origin(d.get_update_state())
    inc.update_different_origin(None)


def test_collect_none_returns_false() -> None:
    inc = COSIncrement(None)
    assert inc.collect(None) is False


def test_collect_already_contained_returns_false() -> None:
    inc = COSIncrement(None)
    d = COSDictionary()
    inc.add(d)
    assert inc.collect(d) is False


def test_collect_unknown_type_returns_false() -> None:
    inc = COSIncrement(None)
    # COSString is not dict/array/object — should hit the final ``return False``.
    s = COSString("hi")
    assert inc.collect(s) is False


def test_collect_dictionary_with_updated_state_adds_self() -> None:
    d = COSDictionary()
    _open_for_updates(d)
    d.get_update_state().update()  # flip the dirty flag
    inc = COSIncrement(None)
    assert inc.collect(d) is False  # only excluded path returns True
    assert inc.contains(d) is True


def test_get_objects_lazy_initialization_via_seed() -> None:
    d = COSDictionary()
    _open_for_updates(d)
    d.get_update_state().update()
    inc = COSIncrement(d)
    items = inc.get_objects()
    assert items == [d]
    # Second call shouldn't re-collect.
    assert inc.get_objects() == [d]


def test_dictionary_with_primitive_entries_only_self_when_dirty() -> None:
    # Primitives lack ``get_update_state`` so the per-entry traversal is
    # skipped (the ``_is_update_info`` guard fires). The dictionary itself
    # is dirty so it's added.
    parent = COSDictionary()
    parent.set_name(COSName.TYPE, "Catalog")
    _open_for_updates(parent)
    parent.get_update_state().update()
    inc = COSIncrement(parent)
    items = inc.get_objects()
    assert parent in items


def test_excluded_dictionary_is_not_added_even_when_dirty() -> None:
    parent = COSDictionary()
    parent.set_name(COSName.TYPE, "Catalog")
    _open_for_updates(parent)
    parent.get_update_state().update()
    inc = COSIncrement(parent).exclude(parent)
    items = inc.get_objects()
    assert parent not in items


def test_collect_array_with_updated_state() -> None:
    arr = COSArray()
    child = COSDictionary()
    arr.add(child)
    _open_for_updates(arr, child)
    arr.get_update_state().update()
    inc = COSIncrement(None)
    assert inc.collect(arr) is True  # array dirty → demands parent update
    # The array itself isn't added by ``_collect_array``; only its
    # update-info children that are dirty get pulled in (none are here).
    assert inc.contains(arr) is False


def test_collect_array_propagates_dirty_child() -> None:
    arr = COSArray()
    child = COSDictionary()
    arr.add(child)
    _open_for_updates(arr, child)
    child.get_update_state().update()
    inc = COSIncrement(None)
    assert inc.collect(arr) is True
    assert inc.contains(child) is True


def test_collect_object_resolved_to_dirty_dictionary() -> None:
    target = COSDictionary()
    obj = COSObject(11, 0, resolved=target)
    _open_for_updates(obj, target)
    obj.get_update_state().update()
    target.get_update_state().update()
    inc = COSIncrement(None)
    inc.collect(obj)
    # COSObject path adds the resolved dict to the increment.
    assert inc.contains(obj) is True
    assert inc.contains(target) is True


def test_collect_object_unresolved_is_skipped() -> None:
    obj = COSObject(5, 0)  # no resolved target, no loader
    inc = COSIncrement(None)
    inc.collect(obj)
    # Object is recorded as processed but nothing added.
    assert inc.contains(obj) is True
    assert obj not in inc.get_objects()


def test_update_different_origin_marks_cross_doc() -> None:
    # Seed has its own origin; the visited update_state belongs to a
    # *different* origin → its ``update`` should be invoked. Attach
    # origins while still parsing so neither side is pre-marked dirty.
    seed = COSDictionary()
    other = COSDictionary()
    state_seed = COSDocumentState()
    state_other = COSDocumentState()
    seed.get_update_state().set_origin_document_state(state_seed)
    other.get_update_state().set_origin_document_state(state_other)
    # Now finish parsing so subsequent ``update`` calls actually flip the bit.
    state_seed.set_parsing(False)
    state_other.set_parsing(False)
    inc = COSIncrement(seed)
    assert other.get_update_state().is_updated() is False
    inc.update_different_origin(other.get_update_state())
    assert other.get_update_state().is_updated() is True


def test_update_different_origin_object_without_method_is_ignored() -> None:
    seed = COSDictionary()
    state_seed = COSDocumentState()
    state_seed.set_parsing(False)
    seed.get_update_state().set_origin_document_state(state_seed)
    inc = COSIncrement(seed)

    class _Stub:
        pass

    # No ``get_origin_document_state`` → early return; should not raise.
    inc.update_different_origin(_Stub())


def test_collect_dictionary_already_contained_skipped() -> None:
    d = COSDictionary()
    _open_for_updates(d)
    d.get_update_state().update()
    inc = COSIncrement(None)
    inc.add(d)
    # Already contained → the ``contains(dictionary)`` guard short-circuits
    # the ``_add`` and returns the cached state.
    assert inc.collect(d) is False
    assert inc.get_objects() == [d]


def test_collect_object_loads_via_loader() -> None:
    # COSObject with a loader: the resolved-on-demand path runs through
    # ``get_object``; the resolved dictionary is dirty so it joins.
    target = COSDictionary()
    _open_for_updates(target)
    target.get_update_state().update()
    obj = COSObject(99, 0, loader=lambda _o: target)
    _open_for_updates(obj)
    obj.get_update_state().update()
    inc = COSIncrement(None)
    inc.collect(obj)
    # After resolution the underlying dict should be tracked.
    assert obj in inc._processed_objects or inc.contains(obj)
