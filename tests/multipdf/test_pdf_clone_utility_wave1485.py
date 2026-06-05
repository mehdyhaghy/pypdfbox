"""Wave 1485 — PDFCloneUtility deep-clone identity semantics, pinned
against the live Apache PDFBox 3.0.7 oracle (agent C).

The full identity table below was confirmed observation-by-observation
against PDFBox's ``cloneForNewDocument`` via the
``oracle/probes/CloneSemanticsProbe.java`` probe (which reaches the
protected ``PDFCloneUtility`` constructor by reflection). Every
assertion here mirrors a printed oracle line and passes WITHOUT the
oracle present.

Pinned facts (PDFBox 3.0.7):

- Scalar leaves — ``COSInteger`` / ``COSName`` / ``COSString`` /
  ``COSNull`` / ``COSBoolean`` — clone to the **same instance** (the
  cloner's type dispatch returns ``base`` verbatim for any non
  array/dict/stream/object), so they are shared between the source and
  the destination graph rather than copied.
- ``COSDictionary`` clones to a **distinct** instance; a second clone of
  the same source returns the **same** destination clone (identity
  cache, ``clonedVersion``).
- "Don't clone a clone": feeding a produced clone back returns it
  unchanged.
- ``COSArray`` clones distinct; scalar members are **shared** (same
  rule as above).
- An indirect reference (``COSObject``) clones to the **resolved**
  object, never to a ``COSObject`` wrapper; two refs to the same target
  share one clone.
- Cloning ``None`` returns ``None``.
- Cloning into the **same** document is allowed and still produces a
  distinct clone.

DIVERGENCE pinned by ``test_indirect_array_cycle_terminates``: upstream
``PDFCloneUtility.cloneCOSArray`` does NOT pre-register the in-progress
array clone in ``clonedVersion`` (only ``cloneCOSDictionary`` /
``cloneCOSStream`` do), so an indirect cycle that loops back to an
*array* ancestor — ``A = [1, B]``, ``B = [refToA]`` — recurses forever
and PDFBox throws ``StackOverflowError`` (confirmed live via
``oracle/probes/CloneArrayCycleOverflowProbe.java``). pypdfbox pre-registers the
array clone the same way it does for dictionaries/streams, so the cycle
terminates and is preserved (``inner is cloned_a``). This is a deliberate
hardening divergence — strictly more robust, and consistent with the
dict/stream codepath upstream itself uses.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSString,
)
from pypdfbox.multipdf import PDFCloneUtility
from pypdfbox.pdmodel import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- scalar leaves are shared, not copied ----------


def test_scalar_leaves_clone_to_same_instance() -> None:
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)

        i = COSInteger.get(42)
        assert cloner.clone_for_new_document(i) is i

        n = COSName.get_pdf_name("Foo")
        assert cloner.clone_for_new_document(n) is n

        s = COSString("hi")
        assert cloner.clone_for_new_document(s) is s

        assert cloner.clone_for_new_document(COSNull.NULL) is COSNull.NULL

        assert cloner.clone_for_new_document(COSBoolean.TRUE) is COSBoolean.TRUE
        assert cloner.clone_for_new_document(COSBoolean.FALSE) is COSBoolean.FALSE


def test_clone_none_returns_none() -> None:
    with PDDocument() as dst:
        assert PDFCloneUtility(dst).clone_for_new_document(None) is None


# ---------- dictionary identity cache ----------


def test_dictionary_clones_distinct_and_cached() -> None:
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        d = COSDictionary()
        d.set_item(COSName.TYPE, COSName.get_pdf_name("Bar"))

        c1 = cloner.clone_for_new_document(d)
        c2 = cloner.clone_for_new_document(d)
        assert isinstance(c1, COSDictionary)
        assert c1 is not d
        assert c1 is c2
        # value scalar is shared
        assert c1.get_item(COSName.TYPE) is COSName.get_pdf_name("Bar")


def test_dont_clone_a_clone() -> None:
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        d = COSDictionary()
        c1 = cloner.clone_for_new_document(d)
        assert cloner.clone_for_new_document(c1) is c1


# ---------- array: distinct shell, shared scalar members ----------


def test_array_clones_distinct_with_shared_scalars() -> None:
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        n = COSName.get_pdf_name("Foo")
        arr = COSArray()
        arr.add(COSInteger.get(7))
        arr.add(n)

        ca = cloner.clone_for_new_document(arr)
        assert isinstance(ca, COSArray)
        assert ca is not arr
        assert ca.size() == 2
        assert ca.get(1) is n


# ---------- indirect references resolve and dedup ----------


def test_indirect_ref_clones_to_resolved_object() -> None:
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        target = COSDictionary()
        target.set_item(COSName.TYPE, COSName.get_pdf_name("Ref"))
        ref = COSObject(1, 0, resolved=target)

        cloned = cloner.clone_for_new_document(ref)
        assert isinstance(cloned, COSDictionary)
        assert not isinstance(cloned, COSObject)


def test_two_indirect_refs_to_same_target_share_one_clone() -> None:
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        target = COSDictionary()
        target.set_item(COSName.TYPE, COSName.get_pdf_name("Ref"))
        ref1 = COSObject(1, 0, resolved=target)
        ref2 = COSObject(1, 0, resolved=target)

        c1 = cloner.clone_for_new_document(ref1)
        c2 = cloner.clone_for_new_document(ref2)
        assert c1 is c2


# ---------- cloning into the same document is allowed ----------


def test_clone_into_same_document_produces_distinct_clone() -> None:
    with PDDocument() as doc:
        cloner = PDFCloneUtility(doc)
        catalog = doc.get_document_catalog().get_cos_object()
        cloned = cloner.clone_for_new_document(catalog)
        assert isinstance(cloned, COSDictionary)
        assert cloned is not catalog


# ---------- divergence: indirect array cycle terminates (vs upstream SOE) ----


def test_indirect_array_cycle_terminates() -> None:
    """``A = [1, B]``, ``B = [refToA]`` — an indirect cycle that loops
    back to an *array* ancestor. pypdfbox pre-registers the array clone,
    so cloning terminates and preserves the cycle shape. Upstream
    PDFBox 3.0.7 throws ``StackOverflowError`` on this exact graph
    (see ``test_indirect_array_cycle_overflows_upstream``)."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        a = COSArray()
        b = COSArray()
        a.add(COSInteger.get(1))
        a.add(b)
        a_ref = COSObject(1, 0, resolved=a)
        b.add(a_ref)

        cloned_a = cloner.clone_for_new_document(a)
        assert isinstance(cloned_a, COSArray)
        cloned_b = cloned_a.get(1)
        assert isinstance(cloned_b, COSArray)
        inner = cloned_b.get(0)
        # Cycle preserved: the indirect ref back to A resolved to the
        # in-progress array clone, not a second independent clone.
        assert inner is cloned_a


# ---------- differential pins (optional, oracle-gated) ----------


@requires_oracle
def test_clone_semantics_match_oracle() -> None:
    out = run_probe_text("CloneSemanticsProbe")
    facts = dict(
        line.split("=", 1) for line in out.strip().splitlines() if "=" in line
    )
    assert facts["int_same"] == "true"
    assert facts["name_same"] == "true"
    assert facts["string_same"] == "true"
    assert facts["null_same"] == "true"
    assert facts["bool_true_same"] == "true"
    assert facts["javanull"] == "true"
    assert facts["dict_distinct"] == "true"
    assert facts["dict_cached_same"] == "true"
    assert facts["dont_clone_clone"] == "true"
    assert facts["arr_distinct"] == "true"
    assert facts["arr_size"] == "2"
    assert facts["arr_name_shared"] == "true"
    assert facts["ref_is_dict"] == "true"
    assert facts["ref_not_object"] == "true"
    assert facts["shared_target_one_clone"] == "true"
    assert facts["same_doc_distinct"] == "true"
    assert facts["same_doc_is_dict"] == "true"


@requires_oracle
def test_indirect_array_cycle_overflows_upstream() -> None:
    """Differential pin for the deliberate divergence: PDFBox 3.0.7
    StackOverflows on the indirect array cycle that pypdfbox handles.
    The probe prints ``overflow`` (and nothing else) when it catches the
    ``StackOverflowError``."""
    out = run_probe_text("CloneArrayCycleOverflowProbe")
    assert out.strip() == "overflow"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-q"])
