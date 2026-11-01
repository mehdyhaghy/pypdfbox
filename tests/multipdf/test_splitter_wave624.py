from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.interactive.documentnavigation.destination import PDDestination

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


def test_wave624_fix_destinations_skips_host_not_in_destination_page_tree() -> None:
    chunk = _make_doc(1)
    host_source = COSDictionary()
    target_source = COSDictionary()
    target_dest = _dest_array(target_source)
    splitter = Splitter()
    splitter._dest_to_fix = [(PDDestination.create(target_dest), host_source)]
    splitter._page_dict_map = {
        id(host_source): COSDictionary(),
        id(target_source): chunk.get_page(0).get_cos_object(),
    }

    try:
        splitter._fix_destinations(chunk)

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
    splitter._page_dict_map = {id(source_page): cloned_page}
    splitter._annot_dict_map = {id(source_annot): cloned_annot}

    cloned = splitter._k_create_clone(objr, COSDictionary(), None, PageTree())

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

    assert Splitter()._k_create_clone(kids, COSDictionary(), None, PageTree()) is None


def test_wave624_clone_tree_element_ignores_missing_parent_tree_key() -> None:
    dst_numbers: dict[int, object] = {}

    Splitter()._clone_tree_element({}, dst_numbers, 99)

    assert dst_numbers == {}
