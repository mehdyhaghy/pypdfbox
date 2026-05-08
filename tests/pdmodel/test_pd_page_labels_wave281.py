from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel import PDDocument, PDPageLabelRange, PDPageLabels


def test_label_range_clear_helpers_remove_entries_wave281() -> None:
    label_range = PDPageLabelRange()
    label_range.set_style(PDPageLabelRange.STYLE_DECIMAL)
    label_range.set_prefix("A-")
    label_range.set_start(5)

    assert label_range.has_style()
    assert label_range.has_prefix()
    assert label_range.has_start()

    label_range.clear_style()
    label_range.clear_prefix()
    label_range.clear_start()

    assert not label_range.has_style()
    assert not label_range.has_prefix()
    assert not label_range.has_start()
    assert label_range.get_style() is None
    assert label_range.get_prefix() is None
    assert label_range.get_start() == 1


def test_get_label_for_page_without_covering_range_falls_back_wave281() -> None:
    labels = PDPageLabels(PDDocument())
    labels.clear_label_ranges()
    labels.set_label_range(3, style=PDPageLabels.STYLE_ROMAN_LOWER)

    assert labels.get_label_for_page(0) == "1"
    assert labels.get_label_for_page(2) == "3"
    assert labels.get_label_for_page(3) == "i"


def test_get_labels_by_page_indices_respects_sparse_range_start_wave281() -> None:
    labels = PDPageLabels(PDDocument())
    labels.set_number_of_pages(5)
    labels.clear_label_ranges()
    labels.set_label_range(2, style=PDPageLabels.STYLE_DECIMAL, prefix="S-")

    assert labels.get_labels_by_page_indices() == ["", "", "S-1", "S-2", "S-3"]
    assert labels.get_page_indices_by_labels() == {"S-1": 2, "S-2": 3, "S-3": 4}


def test_nested_kids_are_read_recursively_wave281() -> None:
    leaf_nums = COSArray()
    leaf_nums.add(COSInteger.get(2))
    leaf_range = COSDictionary()
    leaf_range.set_name(COSName.get_pdf_name("S"), PDPageLabelRange.STYLE_ROMAN_UPPER)
    leaf_nums.add(leaf_range)

    leaf = COSDictionary()
    leaf.set_item(COSName.get_pdf_name("Nums"), leaf_nums)

    middle_kids = COSArray()
    middle_kids.add(leaf)
    middle = COSDictionary()
    middle.set_item(COSName.get_pdf_name("Kids"), middle_kids)

    root_kids = COSArray()
    root_kids.add(middle)
    root = COSDictionary()
    root.set_item(COSName.get_pdf_name("Kids"), root_kids)

    labels = PDPageLabels(PDDocument(), root)
    labels.set_number_of_pages(4)

    assert labels.get_labels_by_page_indices() == ["1", "2", "I", "II"]
