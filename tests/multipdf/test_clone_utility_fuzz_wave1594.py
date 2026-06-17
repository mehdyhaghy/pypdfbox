"""Fuzz / parity hardening for ``PDFCloneUtility`` (wave 1594).

Hammers the deep-clone object-graph machinery of
``pypdfbox.multipdf.PDFCloneUtility`` against the behaviours of upstream
``org.apache.pdfbox.multipdf.PDFCloneUtility#cloneForNewDocument`` in
PDFBox 3.0.7:

* simple dict / array / stream deep-copy (distinct instance, same data),
* the ``clonedVersion`` identity map keeping shared subgraphs shared and
  collapsing cycles instead of recursing forever,
* indirect references (``COSObject``) followed to their target and the
  target cloned (never the wrapper),
* immutables (``COSName`` / ``COSInteger`` / ``COSString`` / ``COSFloat``
  / ``COSBoolean`` / ``COSNull``) returned verbatim,
* "don't clone a clone" short-circuit via the ``clonedValues`` set,
* cloning into the same document.

No real divergence was found while authoring these; they pin the current
parity-correct behaviour so a future refactor can't regress it.
"""

from __future__ import annotations

import random

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.multipdf import PDFCloneUtility
from pypdfbox.pdmodel import PDDocument


class _Wrap:
    """Minimal ``COSObjectable``-like wrapper for ``clone_merge``."""

    def __init__(self, base):
        self._b = base

    def get_cos_object(self):
        return self._b


# --------------------------------------------------------------------------
# simple deep-copy shape
# --------------------------------------------------------------------------


def test_simple_dict_is_distinct_instance():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        src = COSDictionary()
        src.set_name("Type", "Page")
        src.set_int("N", 9)
        clone = c.clone_for_new_document(src)
        assert clone is not src
        assert isinstance(clone, COSDictionary)
        assert clone.get_name("Type") == "Page"
        assert clone.get_int("N") == 9


def test_dict_clone_is_shallow_independent():
    """Mutating the clone must not touch the source dict."""
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        src = COSDictionary()
        src.set_name("Type", "Orig")
        clone = c.clone_for_new_document(src)
        clone.set_name("Type", "Changed")
        assert src.get_name("Type") == "Orig"


def test_simple_array_is_distinct_instance():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        src = COSArray()
        src.add(COSInteger.get(1))
        src.add(COSInteger.get(2))
        src.add(COSInteger.get(3))
        clone = c.clone_for_new_document(src)
        assert clone is not src
        assert isinstance(clone, COSArray)
        assert clone.size() == 3
        assert [clone.get_int(i) for i in range(3)] == [1, 2, 3]


def test_empty_dict_and_empty_array_clone():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        ed = c.clone_for_new_document(COSDictionary())
        ea = c.clone_for_new_document(COSArray())
        assert isinstance(ed, COSDictionary) and ed.size() == 0
        assert isinstance(ea, COSArray) and ea.size() == 0


# --------------------------------------------------------------------------
# stream cloning: dict + body bytes
# --------------------------------------------------------------------------


def test_stream_body_and_dict_copied():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        s = COSStream()
        s.set_name("Type", "XObject")
        s.set_name("Subtype", "Image")
        s.set_raw_data(b"\x01\x02\x03\xff payload")
        clone = c.clone_for_new_document(s)
        assert clone is not s
        assert isinstance(clone, COSStream)
        assert clone.get_name("Type") == "XObject"
        assert clone.get_name("Subtype") == "Image"
        assert clone.get_raw_data() == b"\x01\x02\x03\xff payload"


def test_stream_without_body_clones_header_only():
    """A header-only stream (no body buffer) must clone without raising."""
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        s = COSStream()
        s.set_name("Type", "XObject")
        assert s.has_data() is False
        clone = c.clone_for_new_document(s)
        assert isinstance(clone, COSStream)
        assert clone.get_name("Type") == "XObject"
        assert clone.get_raw_data() == b""


def test_stream_raw_bytes_not_reencoded():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        s = COSStream()
        s.set_name("Filter", "FlateDecode")
        raw = b"\x78\x9c\x4b\x4c\x4a\x06\x00\x02\x4d\x01\x27"
        s.set_raw_data(raw)
        clone = c.clone_for_new_document(s)
        assert clone.get_raw_data() == raw
        assert clone.get_name("Filter") == "FlateDecode"


def test_stream_clone_body_is_independent_copy():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        s = COSStream()
        s.set_raw_data(b"original-bytes")
        clone = c.clone_for_new_document(s)
        clone.set_raw_data(b"mutated")
        assert s.get_raw_data() == b"original-bytes"


def test_stream_nested_in_array_and_dict():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        st = COSStream()
        st.set_raw_data(b"q Q")
        arr = COSArray()
        arr.add(st)
        outer = COSDictionary()
        outer.set_item("Contents", arr)
        clone = c.clone_for_new_document(outer)
        cl_arr = clone.get_item("Contents")
        assert isinstance(cl_arr, COSArray)
        cl_st = cl_arr.get(0)
        assert isinstance(cl_st, COSStream)
        assert cl_st is not st
        assert cl_st.get_raw_data() == b"q Q"


# --------------------------------------------------------------------------
# shared-subgraph identity (clonedVersion map)
# --------------------------------------------------------------------------


def test_shared_dict_under_two_keys_cloned_once():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        shared = COSDictionary()
        shared.set_name("Tag", "S")
        parent = COSDictionary()
        parent.set_item("First", shared)
        parent.set_item("Second", shared)
        clone = c.clone_for_new_document(parent)
        assert clone.get_item("First") is clone.get_item("Second")
        assert clone.get_item("First") is not shared


def test_shared_array_across_branches_cloned_once():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        shared = COSArray()
        shared.add(COSInteger.get(1))
        a = COSDictionary()
        a.set_item("X", shared)
        b = COSDictionary()
        b.set_item("Y", shared)
        root = COSArray()
        root.add(a)
        root.add(b)
        clone = c.clone_for_new_document(root)
        assert clone.get(0).get_item("X") is clone.get(1).get_item("Y")


def test_repeat_clone_returns_same_dest_object():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        src = COSDictionary()
        src.set_name("Type", "R")
        first = c.clone_for_new_document(src)
        second = c.clone_for_new_document(src)
        assert first is second


def test_shared_target_across_distinct_cos_objects():
    """Two distinct ``COSObject`` wrappers around the SAME target dict must
    resolve to one clone (upstream ``shared_target_one_clone``)."""
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        target = COSDictionary()
        target.set_name("Type", "T")
        r1 = COSObject(1, 0, resolved=target)
        r2 = COSObject(2, 0, resolved=target)
        assert c.clone_for_new_document(r1) is c.clone_for_new_document(r2)


# --------------------------------------------------------------------------
# cyclic graphs terminate
# --------------------------------------------------------------------------


def test_dict_self_reference_terminates():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        d = COSDictionary()
        d.set_name("Type", "Cycle")
        d.set_item("Self", COSObject(5, 0, resolved=d))
        clone = c.clone_for_new_document(d)
        assert clone is not d
        assert clone.get_item("Self") is clone


def test_two_step_cycle_a_b_a_terminates():
    """A -> B -> (indirect) A: graph cycle must collapse, both cloned once."""
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        a = COSDictionary()
        a.set_name("Name", "A")
        b = COSDictionary()
        b.set_name("Name", "B")
        a.set_item("ToB", b)
        b.set_item("ToA", COSObject(7, 0, resolved=a))
        clone_a = c.clone_for_new_document(a)
        clone_b = clone_a.get_item("ToB")
        assert isinstance(clone_b, COSDictionary)
        assert clone_b.get_name("Name") == "B"
        # the indirect back-edge lands on the cloned A, not source A
        assert clone_b.get_item("ToA") is clone_a


def test_cycle_through_array_terminates():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        d = COSDictionary()
        d.set_name("Type", "Loop")
        arr = COSArray()
        d.set_item("Kids", arr)
        arr.add(COSObject(9, 0, resolved=d))
        clone = c.clone_for_new_document(d)
        cl_arr = clone.get_item("Kids")
        assert cl_arr.get(0) is clone


def test_array_direct_self_reference_terminates():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        a = COSArray()
        a.add(COSInteger.get(1))
        a.add(COSObject(4, 0, resolved=a))
        clone = c.clone_for_new_document(a)
        assert clone.size() == 2
        assert clone.get(1) is clone


def test_stream_self_reference_terminates():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        s = COSStream()
        s.set_raw_data(b"data")
        s.set_item("Me", COSObject(3, 0, resolved=s))
        clone = c.clone_for_new_document(s)
        assert clone.get_item("Me") is clone


def test_indirect_array_cycle_does_not_overflow():
    """Documented hardening divergence: an indirect cycle that loops back
    to an *array* ancestor (A=[1, B]; B=[ref->A]) terminates in pypdfbox
    (upstream PDFBox 3.0.7 throws StackOverflowError)."""
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        a = COSArray()
        a.add(COSInteger.get(1))
        b = COSArray()
        a.add(b)
        b.add(COSObject(8, 0, resolved=a))
        clone = c.clone_for_new_document(a)
        assert isinstance(clone, COSArray)
        cl_b = clone.get(1)
        assert isinstance(cl_b, COSArray)
        assert cl_b.get(0) is clone


# --------------------------------------------------------------------------
# indirect references (COSObject)
# --------------------------------------------------------------------------


def test_indirect_ref_followed_to_target():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        target = COSDictionary()
        target.set_name("Type", "Pages")
        clone = c.clone_for_new_document(COSObject(7, 0, resolved=target))
        assert isinstance(clone, COSDictionary)
        assert not isinstance(clone, COSObject)
        assert clone is not target
        assert clone.get_name("Type") == "Pages"


def test_double_indirection_followed():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        target = COSDictionary()
        target.set_name("Type", "Final")
        inner = COSObject(2, 0, resolved=target)
        outer = COSObject(1, 0, resolved=inner)
        clone = c.clone_for_new_document(outer)
        assert isinstance(clone, COSDictionary)
        assert clone.get_name("Type") == "Final"


def test_unresolvable_indirect_ref_dropped():
    """A COSObject resolving to None clones to None; its dict key drops out
    (upstream setItem(key, null) removes the key)."""
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        d = COSDictionary()
        d.set_item("Bad", COSObject(99, 0, resolved=None))
        d.set_int("Good", 1)
        clone = c.clone_for_new_document(d)
        assert clone.get_item("Bad") is None
        assert clone.get_int("Good") == 1


def test_indirect_ref_to_stream_clones_stream():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        st = COSStream()
        st.set_raw_data(b"streamdata")
        st.set_name("Type", "XObject")
        clone = c.clone_for_new_document(COSObject(12, 0, resolved=st))
        assert isinstance(clone, COSStream)
        assert clone.get_raw_data() == b"streamdata"


# --------------------------------------------------------------------------
# immutables / primitives returned verbatim
# --------------------------------------------------------------------------


def test_primitives_returned_same_instance():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        n = COSInteger.get(42)
        s = COSString("hello")
        name = COSName.get_pdf_name("Foo")
        f = COSFloat(1.5)
        assert c.clone_for_new_document(n) is n
        assert c.clone_for_new_document(s) is s
        assert c.clone_for_new_document(name) is name
        assert c.clone_for_new_document(f) is f


def test_null_and_boolean_singletons_returned_same():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        assert c.clone_for_new_document(COSNull.NULL) is COSNull.NULL
        assert c.clone_for_new_document(COSBoolean.TRUE) is COSBoolean.TRUE
        assert c.clone_for_new_document(COSBoolean.FALSE) is COSBoolean.FALSE


def test_name_inside_array_shared_not_copied():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        name = COSName.get_pdf_name("Bar")
        arr = COSArray()
        arr.add(name)
        clone = c.clone_for_new_document(arr)
        assert clone.get(0) is name


# --------------------------------------------------------------------------
# "don't clone a clone" + None
# --------------------------------------------------------------------------


def test_none_returns_none():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        assert c.clone_for_new_document(None) is None


def test_dont_clone_a_clone():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        d = COSDictionary()
        d.set_name("Type", "X")
        first = c.clone_for_new_document(d)
        assert c.clone_for_new_document(first) is first


def test_dont_clone_a_clone_array():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        a = COSArray()
        a.add(COSInteger.get(1))
        first = c.clone_for_new_document(a)
        assert c.clone_for_new_document(first) is first


# --------------------------------------------------------------------------
# same-document cloning
# --------------------------------------------------------------------------


def test_clone_into_same_document_catalog():
    with PDDocument() as doc:
        c = PDFCloneUtility(doc)
        catalog = doc.get_document_catalog().get_cos_object()
        clone = c.clone_for_new_document(catalog)
        assert clone is not catalog
        assert isinstance(clone, COSDictionary)


def test_get_destination_identity():
    with PDDocument() as doc:
        c = PDFCloneUtility(doc)
        assert c.get_destination() is doc


# --------------------------------------------------------------------------
# nested mixed graph
# --------------------------------------------------------------------------


def test_deeply_nested_mixed_graph():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        leaf = COSStream()
        leaf.set_raw_data(b"leaf")
        leaf.set_name("Subtype", "Form")
        mid_arr = COSArray()
        mid_arr.add(leaf)
        mid_arr.add(COSString("inner"))
        mid_dict = COSDictionary()
        mid_dict.set_item("Arr", mid_arr)
        mid_dict.set_int("Depth", 2)
        root = COSDictionary()
        root.set_item("Mid", mid_dict)
        root.set_name("Type", "Root")
        clone = c.clone_for_new_document(root)
        assert clone.get_name("Type") == "Root"
        cm = clone.get_item("Mid")
        assert cm is not mid_dict
        assert cm.get_int("Depth") == 2
        ca = cm.get_item("Arr")
        assert ca is not mid_arr
        cl_leaf = ca.get(0)
        assert isinstance(cl_leaf, COSStream)
        assert cl_leaf.get_raw_data() == b"leaf"
        # COSString interned/returned verbatim
        assert ca.get(1) is mid_arr.get(1)


@pytest.mark.parametrize("seed", range(8))
def test_random_graph_clones_without_error_and_is_distinct(seed):
    """Build a random acyclic dict/array/stream graph and assert the clone
    is a distinct top-level container preserving size."""
    rng = random.Random(seed)

    def build(depth):
        if depth <= 0:
            choice = rng.randint(0, 2)
            if choice == 0:
                return COSInteger.get(rng.randint(0, 100))
            if choice == 1:
                return COSName.get_pdf_name(f"N{rng.randint(0, 9)}")
            return COSString(f"s{rng.randint(0, 9)}")
        kind = rng.randint(0, 2)
        if kind == 0:
            d = COSDictionary()
            for k in range(rng.randint(0, 3)):
                d.set_item(f"K{k}", build(depth - 1))
            return d
        if kind == 1:
            a = COSArray()
            for _ in range(rng.randint(0, 3)):
                a.add(build(depth - 1))
            return a
        st = COSStream()
        st.set_raw_data(bytes(rng.randint(0, 255) for _ in range(rng.randint(0, 8))))
        st.set_int("Marker", rng.randint(0, 5))
        return st

    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        src = build(4)
        # ensure top is a container so size() is meaningful
        if not isinstance(src, COSDictionary | COSArray | COSStream):
            wrapper = COSArray()
            wrapper.add(src)
            src = wrapper
        clone = c.clone_for_new_document(src)
        assert clone is not src
        assert type(clone) is type(src)
        if isinstance(src, COSArray | COSDictionary):
            assert clone.size() == src.size()


# --------------------------------------------------------------------------
# clone_merge
# --------------------------------------------------------------------------


def test_clone_merge_appends_array_items():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        src = COSArray()
        src.add(COSInteger.get(1))
        src.add(COSInteger.get(2))
        tgt = COSArray()
        tgt.add(COSInteger.get(99))
        c.clone_merge(_Wrap(src), _Wrap(tgt))
        assert [tgt.get_int(i) for i in range(tgt.size())] == [99, 1, 2]


def test_clone_merge_same_cos_is_noop():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        a = COSArray()
        a.add(COSInteger.get(1))
        c.clone_merge(_Wrap(a), _Wrap(a))
        assert a.size() == 1


def test_clone_merge_dict_adds_missing_preserves_existing():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        src = COSDictionary()
        src.set_name("New", "V")
        src.set_name("Shared", "FromSrc")
        tgt = COSDictionary()
        tgt.set_name("Shared", "FromTgt")
        c.clone_merge(_Wrap(src), _Wrap(tgt))
        assert tgt.get_name("New") == "V"
        assert tgt.get_name("Shared") == "FromTgt"


def test_clone_merge_recurses_into_shared_subdict():
    with PDDocument() as dst:
        c = PDFCloneUtility(dst)
        si = COSDictionary()
        si.set_name("A", "1")
        sd = COSDictionary()
        sd.set_item("Inner", si)
        ti = COSDictionary()
        ti.set_name("B", "2")
        td = COSDictionary()
        td.set_item("Inner", ti)
        c.clone_merge(_Wrap(sd), _Wrap(td))
        inner = td.get_item("Inner")
        assert inner.get_name("A") == "1"
        assert inner.get_name("B") == "2"
