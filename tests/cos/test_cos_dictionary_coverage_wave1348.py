"""Wave-1348 coverage-boost tests for ``pypdfbox.cos.cos_dictionary``.

Closes residual gaps after wave 1332:

* the ``get_object_from_path`` early-return branch when the path drills
  through a non-collection (line 935);
* the ``get_indirect_object_keys`` / ``reset_object_keys`` ``continue``
  branches that short-circuit when an indirect key has already been
  visited (lines 963, 1010);
* the array-walk ``reset_object_keys`` fallthrough (line 1016);
* the ``UnmodifiableCOSDictionary.clear_item`` write-guard (line 1099);
* the unreached ``_get_dictionary_string`` ``None``-input fast path
  (line 194) and the ``COSObject`` formatter branch (lines 219-221);
* the early-stop branches in ``_array_get_indirect_object_keys`` /
  ``_array_reset_object_keys`` when an indirect key is already known
  (lines 178, 156).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import (
    COSDictionary,
    UnmodifiableCOSDictionary,
    _array_get_indirect_object_keys,
    _array_reset_object_keys,
    _get_dictionary_string,
)
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_object_key import COSObjectKey

# ---------- get_object_from_path ------------------------------------------


def test_get_object_from_path_returns_none_when_segment_hits_scalar() -> None:
    """When path traversal lands on a non-collection (here a COSInteger),
    the next segment cannot be followed and ``None`` is returned (line 935).
    """
    d = COSDictionary()
    d.set_int(COSName.get_pdf_name("Count"), 7)
    # /Count resolves to a COSInteger; drilling further must yield None.
    assert d.get_object_from_path("Count/Anything") is None


# ---------- get_indirect_object_keys: revisit short-circuit ---------------


def test_get_indirect_object_keys_skips_already_seen() -> None:
    """When the indirect-key is pre-seeded into the collection, the
    walker must hit the ``continue`` in ``get_indirect_object_keys``
    (line 963) without dereferencing the COSObject."""
    ref = COSObject(7, 0)
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("First"), ref)
    seen: set[COSObjectKey] = {COSObjectKey(7, 0)}
    # Should not raise even though ref has no resolved object.
    d.get_indirect_object_keys(seen)
    assert COSObjectKey(7, 0) in seen


# ---------- reset_object_keys: revisit short-circuit ----------------------


def test_reset_object_keys_skips_already_seen() -> None:
    """Same revisit branch (line 1010) for ``reset_object_keys``."""
    ref = COSObject(9, 0)
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("First"), ref)
    seen: set[COSObjectKey] = {COSObjectKey(9, 0)}
    out = d.reset_object_keys(seen)
    assert out is seen
    assert COSObjectKey(9, 0) in seen


# ---------- reset_object_keys: array fallthrough --------------------------


def test_reset_object_keys_walks_into_nested_array() -> None:
    """A COSArray value drives the array branch (line 1016)."""
    inner_ref = COSObject(11, 0)
    arr = COSArray()
    arr.add(inner_ref)
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Kids"), arr)
    seen: set[COSObjectKey] = set()
    d.reset_object_keys(seen)
    assert COSObjectKey(11, 0) in seen


# ---------- UnmodifiableCOSDictionary write-guards ------------------------


def test_unmodifiable_clear_item_raises() -> None:
    """``UnmodifiableCOSDictionary.clear_item`` must raise (line 1099)."""
    src = COSDictionary()
    src.set_int(COSName.get_pdf_name("X"), 1)
    locked = UnmodifiableCOSDictionary(src)
    with pytest.raises(TypeError, match="unmodifiable"):
        locked.clear_item(COSName.get_pdf_name("X"))


# ---------- _get_dictionary_string formatter paths ------------------------


def test_get_dictionary_string_none_input() -> None:
    """Top-level ``None`` short-circuits to ``"null"`` (line 194)."""
    assert _get_dictionary_string(None, []) == "null"


def test_get_dictionary_string_cosobject_with_inner_dict() -> None:
    """A COSObject wrapper formats as ``COSObject{...}`` (lines 218-221).
    The non-null branch is what we need to exercise."""
    inner = COSDictionary()
    inner.set_int(COSName.get_pdf_name("Z"), 5)
    ref = COSObject(0, 0)
    ref._object = inner  # bypass loader; inject inner dict directly
    s = _get_dictionary_string(ref, [])
    assert s.startswith("COSObject{")
    assert "COSDictionary{" in s


def test_get_dictionary_string_top_level_cosarray() -> None:
    """Top-level COSArray drives the array branch (lines 211-217)."""
    arr = COSArray()
    arr.add(COSInteger.get(1))
    arr.add(COSInteger.get(2))
    s = _get_dictionary_string(arr, [])
    assert s.startswith("COSArray{")
    assert s.endswith("}")


def test_get_dictionary_string_cosstream_includes_hash() -> None:
    """A ``COSStream`` triggers the COSStream branch (lines 203-207)."""
    from pypdfbox.cos.cos_stream import COSStream

    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(b"hello")
    s = _get_dictionary_string(stream, [])
    assert "COSStream{" in s
    assert s.startswith("COSDictionary{")


# ---------- array helper revisit-short-circuit ----------------------------


def test_array_get_indirect_object_keys_skips_already_seen() -> None:
    """Pre-seeded key drives the ``continue`` in the array walker."""
    ref = COSObject(13, 0)
    arr = COSArray()
    arr.add(ref)
    seen: set[COSObjectKey] = {COSObjectKey(13, 0)}
    _array_get_indirect_object_keys(arr, seen)
    assert seen == {COSObjectKey(13, 0)}


def test_array_reset_object_keys_skips_already_seen() -> None:
    ref = COSObject(15, 0)
    arr = COSArray()
    arr.add(ref)
    seen: set[COSObjectKey] = {COSObjectKey(15, 0)}
    _array_reset_object_keys(arr, seen)
    assert seen == {COSObjectKey(15, 0)}


# ---------- nested array of arrays (drives _array_*_keys recursion) -------


def test_array_get_indirect_object_keys_recurses_into_dict_member() -> None:
    """An array containing a COSDictionary triggers the dict-recursion
    branch in ``_array_get_indirect_object_keys`` (line 156)."""
    inner_ref = COSObject(21, 0)
    inner_dict = COSDictionary()
    inner_dict.set_item(COSName.get_pdf_name("Ref"), inner_ref)
    arr = COSArray()
    arr.add(inner_dict)
    seen: set[COSObjectKey] = set()
    _array_get_indirect_object_keys(arr, seen)
    assert COSObjectKey(21, 0) in seen


def test_array_get_indirect_object_keys_recurses_nested_array() -> None:
    inner_ref = COSObject(17, 0)
    inner_arr = COSArray()
    inner_arr.add(inner_ref)
    outer = COSArray()
    outer.add(inner_arr)
    seen: set[COSObjectKey] = set()
    _array_get_indirect_object_keys(outer, seen)
    assert COSObjectKey(17, 0) in seen


def test_array_reset_object_keys_recurses_nested_array() -> None:
    inner_ref = COSObject(19, 0)
    inner_arr = COSArray()
    inner_arr.add(inner_ref)
    outer = COSArray()
    outer.add(inner_arr)
    seen: set[COSObjectKey] = set()
    _array_reset_object_keys(outer, seen)
    assert COSObjectKey(19, 0) in seen


# ---------- direct COSInteger fallthrough in path walker ------------------


def test_get_object_from_path_walks_array_then_dict() -> None:
    """Walk an array index then a dict key to make sure normal traversal
    still works (regression guard for the missing-line edits)."""
    inner = COSDictionary()
    inner.set_int(COSName.get_pdf_name("Y"), 42)
    arr = COSArray()
    arr.add(inner)
    outer = COSDictionary()
    outer.set_item(COSName.get_pdf_name("Kids"), arr)
    got = outer.get_object_from_path("Kids/[0]/Y")
    assert isinstance(got, COSInteger)
    assert got.int_value() == 42
