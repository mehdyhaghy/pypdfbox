"""Coverage-boost tests for ``pypdfbox.pdmodel.common.cos_array_list``.

Targets branches missed by ``test_cos_array_list.py`` — alternate
constructor shapes, filtered-mode guards, indexed mutation, removal
helpers, ``COSArrayList.converter_to_cos_array``, and the dunder
protocol surface.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.common.cos_array_list import COSArrayList, _to_cos

# ---------------------------------------------------------------------------
# constructor shapes
# ---------------------------------------------------------------------------


def test_constructor_actual_and_cos_array_matched_lengths() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(1))
    arr.add(COSInteger.get(2))
    cal: COSArrayList[int] = COSArrayList([1, 2], arr)
    assert cal.size() == 2
    assert not cal._is_filtered


def test_constructor_actual_and_cos_array_mismatch_enters_filtered_mode() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(1))
    arr.add(COSInteger.get(2))
    arr.add(COSInteger.get(3))
    cal: COSArrayList[int] = COSArrayList([1, 2], arr)
    assert cal._is_filtered

    with pytest.raises(NotImplementedError):
        cal.add(99)
    with pytest.raises(NotImplementedError):
        cal.add_all([99])
    with pytest.raises(NotImplementedError):
        cal.set(0, 99)
    with pytest.raises(NotImplementedError):
        cal.remove(0)


def test_constructor_dictionary_lazy_attaches_on_first_add() -> None:
    parent = COSDictionary()
    key = COSName.get_pdf_name("Kids")
    cal: COSArrayList[int] = COSArrayList(
        dictionary=parent, dictionary_key=key
    )
    assert parent.get_item(key) is None
    cal.add(1)
    assert parent.get_item(key) is cal.to_list()


def test_constructor_single_item_seed_promotes_to_array() -> None:
    parent = COSDictionary()
    key = COSName.get_pdf_name("F")
    seed_str = COSString("hello")
    cal: COSArrayList[str] = COSArrayList(
        actual_list="hello",
        cos_array=seed_str,
        dictionary=parent,
        dictionary_key=key,
    )
    assert cal.size() == 1
    assert cal.get(0) == "hello"
    cal.add("world")
    assert parent.get_item(key) is cal.to_list()
    assert cal.size() == 2


def test_constructor_unsupported_combination_raises() -> None:
    with pytest.raises(TypeError):
        COSArrayList(actual_list=[1, 2])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# read-only helpers
# ---------------------------------------------------------------------------


def test_contains_and_contains_all_and_iterators() -> None:
    cal: COSArrayList[int] = COSArrayList()
    cal.add_all([1, 2, 3])
    assert cal.contains(2)
    assert cal.contains_all([1, 3])
    assert not cal.contains_all([1, 99])
    assert list(cal.iterator()) == [1, 2, 3]
    assert list(cal.list_iterator(1)) == [2, 3]
    assert cal.to_array() == [1, 2, 3]
    assert cal.sub_list(0, 2) == [1, 2]


def test_index_of_and_last_index_of_present_and_absent() -> None:
    cal: COSArrayList[int] = COSArrayList()
    cal.add_all([1, 2, 1, 2])
    assert cal.index_of(2) == 1
    assert cal.index_of(99) == -1
    assert cal.last_index_of(1) == 2
    assert cal.last_index_of(99) == -1


# ---------------------------------------------------------------------------
# mutation
# ---------------------------------------------------------------------------


def test_add_at_index_keeps_array_in_sync() -> None:
    cal: COSArrayList[int] = COSArrayList()
    cal.add(1)
    cal.add(3)
    cal.add(2, index=1)
    assert cal.to_array() == [1, 2, 3]
    assert cal.to_list().size() == 3


def test_add_all_at_index_keeps_array_in_sync() -> None:
    cal: COSArrayList[int] = COSArrayList()
    cal.add_all([1, 4])
    cal.add_all([2, 3], index=1)
    assert cal.to_array() == [1, 2, 3, 4]
    assert cal.to_list().size() == 4


def test_add_all_empty_returns_false_without_promotion() -> None:
    parent = COSDictionary()
    key = COSName.get_pdf_name("Kids")
    cal: COSArrayList[int] = COSArrayList(
        dictionary=parent, dictionary_key=key
    )
    assert cal.add_all([]) is False
    # parent dict not yet promoted because nothing was added
    assert parent.get_item(key) is None


def test_add_all_with_lazy_dict_promotes_on_first_batch() -> None:
    parent = COSDictionary()
    key = COSName.get_pdf_name("Kids")
    cal: COSArrayList[int] = COSArrayList(
        dictionary=parent, dictionary_key=key
    )
    assert cal.add_all([1, 2, 3]) is True
    assert parent.get_item(key) is cal.to_list()


def test_is_empty_reflects_state() -> None:
    cal: COSArrayList[int] = COSArrayList()
    assert cal.is_empty()
    cal.add(1)
    assert not cal.is_empty()


def test_set_returns_previous_and_updates_array() -> None:
    cal: COSArrayList[int] = COSArrayList()
    cal.add_all([10, 20, 30])
    prev = cal.set(1, 99)
    assert prev == 20
    assert cal.to_array() == [10, 99, 30]


def test_set_first_index_on_lazy_dict_updates_parent_entry() -> None:
    parent = COSDictionary()
    key = COSName.get_pdf_name("F")
    seed = COSString("a")
    cal: COSArrayList[str] = COSArrayList(
        actual_list="a",
        cos_array=seed,
        dictionary=parent,
        dictionary_key=key,
    )
    cal.set(0, "b")
    # parent entry was overwritten with the cos string for "b"
    new_val = parent.get_item(key)
    assert isinstance(new_val, COSString)
    assert new_val.get_string() == "b"


def test_remove_by_index_returns_popped_value() -> None:
    cal: COSArrayList[int] = COSArrayList()
    cal.add_all([1, 2, 3])
    removed = cal.remove(1)
    # int args are always treated as positional indices (mirror upstream),
    # so this removes the entry at index 1.
    assert removed == 2
    assert cal.to_array() == [1, 3]


def test_remove_by_value_returns_true_or_false() -> None:
    # use string keys so the int / object overload disambiguates cleanly.
    cal: COSArrayList[str] = COSArrayList()
    cal.add_all(["a", "b", "c"])
    assert cal.remove("b") is True
    assert cal.to_array() == ["a", "c"]
    assert cal.remove("missing") is False


def test_remove_all_removes_matching_entries() -> None:
    cal: COSArrayList[str] = COSArrayList()
    cal.add_all(["a", "b", "c", "b"])
    changed = cal.remove_all(["b"])
    assert changed
    assert cal.remove_all(["zz"]) is False


def test_retain_all_keeps_only_listed_entries() -> None:
    cal: COSArrayList[int] = COSArrayList()
    cal.add_all([1, 2, 3, 4])
    changed = cal.retain_all([2, 4])
    assert changed
    assert cal.to_array() == [2, 4]
    # second call with same retain set is a no-op.
    assert cal.retain_all([2, 4]) is False


def test_clear_before_promotion_removes_pending_parent_entry() -> None:
    parent = COSDictionary()
    key = COSName.get_pdf_name("Kids")
    # parent_dict still set (no add yet); clear() should remove the entry.
    parent.set_item(key, COSString("placeholder"))
    cal: COSArrayList[int] = COSArrayList(
        dictionary=parent, dictionary_key=key
    )
    cal.clear()
    assert parent.get_item(key) is None
    assert cal.size() == 0


def test_clear_after_promotion_empties_backing_array() -> None:
    parent = COSDictionary()
    key = COSName.get_pdf_name("Kids")
    cal: COSArrayList[int] = COSArrayList(
        dictionary=parent, dictionary_key=key
    )
    cal.add(1)
    backing = cal.to_list()
    cal.clear()
    assert cal.size() == 0
    # parent still references the (now empty) backing array.
    assert parent.get_item(key) is backing
    assert backing.size() == 0


# ---------------------------------------------------------------------------
# converter + to_cos_object_list
# ---------------------------------------------------------------------------


def test_converter_to_cos_array_handles_none_and_existing_list() -> None:
    assert COSArrayList.converter_to_cos_array(None) is None
    cal: COSArrayList[int] = COSArrayList()
    cal.add(1)
    assert COSArrayList.converter_to_cos_array(cal) is cal.to_list()


def test_converter_to_cos_array_builds_fresh_array() -> None:
    arr = COSArrayList.converter_to_cos_array([1, "x"])
    assert arr is not None
    assert arr.size() == 2


def test_to_cos_object_list_round_trips() -> None:
    cal: COSArrayList[int] = COSArrayList()
    result = cal.to_cos_object_list([1, "y", 2.5])
    assert len(result) == 3


# ---------------------------------------------------------------------------
# dunder + parity surface
# ---------------------------------------------------------------------------


def test_dunder_protocols_and_equality() -> None:
    cal: COSArrayList[int] = COSArrayList()
    cal.add_all([1, 2, 3])
    assert len(cal) == 3
    assert list(iter(cal)) == [1, 2, 3]
    assert 2 in cal
    assert cal[0] == 1
    cal[0] = 99
    assert cal[0] == 99
    del cal[0]
    assert cal.to_array() == [2, 3]
    assert cal == [2, 3]
    other: COSArrayList[int] = COSArrayList()
    other.add_all([2, 3])
    assert cal == other
    assert cal.__eq__(42) is NotImplemented
    assert hash(cal) == id(cal)
    assert "COSArrayList" in repr(cal)


def test_equals_and_hash_code_and_to_string() -> None:
    cal: COSArrayList[int] = COSArrayList()
    cal.add_all([1, 2])
    other: COSArrayList[int] = COSArrayList()
    other.add_all([1, 2])
    assert cal.equals(other)
    assert not cal.equals(object())
    assert isinstance(cal.hash_code(), int)
    assert "COSArrayList" in cal.to_string()


# ---------------------------------------------------------------------------
# _to_cos helper coverage
# ---------------------------------------------------------------------------


def test_to_cos_dispatch_for_all_python_types() -> None:
    assert isinstance(_to_cos("abc"), COSString)
    assert isinstance(_to_cos(7), COSInteger)
    assert isinstance(_to_cos(1.5), COSFloat)
    assert _to_cos(None) is COSNull.NULL
    # bool branch must precede int (booleans are ints in python)
    assert _to_cos(True) is COSBoolean.TRUE
    name = COSName.get_pdf_name("X")
    assert _to_cos(name) is name

    class _Objectable:
        def __init__(self) -> None:
            self._dict = COSDictionary()

        def get_cos_object(self) -> COSDictionary:
            return self._dict

    o = _Objectable()
    assert _to_cos(o) is o.get_cos_object()


def test_to_cos_unconvertible_raises() -> None:
    with pytest.raises(TypeError):
        _to_cos(object())
