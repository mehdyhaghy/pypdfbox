from __future__ import annotations

import logging

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.multipdf import Splitter

_B = COSName.get_pdf_name("B")
_FT = COSName.get_pdf_name("FT")
_K = COSName.get_pdf_name("K")
_OBJ = COSName.get_pdf_name("Obj")
_P = COSName.get_pdf_name("P")
_PARENT = COSName.get_pdf_name("Parent")
_PG = COSName.get_pdf_name("Pg")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_TYPE = COSName.get_pdf_name("Type")


def _make_doc(page_count: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(page_count):
        doc.add_page(PDPage())
    return doc


def test_wave564_split_with_range_outside_document_returns_no_chunks() -> None:
    source = _make_doc(2)

    chunks = Splitter().set_start_page(3).split(source)

    try:
        assert chunks == []
    finally:
        source.close()


def test_wave564_process_page_removes_bead_entry_from_imported_page() -> None:
    source = _make_doc(1)
    source.get_page(0).get_cos_object().set_item(_B, COSArray())

    chunks = Splitter().split(source)

    try:
        imported = chunks[0].get_page(0).get_cos_object()
        assert not imported.contains_key(_B)
        assert source.get_page(0).get_cos_object().contains_key(_B)
    finally:
        for chunk in chunks:
            chunk.close()
        source.close()


def test_wave564_signature_widget_parent_cycle_does_not_loop() -> None:
    widget = COSDictionary()
    widget.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    parent = COSDictionary()
    grandparent = COSDictionary()
    widget.set_item(_PARENT, parent)
    parent.set_item(_PARENT, grandparent)
    grandparent.set_item(_PARENT, parent)

    assert not Splitter._is_signature_widget(widget)  # noqa: SLF001


def test_wave564_signature_widget_parent_chain_detects_sig_field() -> None:
    widget = COSDictionary()
    widget.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    parent = COSDictionary()
    grandparent = COSDictionary()
    grandparent.set_item(_FT, COSName.get_pdf_name("Sig"))
    parent.set_item(_PARENT, grandparent)
    widget.set_item(_PARENT, parent)

    assert Splitter._is_signature_widget(widget)  # noqa: SLF001


def test_wave564_objr_without_payload_is_dropped() -> None:
    class PageTree:
        def index_of(self, page_dict: COSDictionary) -> int:
            return 0

    objr = COSDictionary()
    objr.set_item(_TYPE, COSName.get_pdf_name("OBJR"))
    objr.set_item(_OBJ, COSDictionary())

    cloned = Splitter()._k_create_clone(  # noqa: SLF001
        objr, COSDictionary(), COSDictionary(), PageTree()
    )

    assert cloned is None


def test_wave564_mcr_with_inherited_page_is_retained() -> None:
    parent_page = COSDictionary()
    parent = COSDictionary()
    parent.set_item(_PG, parent_page)
    mcr = COSDictionary()
    mcr.set_item(_TYPE, COSName.get_pdf_name("MCR"))
    mcr.set_item(_K, COSInteger.get(3))

    cloned = Splitter()._k_create_clone(  # noqa: SLF001
        mcr, parent, parent_page, object()
    )

    assert isinstance(cloned, COSDictionary)
    assert cloned.get_dictionary_object(_P) is None
    assert cloned.get_dictionary_object(_K).int_value() == 3


def test_wave564_clone_tree_element_warns_for_unretained_dictionary(
    caplog: pytest.LogCaptureFixture,
) -> None:
    splitter = Splitter()
    dst_numbers: dict[int, object] = {}

    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.splitter"):
        splitter._clone_tree_element({4: COSDictionary()}, dst_numbers, 4)  # noqa: SLF001

    assert dst_numbers == {}
    assert "ParentTree index 4 dictionary not found" in caplog.text
