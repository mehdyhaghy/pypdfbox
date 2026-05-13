"""Hand-written tests for ``pypdfbox.debugger.ui.PDFTreeModel``."""

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSObject,
)
from pypdfbox.debugger.ui import (
    ArrayEntry,
    DocumentEntry,
    MapEntry,
    PageEntry,
    PDFTreeModel,
    XrefEntries,
)
from pypdfbox.pdmodel import PDDocument, PDPage

# --- root selection --------------------------------------------------------


def test_root_defaults_to_none() -> None:
    assert PDFTreeModel().get_root() is None


def test_root_from_document_entry() -> None:
    doc = PDDocument()
    try:
        entry = DocumentEntry(doc, "x.pdf")
        model = PDFTreeModel(entry)
        assert model.get_root() is entry
    finally:
        doc.close()


def test_root_from_xref_entries() -> None:
    doc = PDDocument()
    try:
        xrefs = XrefEntries(doc)
        model = PDFTreeModel(xrefs)
        assert model.get_root() is xrefs
    finally:
        doc.close()


def test_root_from_pddocument_is_trailer() -> None:
    doc = PDDocument()
    try:
        model = PDFTreeModel(doc)
        assert model.get_root() is doc.get_document().get_trailer()
    finally:
        doc.close()


# --- COSArray children -----------------------------------------------------


def test_cos_array_children() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(1))
    arr.add(COSInteger.get(2))
    model = PDFTreeModel()
    assert model.get_child_count(arr) == 2
    child = model.get_child(arr, 1)
    assert isinstance(child, ArrayEntry)
    assert child.get_index() == 1
    assert child.get_value().int_value() == 2


# --- COSDictionary children ------------------------------------------------


def test_cos_dictionary_children_sorted_by_key() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Z"), COSInteger.get(26))
    d.set_item(COSName.get_pdf_name("A"), COSInteger.get(1))
    d.set_item(COSName.get_pdf_name("M"), COSInteger.get(13))
    model = PDFTreeModel()
    assert model.get_child_count(d) == 3

    first = model.get_child(d, 0)
    assert isinstance(first, MapEntry)
    assert first.get_key().get_name() == "A"
    assert first.get_value().int_value() == 1

    last = model.get_child(d, 2)
    assert last.get_key().get_name() == "Z"


# --- MapEntry / ArrayEntry delegation -------------------------------------


def test_map_entry_delegates_to_value() -> None:
    inner = COSArray()
    inner.add(COSInteger.get(10))
    me = MapEntry()
    me.set_key(COSName.get_pdf_name("Container"))
    me.set_value(inner)
    model = PDFTreeModel()
    assert model.get_child_count(me) == 1
    child = model.get_child(me, 0)
    assert isinstance(child, ArrayEntry)
    assert child.get_value().int_value() == 10


def test_array_entry_delegates_to_value() -> None:
    inner = COSArray()
    inner.add(COSInteger.get(5))
    ae = ArrayEntry()
    ae.set_value(inner)
    model = PDFTreeModel()
    assert model.get_child_count(ae) == 1


# --- index_of_child / leaves ----------------------------------------------


def test_get_index_of_child_for_dict() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Foo"), COSInteger.get(1))
    d.set_item(COSName.get_pdf_name("Bar"), COSInteger.get(2))
    model = PDFTreeModel()
    foo_child = model.get_child(d, 1)
    assert model.get_index_of_child(d, foo_child) == 1


def test_get_index_of_child_returns_minus_one_for_none() -> None:
    model = PDFTreeModel()
    assert model.get_index_of_child(None, COSInteger.get(1)) == -1
    assert model.get_index_of_child(COSArray(), None) == -1


def test_is_leaf() -> None:
    model = PDFTreeModel()
    assert model.is_leaf(COSInteger.get(1)) is True
    assert model.is_leaf(COSArray()) is False
    assert model.is_leaf(COSDictionary()) is False


def test_get_child_unknown_type_raises() -> None:
    with pytest.raises(ValueError):
        PDFTreeModel().get_child("not a cos object", 0)


# --- DocumentEntry / page navigation ---------------------------------------


def test_document_entry_navigation() -> None:
    doc = PDDocument()
    doc.add_page(PDPage())
    doc.add_page(PDPage())
    try:
        entry = DocumentEntry(doc, "x.pdf")
        model = PDFTreeModel(entry)
        assert model.get_child_count(entry) == 2
        first = model.get_child(entry, 0)
        assert isinstance(first, PageEntry)
        assert model.get_index_of_child(entry, first) == 0
    finally:
        doc.close()


# --- COSObject as parent ---------------------------------------------------


def test_cos_object_parent() -> None:
    target = COSInteger.get(7)
    obj = COSObject(1, 0, resolved=target)
    model = PDFTreeModel()
    assert model.get_child_count(obj) == 1
    assert model.get_child(obj, 0) is target


# --- write side ------------------------------------------------------------


def test_value_for_path_changed_is_noop() -> None:
    PDFTreeModel().value_for_path_changed(("dummy",), None)
