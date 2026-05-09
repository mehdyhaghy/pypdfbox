from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel import PDPageLabelRange, PDPageLabels, PDViewerPreferences


def test_viewer_preferences_invalid_boundary_enums_return_none_and_repr() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("ViewClip"), "BogusViewClip")
    raw.set_name(COSName.get_pdf_name("PrintArea"), "BogusPrintArea")
    raw.set_name(COSName.get_pdf_name("PrintClip"), "BogusPrintClip")
    prefs = PDViewerPreferences(raw)

    assert prefs.get_view_clip_enum() is None
    assert prefs.get_print_area_enum() is None
    assert prefs.get_print_clip_enum() is None
    assert repr(prefs) == "PDViewerPreferences(...)"


def test_page_label_range_computes_remaining_styles_and_unknown_fallback() -> None:
    assert PDPageLabelRange.is_valid_style(None) is False

    upper_roman = PDPageLabelRange()
    upper_roman.set_style(PDPageLabelRange.STYLE_ROMAN_UPPER)
    assert upper_roman.compute_label_for_offset(3) == "IV"

    upper_letters = PDPageLabelRange()
    upper_letters.set_style(PDPageLabelRange.STYLE_LETTERS_UPPER)
    assert upper_letters.compute_label_for_offset(26) == "AA"

    lower_letters = PDPageLabelRange()
    lower_letters.set_style(PDPageLabelRange.STYLE_LETTERS_LOWER)
    assert lower_letters.compute_label_for_offset(27) == "bb"

    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("S"), "UnknownStyle")
    unknown = PDPageLabelRange(raw, start_index=9)
    assert unknown.compute_label_for_offset(2) == "3"
    assert "PDPageLabelRange(start_index=9" in repr(unknown)


def test_page_labels_edge_case_number_tree_and_fallback_labels() -> None:
    assert PDPageLabels(None).get_number_of_pages() == 0  # type: ignore[arg-type]

    empty_tree = COSDictionary()
    empty_tree.set_item(COSName.get_pdf_name("Kids"), COSArray())
    labels = PDPageLabels(None, empty_tree)  # type: ignore[arg-type]
    assert labels.get_page_indices() == [0]


def test_page_labels_to_letters_and_prefix_trimming_paths() -> None:
    from pypdfbox.pdmodel.pd_page_labels import to_letters

    assert to_letters(0) == ""

    labels = PDPageLabels(None)  # type: ignore[arg-type]
    labels.set_number_of_pages(2)
    labels.set_label_range(0, style=PDPageLabels.STYLE_DECIMAL, prefix="A\x00B-")

    assert labels.get_label_for_page(0) == "A1"
    assert labels.get_labels_by_page_indices() == ["A1", "A2"]


def test_page_labels_unknown_style_falls_back_to_decimal() -> None:
    raw_range = COSDictionary()
    raw_range.set_name(COSName.get_pdf_name("S"), "Unrecognized")
    raw_range.set_item(COSName.get_pdf_name("P"), COSString("raw-"))
    label_range = PDPageLabelRange(raw_range)

    labels = PDPageLabels(None)  # type: ignore[arg-type]
    labels.set_number_of_pages(1)
    labels.set_label_item(0, label_range)

    assert labels.get_labels_by_page_indices() == ["raw-1"]
    assert labels.get_label_for_page(0) == "raw-1"


def test_page_labels_malformed_nums_entries_are_ignored() -> None:
    nums = COSArray()
    nums.add(COSString("not-an-integer-key"))
    nums.add(COSDictionary())
    nums.add(COSInteger.get(2))
    nums.add(COSString("not-a-dictionary-value"))
    nums.add(COSInteger.get(-1))
    nums.add(COSDictionary())
    tree = COSDictionary()
    tree.set_item(COSName.get_pdf_name("Nums"), nums)

    labels = PDPageLabels(None, tree)  # type: ignore[arg-type]

    assert labels.get_page_indices() == [0]
