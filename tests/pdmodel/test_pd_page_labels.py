from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel import (
    PDDocument,
    PDPage,
    PDPageLabelRange,
    PDPageLabels,
)


def _doc_with_pages(n: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n):
        doc.add_page(PDPage())
    return doc


# ---------- PDPageLabelRange ----------


def test_range_default_start_is_one() -> None:
    r = PDPageLabelRange()
    assert r.get_start() == 1


def test_range_set_start_validates_positive() -> None:
    r = PDPageLabelRange()
    with pytest.raises(ValueError):
        r.set_start(0)
    with pytest.raises(ValueError):
        r.set_start(-1)


def test_range_round_trip_style_and_prefix() -> None:
    r = PDPageLabelRange()
    r.set_style(PDPageLabelRange.STYLE_ROMAN_LOWER)
    r.set_prefix("Pre-")
    r.set_start(5)
    assert r.get_style() == PDPageLabelRange.STYLE_ROMAN_LOWER
    assert r.get_prefix() == "Pre-"
    assert r.get_start() == 5


def test_range_clear_with_none() -> None:
    r = PDPageLabelRange()
    r.set_style("D")
    r.set_prefix("X")
    r.set_style(None)
    r.set_prefix(None)
    assert r.get_style() is None
    assert r.get_prefix() is None


# ---------- PDPageLabels ----------


def test_default_range_present() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    assert labels.get_page_range_count() == 1
    default = labels.get_page_label_range(0)
    assert default is not None
    assert default.get_style() == PDPageLabelRange.STYLE_DECIMAL


def test_set_label_item_validates_negative() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    with pytest.raises(ValueError):
        labels.set_label_item(-1, PDPageLabelRange())


def test_decimal_labels_simple() -> None:
    doc = _doc_with_pages(3)
    labels = PDPageLabels(doc)
    out = labels.get_labels_by_page_indices()
    assert out == ["1", "2", "3"]


def test_two_ranges_decimal_then_roman() -> None:
    doc = _doc_with_pages(5)
    labels = PDPageLabels(doc)
    # First two pages: lowercase roman, restarting at 1.
    roman = PDPageLabelRange()
    roman.set_style(PDPageLabelRange.STYLE_ROMAN_LOWER)
    labels.set_label_item(0, roman)
    # From page 2 onward: decimal starting at 1.
    decimal = PDPageLabelRange()
    decimal.set_style(PDPageLabelRange.STYLE_DECIMAL)
    labels.set_label_item(2, decimal)
    out = labels.get_labels_by_page_indices()
    assert out == ["i", "ii", "1", "2", "3"]


def test_prefix_with_letters() -> None:
    doc = _doc_with_pages(3)
    labels = PDPageLabels(doc)
    r = PDPageLabelRange()
    r.set_style(PDPageLabelRange.STYLE_LETTERS_UPPER)
    r.set_prefix("App-")
    labels.set_label_item(0, r)
    out = labels.get_labels_by_page_indices()
    assert out == ["App-A", "App-B", "App-C"]


def test_letter_label_doubles_after_z() -> None:
    doc = _doc_with_pages(28)
    labels = PDPageLabels(doc)
    r = PDPageLabelRange()
    r.set_style(PDPageLabelRange.STYLE_LETTERS_LOWER)
    labels.set_label_item(0, r)
    out = labels.get_labels_by_page_indices()
    # 1..26 → a..z, 27..28 → aa, bb (letter doubling per PDF 32000-1).
    assert out[0] == "a"
    assert out[25] == "z"
    assert out[26] == "aa"
    assert out[27] == "bb"


def test_get_label_by_page_index() -> None:
    doc = _doc_with_pages(3)
    labels = PDPageLabels(doc)
    assert labels.get_label_by_page_index(0) == "1"
    assert labels.get_label_by_page_index(2) == "3"
    assert labels.get_label_by_page_index(99) is None
    assert labels.get_label_by_page_index(-1) is None


def test_get_page_indices_by_labels() -> None:
    doc = _doc_with_pages(3)
    labels = PDPageLabels(doc)
    inv = labels.get_page_indices_by_labels()
    assert inv == {"1": 0, "2": 1, "3": 2}


def test_label_range_iterator_in_order() -> None:
    doc = _doc_with_pages(4)
    labels = PDPageLabels(doc)
    extra = PDPageLabelRange()
    extra.set_style(PDPageLabelRange.STYLE_DECIMAL)
    extra.set_start(100)
    labels.set_label_item(2, extra)
    keys = [k for k, _ in labels.get_label_range_iterator()]
    assert keys == [0, 2]


def test_cos_object_round_trip_through_dict() -> None:
    doc = _doc_with_pages(3)
    labels = PDPageLabels(doc)
    decimal = PDPageLabelRange()
    decimal.set_style(PDPageLabelRange.STYLE_DECIMAL)
    decimal.set_start(10)
    labels.set_label_item(1, decimal)

    serialized = labels.get_cos_object()
    nums = serialized.get_dictionary_object(COSName.get_pdf_name("Nums"))
    assert isinstance(nums, COSArray)
    # Two ranges (default at 0 + custom at 1) → 4 entries.
    assert nums.size() == 4
    assert isinstance(nums.get(0), COSInteger)
    assert isinstance(nums.get(2), COSInteger)


def test_construct_from_dict_reads_nums_array() -> None:
    nums = COSArray()
    nums.add(COSInteger.get(0))
    range_dict = COSDictionary()
    range_dict.set_name(COSName.get_pdf_name("S"), PDPageLabelRange.STYLE_ROMAN_LOWER)
    nums.add(range_dict)
    nums.add(COSInteger.get(2))
    range2 = COSDictionary()
    range2.set_name(COSName.get_pdf_name("S"), PDPageLabelRange.STYLE_DECIMAL)
    nums.add(range2)
    tree = COSDictionary()
    tree.set_item(COSName.get_pdf_name("Nums"), nums)

    doc = _doc_with_pages(4)
    labels = PDPageLabels(doc, tree)
    out = labels.get_labels_by_page_indices()
    assert out == ["i", "ii", "1", "2"]


def test_catalog_set_get_page_labels() -> None:
    doc = _doc_with_pages(2)
    labels = PDPageLabels(doc)
    doc.get_document_catalog().set_page_labels(labels)
    fetched = doc.get_document_catalog().get_page_labels()
    assert fetched is not None
    assert fetched.get_labels_by_page_indices() == ["1", "2"]


# ---------- get_label_for_page ----------


def test_get_label_for_page_default_returns_one() -> None:
    """Empty/default labels: get_label_for_page(0) → '1' (decimal default)."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    assert labels.get_label_for_page(0) == "1"


def test_get_label_for_page_decimal_with_start_offset() -> None:
    """One range with /S /D /St 5 at page 0: page 0 → '5', page 1 → '6'."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.set_label_range(0, style=PDPageLabels.STYLE_DECIMAL, start_number=5)
    assert labels.get_label_for_page(0) == "5"
    assert labels.get_label_for_page(1) == "6"


def test_get_label_for_page_roman_lower() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.set_label_range(0, style=PDPageLabels.STYLE_ROMAN_LOWER)
    assert labels.get_label_for_page(0) == "i"
    assert labels.get_label_for_page(3) == "iv"


def test_get_label_for_page_letters_upper_doubles() -> None:
    """Letters style: page 0 → 'A', page 25 → 'Z', page 26 → 'AA'."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.set_label_range(0, style=PDPageLabels.STYLE_LETTERS_UPPER)
    assert labels.get_label_for_page(0) == "A"
    assert labels.get_label_for_page(25) == "Z"
    assert labels.get_label_for_page(26) == "AA"


def test_get_label_for_page_walks_to_right_range() -> None:
    """Multiple ranges: pick the range covering the requested index."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.set_label_range(0, style=PDPageLabels.STYLE_ROMAN_LOWER)
    labels.set_label_range(3, style=PDPageLabels.STYLE_DECIMAL, prefix="A-")
    labels.set_label_range(
        7, style=PDPageLabels.STYLE_LETTERS_UPPER, start_number=1
    )
    assert labels.get_label_for_page(0) == "i"
    assert labels.get_label_for_page(2) == "iii"
    # Range starts at 3, /St defaults to 1 → page 3 → "A-1".
    assert labels.get_label_for_page(3) == "A-1"
    assert labels.get_label_for_page(5) == "A-3"
    # Range starts at 7 with letters → page 7 → "A".
    assert labels.get_label_for_page(7) == "A"
    assert labels.get_label_for_page(8) == "B"


def test_get_label_for_page_with_prefix_only() -> None:
    """Range with prefix and no style: just emits the prefix."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    r = PDPageLabelRange()
    r.set_prefix("Cover")
    labels.set_label_item(0, r)
    assert labels.get_label_for_page(0) == "Cover"


# ---------- get_label_ranges ----------


def test_get_label_ranges_lists_each_entry() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.set_label_range(0, style=PDPageLabels.STYLE_ROMAN_LOWER)
    labels.set_label_range(
        4, style=PDPageLabels.STYLE_DECIMAL, prefix="A-", start_number=10
    )
    ranges = labels.get_label_ranges()
    assert len(ranges) == 2
    assert ranges[0] == {
        "start_index": 0,
        "style": "r",
        "prefix": None,
        "start_number": 1,
    }
    assert ranges[1] == {
        "start_index": 4,
        "style": "D",
        "prefix": "A-",
        "start_number": 10,
    }


# ---------- set_label_range ----------


def test_set_label_range_validates_negative() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    with pytest.raises(ValueError):
        labels.set_label_range(-1, style=PDPageLabels.STYLE_DECIMAL)


def test_set_label_range_replaces_existing() -> None:
    """A second set_label_range at the same start_index overwrites."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.set_label_range(0, style=PDPageLabels.STYLE_DECIMAL)
    labels.set_label_range(0, style=PDPageLabels.STYLE_ROMAN_UPPER)
    assert labels.get_label_for_page(0) == "I"


# ---------- to_roman / to_letters helpers ----------


def test_to_roman_basic() -> None:
    from pypdfbox.pdmodel.pd_page_labels import to_roman

    assert to_roman(1) == "I"
    assert to_roman(4) == "IV"
    assert to_roman(9) == "IX"
    assert to_roman(40) == "XL"
    assert to_roman(1990) == "MCMXC"


def test_to_letters_basic() -> None:
    from pypdfbox.pdmodel.pd_page_labels import to_letters

    assert to_letters(1) == "A"
    assert to_letters(26) == "Z"
    assert to_letters(27) == "AA"
    assert to_letters(28) == "BB"
