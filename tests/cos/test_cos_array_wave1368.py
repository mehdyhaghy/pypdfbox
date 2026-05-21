"""Wave 1368 — COSArray typed retrieval + indirect-reference edges.

Coverage round-out for paths not yet exercised:

* ``index_of_object`` matching direct values vs values reached through a
  ``COSObject`` indirect reference.
* ``remove_object`` returning ``False`` when no candidate matches.
* ``to_float_array``, ``to_cos_name_string_list``, ``to_cos_string_string_list``,
  ``to_cos_number_integer_list``, and ``to_cos_number_float_list`` with mixed
  entries (including indirect references) — every "non-target" slot must
  fall through to the documented sentinel (``0.0`` or ``None``).
* ``grow_to_size`` no-op when the array is already at the target length.
* Parallel modification by ``remove_object`` while iterating: the iterator
  must observe the pre-modification snapshot via ``to_list()``.
* ``get_object`` resolving a ``COSObject`` to ``None`` when the target is
  ``COSNull.NULL`` (parity with PDFBox where free entries surface as
  ``null``).
* ``__contains__`` / ``contains`` matching the underlying list ``in`` op.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSString,
)


def test_index_of_object_finds_direct_value() -> None:
    name = COSName.get_pdf_name("Foo")
    arr = COSArray([COSInteger.get(1), name, COSInteger.get(2)])
    assert arr.index_of_object(name) == 1


def test_index_of_object_dereferences_cosobject_holder() -> None:
    target = COSName.get_pdf_name("Inner")
    indirect = COSObject(5, 0, resolved=target)
    arr = COSArray([COSInteger.get(1), indirect])
    # The raw entry is a COSObject; index_of_object resolves and matches.
    assert arr.index_of_object(target) == 1


def test_index_of_object_returns_minus_one_for_missing() -> None:
    arr = COSArray([COSInteger.get(1), COSInteger.get(2)])
    sentinel = COSName.get_pdf_name("Nope")
    assert arr.index_of_object(sentinel) == -1


def test_remove_object_returns_false_when_absent() -> None:
    arr = COSArray([COSInteger.get(1)])
    sentinel = COSName.get_pdf_name("Nope")
    assert arr.remove_object(sentinel) is False
    assert arr.size() == 1


def test_remove_object_through_indirect_holder() -> None:
    target = COSName.get_pdf_name("Target")
    indirect = COSObject(3, 0, resolved=target)
    arr = COSArray([COSInteger.get(1), indirect])
    assert arr.remove_object(target) is True
    assert arr.size() == 1


def test_to_float_array_substitutes_zero_for_non_numeric() -> None:
    arr = COSArray(
        [
            COSInteger.get(1),
            COSFloat(2.5),
            COSName.get_pdf_name("Hi"),
            COSString("3"),
        ]
    )
    assert arr.to_float_array() == [1.0, 2.5, 0.0, 0.0]


def test_to_float_array_resolves_indirect_numeric() -> None:
    ref = COSObject(8, 0, resolved=COSFloat(7.5))
    arr = COSArray([ref, COSInteger.get(2)])
    assert arr.to_float_array() == [7.5, 2.0]


def test_to_cos_name_string_list_substitutes_none_for_non_names() -> None:
    arr = COSArray(
        [
            COSName.get_pdf_name("First"),
            COSInteger.get(5),
            COSString("middle"),
            COSName.get_pdf_name("Second"),
        ]
    )
    assert arr.to_cos_name_string_list() == ["First", None, None, "Second"]


def test_to_cos_string_string_list_substitutes_none_for_non_strings() -> None:
    arr = COSArray(
        [
            COSString("a"),
            COSInteger.get(7),
            COSName.get_pdf_name("Note"),
            COSString("b"),
        ]
    )
    assert arr.to_cos_string_string_list() == ["a", None, None, "b"]


def test_to_cos_number_integer_list_handles_mixed_entries() -> None:
    arr = COSArray(
        [
            COSInteger.get(1),
            COSFloat(2.7),
            COSString("nope"),
            COSBoolean.TRUE,
        ]
    )
    assert arr.to_cos_number_integer_list() == [1, 2, None, None]


def test_to_cos_number_float_list_handles_mixed_entries() -> None:
    arr = COSArray(
        [
            COSInteger.get(1),
            COSFloat(2.5),
            COSName.get_pdf_name("Note"),
        ]
    )
    # 2.5 is exactly representable so we avoid float-32 widening drift.
    assert arr.to_cos_number_float_list() == [1.0, 2.5, None]


def test_to_cos_number_float_list_resolves_indirect_entry() -> None:
    inner = COSInteger.get(11)
    ref = COSObject(9, 0, resolved=inner)
    arr = COSArray([ref])
    assert arr.to_cos_number_float_list() == [11.0]


def test_grow_to_size_no_change_when_already_at_target() -> None:
    arr = COSArray([COSInteger.get(1), COSInteger.get(2)])
    arr.grow_to_size(2)
    assert arr.size() == 2
    arr.grow_to_size(0)  # smaller-than-current is a no-op too
    assert arr.size() == 2


def test_grow_to_size_pads_with_fill_value() -> None:
    arr = COSArray()
    fill = COSNull.NULL
    arr.grow_to_size(3, fill)
    assert arr.size() == 3
    assert all(entry is fill for entry in arr.to_list())


def test_iter_then_remove_object_using_snapshot() -> None:
    """Mutating COSArray while iterating ``to_list()`` is safe — the list
    is a defensive copy, so removals during the loop do not affect it."""
    arr = COSArray.of_cos_integers([1, 2, 3, 4, 5])
    snapshot = arr.to_list()
    for entry in snapshot:
        if isinstance(entry, COSInteger) and entry.value % 2 == 0:
            arr.remove(entry)
    assert [int(e.value) for e in arr if isinstance(e, COSInteger)] == [1, 3, 5]


def test_get_object_resolves_indirect_null_to_none() -> None:
    ref = COSObject(2, 0, resolved=COSNull.NULL)
    arr = COSArray([ref])
    assert arr.get_object(0) is None


def test_get_object_returns_direct_value_unchanged() -> None:
    direct = COSName.get_pdf_name("Direct")
    arr = COSArray([direct])
    assert arr.get_object(0) is direct


def test_contains_uses_python_in_operator() -> None:
    target = COSName.get_pdf_name("Target")
    arr = COSArray([COSInteger.get(1), target])
    assert (target in arr) is True
    assert arr.contains(target) is True
    assert arr.contains(COSName.get_pdf_name("Missing")) is False


def test_remove_all_returns_false_when_nothing_removed() -> None:
    arr = COSArray.of_cos_integers([1, 2, 3])
    assert arr.remove_all([COSName.get_pdf_name("Nope")]) is False
    assert arr.size() == 3


def test_retain_all_keeps_only_listed_entries() -> None:
    one = COSInteger.get(1)
    two = COSInteger.get(2)
    three = COSInteger.get(3)
    arr = COSArray([one, two, three])
    assert arr.retain_all([one, three]) is True
    assert arr.to_list() == [one, three]


def test_retain_all_returns_false_when_no_change() -> None:
    one = COSInteger.get(1)
    two = COSInteger.get(2)
    arr = COSArray([one, two])
    assert arr.retain_all([one, two, COSInteger.get(99)]) is False


def test_typed_setters_grow_array_as_needed() -> None:
    arr = COSArray()
    arr.set_int(3, 42)
    assert arr.size() == 4
    # First three slots are the placeholder, last slot is the integer.
    assert arr.get_int(0) == -1  # default for absent
    assert arr.get_int(3) == 42


@pytest.mark.parametrize(
    "method,index,value",
    [
        ("set_name", 0, "MyName"),
        ("set_int", 0, 99),
        ("set_float", 0, 1.5),
        ("set_boolean", 0, True),
        ("set_string", 0, "hello"),
    ],
    ids=["name", "int", "float", "boolean", "string"],
)
def test_typed_setters_replace_existing_entry(method: str, index: int, value: object) -> None:
    arr = COSArray([COSNull.NULL])
    getattr(arr, method)(index, value)
    assert arr.size() == 1


def test_typed_setters_reject_negative_index() -> None:
    arr = COSArray()
    with pytest.raises(IndexError):
        arr.set_int(-1, 7)


def test_get_int_returns_default_for_past_end_index() -> None:
    arr = COSArray([COSInteger.get(1)])
    assert arr.get_int(10, default=99) == 99
    assert arr.get_float(10, default=9.9) == 9.9
    assert arr.get_boolean(10, default=True) is True
    assert arr.get_string(10, default="x") == "x"
    assert arr.get_name(10, default="x") == "x"


def test_factory_constructors_intern_names_and_singletons() -> None:
    by_factory = COSArray.of_cos_names(["A", "B"])
    a = COSName.get_pdf_name("A")
    b = COSName.get_pdf_name("B")
    assert by_factory.get(0) is a
    assert by_factory.get(1) is b


def test_factory_int_array_uses_singleton_pool() -> None:
    arr = COSArray.of_cos_integers([0, 1, 2])
    # COSInteger.get returns interned instances for small values.
    assert arr.get(0) is COSInteger.get(0)
    assert arr.get(2) is COSInteger.get(2)


def test_set_float_array_replaces_contents() -> None:
    arr = COSArray([COSInteger.get(1)])
    arr.set_float_array([1.1, 2.2, 3.3])
    assert arr.size() == 3
    assert arr.get_float(0) == pytest.approx(1.1)
    assert arr.get_float(2) == pytest.approx(3.3)


def test_to_string_round_trips_simple_values() -> None:
    arr = COSArray([COSInteger.get(1), COSName.get_pdf_name("X")])
    # Just exercise the formatter; exact braces match upstream parity.
    rendered = arr.to_string()
    assert rendered.startswith("COSArray{")
    assert rendered.endswith("}")


def test_iterator_method_returns_iter_over_items() -> None:
    one = COSInteger.get(1)
    two = COSInteger.get(2)
    arr = COSArray([one, two])
    assert list(arr.iterator()) == [one, two]
