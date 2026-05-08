from __future__ import annotations

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSStream
from pypdfbox.multipdf import LayerUtility


def _make_doc_with_content() -> PDDocument:
    doc = PDDocument()
    page = PDPage()
    stream = COSStream()
    stream.set_raw_data(b"q Q\n")
    page.set_contents(stream)
    doc.add_page(page)
    return doc


def test_wave313_append_form_as_layer_bumps_document_to_pdf_15() -> None:
    source = _make_doc_with_content()
    target = _make_doc_with_content()
    util = LayerUtility(target)

    form = util.import_page_as_form(source, 0)
    util.append_form_as_layer(target.get_page(0), form, None, "wave313")

    assert target.get_version() == 1.5

    source.close()
    target.close()


def test_wave313_append_form_as_layer_does_not_downgrade_newer_pdf() -> None:
    source = _make_doc_with_content()
    target = _make_doc_with_content()
    target.set_version(1.7)
    util = LayerUtility(target)

    form = util.import_page_as_form(source, 0)
    util.append_form_as_layer(target.get_page(0), form, None, "wave313")

    assert target.get_version() == 1.7

    source.close()
    target.close()
