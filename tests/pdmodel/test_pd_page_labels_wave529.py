from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel import PDDocument, PDPageLabelRange, PDPageLabels


def _name(name: str) -> COSName:
    return COSName.get_pdf_name(name)


def test_wave529_child_number_tree_takes_precedence_over_parent_nums() -> None:
    child_nums = COSArray()
    child_nums.add(COSInteger.get(1))
    child_range = COSDictionary()
    child_range.set_name(_name("S"), PDPageLabelRange.STYLE_ROMAN_LOWER)
    child_nums.add(child_range)
    child = COSDictionary()
    child.set_item(_name("Nums"), child_nums)

    parent_nums = COSArray()
    parent_nums.add(COSInteger.get(4))
    parent_range = COSDictionary()
    parent_range.set_name(_name("S"), PDPageLabelRange.STYLE_LETTERS_UPPER)
    parent_nums.add(parent_range)

    root = COSDictionary()
    kids = COSArray()
    kids.add(COSString("ignored"))
    kids.add(child)
    root.set_item(_name("Kids"), kids)
    root.set_item(_name("Nums"), parent_nums)

    labels = PDPageLabels(PDDocument(), root)

    assert labels.get_page_label_range(1) is not None
    assert labels.get_page_label_range(4) is None


def test_wave529_nums_parser_skips_malformed_and_negative_entries() -> None:
    nums = COSArray()
    nums.add(COSString("not-an-int"))
    nums.add(COSDictionary())
    nums.add(COSInteger.get(-1))
    nums.add(COSDictionary())
    nums.add(COSInteger.get(2))
    nums.add(COSString("not-a-range"))
    nums.add(COSInteger.get(3))
    good_range = COSDictionary()
    good_range.set_name(_name("S"), PDPageLabelRange.STYLE_DECIMAL)
    nums.add(good_range)
    nums.add(COSInteger.get(9))

    root = COSDictionary()
    root.set_item(_name("Nums"), nums)

    labels = PDPageLabels(PDDocument(), root)

    assert labels.get_page_indices() == [0, 3]
    assert labels.get_page_label_range(3) is not None


def test_wave529_page_count_falls_back_to_zero_when_document_raises() -> None:
    class BrokenDocument:
        def get_number_of_pages(self) -> int:
            raise RuntimeError("cannot count pages")

    labels = PDPageLabels(BrokenDocument())  # type: ignore[arg-type]

    assert labels.get_number_of_pages() == 0
    assert labels.get_labels_by_page_indices() == []


def test_wave529_set_number_of_pages_rejects_negative_count() -> None:
    labels = PDPageLabels(PDDocument())

    with pytest.raises(ValueError, match="may not be < 0"):
        labels.set_number_of_pages(-1)


def test_wave529_inverse_label_map_keeps_highest_page_index_for_duplicates() -> None:
    labels = PDPageLabels(PDDocument())
    labels.set_number_of_pages(3)
    labels.set_label_range(0, prefix="Section")

    assert labels.get_labels_by_page_indices() == ["Section", "Section", "Section"]
    assert labels.get_page_indices_by_labels() == {"Section": 2}


def test_wave529_missing_ranges_use_default_label_and_repr_reports_count() -> None:
    labels = PDPageLabels(PDDocument())
    labels.clear_label_ranges()

    assert labels.get_label_for_page(-1) == "0"
    assert labels.get_label_for_page(4) == "5"
    assert labels.find_label_range_containing(0) is None
    assert repr(labels) == "PDPageLabels(ranges=0)"
