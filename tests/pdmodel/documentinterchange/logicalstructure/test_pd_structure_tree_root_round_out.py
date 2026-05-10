"""Hand-written round-out tests for PDStructureTreeRoot + PDStructureElement.

Wave 41 covers:
- /K children traversal (single dict / indirect / OBJR / MCR / nested elements)
- /A attribute-object listing + has-class + role-map normalization
- /C class-name string accessor
- /RoleMap read+normalize standard names; resolve_role_map helper
- /ParentTree build from /MCID-keyed objects in pages
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDAttributeObject,
    PDMarkedContentReference,
    PDObjectReference,
    PDStructureElement,
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.pd_page import PDPage

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_K = COSName.get_pdf_name("K")
_P = COSName.get_pdf_name("P")
_S = COSName.get_pdf_name("S")
_PARENT_TREE = COSName.get_pdf_name("ParentTree")


# ---------- PDStructureTreeRoot.iter_descendants / find_by_role ----------


def _make_tree_root_with_kids() -> tuple[
    PDStructureTreeRoot,
    dict[str, PDStructureElement],
]:
    root = PDStructureTreeRoot()
    doc = PDStructureElement(structure_type="Document")
    h1 = PDStructureElement(structure_type="H1")
    p = PDStructureElement(structure_type="P")
    figure = PDStructureElement(structure_type="Figure")
    span = PDStructureElement(structure_type="Span")

    p.append_kid(span)
    doc.append_kid(h1)
    doc.append_kid(p)
    doc.append_kid(figure)
    root.append_kid(doc)

    return root, {
        "doc": doc,
        "h1": h1,
        "p": p,
        "figure": figure,
        "span": span,
    }


def test_struct_tree_root_iter_descendants_walks_full_tree() -> None:
    root, nodes = _make_tree_root_with_kids()
    seen = list(root.iter_descendants())
    seen_ids = [id(n.get_cos_object()) for n in seen]
    expected = [
        nodes["doc"],
        nodes["h1"],
        nodes["p"],
        nodes["span"],
        nodes["figure"],
    ]
    assert seen_ids == [id(n.get_cos_object()) for n in expected]


def test_struct_tree_root_find_by_role_matches() -> None:
    root, nodes = _make_tree_root_with_kids()
    h1s = list(root.find_by_role("H1"))
    assert [id(n.get_cos_object()) for n in h1s] == [id(nodes["h1"].get_cos_object())]


def test_struct_tree_root_find_first_by_role_returns_first() -> None:
    root, nodes = _make_tree_root_with_kids()
    first = root.find_first_by_role("Figure")
    assert first is not None
    assert first.get_cos_object() is nodes["figure"].get_cos_object()


def test_struct_tree_root_find_first_by_role_missing_returns_none() -> None:
    root, _ = _make_tree_root_with_kids()
    assert root.find_first_by_role("Caption") is None


def test_struct_tree_root_iter_descendants_terminates_on_cycle() -> None:
    root = PDStructureTreeRoot()
    a = PDStructureElement(structure_type="Section")
    b = PDStructureElement(structure_type="Section")
    a.append_kid(b)
    b.append_kid(a)
    root.append_kid(a)
    desc = list(root.iter_descendants())
    seen_ids = [id(d.get_cos_object()) for d in desc]
    # Identity-set should terminate the walk.
    assert len(set(seen_ids)) == len(seen_ids)


# ---------- PDStructureTreeRoot.resolve_role_map ----------


def test_resolve_role_map_returns_input_when_no_role_map() -> None:
    root = PDStructureTreeRoot()
    assert root.resolve_role_map("MyHeader") == "MyHeader"


def test_resolve_role_map_passes_through_standard_type() -> None:
    root = PDStructureTreeRoot()
    root.set_role_map({"MyHeader": "H1"})
    # /S already standard — left alone.
    assert root.resolve_role_map("H1") == "H1"


def test_resolve_role_map_one_hop() -> None:
    root = PDStructureTreeRoot()
    root.set_role_map({"MyHeader": "H1"})
    assert root.resolve_role_map("MyHeader") == "H1"


def test_resolve_role_map_multi_hop_until_standard() -> None:
    root = PDStructureTreeRoot()
    root.set_role_map({"A": "B", "B": "C", "C": "P"})
    assert root.resolve_role_map("A") == "P"


def test_resolve_role_map_breaks_cycle() -> None:
    root = PDStructureTreeRoot()
    root.set_role_map({"A": "B", "B": "A"})
    result = root.resolve_role_map("A")
    assert result in {"A", "B"}


def test_resolve_role_map_none_returns_none() -> None:
    root = PDStructureTreeRoot()
    assert root.resolve_role_map(None) is None


# ---------- PDStructureTreeRoot.build_parent_tree ----------


def test_build_parent_tree_creates_entries_for_pages() -> None:
    root = PDStructureTreeRoot()
    page_a = PDPage()
    page_b = PDPage()
    page_a.set_struct_parents(0)
    page_b.set_struct_parents(2)

    tree = root.build_parent_tree([page_a, page_b])

    nums = tree.get_numbers()
    assert nums is not None
    assert set(nums.keys()) == {0, 2}
    assert isinstance(nums[0], COSArray)
    assert isinstance(nums[2], COSArray)
    # ParentTreeNextKey should exceed the max existing key.
    assert root.get_parent_tree_next_key() == 3


def test_build_parent_tree_skips_pages_without_struct_parents() -> None:
    root = PDStructureTreeRoot()
    page_a = PDPage()
    # No /StructParents set — defaults to -1.
    tree = root.build_parent_tree([page_a])
    nums = tree.get_numbers() or {}
    assert nums == {}


def test_build_parent_tree_preserves_existing_entries() -> None:
    root = PDStructureTreeRoot()
    # Pre-seed with an existing entry.
    parent_tree_dict = COSDictionary()
    nums_arr = COSArray()
    nums_arr.add(COSInteger.get(5))
    page_arr = COSArray()
    page_arr.add(COSDictionary())  # MCID 0 → struct elem
    nums_arr.add(page_arr)
    parent_tree_dict.set_item(COSName.get_pdf_name("Nums"), nums_arr)
    root.get_cos_object().set_item(_PARENT_TREE, parent_tree_dict)

    page = PDPage()
    page.set_struct_parents(7)

    tree = root.build_parent_tree([page])
    nums = tree.get_numbers() or {}
    assert 5 in nums
    assert 7 in nums
    # The pre-seeded entry survives.
    assert isinstance(nums[5], COSArray)
    assert nums[5].size() == 1


# ---------- /K traversal: indirect + OBJR + MCR + nested ----------


def test_root_get_kids_dispatches_typed_entries() -> None:
    root = PDStructureTreeRoot()
    elem = COSDictionary()
    elem.set_name(_TYPE, "StructElem")
    objr = COSDictionary()
    objr.set_name(_TYPE, "OBJR")
    mcr = COSDictionary()
    mcr.set_name(_TYPE, "MCR")
    arr = COSArray([elem, objr, mcr, COSInteger.get(7)])
    root.get_cos_object().set_item(_K, arr)

    kids = root.get_kids()
    assert isinstance(kids[0], PDStructureElement)
    assert isinstance(kids[1], PDObjectReference)
    assert isinstance(kids[2], PDMarkedContentReference)
    assert kids[3] == 7


def test_root_append_kid_struct_elem_sets_parent_pointer() -> None:
    root = PDStructureTreeRoot()
    child = PDStructureElement(structure_type="Document")
    root.append_kid(child)
    assert child.get_parent() is root.get_cos_object()


# ---------- PDStructureElement.get_class_names_as_strings + has_class ----------


def test_get_class_names_as_strings_single_value() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.add_class_name("Bold")
    assert elem.get_class_names_as_strings() == ["Bold"]


def test_get_class_names_as_strings_array() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.add_class_name("Bold")
    elem.add_class_name("Italic")
    assert elem.get_class_names_as_strings() == ["Bold", "Italic"]


def test_get_class_names_as_strings_empty() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_class_names_as_strings() == []


def test_has_class_true_for_present_name() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.add_class_name("Bold")
    elem.add_class_name("Italic")
    assert elem.has_class("Italic") is True
    assert elem.has_class("Bold") is True


def test_has_class_false_for_missing_name() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.add_class_name("Bold")
    assert elem.has_class("Italic") is False


def test_has_class_none_returns_false() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.add_class_name("Bold")
    assert elem.has_class(None) is False


# ---------- PDStructureElement.get_attribute_objects + has_attribute_owner ----


def test_get_attribute_objects_dispatches_typed_owners() -> None:
    elem = PDStructureElement(structure_type="P")
    layout = PDAttributeObject()
    layout.set_owner("Layout")
    list_attr = PDAttributeObject()
    list_attr.set_owner("List")
    elem.add_attribute(layout)
    elem.add_attribute(list_attr)

    typed = elem.get_attribute_objects()
    assert len(typed) == 2
    owners = {a.get_owner() for a in typed}
    assert owners == {"Layout", "List"}


def test_get_attribute_objects_handles_single_dict_a() -> None:
    elem = PDStructureElement(structure_type="P")
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("O"), "Layout")
    elem.get_cos_object().set_item(COSName.get_pdf_name("A"), raw)
    typed = elem.get_attribute_objects()
    assert len(typed) == 1
    assert typed[0].get_owner() == "Layout"


def test_get_attribute_objects_empty_when_a_absent() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_attribute_objects() == []


def test_has_attribute_owner_true_when_owner_present() -> None:
    elem = PDStructureElement(structure_type="P")
    a = PDAttributeObject()
    a.set_owner("Layout")
    elem.add_attribute(a)
    assert elem.has_attribute_owner("Layout") is True


def test_has_attribute_owner_false_when_owner_missing() -> None:
    elem = PDStructureElement(structure_type="P")
    a = PDAttributeObject()
    a.set_owner("Layout")
    elem.add_attribute(a)
    assert elem.has_attribute_owner("List") is False


def test_has_attribute_owner_none_returns_false() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.has_attribute_owner(None) is False


# ---------- PDStructureElement.iter_object_references ----------


def test_iter_object_references_filters_to_objr_only() -> None:
    elem = PDStructureElement(structure_type="P")
    objr_a = PDObjectReference()
    objr_b = PDObjectReference()
    elem.append_kid(objr_a)
    elem.append_kid(7)  # MCID
    elem.append_kid(objr_b)
    refs = list(elem.iter_object_references())
    assert len(refs) == 2
    assert all(isinstance(r, PDObjectReference) for r in refs)


def test_iter_object_references_empty_when_none_present() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.append_kid(3)
    elem.append_kid(PDStructureElement(structure_type="Span"))
    assert list(elem.iter_object_references()) == []


# ---------- PDStructureElement.get_parent_node ----------


def test_get_parent_node_dispatches_to_struct_tree_root() -> None:
    root = PDStructureTreeRoot()
    elem = PDStructureElement(structure_type="P")
    elem.set_parent(root)
    parent = elem.get_parent_node()
    assert isinstance(parent, PDStructureTreeRoot)
    assert parent.get_cos_object() is root.get_cos_object()


def test_get_parent_node_dispatches_to_struct_elem() -> None:
    parent_elem = PDStructureElement(structure_type="Document")
    elem = PDStructureElement(structure_type="P")
    elem.set_parent(parent_elem)
    parent = elem.get_parent_node()
    assert isinstance(parent, PDStructureElement)
    assert parent.get_cos_object() is parent_elem.get_cos_object()


def test_get_parent_node_returns_none_when_p_absent() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_parent_node() is None


# ---------- PDStructureElement.get_structure_tree_root walk ----------


def test_get_structure_tree_root_finds_root_through_chain() -> None:
    root = PDStructureTreeRoot()
    doc = PDStructureElement(structure_type="Document")
    p = PDStructureElement(structure_type="P")
    span = PDStructureElement(structure_type="Span")
    doc.set_parent(root)
    p.set_parent(doc)
    span.set_parent(p)
    found = span.get_structure_tree_root()
    assert isinstance(found, PDStructureTreeRoot)
    assert found.get_cos_object() is root.get_cos_object()


def test_get_structure_tree_root_returns_none_when_no_root() -> None:
    elem = PDStructureElement(structure_type="P")
    other = PDStructureElement(structure_type="Document")
    elem.set_parent(other)
    assert elem.get_structure_tree_root() is None
