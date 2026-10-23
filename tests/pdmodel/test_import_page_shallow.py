"""``PDDocument.import_page`` follows upstream ``importPage``: a shallow
page-dictionary copy, re-embedded FlateDecode contents and resolved
page geometry, with no AcroForm side effects."""

import logging

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_N = COSName.get_pdf_name


def _stream(payload: bytes) -> COSStream:
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(payload)
    return stream


def _decoded(stream: COSStream) -> bytes:
    with stream.create_input_stream() as src:
        return src.read()


def test_resources_and_annots_are_shared_with_source() -> None:
    src = PDDocument()
    page = PDPage()
    resources = COSDictionary()
    annots = COSArray([COSDictionary()])
    page.get_cos_object().set_item(_N("Resources"), resources)
    page.get_cos_object().set_item(_N("Annots"), annots)
    src.add_page(page)

    dst = PDDocument()
    imported = dst.import_page(page)

    imported_dict = imported.get_cos_object()
    assert imported_dict is not page.get_cos_object()
    assert imported_dict.get_dictionary_object(_N("Resources")) is resources
    assert imported_dict.get_dictionary_object(_N("Annots")) is annots
    assert dst.get_number_of_pages() == 1
    assert imported_dict.get_dictionary_object(_N("Parent")) is (
        dst.get_pages().get_cos_object()
    )
    # The source page still belongs to the source tree.
    assert page.get_cos_object().get_dictionary_object(_N("Parent")) is (
        src.get_pages().get_cos_object()
    )


def test_contents_array_becomes_one_flate_stream() -> None:
    src = PDDocument()
    page = PDPage()
    page.get_cos_object().set_item(
        _N("Contents"), COSArray([_stream(b"q"), _stream(b"Q")])
    )
    src.add_page(page)

    imported = PDDocument().import_page(page)

    contents = imported.get_cos_object().get_dictionary_object(_N("Contents"))
    assert isinstance(contents, COSStream)
    assert contents.get_dictionary_object(_N("Filter")) == COSName.FLATE_DECODE
    # upstream PDPage.getContents appends a newline after each array entry
    assert _decoded(contents) == b"q\nQ\n"


def test_single_contents_stream_is_reencoded_without_delimiter() -> None:
    src = PDDocument()
    page = PDPage()
    original = _stream(b"0 0 m")
    page.get_cos_object().set_item(_N("Contents"), original)
    src.add_page(page)

    imported = PDDocument().import_page(page)

    contents = imported.get_cos_object().get_dictionary_object(_N("Contents"))
    assert contents is not original
    assert _decoded(contents) == b"0 0 m"


def test_inherited_geometry_is_materialized() -> None:
    src = PDDocument()
    page = PDPage()
    src.add_page(page)
    page.get_cos_object().remove_item(_N("MediaBox"))
    tree = src.get_pages().get_cos_object()
    tree.set_item(_N("MediaBox"), PDRectangle(0, 0, 200, 300).to_cos_array())
    tree.set_item(_N("Rotate"), COSInteger.get(90))

    imported = PDDocument().import_page(page)

    imported_dict = imported.get_cos_object()
    assert imported.get_media_box().get_height() == 300
    assert imported_dict.contains_key(_N("MediaBox"))
    assert imported_dict.contains_key(_N("CropBox"))
    assert imported_dict.get_int(_N("Rotate")) == 90


def test_inherited_resources_are_not_imported(caplog) -> None:
    src = PDDocument()
    page = PDPage()
    src.add_page(page)
    page.get_cos_object().remove_item(_N("Resources"))
    src.get_pages().get_cos_object().set_item(_N("Resources"), COSDictionary())

    with caplog.at_level(logging.WARNING):
        imported = PDDocument().import_page(page)

    assert not imported.get_cos_object().contains_key(_N("Resources"))
    assert "inherited resources" in caplog.text


def test_widget_fields_are_not_promoted_to_acroform() -> None:
    src = PDDocument()
    page = PDPage()
    field = COSDictionary()
    field.set_item(_N("FT"), _N("Tx"))
    widget = COSDictionary()
    widget.set_item(_N("Subtype"), _N("Widget"))
    widget.set_item(_N("Parent"), field)
    page.get_cos_object().set_item(_N("Annots"), COSArray([widget]))
    src.add_page(page)

    dst = PDDocument()
    dst.import_page(page)

    catalog = dst.get_document_catalog().get_cos_object()
    assert not catalog.contains_key(_N("AcroForm"))
