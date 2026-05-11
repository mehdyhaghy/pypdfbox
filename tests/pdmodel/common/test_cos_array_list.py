from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common import COSArrayList


class _Item:
    def __init__(self, key: str) -> None:
        self._dict = COSDictionary()
        self._dict.set_name("K", key)

    def get_cos_object(self) -> COSDictionary:
        return self._dict


def test_default_constructor_empty() -> None:
    cal: COSArrayList[_Item] = COSArrayList()
    assert cal.size() == 0
    assert cal.is_empty()


def test_add_wrappers_syncs_array() -> None:
    cal: COSArrayList[_Item] = COSArrayList()
    item = _Item("a")
    cal.add(item)
    assert cal.size() == 1
    assert cal.to_list().size() == 1
    assert cal.to_list().get_object(0) is item.get_cos_object()


def test_add_string_uses_cos_string() -> None:
    cal: COSArrayList[str] = COSArrayList()
    cal.add("hello")
    cos_value = cal.to_list().get_object(0)
    assert isinstance(cos_value, COSString)
    assert cos_value.get_string() == "hello"


def test_add_int_via_converter() -> None:
    arr = COSArrayList.converter_to_cos_array([1, 2.5, "x", None])
    assert arr is not None
    assert arr.size() == 4


def test_dictionary_lazy_promotion() -> None:
    parent = COSDictionary()
    key = COSName.get_pdf_name("Kids")
    cal: COSArrayList[_Item] = COSArrayList(
        dictionary=parent, dictionary_key=key
    )
    assert parent.get_dictionary_object(key) is None
    cal.add(_Item("a"))
    # Promotion happens on first add — backing array now in parent dict.
    assert parent.get_dictionary_object(key) is cal.to_list()


def test_filtered_list_blocks_mutation() -> None:
    backing = COSArray()
    backing.add(_Item("a").get_cos_object())
    backing.add(_Item("b").get_cos_object())
    actual: list[_Item] = [_Item("only-one")]
    cal: COSArrayList[_Item] = COSArrayList(actual, backing)
    with pytest.raises(NotImplementedError):
        cal.add(_Item("c"))
    with pytest.raises(NotImplementedError):
        cal.remove(0)


def test_set_replaces_element() -> None:
    cal: COSArrayList[_Item] = COSArrayList()
    cal.add(_Item("a"))
    new_item = _Item("b")
    cal.set(0, new_item)
    assert cal.get(0) is new_item
    assert cal.to_list().get_object(0) is new_item.get_cos_object()


def test_remove_by_index() -> None:
    cal: COSArrayList[_Item] = COSArrayList()
    cal.add(_Item("a"))
    cal.add(_Item("b"))
    cal.remove(0)
    assert cal.size() == 1


def test_clear() -> None:
    cal: COSArrayList[_Item] = COSArrayList()
    cal.add(_Item("a"))
    cal.clear()
    assert cal.size() == 0
    assert cal.to_list().size() == 0


def test_iteration() -> None:
    cal: COSArrayList[_Item] = COSArrayList()
    items = [_Item("a"), _Item("b"), _Item("c")]
    for item in items:
        cal.add(item)
    assert list(cal) == items


def test_index_of_and_last_index_of() -> None:
    cal: COSArrayList[str] = COSArrayList()
    cal.add("x")
    cal.add("y")
    cal.add("x")
    assert cal.index_of("x") == 0
    assert cal.last_index_of("x") == 2
    assert cal.index_of("nope") == -1


def test_to_array_returns_copy() -> None:
    cal: COSArrayList[str] = COSArrayList()
    cal.add("a")
    copy = cal.to_array()
    copy.append("b")
    assert cal.size() == 1
