from __future__ import annotations

import datetime as dt

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSObjectKey,
    COSStream,
    COSString,
)


def test_empty_construction() -> None:
    d = COSDictionary()
    assert d.size() == 0
    assert d.is_empty()
    assert len(d) == 0


def test_set_and_get_with_cosname_key() -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    assert d.get_item(COSName.TYPE) is COSName.PAGES  # type: ignore[attr-defined]


def test_set_and_get_with_string_key() -> None:
    d = COSDictionary()
    d.set_item("Length", COSInteger(42))
    assert d.get_item("Length") == COSInteger(42)
    # String key normalizes to the same interned COSName as before.
    assert d.get_item(COSName.LENGTH) == COSInteger(42)  # type: ignore[attr-defined]


def test_remove_item_returns_value_or_none() -> None:
    d = COSDictionary()
    d.set_item("X", COSInteger(1))
    assert d.remove_item("X") == COSInteger(1)
    assert d.remove_item("X") is None


def test_set_item_with_none_removes_key() -> None:
    d = COSDictionary([("X", COSInteger(1))])
    d.set_item("X", None)
    assert d.get_item("X") is None
    assert "X" not in d


def test_contains_key() -> None:
    d = COSDictionary()
    d.set_item("Foo", COSInteger(0))
    assert d.contains_key("Foo")
    assert "Foo" in d
    assert COSName.get_pdf_name("Foo") in d
    assert "Bar" not in d


def test_contains_value_uses_cos_value_equality() -> None:
    d = COSDictionary([("A", COSInteger(7)), ("B", COSString("title"))])

    assert d.contains_value(COSInteger(7))
    assert d.contains_value(COSString("title"))
    assert not d.contains_value(COSInteger(8))


def test_get_key_for_value_returns_first_matching_key() -> None:
    d = COSDictionary(
        [
            ("First", COSInteger(1)),
            ("Second", COSString("shared")),
            ("Third", COSString("shared")),
        ]
    )

    assert d.get_key_for_value(COSString("shared")) == COSName.get_pdf_name("Second")
    assert d.get_key_for_value(COSInteger(1)) == COSName.get_pdf_name("First")
    assert d.get_key_for_value(COSInteger(99)) is None


def test_clear() -> None:
    d = COSDictionary([("A", COSInteger(1)), ("B", COSInteger(2))])
    d.clear()
    assert d.is_empty()


def test_construct_from_pairs_preserves_order() -> None:
    pairs = [("First", COSInteger(1)), ("Second", COSInteger(2)), ("Third", COSInteger(3))]
    d = COSDictionary(pairs)
    assert [k.name for k in d.key_set()] == ["First", "Second", "Third"]


def test_dereference_via_get_dictionary_object() -> None:
    inner = COSInteger(99)
    indirect = COSObject(5, 0, resolved=inner)
    d = COSDictionary()
    d.set_item("Ref", indirect)
    assert d.get_item("Ref") is indirect
    assert d.get_dictionary_object("Ref") is inner


def test_get_dictionary_object_returns_none_for_cos_null() -> None:
    direct = COSDictionary([("Null", COSNull.NULL)])
    assert direct.get_item("Null") is COSNull.NULL
    assert direct.get_dictionary_object("Null") is None

    indirect_null = COSObject(7, 0, resolved=COSNull.NULL)
    indirect = COSDictionary([("Null", indirect_null)])
    assert indirect.get_item("Null") is indirect_null
    assert indirect.get_dictionary_object("Null") is None


def test_get_dictionary_object_falls_back_to_second_key() -> None:
    value = COSName.get_pdf_name("DeviceRGB")
    d = COSDictionary([("ColorSpace", value)])

    assert d.get_dictionary_object("CS", "ColorSpace") is value
    assert (
        d.get_dictionary_object(COSName.get_pdf_name("CS"), COSName.get_pdf_name("ColorSpace"))
        is value
    )


def test_get_dictionary_object_first_key_wins_and_cos_null_falls_back() -> None:
    first = COSName.get_pdf_name("First")
    second = COSName.get_pdf_name("Second")

    d = COSDictionary([("CS", first), ("ColorSpace", second)])
    assert d.get_dictionary_object("CS", "ColorSpace") is first

    d.set_item("CS", COSNull.NULL)
    assert d.get_dictionary_object("CS", "ColorSpace") is second


def test_get_dictionary_object_preserves_non_name_default_value() -> None:
    default = COSInteger.get(17)
    d = COSDictionary()

    assert d.get_dictionary_object("Missing", default) is default


def test_get_item_falls_back_to_second_key_without_dereferencing() -> None:
    target = COSName.get_pdf_name("DeviceRGB")
    indirect = COSObject(17, 0, resolved=target)
    d = COSDictionary([("ColorSpace", indirect)])

    assert d.get_item("CS", "ColorSpace") is indirect
    assert d.get_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("ColorSpace")) is indirect


def test_get_item_first_key_wins_even_for_cos_null() -> None:
    second = COSName.get_pdf_name("DeviceRGB")
    d = COSDictionary([("CS", COSNull.NULL), ("ColorSpace", second)])

    assert d.get_item("CS", "ColorSpace") is COSNull.NULL


def test_get_item_preserves_non_name_default_value() -> None:
    default = COSInteger.get(17)
    d = COSDictionary()

    assert d.get_item("Missing", default) is default


def test_typed_setters() -> None:
    d = COSDictionary()
    d.set_name("Type", "Page")
    d.set_string("Title", "hello")
    d.set_int("Count", 5)
    d.set_float("Width", 2.5)
    d.set_boolean("Flag", True)
    assert d.get_name("Type") == "Page"
    assert d.get_string("Title") == "hello"
    assert d.get_int("Count") == 5
    assert d.get_float("Width") == 2.5
    assert d.get_boolean("Flag") is True


def test_set_name_with_none_removes() -> None:
    d = COSDictionary()
    d.set_name("Type", "Page")
    d.set_name("Type", None)
    assert d.get_item("Type") is None


def test_set_string_with_none_removes() -> None:
    d = COSDictionary([("X", COSString("hi"))])
    d.set_string("X", None)
    assert "X" not in d


def test_typed_getters_default_when_missing() -> None:
    d = COSDictionary()
    assert d.get_string("Missing", "fallback") == "fallback"
    assert d.get_int("Missing") == -1
    assert d.get_int("Missing", 7) == 7
    assert d.get_float("Missing") == -1.0
    assert d.get_boolean("Missing") is False


def test_get_int_coerces_float_to_int() -> None:
    d = COSDictionary([("X", COSFloat(2.9))])
    assert d.get_int("X") == 2


def test_set_long_stores_cos_integer() -> None:
    d = COSDictionary()
    d.set_long("Revision", 2**40)

    assert d.get_item("Revision") == COSInteger(2**40)
    assert d.get_long("Revision") == 2**40


def test_get_long_default_and_numeric_coercion() -> None:
    d = COSDictionary([("Float", COSFloat(2.9)), ("Name", COSName.get_pdf_name("N"))])

    assert d.get_long("Missing") == -1
    assert d.get_long("Missing", 7) == 7
    assert d.get_long("Float") == 2
    assert d.get_long("Name", 11) == 11


def test_get_string_falls_through_to_name() -> None:
    d = COSDictionary([("X", COSName.get_pdf_name("Page"))])
    assert d.get_string("X") == "Page"


def test_get_cos_dictionary_returns_resolved_dictionary_or_none() -> None:
    child = COSDictionary([("Count", COSInteger(2))])
    direct = COSDictionary([("Child", child), ("Wrong", COSInteger(1))])

    assert direct.get_cos_dictionary("Child") is child
    assert direct.get_cos_dictionary("Wrong") is None
    assert direct.get_cos_dictionary("Missing") is None

    indirect = COSDictionary([("Child", COSObject(9, 0, resolved=child))])
    assert indirect.get_cos_dictionary("Child") is child


def test_get_cos_array_returns_resolved_array_or_none() -> None:
    array = COSArray([COSInteger(1), COSInteger(2)])
    direct = COSDictionary([("Kids", array), ("Wrong", COSName.get_pdf_name("Page"))])

    assert direct.get_cos_array("Kids") is array
    assert direct.get_cos_array("Wrong") is None
    assert direct.get_cos_array("Missing") is None

    indirect = COSDictionary([("Kids", COSObject(10, 0, resolved=array))])
    assert indirect.get_cos_array("Kids") is array


def test_invalid_key_type_raises() -> None:
    d = COSDictionary()
    with pytest.raises(TypeError):
        d.set_item(123, COSInteger(1))  # type: ignore[arg-type]


def test_subscript_protocols() -> None:
    d = COSDictionary()
    d["A"] = COSInteger(1)
    assert d["A"] == COSInteger(1)
    del d["A"]
    with pytest.raises(KeyError):
        _ = d["A"]


def test_add_all_merges_overwriting() -> None:
    a = COSDictionary([("X", COSInteger(1)), ("Y", COSInteger(2))])
    b = COSDictionary([("Y", COSInteger(20)), ("Z", COSInteger(30))])
    a.add_all(b)
    assert a.get_int("X") == 1
    assert a.get_int("Y") == 20
    assert a.get_int("Z") == 30


def test_iteration_yields_keys() -> None:
    d = COSDictionary([("A", COSInteger(1)), ("B", COSInteger(2))])
    assert [k.name for k in d] == ["A", "B"]


def test_entry_set_and_values() -> None:
    d = COSDictionary([("A", COSInteger(1)), ("B", COSBoolean.TRUE)])
    entries = list(d.entry_set())
    assert entries[0][0].name == "A"
    assert entries[1][1] is COSBoolean.TRUE
    assert list(d.values()) == [COSInteger(1), COSBoolean.TRUE]


def test_visitor_dispatch() -> None:
    from tests.cos.helpers import RecordingVisitor

    v = RecordingVisitor()
    d = COSDictionary()
    d.accept(v)
    assert v.calls == [("dictionary", d)]


def test_for_each_visits_entries_in_insertion_order() -> None:
    d = COSDictionary([("A", COSInteger(1)), ("B", COSInteger(2)), ("C", COSInteger(3))])
    seen: list[tuple[str, int]] = []
    d.for_each(lambda k, v: seen.append((k.name, v.value)))  # type: ignore[attr-defined]
    assert seen == [("A", 1), ("B", 2), ("C", 3)]


def test_get_values_returns_live_view() -> None:
    d = COSDictionary([("A", COSInteger(1)), ("B", COSInteger(2))])
    values = d.get_values()
    assert list(values) == [COSInteger(1), COSInteger(2)]
    d.set_item("C", COSInteger(3))
    assert list(values) == [COSInteger(1), COSInteger(2), COSInteger(3)]


def test_get_cos_name_returns_resolved_name_or_default() -> None:
    page_name = COSName.get_pdf_name("Page")
    d = COSDictionary([("Type", page_name), ("Wrong", COSInteger(1))])
    assert d.get_cos_name("Type") is page_name
    assert d.get_cos_name("Wrong") is None
    assert d.get_cos_name("Missing") is None
    fallback = COSName.get_pdf_name("XObject")
    assert d.get_cos_name("Missing", fallback) is fallback


def test_get_cos_object_no_arg_returns_self() -> None:
    d = COSDictionary([("A", COSInteger(1))])
    assert d.get_cos_object() is d


def test_get_cos_object_key_returns_indirect_or_none() -> None:
    inner = COSInteger(5)
    indirect = COSObject(11, 0, resolved=inner)
    d = COSDictionary([("Ref", indirect), ("Direct", inner)])
    assert d.get_cos_object("Ref") is indirect
    assert d.get_cos_object("Direct") is None
    assert d.get_cos_object("Missing") is None


def test_get_cos_stream_returns_resolved_stream_or_none() -> None:
    stream = COSStream()
    direct = COSDictionary([("S", stream), ("Wrong", COSInteger(1))])
    assert direct.get_cos_stream("S") is stream
    assert direct.get_cos_stream("Wrong") is None

    indirect = COSDictionary([("S", COSObject(13, 0, resolved=stream))])
    assert indirect.get_cos_stream("S") is stream
    stream.close()


def test_get_date_parses_pdf_date_string() -> None:
    d = COSDictionary([("CreationDate", COSString("D:20260509120000Z"))])
    parsed = d.get_date("CreationDate")
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 5
    assert parsed.day == 9
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == dt.timedelta(0)


def test_get_date_returns_default_for_missing_or_unparseable() -> None:
    fallback = dt.datetime(2000, 1, 1, tzinfo=dt.UTC)
    d = COSDictionary([("Bad", COSString("not a date"))])
    assert d.get_date("Missing") is None
    assert d.get_date("Missing", fallback) is fallback
    assert d.get_date("Bad", fallback) is fallback


def test_embedded_string_int_date_round_trip() -> None:
    d = COSDictionary()
    d.set_embedded_string("Sub", "Title", "hello")
    d.set_embedded_int("Sub", "Count", 42)
    d.set_embedded_date("Sub", "When", dt.datetime(2026, 5, 9, tzinfo=dt.UTC))

    assert d.get_embedded_string("Sub", "Title") == "hello"
    assert d.get_embedded_int("Sub", "Count") == 42
    parsed = d.get_embedded_date("Sub", "When")
    assert parsed is not None
    assert parsed.year == 2026

    # Defaults bubble through when the embedded dict is absent.
    assert d.get_embedded_string("Other", "Title", "fallback") == "fallback"
    assert d.get_embedded_int("Other", "Count", 99) == 99
    assert d.get_embedded_date("Other", "When") is None


def test_get_object_from_path_walks_dicts_and_arrays() -> None:
    rect = COSArray([COSInteger(0), COSInteger(0), COSInteger(100), COSInteger(200)])
    annot = COSDictionary([("Rect", rect)])
    annots = COSArray([annot])
    page = COSDictionary([("Annots", annots)])

    assert page.get_object_from_path("Annots") is annots
    assert page.get_object_from_path("Annots/[0]") is annot
    assert page.get_object_from_path("Annots/[0]/Rect") is rect
    # Path beyond a leaf returns None.
    leaf = page.get_object_from_path("Annots/[0]/Rect/[3]")
    assert leaf == COSInteger(200)


def test_get_indirect_object_keys_collects_references() -> None:
    leaf = COSInteger(7)
    leaf_ref = COSObject(20, 0, resolved=leaf)
    nested = COSDictionary([("Leaf", leaf_ref)])
    nested_ref = COSObject(21, 0, resolved=nested)
    arr = COSArray([COSObject(22, 0, resolved=COSInteger(8))])
    root = COSDictionary([("Inner", nested_ref), ("Arr", arr)])

    keys: set[COSObjectKey] = set()
    root.get_indirect_object_keys(keys)
    assert COSObjectKey(20, 0) in keys
    assert COSObjectKey(22, 0) in keys


def test_get_indirect_object_keys_skips_parent_recursion() -> None:
    parent = COSDictionary()
    child = COSDictionary([("Parent", COSObject(30, 0, resolved=parent))])
    parent.set_item("Kids", child)
    keys: set[COSObjectKey] = set()
    # Should not blow the recursion stack — /Parent and /P entries skip
    # descent into the referenced dictionary (matches upstream behavior:
    # the parent dict is neither recursed into nor recorded as a leaf
    # since its branch already ended in the dictionary case).
    child.get_indirect_object_keys(keys)


def test_reset_imported_object_keys_walks_without_error() -> None:
    leaf = COSInteger(1)
    inner = COSDictionary([("X", COSObject(40, 0, resolved=leaf))])
    root = COSDictionary([("Inner", COSObject(41, 0, resolved=inner))])
    # Should not raise; pypdfbox cannot mutate the COSObject keys.
    root.reset_imported_object_keys()


def test_to_string_emits_structural_form() -> None:
    d = COSDictionary([("Type", COSName.get_pdf_name("Page")), ("Count", COSInteger(2))])
    rendered = d.to_string()
    assert rendered.startswith("COSDictionary{")
    assert "Type" in rendered
    assert "Count" in rendered
    assert str(d) == rendered


def test_to_string_breaks_self_recursion() -> None:
    d = COSDictionary()
    d.set_item("Self", d)
    out = d.to_string()
    assert "hash:" in out
