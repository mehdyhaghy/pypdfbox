import io

from pypdfbox.loader import Loader
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_resources import PDResources


def _two_pages_one_font() -> bytes:
    doc = PDDocument()
    font = PDFontFactory.create_default_font(Standard14Fonts.FontName.HELVETICA.value)
    resources = PDResources()
    resources.add(font)
    for text in ("one", "two"):
        page = PDPage()
        page.set_resources(resources)
        doc.add_page(page)
        cs = PDPageContentStream(doc, page)
        cs.begin_text()
        cs.set_font(font, 12)
        cs.show_text(text)
        cs.end_text()
        cs.close()
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def test_pages_carry_document_resource_cache() -> None:
    doc = PDDocument(Loader.load_pdf(_two_pages_one_font()))
    try:
        cache = doc.get_resource_cache()
        assert cache is not None
        pages = doc.get_pages()
        assert pages.get(0).get_resource_cache() is cache
        assert all(p.get_resource_cache() is cache for p in pages)
        assert pages.get(1).get_resources().get_resource_cache() is cache
    finally:
        doc.close()


def test_indirect_font_shared_across_pages() -> None:
    doc = PDDocument(Loader.load_pdf(_two_pages_one_font()))
    try:
        fonts = []
        for page in doc.get_pages():
            res = page.get_resources()
            (name,) = list(res.get_font_names())
            fonts.append(res.get_font(name))
        assert fonts[0] is fonts[1]
    finally:
        doc.close()


def test_page_tree_without_document_has_no_cache() -> None:
    doc = PDDocument()
    doc.add_page(PDPage())
    from pypdfbox.pdmodel.pd_page_tree import PDPageTree

    pages_dict = doc.get_document_catalog().get_cos_object().get_dictionary_object("Pages")
    tree = PDPageTree(pages_dict)
    assert tree.get(0).get_resource_cache() is None
    assert all(p.get_resource_cache() is None for p in tree)
