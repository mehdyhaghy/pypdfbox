"""Wave 1341 coverage boost for ``pypdfbox.cos.cos_increment``.

Targets the dict-entry directness branch (lines 160-171), the
``child_demands_parent_update`` re-add (line 177), the
``_collect_array`` already-contained skip (line 185), and the
``_collect_object`` already-contained early-return (line 195).

The dict-entry path at line 165 calls ``entry.is_need_to_be_updated()``;
because the concrete COS types ship ``is_needs_to_be_updated`` (plural)
rather than the singular form defined on the ``COSUpdateInfo`` ABC, we
use a thin subclass that supplies the singular alias so the branch is
reachable. The mismatch is reported in the wave 1341 agent-D notes.
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


class _UpdateableArray(COSArray):
    """COSArray that exposes the singular ``is_need_to_be_updated`` alias
    so ``COSIncrement._collect_dictionary`` can interrogate it."""

    def is_need_to_be_updated(self) -> bool:
        return self.get_update_state().is_updated()


class _UpdateableDict(COSDictionary):
    """COSDictionary with the singular ``is_need_to_be_updated`` alias and
    a settable ``is_direct`` so the inner directness branch is reachable."""

    def __init__(self) -> None:
        super().__init__()
        self._is_direct = False

    def is_need_to_be_updated(self) -> bool:
        return self.get_update_state().is_updated()

    def is_direct(self) -> bool:
        return self._is_direct

    def set_direct_flag(self, value: bool) -> None:
        self._is_direct = value


def _attach_state(*items: object) -> COSDocumentState:
    state = COSDocumentState()
    state.set_parsing(False)
    for item in items:
        get = getattr(item, "get_update_state", None)
        if get is not None:
            get().set_origin_document_state(state)
    return state


# ---------------------------------------------------------------------------
# dict-entry directness branch (lines 165-170)
# ---------------------------------------------------------------------------
def test_dirty_array_child_is_excluded_and_demands_parent_update() -> None:
    parent = _UpdateableDict()
    child = _UpdateableArray()
    parent.set_item(COSName.get_pdf_name("Kids"), child)
    _attach_state(parent, child)
    child.get_update_state().update()
    inc = COSIncrement(parent)
    items = inc.get_objects()
    # The dirty array is excluded by the directness branch, parent is
    # added via the ``child_demands_parent_update`` re-add path (line 177).
    assert inc.is_excluded(child) is True
    assert parent in items


def test_dirty_direct_dict_child_is_excluded_when_marked_direct() -> None:
    parent = _UpdateableDict()
    child = _UpdateableDict()
    parent.set_item(COSName.get_pdf_name("Embedded"), child)
    _attach_state(parent, child)
    child.set_direct_flag(True)
    child.get_update_state().update()
    inc = COSIncrement(parent)
    inc.get_objects()
    assert inc.is_excluded(child) is True


def test_excluded_parent_returns_child_demands_value() -> None:
    parent = _UpdateableDict()
    child = _UpdateableArray()
    parent.set_item(COSName.get_pdf_name("Kids"), child)
    _attach_state(parent, child)
    child.get_update_state().update()
    inc = COSIncrement(parent).exclude(parent)
    items = inc.get_objects()
    # Parent excluded → not added to the increment.
    assert parent not in items


# ---------------------------------------------------------------------------
# ``_collect_array`` already-contained skip (line 184-185)
# ---------------------------------------------------------------------------
def test_collect_array_skips_already_contained_entry() -> None:
    """Attach origin state while parsing so neither entry is auto-dirtied,
    then pre-add the child so the ``contains(entry)`` continue branch is
    exercised."""
    state = COSDocumentState()  # parsing=True by default; no auto-dirty
    arr = COSArray()
    child = COSArray()
    arr.add(child)
    arr.get_update_state().set_origin_document_state(state)
    child.get_update_state().set_origin_document_state(state)
    state.set_parsing(False)
    inc = COSIncrement(None)
    # Pre-collect ``child`` so the loop hits the ``continue`` branch.
    inc.add(child)
    # Clean array: no updates → returns ``is_updated()`` == False.
    assert inc.collect(arr) is False
    # ``child`` was already added, not re-processed.
    assert inc.contains(child) is True


def test_collect_array_skips_primitive_entries() -> None:
    arr = COSArray()
    arr.add(COSString("primitive"))
    _attach_state(arr)
    inc = COSIncrement(None)
    # Primitive entry has no ``get_update_state`` so it triggers the
    # ``not _is_update_info(entry)`` branch of the continue.
    inc.collect(arr)
    assert list(inc) == []


# ---------------------------------------------------------------------------
# ``_collect_object`` already-contained early return (lines 194-195)
# ---------------------------------------------------------------------------
def test_collect_object_short_circuits_when_already_contained() -> None:
    target = COSDictionary()
    obj = COSObject(7, 0, resolved=target)
    _attach_state(obj, target)
    obj.get_update_state().update()
    inc = COSIncrement(None)
    # Pre-mark the object as already processed; the second call should
    # return immediately via the line-194 contains guard.
    inc.add_processed_object(obj)
    assert inc.contains(obj) is True
    # Re-collecting through the dispatcher hits the early return — no
    # state mutation, no exception.
    inc.collect(obj)
    assert obj not in inc._objects  # type: ignore[attr-defined]


def test_collect_object_internal_helper_skips_already_contained() -> None:
    """The ``_collect_object`` helper has its own ``contains`` guard at
    line 194; bypass the dispatcher to exercise it directly."""
    obj = COSObject(13, 0)
    _attach_state(obj)
    inc = COSIncrement(None)
    inc.add_processed_object(obj)
    # Direct call: contains(obj) → True via processed_objects, early return.
    inc._collect_object(obj)  # type: ignore[attr-defined]
    assert obj not in inc._objects  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# ``child_demands_parent_update`` re-add for non-direct/non-array entry
# ---------------------------------------------------------------------------
def test_child_demands_parent_update_re_adds_clean_parent() -> None:
    """When a dirty array child propagates ``child_demands_parent_update``
    back up but the parent itself is clean, the re-add branch on lines
    176-177 triggers — without it the increment would be missing the
    parent entry needed for the writer to walk the graph."""
    # Use COSDocumentState in parsing mode so attaching origin doesn't
    # auto-dirty either side. Then dirty *only* the array child.
    state = COSDocumentState()
    parent = _UpdateableDict()
    child = _UpdateableArray()
    parent.set_item(COSName.get_pdf_name("Kids"), child)
    parent.get_update_state().set_origin_document_state(state)
    child.get_update_state().set_origin_document_state(state)
    state.set_parsing(False)
    # Parent stays clean; child marked dirty.
    assert parent.get_update_state().is_updated() is False
    child.get_update_state().update()
    inc = COSIncrement(parent)
    items = inc.get_objects()
    # The directness branch excludes the array and bubbles the
    # ``child_demands_parent_update`` flag, then line 176-177 re-adds
    # the clean parent.
    assert parent in items
