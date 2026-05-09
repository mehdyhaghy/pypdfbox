from __future__ import annotations

import logging

import pytest

from pypdfbox import PDDocument
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


def test_wave604_scrub_acroform_drops_signature_state_but_keeps_other_fields() -> None:
    doc = PDDocument()
    acroform = COSDictionary()
    acroform.set_item(_SIG_FLAGS, COSInteger.get(3))
    fields = COSArray()
    sig_field = COSDictionary()
    sig_field.set_item(_FT, COSName.get_pdf_name("Sig"))
    text_field = COSDictionary()
    text_field.set_item(_FT, COSName.get_pdf_name("Tx"))
    fields.add(sig_field)
    fields.add(text_field)
    acroform.set_item(_FIELDS, fields)
    doc.get_document_catalog().get_cos_object().set_item(_ACROFORM, acroform)

    try:
        Splitter()._scrub_acroform(doc)  # noqa: SLF001

        kept_fields = acroform.get_dictionary_object(_FIELDS)
        assert isinstance(kept_fields, COSArray)
        assert not acroform.contains_key(_SIG_FLAGS)
        assert kept_fields.size() == 1
        assert kept_fields.get_object(0) is text_field
        assert doc.get_document_catalog().get_cos_object().contains_key(_ACROFORM)
    finally:
        doc.close()


def test_wave604_scrub_acroform_removes_empty_signature_only_form() -> None:
    doc = PDDocument()
    acroform = COSDictionary()
    fields = COSArray()
    sig_field = COSDictionary()
    sig_field.set_item(_FT, COSName.get_pdf_name("Sig"))
    fields.add(sig_field)
    acroform.set_item(_FIELDS, fields)
    doc.get_document_catalog().get_cos_object().set_item(_ACROFORM, acroform)

    try:
        Splitter()._scrub_acroform(doc)  # noqa: SLF001

        assert not doc.get_document_catalog().get_cos_object().contains_key(_ACROFORM)
    finally:
        doc.close()


def test_wave604_signature_widget_detects_signature_value_by_byte_range() -> None:
    widget = COSDictionary()
    widget.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    sig_value = COSDictionary()
    sig_value.set_item(_BYTE_RANGE, COSArray())
    widget.set_item(_V, sig_value)

    assert Splitter._is_signature_widget(widget)  # noqa: SLF001


def test_wave604_clone_tree_array_preserves_mcid_holes_with_nulls() -> None:
    retained_src = COSDictionary()
    retained_clone = COSDictionary()
    dropped_src = COSDictionary()
    src_array = COSArray()
    src_array.add(retained_src)
    src_array.add(dropped_src)
    splitter = Splitter()
    splitter._struct_dict_map = {id(retained_src): retained_clone}  # noqa: SLF001
    dst_numbers: dict[int, object] = {}

    splitter._clone_tree_element({9: src_array}, dst_numbers, 9)  # noqa: SLF001

    cloned = dst_numbers[9]
    assert isinstance(cloned, COSArray)
    assert cloned.get_object(0) is retained_clone
    assert cloned.get(1) is COSNull.NULL


def test_wave604_clone_tree_element_warns_for_unexpected_number_tree_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.splitter"):
        Splitter()._clone_tree_element({7: COSInteger.get(4)}, {}, 7)  # noqa: SLF001

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

    Splitter()._remove_possible_orphan_annotation(  # noqa: SLF001
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
        Splitter()._remove_possible_orphan_annotation(  # noqa: SLF001
            source_annot, COSDictionary(), page, dst
        )

    assert not dst.contains_key(_OBJ)
    assert "isn't in the page" in caplog.text
