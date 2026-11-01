"""PDPageLabels number-tree reading after PDFBOX-6296 (3.0 branch, unreleased
3.0.9): only PDPageLabelRange values are accepted, and the constructor's
page-0 entry survives a null value."""

import logging

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSNull, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDPageLabelRange, PDPageLabels

_NUMS = COSName.get_pdf_name("Nums")
_KIDS = COSName.get_pdf_name("Kids")
_P = COSName.get_pdf_name("P")
_S = COSName.get_pdf_name("S")


def _range(prefix: str, style: str | None = None) -> COSDictionary:
    d = COSDictionary()
    d.set_string(_P, prefix)
    if style is not None:
        d.set_name(_S, style)
    return d


def _leaf(*pairs: object) -> COSDictionary:
    nums = COSArray()
    for item in pairs:
        nums.add(item)  # type: ignore[arg-type]
    leaf = COSDictionary()
    leaf.set_item(_NUMS, nums)
    return leaf


def _doc(pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(pages):
        doc.add_page(PDPage())
    return doc


def test_null_value_keeps_seeded_page0_range() -> None:
    tree = _leaf(COSInteger.get(0), COSNull.NULL, COSInteger.get(2), _range("B-", "D"))
    with _doc(3) as doc:
        labels = PDPageLabels(doc, tree)
        assert labels.get_page_indices() == [0, 2]
        seeded = labels.get_page_label_range(0)
        assert seeded is not None
        assert seeded.get_style() == PDPageLabelRange.STYLE_DECIMAL
        assert labels.get_labels_by_page_indices() == ["1", "2", "B-1"]


def test_null_value_at_other_key_adds_no_range() -> None:
    tree = _leaf(COSInteger.get(0), _range("A-", "D"), COSInteger.get(1), COSNull.NULL)
    with _doc(2) as doc:
        labels = PDPageLabels(doc, tree)
        assert labels.get_page_indices() == [0]
        assert labels.get_page_label_range(1) is None
        assert labels.get_labels_by_page_indices() == ["A-1", "A-2"]


def test_kids_tree_is_read() -> None:
    root = COSDictionary()
    kids = COSArray()
    kids.add(_leaf(COSInteger.get(0), _range("i-", "r")))
    kids.add(_leaf(COSInteger.get(2), _range("", "D")))
    root.set_item(_KIDS, kids)
    with _doc(4) as doc:
        labels = PDPageLabels(doc, root)
        assert labels.get_labels_by_page_indices() == ["i-i", "i-ii", "1", "2"]


def test_empty_kids_array_hides_nums() -> None:
    root = _leaf(COSInteger.get(1), _range("X-", "D"))
    root.set_item(_KIDS, COSArray())
    with _doc(2) as doc:
        labels = PDPageLabels(doc, root)
        assert labels.get_page_indices() == [0]


def test_non_integer_key_drops_only_its_own_leaf(
    caplog: pytest.LogCaptureFixture,
) -> None:
    root = COSDictionary()
    kids = COSArray()
    kids.add(_leaf(COSInteger.get(1), _range("good-", "D")))
    kids.add(_leaf(COSInteger.get(2), _range("lost-", "D"), COSName.get_pdf_name("X"), _range("x")))
    root.set_item(_KIDS, kids)
    with _doc(3) as doc, caplog.at_level(logging.ERROR, logger="pypdfbox.pdmodel.pd_page_labels"):
        labels = PDPageLabels(doc, root)
        assert labels.get_page_indices() == [0, 1]
    assert "page labels ignored, index 2 should be a number" in caplog.text


def test_negative_key_is_ignored() -> None:
    tree = _leaf(COSInteger.get(-1), _range("neg-"), COSInteger.get(1), _range("p-", "D"))
    labels = PDPageLabels(None, tree)  # type: ignore[arg-type]
    assert labels.get_page_indices() == [0, 1]


@pytest.mark.parametrize(
    "value",
    [COSInteger.get(5), COSStream()],
    ids=["integer", "stream"],
)
def test_non_dictionary_value_raises(value: object) -> None:
    tree = _leaf(COSInteger.get(1), value)
    with pytest.raises(OSError, match="PDPageLabelRange-typed value in number tree"):
        PDPageLabels(None, tree)  # type: ignore[arg-type]


def test_odd_size_nums_warns_and_reads_pairs(caplog: pytest.LogCaptureFixture) -> None:
    tree = _leaf(COSInteger.get(1), _range("p-", "D"), COSInteger.get(2))
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.pd_page_labels"):
        labels = PDPageLabels(None, tree)  # type: ignore[arg-type]
    assert labels.get_page_indices() == [0, 1]
    assert "Numbers array has odd size: 3" in caplog.text
