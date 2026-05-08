from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_marked_content import (
    PDMarkedContent,
)


def test_wave290_malformed_properties_fall_back_to_absent_values() -> None:
    properties = COSDictionary()
    properties.set_item(COSName.get_pdf_name("MCID"), COSName.get_pdf_name("bad"))
    properties.set_item(COSName.get_pdf_name("Lang"), COSInteger.get(1))
    properties.set_item(COSName.get_pdf_name("ActualText"), COSInteger.get(1))

    marked_content = PDMarkedContent(COSName.get_pdf_name("Span"), properties)

    assert marked_content.get_mcid() == -1
    assert marked_content.has_mcid() is False
    assert marked_content.get_language() is None
    assert marked_content.get_actual_text() is None


def test_wave332_lang_string_operand_matches_pdfbox_get_name_as_string() -> None:
    properties = COSDictionary()
    properties.set_item(COSName.get_pdf_name("Lang"), COSString("en-US"))

    marked_content = PDMarkedContent(COSName.get_pdf_name("Span"), properties)

    assert marked_content.get_language() == "en-US"
