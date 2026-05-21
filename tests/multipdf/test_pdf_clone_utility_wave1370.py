"""Wave 1370 — PDFCloneUtility identity-aware cloning (agent E).

Covers the identity / cross-document boundary cases that the existing
clone-utility suite doesn't already nail down:

- A ``COSObject`` indirect reference whose target lives in source doc A
  must be deep-cloned into destination doc B (it cannot be left as an
  indirect ref pointing back into A's xref).
- A graph where two ``COSObject`` indirect refs both resolve to the
  *same* target must end up sharing one cloned target on the destination
  side (identity preservation across indirect refs).
- ``clone_for_new_document`` is idempotent: cloning the same root twice
  returns the same destination clone tree (so an outer caller that
  re-runs clone never duplicates state).
- ``clone_for_new_document`` of an unresolved indirect ref (``COSObject``
  with no resolved object) returns ``None`` — no NPE.
- ``clone_merge_cos_base`` is cycle-safe across two parallel cycles in
  source + target (Python-side ``seen_pairs`` guard).
"""
from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSObject,
    COSStream,
)
from pypdfbox.multipdf import PDFCloneUtility
from pypdfbox.pdmodel import PDDocument


class _Wrap:
    """Minimal ``get_cos_object`` wrapper for :meth:`clone_merge`."""

    def __init__(self, base) -> None:
        self._b = base

    def get_cos_object(self):
        return self._b


# ---------- cross-document indirect ref ----------


def test_cross_document_indirect_ref_target_is_cloned_into_dest() -> None:
    """An indirect-ref to a dict that lives in source doc A must be
    fully cloned into destination doc B — no leakage of A's COS
    instance into B."""
    with PDDocument() as src_doc, PDDocument() as dst_doc:
        # Source-side target dict (lives in src_doc conceptually).
        src_target = COSDictionary()
        src_target.set_name("Type", "OnSrc")
        src_target.set_int("Mark", 42)
        # Plant it under src_doc's catalog so identity stays with src_doc.
        src_doc.get_document_catalog().get_cos_object().set_item(
            "TargetSlot", src_target
        )
        ref = COSObject(7, 0, resolved=src_target)
        # Compose the source graph the merger would walk.
        src_root = COSDictionary()
        src_root.set_item("Ref", ref)

        cloner = PDFCloneUtility(dst_doc)
        cloned_root = cloner.clone_for_new_document(src_root)
        assert isinstance(cloned_root, COSDictionary)
        cloned_target = cloned_root.get_item("Ref")
        # Target on dest side is a fresh dict, NOT the source instance.
        assert isinstance(cloned_target, COSDictionary)
        assert cloned_target is not src_target
        assert cloned_target.get_name("Type") == "OnSrc"
        assert cloned_target.get_int("Mark") == 42


def test_two_indirect_refs_to_same_target_share_one_clone() -> None:
    """Two distinct ``COSObject`` instances pointing at the same target
    dict must produce one cloned target on the destination (identity
    preservation across the deep graph)."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        target = COSDictionary()
        target.set_name("Tag", "Shared")
        ref_one = COSObject(11, 0, resolved=target)
        ref_two = COSObject(12, 0, resolved=target)  # different num, same target
        outer = COSDictionary()
        outer.set_item("A", ref_one)
        outer.set_item("B", ref_two)
        cloned = cloner.clone_for_new_document(outer)
        assert isinstance(cloned, COSDictionary)
        a = cloned.get_item("A")
        b = cloned.get_item("B")
        # Both indirect refs resolve to the same cloned target.
        assert a is b
        assert isinstance(a, COSDictionary)
        assert a is not target


def test_idempotent_double_clone_returns_same_dest_tree() -> None:
    """Cloning the same source root twice yields ``first is second``:
    the identity table coalesces."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src_root = COSDictionary()
        src_root.set_name("Type", "Idem")
        nested = COSArray()
        nested.add(COSInteger.get(1))
        src_root.set_item("Kids", nested)

        first = cloner.clone_for_new_document(src_root)
        second = cloner.clone_for_new_document(src_root)
        assert first is second
        # And every nested clone is also identity-stable.
        assert (
            first.get_item("Kids")  # type: ignore[union-attr]
            is second.get_item("Kids")  # type: ignore[union-attr]
        )


def test_unresolved_indirect_ref_clones_to_none() -> None:
    """COSObject with no resolved target returns ``None`` from
    ``get_object()``. The cloner descends, finds nothing, and returns
    None — no AttributeError, no NPE."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        # No ``resolved=`` and no loader → get_object() returns None.
        dangling = COSObject(99, 0)
        # Wrapping in an array so an outer container can be cloned even
        # though the entry yields None.
        outer = COSArray()
        outer.add(dangling)
        cloned = cloner.clone_for_new_document(outer)
        assert isinstance(cloned, COSArray)
        # Dangling entries are skipped (clone_cos_array's ``if cloned is None``
        # guard mirrors upstream).
        assert cloned.size() == 0


def test_clone_then_clone_clone_returns_clone_unchanged() -> None:
    """``clone_for_new_document(clone)`` returns the clone verbatim — the
    "don't clone a clone" short-circuit."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSDictionary()
        src.set_name("Type", "X")
        clone_one = cloner.clone_for_new_document(src)
        clone_two = cloner.clone_for_new_document(clone_one)
        assert clone_two is clone_one
        clone_three = cloner.clone_for_new_document(clone_two)
        assert clone_three is clone_one


# ---------- clone_merge cycle safety ----------


def test_clone_merge_cycle_in_both_sides_terminates() -> None:
    """A cycle on both source and target should not loop forever — the
    ``seen_pairs`` cycle guard breaks the recursion."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)

        # Source side: self-pointing dict via /Self → self
        src = COSDictionary()
        src.set_name("Side", "Src")
        src.set_item("Self", src)
        # Target side: same structural cycle.
        tgt = COSDictionary()
        tgt.set_name("Side", "Tgt")
        tgt.set_item("Self", tgt)

        # Must terminate.
        cloner.clone_merge(_Wrap(src), _Wrap(tgt))
        # Side stayed on target; /Self stayed self-cyclic (cycle handler
        # recognised the pair and bottomed out without mutating).
        assert tgt.get_name("Side") == "Tgt"
        assert tgt.get_item("Self") is tgt


def test_clone_merge_array_of_dicts_clones_each_element() -> None:
    """``clone_merge`` on two arrays of dicts deep-clones each source
    dict, NOT just appends a reference."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        d1 = COSDictionary()
        d1.set_name("Name", "One")
        d2 = COSDictionary()
        d2.set_name("Name", "Two")
        src_arr = COSArray()
        src_arr.add(d1)
        src_arr.add(d2)
        tgt_arr = COSArray()
        cloner.clone_merge(_Wrap(src_arr), _Wrap(tgt_arr))
        assert tgt_arr.size() == 2
        # Cloned dicts, NOT the source instances.
        assert tgt_arr.get(0) is not d1
        assert tgt_arr.get(1) is not d2
        assert tgt_arr.get(0).get_name("Name") == "One"  # type: ignore[union-attr]
        assert tgt_arr.get(1).get_name("Name") == "Two"  # type: ignore[union-attr]


def test_clone_stream_is_added_to_dest_scratch_file() -> None:
    """A cloned stream's scratch backing must be the destination
    document's scratch file, not the source's."""
    with PDDocument() as src_doc, PDDocument() as dst_doc:
        # Snapshot scratch identities so we can assert which one the
        # clone bound to.
        src_scratch = src_doc.get_document().scratch_file
        dst_scratch = dst_doc.get_document().scratch_file
        # Build a stream on src_doc's scratch file.
        src_stream = COSStream(src_scratch)
        src_stream.set_raw_data(b"abc")
        src_stream.set_name("Filter", "FlateDecode")

        cloner = PDFCloneUtility(dst_doc)
        cloned = cloner.clone_for_new_document(src_stream)
        assert isinstance(cloned, COSStream)
        # The cloned stream's backing scratch is dst's scratch (private
        # attribute ``_scratch`` mirrors upstream's ScratchFile field).
        assert cloned._scratch is dst_scratch  # noqa: SLF001
        assert cloned._scratch is not src_scratch  # noqa: SLF001


def test_clone_array_with_self_reference_via_indirect_ref() -> None:
    """An array whose single entry is an indirect ref to itself must
    survive as a self-pointing array on the destination — no recursion."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        arr = COSArray()
        self_ref = COSObject(13, 0, resolved=arr)
        arr.add(self_ref)
        cloned = cloner.clone_for_new_document(arr)
        assert isinstance(cloned, COSArray)
        assert cloned.size() == 1
        # Cloned array references itself, NOT the source array.
        assert cloned.get(0) is cloned
