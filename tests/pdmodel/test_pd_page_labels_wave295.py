from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel import PDDocument, PDPageLabelRange, PDPageLabels


def test_set_label_item_updates_range_start_index_wave295() -> None:
    labels = PDPageLabels(PDDocument())
    label_range = PDPageLabelRange()

    labels.set_label_item(4, label_range)

    assert labels.get_page_label_range(4) is label_range
    assert label_range.get_start_index() == 4


def test_set_label_range_records_range_start_index_wave295() -> None:
    labels = PDPageLabels(PDDocument())

    labels.set_label_range(6, style=PDPageLabels.STYLE_ROMAN_LOWER)

    label_range = labels.get_page_label_range(6)
    assert label_range is not None
    assert label_range.get_start_index() == 6


def test_parsed_nums_records_range_start_index_wave295() -> None:
    nums = COSArray()
    nums.add(COSInteger.get(3))
    range_dict = COSDictionary()
    range_dict.set_name(COSName.get_pdf_name("S"), PDPageLabelRange.STYLE_DECIMAL)
    nums.add(range_dict)
    tree = COSDictionary()
    tree.set_item(COSName.get_pdf_name("Nums"), nums)

    labels = PDPageLabels(PDDocument(), tree)

    label_range = labels.get_page_label_range(3)
    assert label_range is not None
    assert label_range.get_start_index() == 3
