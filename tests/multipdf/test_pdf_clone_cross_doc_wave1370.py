"""Wave 1370 — PDFCloneUtility cross-document scenarios (agent E).

These tests exercise the cloner across two independent destination
documents and across the boundary where source-document objects appear
through indirect references.

- Two destination documents must NOT share cloner identity tables — a
  source object cloned into doc A must clone independently into doc B
  when a separate cloner is built for B.
- Re-using the same cloner is OK: feeding the same source root yields
  the same clone (identity table coalesces).
- A source COSStream whose body bytes are non-trivial: the cloned copy
  in the destination must have an INDEPENDENT body (mutating either
  side after the clone must not affect the other).
- An array with both a primitive and a nested dict: the primitive is
  returned verbatim, the dict is deep-cloned.
- ``clone_merge_cos_base`` with one dictionary side and one array side
  is a no-op (mirrors upstream: type-mismatched merges bottom out).
- ``has_self_reference`` static method round-trips: returns True for an
  indirect ref pointing back at its parent, False otherwise.
"""
from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.multipdf import PDFCloneUtility
from pypdfbox.pdmodel import PDDocument

# ---------- two destinations, separate cloners ----------


def test_two_destinations_independent_clones() -> None:
    """Cloning the *same* source dict into two different destinations via
    two different cloners produces two distinct destination dicts (no
    cross-talk through a global identity table)."""
    src = COSDictionary()
    src.set_name("Type", "Shared")
    src.set_int("Mark", 1)
    with PDDocument() as dst_a, PDDocument() as dst_b:
        cloner_a = PDFCloneUtility(dst_a)
        cloner_b = PDFCloneUtility(dst_b)
        clone_a = cloner_a.clone_for_new_document(src)
        clone_b = cloner_b.clone_for_new_document(src)
        assert isinstance(clone_a, COSDictionary)
        assert isinstance(clone_b, COSDictionary)
        assert clone_a is not clone_b
        # Both still carry the same content.
        assert clone_a.get_name("Type") == "Shared"
        assert clone_b.get_name("Type") == "Shared"


def test_same_cloner_returns_same_clone_for_same_source() -> None:
    """Two calls with the same source dict on the same cloner return the
    same destination clone."""
    src = COSDictionary()
    src.set_name("Type", "X")
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        clone_one = cloner.clone_for_new_document(src)
        clone_two = cloner.clone_for_new_document(src)
        assert clone_one is clone_two


# ---------- stream body independence ----------


def test_cloned_stream_body_is_independent() -> None:
    """After cloning, writing to the source's body does NOT alter the
    cloned destination's body (the body bytes were copied, not shared)."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSStream()
        src.set_name("Filter", "FlateDecode")
        src.set_raw_data(b"original")
        cloned = cloner.clone_for_new_document(src)
        assert isinstance(cloned, COSStream)
        assert cloned.get_raw_data() == b"original"
        # Now mutate the source.
        src.set_raw_data(b"mutated")
        # Cloned remains untouched.
        assert cloned.get_raw_data() == b"original"


def test_cloned_dict_entries_are_independent() -> None:
    """Mutating the source dict after clone doesn't bleed into the cloned
    dict (no shared backing dict)."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSDictionary()
        src.set_int("Count", 1)
        cloned = cloner.clone_for_new_document(src)
        assert isinstance(cloned, COSDictionary)
        # Mutate the source.
        src.set_int("Count", 99)
        # Cloned still reads 1.
        assert cloned.get_int("Count") == 1


# ---------- primitives + nested dicts ----------


def test_array_of_mixed_primitive_and_dict() -> None:
    """An array containing both a COSInteger (primitive — returned
    verbatim) and a COSDictionary (deep-cloned) must produce a fresh
    array containing the same primitive and a *different* dict instance."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        nested = COSDictionary()
        nested.set_name("Tag", "Inner")
        prim = COSInteger.get(42)
        src_arr = COSArray()
        src_arr.add(prim)
        src_arr.add(nested)
        cloned = cloner.clone_for_new_document(src_arr)
        assert isinstance(cloned, COSArray)
        # Primitive is the SAME object (no copy).
        assert cloned.get(0) is prim
        # Dict is a fresh clone.
        cloned_nested = cloned.get(1)
        assert isinstance(cloned_nested, COSDictionary)
        assert cloned_nested is not nested
        assert cloned_nested.get_name("Tag") == "Inner"


def test_string_primitive_returned_verbatim() -> None:
    """COSString instances are returned by-reference (they're primitive
    to the cloner)."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        s = COSString("hello")
        clone = cloner.clone_for_new_document(s)
        assert clone is s


# ---------- clone_merge type mismatch is a no-op ----------


def test_clone_merge_type_mismatch_dict_vs_array_noop() -> None:
    """clone_merge_cos_base of (dict source, array target) is a no-op —
    mirrors upstream: both sides must match type to merge."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src_dict = COSDictionary()
        src_dict.set_name("Type", "X")
        tgt_arr = COSArray()
        tgt_arr.add(COSInteger.get(5))
        # Direct call to clone_merge_cos_base — should NOT add the dict
        # to the array; it must bottom out silently.
        cloner.clone_merge_cos_base(src_dict, tgt_arr, set())
        # Array unchanged.
        assert tgt_arr.size() == 1
        assert tgt_arr.get_int(0) == 5


def test_clone_merge_type_mismatch_array_vs_dict_noop() -> None:
    """Same as above with mismatched roles reversed."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src_arr = COSArray()
        src_arr.add(COSInteger.get(1))
        tgt_dict = COSDictionary()
        tgt_dict.set_name("Type", "Y")
        cloner.clone_merge_cos_base(src_arr, tgt_dict, set())
        # Dict unchanged.
        assert tgt_dict.get_name("Type") == "Y"
        assert len(list(tgt_dict.entry_set())) == 1


# ---------- has_self_reference round-trip ----------


def test_has_self_reference_true_when_target_is_parent() -> None:
    parent = COSDictionary()
    parent.set_name("Type", "Self")
    ref_to_self = COSObject(1, 0, resolved=parent)
    assert PDFCloneUtility.has_self_reference(parent, ref_to_self) is True


def test_has_self_reference_false_when_target_is_other() -> None:
    parent = COSDictionary()
    other = COSDictionary()
    other.set_name("Type", "Other")
    ref_to_other = COSObject(2, 0, resolved=other)
    assert PDFCloneUtility.has_self_reference(parent, ref_to_other) is False


def test_has_self_reference_false_for_non_indirect_value() -> None:
    """A direct dict value (not an indirect ref) is never a self-reference
    even if it IS the parent — only COSObject indirect-refs matter."""
    parent = COSDictionary()
    parent.set_item("Self", parent)  # circular but direct
    direct = parent.get_item("Self")
    assert isinstance(direct, COSBase)
    assert PDFCloneUtility.has_self_reference(parent, direct) is False  # type: ignore[arg-type]
