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


# --- ArrayEntry delegation in get_child -----------------------------------


def test_array_entry_get_child_delegates() -> None:
    inner = COSArray()
    inner.add(COSInteger.get(11))
    ae = ArrayEntry()
    ae.set_value(inner)
    model = PDFTreeModel()
    child = model.get_child(ae, 0)
    assert isinstance(child, ArrayEntry)
    assert child.get_value().int_value() == 11


# --- XrefEntries / XrefEntry / PageEntry / COSObject branches -------------


def test_xref_entries_navigation() -> None:
    doc = PDDocument()
    try:
        xrefs = XrefEntries(doc)
        model = PDFTreeModel(xrefs)
        count = model.get_child_count(xrefs)
        assert count >= 0  # may legitimately be zero on a fresh doc
        if count > 0:
            child = model.get_child(xrefs, 0)
            assert model.get_index_of_child(xrefs, child) == 0
            # XrefEntry has count == 1 + child resolves to its target.
            assert model.get_child_count(child) == 1
    finally:
        doc.close()


def test_page_entry_get_child_delegates_to_dict() -> None:
    doc = PDDocument()
    doc.add_page(PDPage())
    try:
        entry = DocumentEntry(doc, "x.pdf")
        page_entry = entry.get_page(0)
        assert isinstance(page_entry, PageEntry)
        model = PDFTreeModel(entry)
        count = model.get_child_count(page_entry)
        assert count > 0  # delegates to the underlying COSDictionary
        child = model.get_child(page_entry, 0)
        assert isinstance(child, MapEntry)
        # And ``get_index_of_child`` delegates likewise.
        assert model.get_index_of_child(page_entry, child) == 0
    finally:
        doc.close()


def test_cos_object_unwraps_in_get_child() -> None:
    target = COSInteger.get(123)
    obj = COSObject(2, 0, resolved=target)
    model = PDFTreeModel()
    assert model.get_child(obj, 0) is target
    assert model.get_index_of_child(obj, target) == 0


def test_xref_entry_get_child_returns_array_entry() -> None:
    from pypdfbox.cos import COSObjectKey
    from pypdfbox.debugger.ui import XrefEntry

    target = COSInteger.get(42)
    cos_obj = COSObject(3, 0, resolved=target)
    xe = XrefEntry(0, COSObjectKey(3, 0), 100, cos_obj)
    model = PDFTreeModel()
    child = model.get_child(xe, 0)
    assert isinstance(child, ArrayEntry)
    assert child.get_value() is target


# --- is_leaf branches ------------------------------------------------------


def test_is_leaf_for_xref_entry_unwraps() -> None:
    from pypdfbox.cos import COSObjectKey
    from pypdfbox.debugger.ui import XrefEntry

    cos_obj = COSObject(4, 0, resolved=COSInteger.get(0))
    xe = XrefEntry(0, COSObjectKey(4, 0), 50, cos_obj)
    model = PDFTreeModel()
    # XrefEntry → its COSObject → leaf check uses the wrapped object.
    assert model.is_leaf(xe) is False  # COSObject is not a leaf


def test_is_leaf_for_map_entry_unwraps() -> None:
    me = MapEntry()
    me.set_key(COSName.get_pdf_name("K"))
    me.set_value(COSInteger.get(5))
    model = PDFTreeModel()
    assert model.is_leaf(me) is True


def test_is_leaf_for_array_entry_unwraps() -> None:
    ae = ArrayEntry()
    ae.set_value(COSInteger.get(5))
    model = PDFTreeModel()
    assert model.is_leaf(ae) is True


def test_get_index_of_child_for_cos_array_with_array_entry() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(1))
    model = PDFTreeModel()
    child = model.get_child(arr, 0)
    assert isinstance(child, ArrayEntry)
    assert model.get_index_of_child(arr, child) == 0


def test_get_index_of_child_raises_for_unknown_type() -> None:
    model = PDFTreeModel()
    with pytest.raises(ValueError):
        model.get_index_of_child("bogus parent", "bogus child")


def test_get_child_count_for_unknown_type_returns_zero() -> None:
    model = PDFTreeModel()
    # The unknown-type branch returns 0 rather than raising — mirrors upstream.
    assert model.get_child_count("not a cos object") == 0


def test_get_index_of_child_for_dict_with_non_map_entry() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Foo"), COSInteger.get(1))
    model = PDFTreeModel()
    # A non-MapEntry child resolves to -1.
    assert model.get_index_of_child(d, COSInteger.get(1)) == -1


# --- additional branches for parity coverage ------------------------------


def test_get_index_of_child_for_cos_array_with_raw_child() -> None:
    """When the child isn't an ArrayEntry, the model delegates to
    ``COSArray.index_of``."""
    arr = COSArray()
    target = COSInteger.get(7)
    arr.add(COSInteger.get(1))
    arr.add(target)
    model = PDFTreeModel()
    # ``target`` is a raw COSBase, not an ArrayEntry → exercises line 125.
    assert model.get_index_of_child(arr, target) == 1


def test_get_index_of_child_for_dict_with_unknown_key_returns_minus_one() -> None:
    """When the MapEntry key isn't in the dict, the search returns -1."""
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("A"), COSInteger.get(1))
    model = PDFTreeModel()
    foreign = MapEntry()
    foreign.set_key(COSName.get_pdf_name("Z"))
    foreign.set_value(COSInteger.get(99))
    # /Z is not in the parent → the keys-loop falls off the end → -1.
    assert model.get_index_of_child(d, foreign) == -1


def test_get_index_of_child_through_map_entry_delegates_to_value() -> None:
    """A MapEntry-wrapped parent delegates the index lookup to its value."""
    inner = COSArray()
    target = COSInteger.get(42)
    inner.add(target)
    me = MapEntry()
    me.set_key(COSName.get_pdf_name("Wrap"))
    me.set_value(inner)
    model = PDFTreeModel()
    assert model.get_index_of_child(me, target) == 0


def test_get_index_of_child_through_array_entry_delegates_to_value() -> None:
    """An ArrayEntry-wrapped parent delegates the index lookup to its value."""
    inner = COSArray()
    target = COSInteger.get(42)
    inner.add(target)
    ae = ArrayEntry()
    ae.set_value(inner)
    model = PDFTreeModel()
    assert model.get_index_of_child(ae, target) == 0


def _build_xref_entries_with_entry() -> XrefEntries:
    """Construct a working ``XrefEntries`` with at least one row."""
    from pypdfbox.cos import COSInteger as _CI
    from pypdfbox.cos import COSObjectKey
    from pypdfbox.pdmodel import PDDocument as _PDDocument

    doc = _PDDocument()
    cos_doc = doc.get_document()
    key = COSObjectKey(99, 0)
    cos_doc.add_xref_table({key: 1234})
    # Populate the object pool so XrefEntries.get_xref_entry returns a wrapped value.
    cos_doc.get_object_from_pool(key).set_object(_CI.get(7))
    return XrefEntries(doc)


def test_xref_entries_get_child_and_index_of_child_branches() -> None:
    """Exercise the XrefEntries / XrefEntry branches in get_child &
    get_index_of_child & get_child_count."""
    xrefs = _build_xref_entries_with_entry()
    model = PDFTreeModel(xrefs)
    assert model.get_child_count(xrefs) == 1
    xe = model.get_child(xrefs, 0)
    # get_index_of_child for XrefEntries reads the child's own index.
    assert model.get_index_of_child(xrefs, xe) == 0
    # XrefEntry as parent: child count is always 1, index is always 0.
    assert model.get_child_count(xe) == 1
    inner_child = model.get_child(xe, 0)
    assert model.get_index_of_child(xe, inner_child) == 0
