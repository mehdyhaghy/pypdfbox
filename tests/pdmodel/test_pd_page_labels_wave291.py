from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel import PDPageLabelRange


def test_page_label_range_has_helpers_ignore_malformed_cos_entries_wave291() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("S"), COSInteger.get(1))
    raw.set_item(COSName.get_pdf_name("P"), COSInteger.get(2))
    raw.set_item(COSName.get_pdf_name("St"), COSName.get_pdf_name("BadStart"))

    label_range = PDPageLabelRange(raw)

    assert label_range.get_style() is None
    assert label_range.has_style() is False
    assert label_range.get_prefix() is None
    assert label_range.has_prefix() is False
    assert label_range.get_start() == 1
    assert label_range.has_start() is False


def test_page_label_range_has_helpers_accept_well_typed_entries_wave291() -> None:
    label_range = PDPageLabelRange()
    label_range.set_style(PDPageLabelRange.STYLE_DECIMAL)
    label_range.set_prefix("")
    label_range.set_start(1)

    assert label_range.has_style() is True
    assert label_range.has_prefix() is True
    assert label_range.has_start() is True
