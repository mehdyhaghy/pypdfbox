"""Wave 1341 coverage-boost tests for :class:`PDStructureNode`.

Targets the residual ``_same_kid`` / objectable-passthrough branches:

* ``append_objectable_kid`` / ``remove_objectable_kid`` /
  ``insert_objectable_before`` when given an argument that does **not**
  expose ``get_cos_object`` (lines 301, 311, 325 — the ``else`` legs).
* ``_same_kid`` raw-equality match (line 407-408) — two objects that
  compare equal but are not the same instance and not COSIntegers.
* ``_same_kid`` COSObject indirection (lines 414-417 and 418-421) —
  an indirect-reference wrapping a dereferenceable target compares
  equal to the bare target on either side.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSObject
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_marked_content_reference import (
    PDMarkedContentReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_node import (
    PDStructureNode,
)

_K = "K"


# ---------- objectable-passthrough branches ----------


def test_append_objectable_kid_with_plain_int() -> None:
    """An ``int`` MCID has no ``get_cos_object`` attribute, so
    :meth:`append_objectable_kid` falls through to :meth:`append_kid`
    directly (line 301)."""
    node = PDStructureNode("StructElem")
    node.append_objectable_kid(7)
    kids = node.get_kids()
    # The MCID is wrapped via _to_cos → COSInteger, then unwrapped by
    # wrap_kid to its int value.
    assert kids == [7]


def test_remove_objectable_kid_with_plain_int_present() -> None:
    """:meth:`remove_objectable_kid` of a bare int kid falls through to
    :meth:`remove_kid` (line 311)."""
    node = PDStructureNode("StructElem")
    node.append_kid(COSInteger.get(3))
    assert node.remove_objectable_kid(3) is True
    assert node.get_kids() == []


def test_remove_objectable_kid_with_plain_int_absent() -> None:
    """When the bare-int kid is not present, the call still falls
    through to ``remove_kid`` but returns ``False`` (line 311)."""
    node = PDStructureNode("StructElem")
    assert node.remove_objectable_kid(99) is False


def test_insert_objectable_before_with_plain_int() -> None:
    """:meth:`insert_objectable_before` with bare-int arguments falls
    through to :meth:`insert_before` (line 325)."""
    node = PDStructureNode("StructElem")
    # Seed the kid array with two MCIDs so insert-before has a target.
    node.append_kid(COSInteger.get(1))
    node.append_kid(COSInteger.get(2))
    assert node.insert_objectable_before(99, 2) is True
    assert node.get_kids() == [1, 99, 2]


# ---------- _same_kid fall-through (line 407-408) ----------


def test_same_kid_generic_equality_match() -> None:
    """Two equal-but-distinct :class:`COSDictionary` instances must
    compare equal via the raw ``==`` fallback (line 407-408). The
    dictionaries are not COSIntegers and not the same object, so the
    final ``if left == right`` is what bridges them."""
    # We can't easily construct two COSDictionaries that compare equal
    # without being identical, but COSObject equality flows through
    # ``__eq__`` defined on the base. Use a stand-in: append a kid then
    # query ``contains_kid`` with an identity-equal duplicate so the
    # path hits ``left == right``.
    node = PDStructureNode("StructElem")
    inner = COSDictionary()
    node.append_kid(inner)
    # Direct ``contains_kid`` of the *same* object — ``left is right``
    # is the fast path (line 399-400). Force a non-identity but
    # value-equal compare via a fresh int wrapper. Two ``COSInteger``
    # values compare via the dedicated branch but two equivalent
    # ``COSString`` objects flow through ``left == right``.
    from pypdfbox.cos import COSString

    s_node = PDStructureNode("StructElem")
    first = COSString("abc")
    s_node.append_kid(first)
    # Build a second COSString with the same content. Equality on
    # COSString collapses two distinct instances by value, so the raw
    # ``left == right`` branch fires.
    second = COSString("abc")
    assert first is not second
    assert s_node.contains_kid(second) is True


# ---------- _same_kid COSObject indirection (lines 414-421) ----------


def test_same_kid_left_cos_object_indirection() -> None:
    """An indirect reference whose resolved value equals the bare kid
    must compare equal via the ``_same_kid`` peek-through-indirection
    branch (lines 414-417). The function is module-private but exposed
    as a private helper; we call it directly because all of the
    public call sites pass values pre-dereferenced through
    :meth:`COSArray.get_object` / :meth:`COSDictionary.get_dictionary_object`,
    so the public surface alone can never feed a raw ``COSObject``
    into ``_same_kid``.

    Upstream PDFBox keeps the same defensive branch in Java
    (``PDStructureNode.java`` lines 260-264, 340-344). The pypdfbox
    port preserves it for parity even though the Python collection
    helpers happen to dereference earlier. Mirrors upstream's
    contract: ``_same_kid`` is what callers use to compare a kid
    against its potentially-indirected sibling.
    """
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_node import (
        _same_kid,
    )

    target = COSDictionary()
    target.set_int("X", 1)
    indirect = COSObject(1, 0, resolved=target)
    assert indirect.get_object() is target

    # Left side: indirect reference. Right side: bare target.
    assert _same_kid(indirect, target) is True


def test_same_kid_right_cos_object_indirection() -> None:
    """Mirror direction of :func:`test_same_kid_left_cos_object_indirection`
    — ``right`` carries the COSObject indirection (lines 418-421).
    """
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_node import (
        _same_kid,
    )

    target = COSDictionary()
    target.set_int("Y", 2)
    indirect = COSObject(2, 0, resolved=target)

    # Left side: bare target. Right side: indirect reference.
    assert _same_kid(target, indirect) is True


def test_same_kid_cos_object_unresolved_returns_false() -> None:
    """A COSObject that fails to resolve must not match against a
    sibling kid — the ``inner is not None`` guard (line 416 / 420)
    prevents false positives.
    """
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_node import (
        _same_kid,
    )

    target = COSDictionary()
    # Resolved=None means the loader was supposedly called and returned
    # None (unresolvable free xref entry). ``get_object`` will return
    # None and the indirection branch must NOT spuriously match.
    unresolved = COSObject(3, 0, resolved=None)
    assert _same_kid(unresolved, target) is False
    assert _same_kid(target, unresolved) is False


def test_same_kid_via_marked_content_reference_array() -> None:
    """Drive the array-side same_kid match through a typed
    :class:`PDMarkedContentReference` so ``contains_kid`` runs the
    array iteration plus the value-equality branch.
    """
    node = PDStructureNode("StructElem")
    mcr = PDMarkedContentReference()
    mcr.set_mcid(5)
    node.append_kid(mcr.get_cos_object())
    # Append a second so /K is an array — exercises the array branch
    # in contains_kid.
    node.append_kid(COSInteger.get(8))
    assert node.contains_kid(mcr.get_cos_object()) is True
    assert node.contains_kid(8) is True
    assert node.contains_kid(999) is False
