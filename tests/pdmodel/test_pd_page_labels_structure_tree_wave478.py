from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDPageLabelRange, PDPageLabels
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureElement,
    PDStructureElementNumberTreeNode,
    PDStructureTreeRoot,
)


def _doc_with_pages(count: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(count):
        doc.add_page(PDPage())
    return doc


def test_page_labels_default_range_can_be_removed_and_restored() -> None:
    with _doc_with_pages(2) as doc:
        labels = PDPageLabels(doc)

        assert labels.has_default_range() is True
        assert labels.is_default_only() is True

        assert labels.remove_label_range(0) is True
        assert labels.has_default_range() is False
        assert labels.get_page_range_count() == 0
        assert labels.remove_label_range(0) is False

        restored = labels.ensure_default_range()

        assert labels.has_default_range() is True
        assert restored.get_style() == PDPageLabelRange.STYLE_DECIMAL
        assert labels.get_labels_by_page_indices() == ["1", "2"]


def test_page_labels_copy_is_independent_and_preserves_page_count() -> None:
    with _doc_with_pages(3) as doc:
        labels = PDPageLabels(doc)
        labels.set_number_of_pages(5)
        labels.set_label_range(
            2,
            style=PDPageLabels.STYLE_ROMAN_UPPER,
            prefix="A-",
            start_number=4,
        )

        clone = labels.copy()
        clone.get_page_label_range(2).set_prefix("B-")  # type: ignore[union-attr]
        clone.set_number_of_pages(3)

        assert labels.get_number_of_pages() == 5
        assert clone.get_number_of_pages() == 3
        assert labels.get_label_for_page(2) == "A-IV"
        assert clone.get_label_for_page(2) == "B-IV"


def test_page_labels_find_range_and_container_protocols() -> None:
    with _doc_with_pages(0) as doc:
        labels = PDPageLabels(doc)
        labels.clear_label_ranges()
        labels.set_label_range(3, style=PDPageLabels.STYLE_DECIMAL)
        labels.set_label_range(7, style=PDPageLabels.STYLE_LETTERS_LOWER)

        assert len(labels) == 2
        assert list(labels) == [3, 7]
        assert 3 in labels
        assert "3" not in labels
        assert labels.get_first_page_index() == 3
        assert labels.get_last_page_index() == 7
        assert labels.find_label_range_containing(2) is None
        assert labels.find_label_range_containing(6) is labels.get_page_label_range(3)
        assert labels.find_label_range_containing(9) is labels.get_page_label_range(7)


def test_structure_tree_root_appends_kid_and_resolves_descendant_roles() -> None:
    root = PDStructureTreeRoot()
    root.set_role_map({"BodyText": "P", "Hero": "BodyText"})
    parent = PDStructureElement(structure_type="Sect")
    child = PDStructureElement(structure_type="Hero")
    parent.append_kid(child)

    root.append_kid(parent)

    assert root.has_kids() is True
    assert root.count_kids() == 1
    assert parent.get_parent() is root.get_cos_object()
    assert list(root.iter_descendants())[0].get_structure_type() == "Sect"
    assert root.resolve_role_map("Hero") == "P"
    assert root.find_first_by_role("P").get_cos_object() is child.get_cos_object()


def test_structure_tree_root_parent_tree_helpers_skip_invalid_pages() -> None:
    root = PDStructureTreeRoot()
    page_without_key = PDPage()
    page_with_key = PDPage()
    page_with_key.set_struct_parents(4)

    tree = root.build_parent_tree([page_without_key, page_with_key])

    assert isinstance(tree, PDStructureElementNumberTreeNode)
    assert root.has_parent_tree() is True
    assert root.get_parent_tree_next_key() == 5
    assert isinstance(tree.get_value(4), COSArray)
    assert tree.get_value(0) is None

    assert root.next_parent_tree_key() == 5
    assert root.get_parent_tree_next_key() == 6


def test_structure_tree_root_get_struct_element_for_mcid_edges() -> None:
    root = PDStructureTreeRoot()
    page = PDPage()
    assert root.get_struct_element_for_mcid(page, 0) is None

    page.set_struct_parents(2)
    entries = COSArray()
    entries.add(COSInteger.get(17))
    elem_dict = COSDictionary()
    elem_dict.set_name(COSName.TYPE, "StructElem")  # type: ignore[attr-defined]
    entries.add(elem_dict)
    tree = PDStructureElementNumberTreeNode()
    tree.set_numbers({2: entries})
    root.set_parent_tree(tree)

    assert root.get_struct_element_for_mcid(page, -1) is None
    assert root.get_struct_element_for_mcid(page, 0) is None
    assert root.get_struct_element_for_mcid(page, 99) is None
    resolved = root.get_struct_element_for_mcid(page, 1)
    assert resolved is not None
    assert resolved.get_cos_object() is elem_dict
