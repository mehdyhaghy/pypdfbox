from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

_FONT = COSName.get_pdf_name("Font")
_F0 = COSName.get_pdf_name("F0")
_F1 = COSName.get_pdf_name("F1")
_PARENT = COSName.get_pdf_name("Parent")
_RESOURCES = COSName.get_pdf_name("Resources")
_TYPE = COSName.get_pdf_name("Type")
_PAGE = COSName.get_pdf_name("Page")


def test_wave319_content_stream_reuses_inherited_resources_without_shadowing() -> None:
    parent_resources = COSDictionary()
    parent_fonts = COSDictionary()
    inherited_font = COSDictionary()
    parent_fonts.set_item(_F0, inherited_font)
    parent_resources.set_item(_FONT, parent_fonts)

    parent = COSDictionary()
    parent.set_item(_RESOURCES, parent_resources)
    page_dict = COSDictionary()
    page_dict.set_item(_TYPE, _PAGE)
    page_dict.set_item(_PARENT, parent)
    page = PDPage(page_dict)

    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")

    with PDDocument() as document, PDPageContentStream(document, page) as content:
        content.begin_text()
        content.set_font(font, 12)
        content.show_text("Hi")
        content.end_text()

    assert page.get_cos_object().get_dictionary_object(_RESOURCES) is None
    assert page.get_resources().get_cos_object() is parent_resources
    assert parent_fonts.get_dictionary_object(_F0) is inherited_font
    assert parent_fonts.get_dictionary_object(_F1) is font.get_cos_object()
    assert page.get_contents() == b"BT\n/F1 12 Tf\n(Hi) Tj\nET\n"
