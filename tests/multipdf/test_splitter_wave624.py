from __future__ import annotations

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.multipdf import Splitter

_ANNOTS = COSName.get_pdf_name("Annots")
_FIT = COSName.get_pdf_name("Fit")
_FT = COSName.get_pdf_name("FT")
_K = COSName.get_pdf_name("K")
_OBJ = COSName.get_pdf_name("Obj")
_P = COSName.get_pdf_name("P")
_PG = COSName.get_pdf_name("Pg")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_TYPE = COSName.get_pdf_name("Type")


def _make_doc(page_count: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(page_count):
        doc.add_page(PDPage())
    return doc


def _dest_array(page_dict: COSDictionary) -> COSArray:
    dest = COSArray()
    dest.add(page_dict)
    dest.add(_FIT)
    return dest


def test_wave624_process_annotations_drops_signature_widget() -> None:
    source_page = PDPage()
    imported = PDPage()
    sig_widget = COSDictionary()
    sig_widget.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    sig_widget.set_item(_FT, COSName.get_pdf_name("Sig"))
    text_annot = COSDictionary()
    text_annot.set_item(_SUBTYPE, COSName.get_pdf_name("Text"))
    annots = COSArray()
    annots.add(sig_widget)
    annots.add(text_annot)
    imported.get_cos_object().set_item(_ANNOTS, annots)

    splitter = Splitter()
    splitter._process_annotations(source_page, imported)  # noqa: SLF001

    cloned_annots = imported.get_cos_object().get_dictionary_object(_ANNOTS)
    assert isinstance(cloned_annots, COSArray)
    assert cloned_annots.size() == 1
    assert cloned_annots.get_object(0) is not text_annot
    assert splitter._signatures_dropped is True  # noqa: SLF001


def test_wave624_fix_destinations_skips_host_not_in_destination_page_tree() -> None:
    chunk = _make_doc(1)
    host_source = COSDictionary()
    target_source = COSDictionary()
    target_dest = _dest_array(target_source)
    splitter = Splitter()
    splitter._dest_to_fix = [(target_dest, host_source)]  # noqa: SLF001
    splitter._page_dict_map = {  # noqa: SLF001
        id(host_source): COSDictionary(),
        id(target_source): chunk.get_page(0).get_cos_object(),
    }

    try:
        splitter._fix_destinations(chunk)  # noqa: SLF001

        assert target_dest.get_object(0) is target_source
    finally:
        chunk.close()


def test_wave624_k_clone_dictionary_rewrites_objr_annotation_reference() -> None:
    class PageTree:
        def index_of(self, page_dict: COSDictionary) -> int:
            return 0

    source_page = COSDictionary()
    cloned_page = COSDictionary()
    source_annot = COSDictionary()
    cloned_annot = COSDictionary()
    objr = COSDictionary()
    objr.set_item(_TYPE, COSName.get_pdf_name("OBJR"))
    objr.set_item(_OBJ, source_annot)
    objr.set_item(_PG, source_page)
    splitter = Splitter()
    splitter._page_dict_map = {id(source_page): cloned_page}  # noqa: SLF001
    splitter._annot_dict_map = {id(source_annot): cloned_annot}  # noqa: SLF001

    cloned = splitter._k_create_clone(objr, COSDictionary(), None, PageTree())  # noqa: SLF001

    assert isinstance(cloned, COSDictionary)
    assert cloned.get_dictionary_object(_OBJ) is cloned_annot
    assert cloned.get_dictionary_object(_PG) is cloned_page
    assert not cloned.contains_key(_P)


def test_wave624_k_clone_array_returns_none_when_all_children_are_dropped() -> None:
    class PageTree:
        def index_of(self, page_dict: COSDictionary) -> int:
            return -1

    source_page = COSDictionary()
    mcr = COSDictionary()
    mcr.set_item(_TYPE, COSName.get_pdf_name("MCR"))
    mcr.set_item(_PG, source_page)
    mcr.set_item(_K, COSInteger.get(0))
    kids = COSArray()
    kids.add(mcr)

    assert Splitter()._k_create_clone(kids, COSDictionary(), None, PageTree()) is None  # noqa: SLF001,E501


def test_wave624_clone_tree_element_ignores_missing_parent_tree_key() -> None:
    dst_numbers: dict[int, object] = {}

    Splitter()._clone_tree_element({}, dst_numbers, 99)  # noqa: SLF001

    assert dst_numbers == {}


def test_wave624_fix_destinations_nulls_empty_destination_array() -> None:
    chunk = _make_doc(1)
    host_source = COSDictionary()
    empty_dest = COSArray()
    splitter = Splitter()
    splitter._dest_to_fix = [(empty_dest, host_source)]  # noqa: SLF001
    splitter._page_dict_map = {  # noqa: SLF001
        id(host_source): chunk.get_page(0).get_cos_object()
    }

    try:
        splitter._fix_destinations(chunk)  # noqa: SLF001

        assert empty_dest.size() == 0
    finally:
        chunk.close()
