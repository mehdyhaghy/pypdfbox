"""PDFMergerUtility behavior from the unreleased PDFBox 3.0.9 (3.0 branch):
PDFBOX-6296 (page labels through PDPageLabels, /Kids honored), PDFBOX-6300
(default numbering for a side without labels) and PDFBOX-6299 (early
destination validation, optimized-mode versions, /Lang and
/ViewerPreferences merged without a structure tree)."""

import io

import pytest

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSInteger, COSName
from pypdfbox.multipdf import DocumentMergeMode, PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage, PDPageLabelRange, PDPageLabels

_PAGE_LABELS = COSName.get_pdf_name("PageLabels")
_NUMS = COSName.get_pdf_name("Nums")
_KIDS = COSName.get_pdf_name("Kids")
_P = COSName.get_pdf_name("P")
_S = COSName.get_pdf_name("S")
_LANG = COSName.get_pdf_name("Lang")
_VIEWER_PREFS = COSName.get_pdf_name("ViewerPreferences")


def _doc(pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(pages):
        doc.add_page(PDPage())
    return doc


def _range(prefix: str, style: str) -> COSDictionary:
    d = COSDictionary()
    d.set_string(_P, prefix)
    d.set_name(_S, style)
    return d


def _kids_tree(*leaves: list[object]) -> COSDictionary:
    kids = COSArray()
    for pairs in leaves:
        nums = COSArray()
        for item in pairs:
            nums.add(item)  # type: ignore[arg-type]
        leaf = COSDictionary()
        leaf.set_item(_NUMS, nums)
        kids.add(leaf)
    root = COSDictionary()
    root.set_item(_KIDS, kids)
    return root


def _labels(doc: PDDocument) -> list[str]:
    page_labels = doc.get_document_catalog().get_page_labels()
    assert page_labels is not None
    return page_labels.get_labels_by_page_indices()


def _catalog(doc: PDDocument) -> COSDictionary:
    return doc.get_document_catalog().get_cos_object()


# ---------- PDFBOX-6296: page labels through PDPageLabels ----------


def test_source_page_labels_in_kids_tree_are_merged() -> None:
    with _doc(2) as dest, _doc(3) as src:
        _catalog(src).set_item(
            _PAGE_LABELS,
            _kids_tree(
                [COSInteger.get(0), _range("A-", "D")],
                [COSInteger.get(2), _range("B-", "r")],
            ),
        )
        PDFMergerUtility().append_document(dest, src)
        assert _labels(dest) == ["1", "2", "A-1", "A-2", "B-i"]


def test_destination_kids_tree_is_flattened_and_kept() -> None:
    with _doc(2) as dest, _doc(1) as src:
        _catalog(dest).set_item(
            _PAGE_LABELS,
            _kids_tree([COSInteger.get(0), _range("D-", "A")]),
        )
        _catalog(src).set_item(
            _PAGE_LABELS,
            _kids_tree([COSInteger.get(0), _range("S-", "D")]),
        )
        PDFMergerUtility().append_document(dest, src)
        merged = _catalog(dest).get_dictionary_object(_PAGE_LABELS)
        assert isinstance(merged, COSDictionary)
        assert merged.get_dictionary_object(_KIDS) is None
        nums = merged.get_dictionary_object(_NUMS)
        assert isinstance(nums, COSArray)
        assert [nums.get_object(i) for i in (0, 2)] == [
            COSInteger.get(0),
            COSInteger.get(2),
        ]
        assert _labels(dest) == ["D-A", "D-B", "S-1"]


def test_source_range_is_cloned_not_shared() -> None:
    with _doc(1) as dest, _doc(1) as src:
        src_labels = PDPageLabels(src)
        item = PDPageLabelRange()
        item.set_prefix("S-")
        src_labels.set_label_item(0, item)
        src.get_document_catalog().set_page_labels(src_labels)

        PDFMergerUtility().append_document(dest, src)

        merged = dest.get_document_catalog().get_page_labels()
        assert merged is not None
        cloned = merged.get_page_label_range(1)
        assert cloned is not None
        assert cloned.get_prefix() == "S-"
        assert cloned.get_cos_object() is not item.get_cos_object()


def test_source_range_replaces_seeded_default_of_empty_destination() -> None:
    with PDDocument() as dest, _doc(2) as src:
        src_labels = PDPageLabels(src)
        item = PDPageLabelRange()
        item.set_style(PDPageLabelRange.STYLE_LETTERS_UPPER)
        src_labels.set_label_item(0, item)
        src.get_document_catalog().set_page_labels(src_labels)

        PDFMergerUtility().append_document(dest, src)

        merged = dest.get_document_catalog().get_page_labels()
        assert merged is not None
        assert merged.get_page_indices() == [0]
        assert _labels(dest) == ["A", "B"]


# ---------- PDFBOX-6300: default numbering for a side without labels ----------


def test_destination_without_labels_and_source_without_labels_adds_none() -> None:
    with _doc(1) as dest, _doc(1) as src:
        PDFMergerUtility().append_document(dest, src)
        assert _catalog(dest).get_dictionary_object(_PAGE_LABELS) is None


def test_source_without_labels_does_not_inherit_destination_style() -> None:
    with _doc(2) as dest, _doc(2) as src:
        dest_labels = PDPageLabels(dest)
        item = PDPageLabelRange()
        item.set_style(PDPageLabelRange.STYLE_LETTERS_LOWER)
        item.set_prefix("x")
        dest_labels.set_label_item(0, item)
        dest.get_document_catalog().set_page_labels(dest_labels)

        PDFMergerUtility().append_document(dest, src)

        assert _labels(dest) == ["xa", "xb", "1", "2"]


def test_three_way_merge_keeps_each_document_numbering() -> None:
    with PDDocument() as dest, _doc(2) as a, _doc(1) as b, _doc(2) as c:
        roman = PDPageLabels(a)
        item = PDPageLabelRange()
        item.set_style(PDPageLabelRange.STYLE_ROMAN_LOWER)
        roman.set_label_item(0, item)
        a.get_document_catalog().set_page_labels(roman)
        util = PDFMergerUtility()
        for src in (a, b, c):
            util.append_document(dest, src)
        assert _labels(dest) == ["i", "ii", "1", "1", "2"]


# ---------- PDFBOX-6299: merge_documents validation ----------


@pytest.mark.parametrize(
    "mode",
    [DocumentMergeMode.PDFBOX_LEGACY_MODE, DocumentMergeMode.OPTIMIZE_RESOURCES_MODE],
    ids=["legacy", "optimize"],
)
def test_missing_destination_raises_even_without_sources(mode: object) -> None:
    util = PDFMergerUtility()
    util.set_document_merge_mode(mode)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must be configured"):
        util.merge_documents()


@pytest.mark.parametrize(
    "mode",
    [DocumentMergeMode.PDFBOX_LEGACY_MODE, DocumentMergeMode.OPTIMIZE_RESOURCES_MODE],
    ids=["legacy", "optimize"],
)
def test_empty_source_list_writes_nothing(mode: object) -> None:
    util = PDFMergerUtility()
    util.set_document_merge_mode(mode)  # type: ignore[arg-type]
    out = io.BytesIO()
    util.set_destination_stream(out)
    util.merge_documents()
    assert out.getvalue() == b""


def _saved(version: float) -> bytes:
    with _doc(1) as doc:
        doc.set_version(version)
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()


def test_optimized_mode_uses_highest_source_version() -> None:
    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.add_source(_saved(1.4))
    util.add_source(_saved(1.7))
    util.add_source(_saved(1.5))
    out = io.BytesIO()
    util.set_destination_stream(out)
    util.merge_documents()
    with PDDocument.load(out.getvalue()) as merged:
        assert merged.get_number_of_pages() == 3
        assert merged.get_version() == pytest.approx(1.7)


# ---------- PDFBOX-6299: /Lang + /ViewerPreferences without a struct tree ----------


def test_lang_and_viewer_preferences_merged_without_structure_tree() -> None:
    with _doc(1) as dest, _doc(1) as src:
        _catalog(src).set_string(_LANG, "de-DE")
        prefs = COSDictionary()
        prefs.set_item(COSName.get_pdf_name("FitWindow"), COSBoolean.TRUE)
        _catalog(src).set_item(_VIEWER_PREFS, prefs)
        assert src.get_document_catalog().get_struct_tree_root() is None

        PDFMergerUtility().append_document(dest, src)

        assert _catalog(dest).get_string(_LANG) == "de-DE"
        merged = _catalog(dest).get_dictionary_object(_VIEWER_PREFS)
        assert isinstance(merged, COSDictionary)
        assert merged.get_boolean(COSName.get_pdf_name("FitWindow")) is True
        assert _catalog(dest).get_dictionary_object(
            COSName.get_pdf_name("MarkInfo")
        ) is None


def test_destination_lang_wins_without_structure_tree() -> None:
    with _doc(1) as dest, _doc(1) as src:
        _catalog(dest).set_string(_LANG, "en-US")
        _catalog(src).set_string(_LANG, "de-DE")
        PDFMergerUtility().append_document(dest, src)
        assert _catalog(dest).get_string(_LANG) == "en-US"
