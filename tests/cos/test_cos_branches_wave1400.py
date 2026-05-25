"""Branch coverage for several :mod:`pypdfbox.cos` files — wave 1400.

Closes residual partial branches in:

* ``cos_array.py``: ``add_all`` with an empty iterable (65 → 63);
  ``reset_object_keys`` with a primitive child (427 → 417).
* ``cos_dictionary.py``: ``reset_object_keys`` /Parent skip (827 → 818).
* ``cos_stream.py``: double-``close()`` on a raw-write stream
  (46 → 51); ``set_skip_encryption(False)`` retains handler (307 → 299).
* ``cos_increment.py``: dict entry not needing update; object resolved
  base not is_update_info; object actual not updated.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSIncrement,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
    COSStream,
    COSString,
)

# ----------------------------------------------------------------------
# COSArray.add_all([]) — branch 65 → 63
# ----------------------------------------------------------------------


def test_cos_array_add_all_empty_iterable_no_update_fired() -> None:
    """When the iterable is empty, ``add_all`` must skip the extend
    (and the update notification). Confirms the false branch of the
    ``if materialized:`` guard.

    Closes branch (65 → 63)."""
    arr = COSArray()
    arr.add_all([])
    assert arr.size() == 0
    # Also exercise the generator-empty form to make sure materialize
    # behaves the same.
    arr.add_all(x for x in ())  # type: ignore[arg-type]
    assert arr.size() == 0


def test_cos_array_add_all_non_empty_fires_update() -> None:
    """Positive control: a non-empty iterable extends and notifies."""
    arr = COSArray()
    arr.add_all([COSInteger.get(1), COSInteger.get(2)])
    assert arr.size() == 2


# ----------------------------------------------------------------------
# COSArray.reset_object_keys — primitive (non-dict/array) child
# ----------------------------------------------------------------------


def test_cos_array_reset_object_keys_with_primitive_child_skips_recurse() -> None:
    """A primitive element (COSString) is neither a Dictionary nor
    an Array nor an indirect ref — the loop iteration must fall through
    without recursing or recording an indirect key.

    Closes branch (427 → 417)."""
    arr = COSArray()
    arr.add(COSString("primitive"))
    arr.add(COSInteger.get(42))
    result = arr.reset_object_keys({})
    # No indirect-object keys gathered — primitives don't contribute.
    assert result == {}


def test_cos_array_reset_object_keys_collects_indirect_refs() -> None:
    """Positive control: an indirect reference (COSObject) does get
    recorded into the indirect_objects set."""
    arr = COSArray()
    arr.add(COSObject(7, 0))
    indirect: set[COSObjectKey] = set()
    arr.reset_object_keys(indirect)
    assert COSObjectKey(7, 0) in indirect


# ----------------------------------------------------------------------
# COSDictionary.reset_object_keys — /Parent skip
# ----------------------------------------------------------------------


def test_cos_dictionary_reset_object_keys_skips_parent_recursion() -> None:
    """``reset_object_keys`` must NOT recurse through /Parent keys —
    that would loop forever in a tree where every child points back
    to its parent.

    Closes branch (827 → 818)."""
    parent = COSDictionary()
    child = COSDictionary()
    child.set_item(COSName.PARENT, parent)
    parent.set_item(COSName.get_pdf_name("Kid"), child)
    # Call on the parent — the loop visits 'Kid' (the child dict),
    # recurses into it, which then visits 'Parent' but must skip the
    # recursion (parent_skip branch).
    result = parent.reset_object_keys({})
    assert result == {}


def test_cos_dictionary_reset_object_keys_skips_p_short_form() -> None:
    """``/P`` is the short-form parent key in tagged PDFs — also skipped
    by ``parent_skip``."""
    p = COSDictionary()
    c = COSDictionary()
    c.set_item(COSName.get_pdf_name("P"), p)
    p.set_item(COSName.get_pdf_name("K"), c)
    result = p.reset_object_keys({})
    assert result == {}


# ----------------------------------------------------------------------
# COSStream raw-output double-close — branch 46 → 51
# ----------------------------------------------------------------------


def test_cos_stream_raw_output_close_is_idempotent() -> None:
    """A second ``close()`` on a raw-output stream must NOT re-commit
    the bytes (which would clobber any subsequent writes). The
    ``_committed`` flag guards the commit step.

    Closes branch (46 → 51)."""
    stream = COSStream()
    out = stream.create_raw_output_stream()
    out.write(b"hello")
    out.close()
    # Second close — guard fires.
    out.close()
    # Stream contents unchanged.
    view = stream.create_view()
    data = bytearray()
    while True:
        b = view.read()
        if b == -1:
            break
        data.append(b)
    assert bytes(data) == b"hello"


# ----------------------------------------------------------------------
# COSStream.set_skip_encryption(False) — branch 307 → 299
# ----------------------------------------------------------------------


def test_cos_stream_set_skip_encryption_false_does_not_drop_handler() -> None:
    """Clearing the skip flag (``set_skip_encryption(False)``) must
    NOT drop the attached handler — only set-to-True does that.

    Closes branch (307 → 299)."""
    stream = COSStream()
    sentinel = object()
    stream._security_handler = sentinel  # noqa: SLF001
    stream.set_skip_encryption(False)
    # Handler survives because the if-True branch was not entered.
    assert stream._security_handler is sentinel  # noqa: SLF001


def test_cos_stream_set_skip_encryption_true_drops_handler() -> None:
    """Positive control: set_skip_encryption(True) clears the handler."""
    stream = COSStream()
    stream._security_handler = object()  # noqa: SLF001
    stream.set_skip_encryption(True)
    assert stream._security_handler is None  # noqa: SLF001


# ----------------------------------------------------------------------
# COSIncrement — branch coverage residuals
# ----------------------------------------------------------------------


def test_cos_increment_dict_entry_not_marked_for_update_is_skipped() -> None:
    """Child dict whose update_state is not flagged updated, and which
    is not a COSArray, must not trigger the exclude/add path.

    Closes branch (165 → 171)."""
    from pypdfbox.cos.cos_document_state import COSDocumentState

    state = COSDocumentState()
    # Keep parsing TRUE while we wire children + attach origin. While
    # parsing, set_origin_document_state's internal ``update()`` is a
    # no-op (is_accepting_updates() is False).
    parent = COSDictionary()
    child = COSDictionary()
    parent.set_item(COSName.get_pdf_name("Kid"), child)
    parent.get_update_state().set_origin_document_state(state)
    child.get_update_state().set_origin_document_state(state)
    # Now flip parsing off so future explicit ``update()`` calls take.
    state.set_parsing(False)
    parent.get_update_state().update()  # only parent goes dirty

    inc = COSIncrement(parent)
    objs = inc.get_objects()
    # Parent is in the increment; the clean child is NOT.
    assert parent in objs
    assert child not in objs


def test_cos_increment_object_actual_not_updated_skips_add() -> None:
    """A COSObject whose resolved actual is *not* dirty, and whose own
    update_state isn't dirty either, must not be added by
    ``_collect_object``.

    Closes branches (208 → 210) and (214 → 193)."""
    from pypdfbox.cos.cos_document_state import COSDocumentState

    state = COSDocumentState()
    # Keep parsing TRUE while wiring origins, then flip off.
    target = COSDictionary()
    obj = COSObject(7, 0, resolved=target)
    obj.get_update_state().set_origin_document_state(state)
    target.get_update_state().set_origin_document_state(state)
    state.set_parsing(False)
    # Neither obj nor target is dirty; collect must not add target.
    inc = COSIncrement(None)
    inc.collect(obj)
    assert inc.contains(obj) is True
    assert target not in inc.get_objects()


def test_cos_increment_object_resolved_base_not_update_info_returns() -> None:
    """When the resolved base isn't a COSUpdateInfo (e.g. a primitive
    like COSInteger), the helper sets ``actual = None`` and the next
    guard short-circuits without adding anything.

    Closes branch (202 → 204)."""
    from pypdfbox.cos.cos_document_state import COSDocumentState

    state = COSDocumentState()
    state.set_parsing(False)
    # Primitive resolved target — COSInteger is not COSUpdateInfo.
    obj = COSObject(11, 0, resolved=COSInteger.get(42))
    obj.get_update_state().set_origin_document_state(state)
    obj.get_update_state().update()  # mark dirty so we enter the inner check
    inc = COSIncrement(None)
    inc.collect(obj)
    # Object is in processed set; primitive resolution didn't propagate.
    assert inc.contains(obj) is True
