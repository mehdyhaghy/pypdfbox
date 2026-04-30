from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSNull, COSObject


def test_empty_construction() -> None:
    a = COSArray()
    assert a.size() == 0
    assert a.is_empty()
    assert len(a) == 0


def test_add_and_size() -> None:
    a = COSArray()
    a.add(COSInteger(1))
    a.add(COSInteger(2))
    assert a.size() == 2
    assert a.get(0).value == 1  # type: ignore[attr-defined]


def test_construct_from_iterable() -> None:
    a = COSArray([COSInteger(1), COSInteger(2), COSInteger(3)])
    assert a.size() == 3


def test_add_at_inserts_at_index() -> None:
    a = COSArray([COSInteger(1), COSInteger(3)])
    a.add_at(1, COSInteger(2))
    assert [int(a.get(i).value) for i in range(3)] == [1, 2, 3]  # type: ignore[attr-defined]


def test_add_all_extends() -> None:
    a = COSArray([COSInteger(1)])
    a.add_all([COSInteger(2), COSInteger(3)])
    assert a.size() == 3


def test_set_replaces_in_place() -> None:
    a = COSArray([COSInteger(1)])
    a.set(0, COSInteger(99))
    assert a.get(0).value == 99  # type: ignore[attr-defined]


def test_remove_by_value() -> None:
    n = COSInteger(5)
    a = COSArray([COSInteger(1), n, COSInteger(2)])
    assert a.remove(n) is True
    assert a.size() == 2
    assert a.remove(COSName.get_pdf_name("Missing")) is False


def test_remove_at_returns_removed() -> None:
    a = COSArray([COSInteger(1), COSInteger(2), COSInteger(3)])
    removed = a.remove_at(1)
    assert removed.value == 2  # type: ignore[attr-defined]
    assert a.size() == 2


def test_clear() -> None:
    a = COSArray([COSInteger(1), COSInteger(2)])
    a.clear()
    assert a.is_empty()


def test_get_object_dereferences_cosobject() -> None:
    inner = COSInteger(42)
    indirect = COSObject(7, 0, resolved=inner)
    a = COSArray([COSInteger(0), indirect])
    assert a.get(1) is indirect
    assert a.get_object(1) is inner


def test_get_object_returns_direct_value_unchanged() -> None:
    direct = COSInteger(99)
    a = COSArray([direct])
    assert a.get_object(0) is direct


def test_get_object_returns_none_for_cos_null() -> None:
    direct = COSArray([COSNull.NULL])
    assert direct.get(0) is COSNull.NULL
    assert direct.get_object(0) is None

    indirect_null = COSObject(8, 0, resolved=COSNull.NULL)
    indirect = COSArray([indirect_null])
    assert indirect.get(0) is indirect_null
    assert indirect.get_object(0) is None


def test_index_of_returns_minus_one_for_missing() -> None:
    a = COSArray([COSInteger(1)])
    assert a.index_of(COSInteger(2)) == -1


def test_index_of_finds() -> None:
    n = COSInteger(7)
    a = COSArray([COSInteger(0), n])
    assert a.index_of(n) == 1


def test_index_of_object_finds_direct_entry() -> None:
    n = COSInteger(7)
    a = COSArray([COSInteger(0), n])
    assert a.index_of_object(n) == 1


def test_index_of_object_finds_resolved_indirect_entry() -> None:
    target = COSInteger(7)
    indirect = COSObject(11, 0, resolved=target)
    a = COSArray([COSInteger(0), indirect])

    assert a.index_of(target) == -1
    assert a.index_of_object(target) == 1


def test_index_of_object_returns_minus_one_for_missing() -> None:
    indirect = COSObject(11, 0, resolved=COSInteger(7))
    a = COSArray([COSInteger(0), indirect])

    assert a.index_of_object(COSInteger(9)) == -1


def test_float_accessors_round_trip_and_default() -> None:
    a = COSArray()
    a.set_float(2, 1.25)

    assert a.get_float(0, 9.0) == 9.0
    assert a.get_float(2) == 1.25
    assert a.get_float(3, 7.5) == 7.5


def test_get_float_accepts_integer_values() -> None:
    a = COSArray([COSInteger(3), COSName.get_pdf_name("NotNumber")])

    assert a.get_float(0) == 3.0
    assert a.get_float(1, 8.0) == 8.0


def test_to_list_returns_copy() -> None:
    a = COSArray([COSInteger(1)])
    out = a.to_list()
    out.append(COSInteger(99))
    assert a.size() == 1


def test_iteration_and_contains_and_indexing() -> None:
    items = [COSInteger(0), COSInteger(1), COSInteger(2)]
    a = COSArray(items)
    assert list(a) == items
    assert items[1] in a
    assert a[2] is items[2]


def test_get_out_of_range_raises_index_error() -> None:
    a = COSArray()
    with pytest.raises(IndexError):
        a.get(0)


def test_visitor_dispatch() -> None:
    from tests.cos.helpers import RecordingVisitor

    v = RecordingVisitor()
    a = COSArray()
    a.accept(v)
    assert v.calls == [("array", a)]
