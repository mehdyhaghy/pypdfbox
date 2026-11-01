import logging

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSNull
from pypdfbox.multipdf import Splitter

_ACROFORM = COSName.get_pdf_name("AcroForm")
_ANNOTS = COSName.get_pdf_name("Annots")
_BYTE_RANGE = COSName.get_pdf_name("ByteRange")
_FIELDS = COSName.get_pdf_name("Fields")
_FT = COSName.get_pdf_name("FT")
_OBJ = COSName.get_pdf_name("Obj")
_SIG_FLAGS = COSName.get_pdf_name("SigFlags")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_TYPE = COSName.get_pdf_name("Type")
_V = COSName.get_pdf_name("V")


def test_wave604_clone_tree_array_preserves_mcid_holes_with_nulls() -> None:
    retained_src = COSDictionary()
    retained_clone = COSDictionary()
    dropped_src = COSDictionary()
    src_array = COSArray()
    src_array.add(retained_src)
    src_array.add(dropped_src)
    splitter = Splitter()
    splitter._struct_dict_map = {id(retained_src): retained_clone}
    dst_numbers: dict[int, object] = {}

    splitter._clone_tree_element({9: src_array}, dst_numbers, 9)

    cloned = dst_numbers[9]
    assert isinstance(cloned, COSArray)
    assert cloned.get_object(0) is retained_clone
    assert cloned.get(1) is COSNull.NULL


def test_wave604_clone_tree_element_warns_for_unexpected_number_tree_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.splitter"):
        Splitter()._clone_tree_element({7: COSInteger.get(4)}, {}, 7)

    assert "tree element neither dictionary nor array" in caplog.text


def test_wave604_remove_possible_orphan_annotation_keeps_annotation_on_page() -> None:
    source_annot = COSDictionary()
    source_annot.set_item(_TYPE, COSName.get_pdf_name("Annot"))
    page = COSDictionary()
    annots = COSArray()
    annots.add(source_annot)
    page.set_item(_ANNOTS, annots)
    dst = COSDictionary()
    dst.set_item(_OBJ, source_annot)

    Splitter()._remove_possible_orphan_annotation(
        source_annot, COSDictionary(), page, dst
    )

    assert dst.get_dictionary_object(_OBJ) is source_annot


def test_wave604_remove_possible_orphan_annotation_removes_missing_page_annotation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source_annot = COSDictionary()
    source_annot.set_item(_SUBTYPE, COSName.get_pdf_name("Link"))
    page = COSDictionary()
    page.set_item(_ANNOTS, COSArray())
    dst = COSDictionary()
    dst.set_item(_OBJ, source_annot)

    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.splitter"):
        Splitter()._remove_possible_orphan_annotation(
            source_annot, COSDictionary(), page, dst
        )

    assert not dst.contains_key(_OBJ)
    assert "isn't in the page" in caplog.text
