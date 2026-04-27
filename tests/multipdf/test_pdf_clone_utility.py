from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.multipdf import PDFCloneUtility
from pypdfbox.pdmodel import PDDocument


def test_clone_for_new_document_returns_none_for_none() -> None:
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        assert cloner.clone_for_new_document(None) is None


def test_get_destination_returns_target_doc() -> None:
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        assert cloner.get_destination() is dst


def test_clone_primitive_returns_same_instance() -> None:
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        # Primitives (numbers, names, strings) are not deep-cloned; PDFBox
        # returns them verbatim.
        n = COSInteger.get(42)
        s = COSString("hello")
        name = COSName.get_pdf_name("Foo")
        assert cloner.clone_for_new_document(n) is n
        assert cloner.clone_for_new_document(s) is s
        assert cloner.clone_for_new_document(name) is name


def test_clone_simple_dictionary_produces_distinct_dict_with_same_entries() -> None:
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSDictionary()
        src.set_name("Type", "Page")
        src.set_int("Count", 3)
        clone = cloner.clone_for_new_document(src)
        assert isinstance(clone, COSDictionary)
        assert clone is not src
        assert clone.get_name("Type") == "Page"
        assert clone.get_int("Count") == 3


def test_clone_array_with_nested_dict() -> None:
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        inner = COSDictionary()
        inner.set_name("Subtype", "Image")
        outer = COSArray()
        outer.add(inner)
        outer.add(COSInteger.get(7))
        clone = cloner.clone_for_new_document(outer)
        assert isinstance(clone, COSArray)
        assert clone is not outer
        assert clone.size() == 2
        clone_inner = clone.get(0)
        assert isinstance(clone_inner, COSDictionary)
        assert clone_inner is not inner
        assert clone_inner.get_name("Subtype") == "Image"


def test_clone_resolves_indirect_reference_to_target() -> None:
    """``COSObject`` indirect refs are followed to their target and the
    target is cloned (mirrors upstream)."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        target = COSDictionary()
        target.set_name("Type", "Pages")
        ref = COSObject(7, 0, resolved=target)
        clone = cloner.clone_for_new_document(ref)
        # Result is a freshly cloned dict, NOT the original target.
        assert isinstance(clone, COSDictionary)
        assert clone is not target
        assert clone.get_name("Type") == "Pages"


def test_shared_subgraph_cloned_once() -> None:
    """When a child dict is referenced by two different parents, both
    parents in the clone point at the same cloned child (identity
    preservation across the deep graph)."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        shared = COSDictionary()
        shared.set_name("Tag", "Shared")
        a = COSDictionary()
        a.set_item("Child", shared)
        b = COSDictionary()
        b.set_item("Child", shared)
        root = COSArray()
        root.add(a)
        root.add(b)
        cloned_root = cloner.clone_for_new_document(root)
        cloned_a = cloned_root.get(0)
        cloned_b = cloned_root.get(1)
        assert isinstance(cloned_a, COSDictionary)
        assert isinstance(cloned_b, COSDictionary)
        assert cloned_a.get_item("Child") is cloned_b.get_item("Child")
        # And neither side is the source ``shared``.
        assert cloned_a.get_item("Child") is not shared


def test_circular_indirect_ref_through_dictionary() -> None:
    """Cycle through indirect refs: dict -> ref -> dict (same dict).
    The cycle in source must remain a cycle in dest, with the cloned
    dict reachable from itself by following the cloned indirect ref."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        d = COSDictionary()
        d.set_name("Type", "Cycle")
        # Indirect ref to ``d`` itself — exactly what upstream's
        # ``hasSelfReference`` check is built to handle.
        self_ref = COSObject(5, 0, resolved=d)
        d.set_item("Self", self_ref)
        clone = cloner.clone_for_new_document(d)
        assert isinstance(clone, COSDictionary)
        assert clone is not d
        # The self-reference resolves to the cloned dict itself; the
        # cycle survives the clone.
        assert clone.get_item("Self") is clone


def test_circular_dict_through_array() -> None:
    """Two-step cycle: dict -> array -> indirect ref -> dict (same)."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        d = COSDictionary()
        d.set_name("Type", "Loop")
        arr = COSArray()
        d.set_item("Kids", arr)
        # Indirect ref to ``d`` placed inside the child array.
        arr.add(COSObject(9, 0, resolved=d))
        clone = cloner.clone_for_new_document(d)
        assert isinstance(clone, COSDictionary)
        cloned_arr = clone.get_item("Kids")
        assert isinstance(cloned_arr, COSArray)
        # Following the cloned array entry must land back on ``clone``,
        # NOT on the source ``d``.
        assert cloned_arr.get(0) is clone


def test_dont_clone_a_clone() -> None:
    """Handing a previously-produced clone back to the cloner returns it
    unchanged, mirroring the ``clonedValues`` short-circuit."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        d = COSDictionary()
        d.set_name("Type", "X")
        first = cloner.clone_for_new_document(d)
        assert first is not d
        second = cloner.clone_for_new_document(first)
        assert second is first


def test_clone_stream_copies_body_and_dict_entries() -> None:
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src_stream = COSStream()
        src_stream.set_name("Type", "XObject")
        src_stream.set_raw_data(b"hello world")
        cloned = cloner.clone_for_new_document(src_stream)
        assert isinstance(cloned, COSStream)
        assert cloned is not src_stream
        assert cloned.get_name("Type") == "XObject"
        assert cloned.get_raw_data() == b"hello world"


def test_repeat_clone_returns_same_dest_object() -> None:
    """Cloning the same source twice returns the same destination clone."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSDictionary()
        src.set_name("Type", "Repeat")
        first = cloner.clone_for_new_document(src)
        second = cloner.clone_for_new_document(src)
        assert first is second


def test_clone_merge_arrays_appends_clones() -> None:
    """``clone_merge`` on two arrays appends cloned source items into
    the target array."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)

        class _Wrap:
            def __init__(self, base):
                self._b = base

            def get_cos_object(self):
                return self._b

        src_arr = COSArray()
        src_arr.add(COSInteger.get(1))
        src_arr.add(COSInteger.get(2))
        tgt_arr = COSArray()
        tgt_arr.add(COSInteger.get(99))
        cloner.clone_merge(_Wrap(src_arr), _Wrap(tgt_arr))
        assert tgt_arr.size() == 3
        assert tgt_arr.get_int(0) == 99
        assert tgt_arr.get_int(1) == 1
        assert tgt_arr.get_int(2) == 2


def test_clone_merge_dictionaries_adds_missing_keys() -> None:
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)

        class _Wrap:
            def __init__(self, base):
                self._b = base

            def get_cos_object(self):
                return self._b

        src_dict = COSDictionary()
        src_dict.set_name("New", "Value")
        src_dict.set_name("Shared", "FromSrc")
        tgt_dict = COSDictionary()
        tgt_dict.set_name("Shared", "FromTgt")
        cloner.clone_merge(_Wrap(src_dict), _Wrap(tgt_dict))
        # Missing key copied across; shared key preserved on target.
        assert tgt_dict.get_name("New") == "Value"
        assert tgt_dict.get_name("Shared") == "FromTgt"
