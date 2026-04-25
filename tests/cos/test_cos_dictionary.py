from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
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


def test_contains_key() -> None:
    d = COSDictionary()
    d.set_item("Foo", COSInteger(0))
    assert d.contains_key("Foo")
    assert "Foo" in d
    assert COSName.get_pdf_name("Foo") in d
    assert "Bar" not in d


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


def test_get_string_falls_through_to_name() -> None:
    d = COSDictionary([("X", COSName.get_pdf_name("Page"))])
    assert d.get_string("X") == "Page"


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
