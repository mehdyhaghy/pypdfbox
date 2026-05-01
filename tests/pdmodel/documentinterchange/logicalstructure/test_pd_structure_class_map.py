from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDAttributeObject,
    PDStructureClassMap,
    PDStructureTreeRoot,
)

_O = COSName.get_pdf_name("O")


def _make_attr(owner: str = "Layout") -> PDAttributeObject:
    d = COSDictionary()
    d.set_name(_O, owner)
    return PDAttributeObject(d)


def test_empty_class_map_returns_empty_dict() -> None:
    cm = PDStructureClassMap()
    assert cm.get_class_definitions() == {}
    assert cm.is_empty()


def test_add_single_class_round_trip() -> None:
    cm = PDStructureClassMap()
    attr = _make_attr("Layout")
    cm.add_class("MyClass", attr)

    defs = cm.get_class_definitions()
    assert list(defs.keys()) == ["MyClass"]
    assert len(defs["MyClass"]) == 1
    assert defs["MyClass"][0].get_cos_object() is attr.get_cos_object()


def test_add_class_promotes_to_array_when_second_added() -> None:
    cm = PDStructureClassMap()
    a1 = _make_attr("Layout")
    a2 = _make_attr("List")
    cm.add_class("MyClass", a1)
    cm.add_class("MyClass", a2)

    raw = cm.get_cos_object().get_dictionary_object("MyClass")
    assert isinstance(raw, COSArray)
    assert raw.size() == 2

    defs = cm.get_class_definitions()
    assert len(defs["MyClass"]) == 2
    assert defs["MyClass"][0].get_owner() == "Layout"
    assert defs["MyClass"][1].get_owner() == "List"


def test_add_class_with_iterable_creates_array() -> None:
    cm = PDStructureClassMap()
    a1 = _make_attr("Layout")
    a2 = _make_attr("List")
    cm.add_class("MyClass", [a1, a2])

    raw = cm.get_cos_object().get_dictionary_object("MyClass")
    assert isinstance(raw, COSArray)
    assert raw.size() == 2


def test_add_class_with_single_iterable_keeps_single_dict() -> None:
    cm = PDStructureClassMap()
    a1 = _make_attr("Layout")
    cm.add_class("MyClass", [a1])

    raw = cm.get_cos_object().get_dictionary_object("MyClass")
    # single-element list → stored as single COSDictionary
    assert isinstance(raw, COSDictionary)


def test_get_class_returns_empty_list_when_absent() -> None:
    cm = PDStructureClassMap()
    assert cm.get_class("missing") == []


def test_get_class_returns_single_entry_as_list() -> None:
    cm = PDStructureClassMap()
    attr = _make_attr("Layout")
    cm.add_class("OneClass", attr)
    result = cm.get_class("OneClass")
    assert len(result) == 1
    assert result[0].get_owner() == "Layout"


def test_get_class_returns_list_for_array_entry() -> None:
    cm = PDStructureClassMap()
    cm.add_class("ManyClass", [_make_attr("Layout"), _make_attr("Table")])
    result = cm.get_class("ManyClass")
    assert len(result) == 2


def test_remove_class_clears_entry() -> None:
    cm = PDStructureClassMap()
    cm.add_class("Tmp", _make_attr())
    assert "Tmp" in cm.get_class_definitions()
    cm.remove_class("Tmp")
    assert cm.get_class_definitions() == {}


def test_remove_class_missing_is_noop() -> None:
    cm = PDStructureClassMap()
    cm.remove_class("Nope")  # must not raise


def test_add_class_rejects_non_attribute_in_iterable() -> None:
    cm = PDStructureClassMap()
    with pytest.raises(TypeError):
        cm.add_class("Bad", [object()])  # type: ignore[list-item]


def test_add_class_rejects_none() -> None:
    cm = PDStructureClassMap()
    with pytest.raises(TypeError):
        cm.add_class("Bad", None)  # type: ignore[arg-type]


# ---------- set_class (replace semantics) ----------


def test_set_class_replaces_existing_single_entry() -> None:
    cm = PDStructureClassMap()
    cm.add_class("MyClass", _make_attr("Layout"))
    cm.set_class("MyClass", _make_attr("List"))

    classes = cm.get_class("MyClass")
    assert len(classes) == 1
    assert classes[0].get_owner() == "List"


def test_set_class_replaces_existing_array_entry() -> None:
    cm = PDStructureClassMap()
    cm.add_class("MyClass", [_make_attr("Layout"), _make_attr("Table")])
    assert len(cm.get_class("MyClass")) == 2

    cm.set_class("MyClass", _make_attr("List"))
    classes = cm.get_class("MyClass")
    assert len(classes) == 1
    assert classes[0].get_owner() == "List"


def test_set_class_with_iterable_stores_array() -> None:
    cm = PDStructureClassMap()
    cm.set_class("MyClass", [_make_attr("Layout"), _make_attr("List")])
    raw = cm.get_cos_object().get_dictionary_object("MyClass")
    assert isinstance(raw, COSArray)
    assert raw.size() == 2


def test_set_class_when_absent_acts_like_add() -> None:
    cm = PDStructureClassMap()
    cm.set_class("New", _make_attr("Layout"))
    assert len(cm.get_class("New")) == 1


def test_set_class_rejects_none() -> None:
    cm = PDStructureClassMap()
    with pytest.raises(TypeError):
        cm.set_class("Bad", None)  # type: ignore[arg-type]


# ---------- pythonic accessors ----------


def test_size_and_len_match_entry_count() -> None:
    cm = PDStructureClassMap()
    assert cm.size() == 0
    assert len(cm) == 0
    cm.add_class("A", _make_attr())
    cm.add_class("B", _make_attr())
    assert cm.size() == 2
    assert len(cm) == 2


def test_get_keys_returns_class_names_in_order() -> None:
    cm = PDStructureClassMap()
    cm.add_class("First", _make_attr())
    cm.add_class("Second", _make_attr())
    cm.add_class("Third", _make_attr())
    assert cm.get_keys() == ["First", "Second", "Third"]


def test_iter_yields_class_names() -> None:
    cm = PDStructureClassMap()
    cm.add_class("A", _make_attr())
    cm.add_class("B", _make_attr())
    assert list(iter(cm)) == ["A", "B"]


def test_contains_for_known_name() -> None:
    cm = PDStructureClassMap()
    cm.add_class("Known", _make_attr())
    assert "Known" in cm
    assert "Unknown" not in cm


def test_contains_with_non_string_returns_false() -> None:
    cm = PDStructureClassMap()
    cm.add_class("X", _make_attr())
    assert (123 in cm) is False  # type: ignore[operator]
    assert (None in cm) is False  # type: ignore[operator]


def test_class_map_wraps_existing_cos_dictionary_with_array_entry() -> None:
    raw_dict = COSDictionary()
    arr = COSArray()
    a = COSDictionary()
    a.set_name(_O, "Layout")
    b = COSDictionary()
    b.set_name(_O, "List")
    arr.add(a)
    arr.add(b)
    raw_dict.set_item("Multi", arr)

    cm = PDStructureClassMap(raw_dict)
    defs = cm.get_class_definitions()
    assert list(defs["Multi"][i].get_owner() for i in range(2)) == ["Layout", "List"]


def test_class_map_skips_non_dictionary_array_entries() -> None:
    raw_dict = COSDictionary()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Skipped"))
    good = COSDictionary()
    good.set_name(_O, "Layout")
    arr.add(good)
    raw_dict.set_item("Mixed", arr)

    cm = PDStructureClassMap(raw_dict)
    assert len(cm.get_class("Mixed")) == 1


# ---------- integration with PDStructureTreeRoot ----------


def test_struct_tree_root_get_class_map_returns_typed_wrapper() -> None:
    root = PDStructureTreeRoot()
    assert root.get_class_map() is None

    raw_class_map = COSDictionary()
    attr = COSDictionary()
    attr.set_name(_O, "Layout")
    raw_class_map.set_item("MyClass", attr)
    root.get_cos_object().set_item(COSName.get_pdf_name("ClassMap"), raw_class_map)

    fetched = root.get_class_map()
    assert isinstance(fetched, PDStructureClassMap)
    defs = fetched.get_class_definitions()
    assert defs["MyClass"][0].get_owner() == "Layout"


def test_struct_tree_root_set_class_map_accepts_typed_wrapper() -> None:
    root = PDStructureTreeRoot()
    cm = PDStructureClassMap()
    cm.add_class("Heading", _make_attr("Layout"))
    cm.add_class("Heading", _make_attr("List"))

    root.set_class_map(cm)

    fetched = root.get_class_map()
    assert isinstance(fetched, PDStructureClassMap)
    assert len(fetched.get_class("Heading")) == 2


def test_struct_tree_root_set_class_map_none_removes_entry() -> None:
    root = PDStructureTreeRoot()
    cm = PDStructureClassMap()
    cm.add_class("X", _make_attr())
    root.set_class_map(cm)
    assert root.get_class_map() is not None

    root.set_class_map(None)
    assert root.get_class_map() is None


def test_struct_tree_root_set_class_map_empty_wrapper_removes_entry() -> None:
    root = PDStructureTreeRoot()
    cm = PDStructureClassMap()
    cm.add_class("X", _make_attr())
    root.set_class_map(cm)

    empty = PDStructureClassMap()
    root.set_class_map(empty)
    assert root.get_class_map() is None
