import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNull
from pypdfbox.multipdf import Splitter

_ACROFORM = COSName.get_pdf_name("AcroForm")
_ANNOTS = COSName.get_pdf_name("Annots")
_DEST = COSName.get_pdf_name("Dest")
_FIELDS = COSName.get_pdf_name("Fields")
_FT = COSName.get_pdf_name("FT")
_PARENT = COSName.get_pdf_name("Parent")
_SIG_FLAGS = COSName.get_pdf_name("SigFlags")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_T = COSName.get_pdf_name("T")
_TYPE = COSName.get_pdf_name("Type")


def _make_doc(page_count: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(page_count):
        doc.add_page(PDPage())
    return doc


def _close_all(source: PDDocument, chunks: list[PDDocument]) -> None:
    for chunk in chunks:
        chunk.close()
    source.close()


def _annotation(subtype: str) -> COSDictionary:
    annot = COSDictionary()
    annot.set_item(_TYPE, COSName.get_pdf_name("Annot"))
    annot.set_item(_SUBTYPE, COSName.get_pdf_name(subtype))
    return annot


def test_wave403_invalid_page_configuration_rejects_non_positive_values() -> None:
    splitter = Splitter()

    with pytest.raises(ValueError, match="Number of pages"):
        splitter.set_split_at_page(0)
    with pytest.raises(ValueError, match="Start page"):
        splitter.set_start_page(0)
    with pytest.raises(ValueError, match="End page"):
        splitter.set_end_page(0)
    splitter.set_start_page(3)
    with pytest.raises(ValueError, match="startPage"):
        splitter.set_end_page(2)


def test_wave403_split_honors_start_end_range_and_split_length() -> None:
    source = _make_doc(5)
    splitter = Splitter().set_start_page(2).set_end_page(4).set_split_at_page(2)

    chunks = splitter.split(source)

    assert [chunk.get_number_of_pages() for chunk in chunks] == [2, 1]
    _close_all(source, chunks)


def test_wave403_cross_chunk_direct_link_destination_is_nulled() -> None:
    source = _make_doc(2)
    pages = list(source.get_pages())
    dest = COSArray()
    dest.add(pages[1].get_cos_object())
    dest.add(COSName.get_pdf_name("Fit"))
    link = _annotation("Link")
    link.set_item(_DEST, dest)
    annots = COSArray()
    annots.add(link)
    pages[0].get_cos_object().set_item(_ANNOTS, annots)

    chunks = Splitter().split(source)

    cloned_annots = chunks[0].get_page(0).get_cos_object().get_dictionary_object(_ANNOTS)
    assert isinstance(cloned_annots, COSArray)
    cloned_link = cloned_annots.get_object(0)
    assert isinstance(cloned_link, COSDictionary)
    cloned_dest = cloned_link.get_dictionary_object(_DEST)
    assert isinstance(cloned_dest, COSArray)
    assert cloned_dest.get(0) is COSNull.NULL
    _close_all(source, chunks)


def test_wave403_widget_parent_is_removed_while_non_signature_widget_kept() -> None:
    imported = PDPage()
    parent = COSDictionary()
    parent.set_item(_FT, COSName.get_pdf_name("Tx"))
    widget = _annotation("Widget")
    widget.set_item(_PARENT, parent)
    annots = COSArray()
    annots.add(widget)
    imported.get_cos_object().set_item(_ANNOTS, annots)

    Splitter()._process_annotations(imported)

    cloned_annots = imported.get_cos_object().get_dictionary_object(_ANNOTS)
    assert isinstance(cloned_annots, COSArray)
    cloned_widget = cloned_annots.get_object(0)
    assert isinstance(cloned_widget, COSDictionary)
    assert not cloned_widget.contains_key(_PARENT)
