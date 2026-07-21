"""PDFBOX-6203 (wave 1603): ``resetImportedObjectKeys`` now really clears keys.

Upstream ``Splitter.createNewDocument`` calls
``destCatalog.getCOSObject().resetImportedObjectKeys()`` so a split chunk's
writer mints fresh contiguous object keys instead of reusing the numbers
imported from the source document (which leaves gaps in the chunk's xref).
Until this wave the pypdfbox port of ``reset_object_keys`` was a documented
partial no-op: it walked the graph but could not clear ``COSObject`` keys.

Covered here:
* ``COSObject.set_key(None)`` zeroes the declared (num, gen) pair — the
  observable upstream effect of ``COSBase.setKey(null)`` seen through
  ``COSObject.getObjectNumber()``;
* ``COSObject.set_key(key)`` with a non-``None`` key keeps the declared pair
  (the pair/base-key split is the port's compression-pool remap channel);
* ``COSDictionary.reset_imported_object_keys`` clears the dictionary's own
  parser-stamped key, reference-wrapper keys, and keys reached through
  nested arrays;
* the ``/Parent`` guard: the parent *reference* is un-keyed but its contents
  are not walked;
* revisit semantics: an already-seen self key short-circuits, an
  already-cleared (object number 0) wrapper is skipped without
  dereferencing — both mirror upstream's null-key handling.
"""

from __future__ import annotations

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_object_key import COSObjectKey

# ---------- COSObject.set_key ----------


def test_cos_object_set_key_none_zeroes_declared_pair() -> None:
    ref = COSObject(42, 3, resolved=COSDictionary())
    ref.set_key(None)
    assert ref.object_number == 0
    assert ref.generation_number == 0
    assert ref.get_object_number() == 0
    assert ref.get_generation_number() == 0


def test_cos_object_set_key_value_keeps_declared_pair() -> None:
    """A non-``None`` key stamps the ``COSBase`` key channel without
    renumbering the declared pair — pool remaps rely on that split."""
    ref = COSObject(42, 0, resolved=COSDictionary())
    ref.set_key(COSObjectKey(7, 0))
    assert ref.object_number == 42
    assert ref.get_key() == COSObjectKey(7, 0)


# ---------- reset_imported_object_keys: dictionary graph ----------


def _keyed_dict(number: int) -> COSDictionary:
    d = COSDictionary()
    d.set_key(COSObjectKey(number, 0))
    return d


def test_reset_clears_self_key_and_reference_wrappers() -> None:
    catalog = _keyed_dict(1)
    prefs = _keyed_dict(50)
    ref = COSObject(50, 0, resolved=prefs)
    catalog.set_item(COSName.get_pdf_name("ViewerPreferences"), ref)

    catalog.reset_imported_object_keys()

    assert catalog.get_key() is None
    assert ref.object_number == 0
    assert ref.generation_number == 0
    assert prefs.get_key() is None


def test_reset_clears_direct_child_dictionary_key() -> None:
    catalog = COSDictionary()
    child = _keyed_dict(9)
    catalog.set_item(COSName.get_pdf_name("MarkInfo"), child)
    catalog.reset_imported_object_keys()
    assert child.get_key() is None


def test_reset_walks_nested_arrays() -> None:
    catalog = COSDictionary()
    inner = _keyed_dict(12)
    arr = COSArray()
    arr.set_key(COSObjectKey(11, 0))
    inner_ref = COSObject(12, 0, resolved=inner)
    arr.add(inner_ref)
    catalog.set_item(COSName.get_pdf_name("Outlines"), arr)

    catalog.reset_imported_object_keys()

    assert arr.get_key() is None
    assert inner_ref.object_number == 0
    assert inner.get_key() is None


def test_reset_unkeys_parent_reference_without_walking_it() -> None:
    """/Parent (and /P) entries: the reference itself is un-keyed but the
    graph behind it is not walked — mirrors upstream's recursion guard."""
    parent = _keyed_dict(90)
    deep = _keyed_dict(91)
    parent.set_item(COSName.get_pdf_name("Deep"), COSObject(91, 0, resolved=deep))
    child = COSDictionary()
    parent_ref = COSObject(90, 0, resolved=parent)
    child.set_item(COSName.PARENT, parent_ref)

    child.reset_imported_object_keys()

    assert parent_ref.object_number == 0
    # Not walked: the parent's own key and its children stay keyed.
    assert parent.get_key() == COSObjectKey(90, 0)
    assert deep.get_key() == COSObjectKey(91, 0)


# ---------- revisit / short-circuit semantics ----------


def test_reset_object_keys_short_circuits_on_seen_self_key() -> None:
    d = _keyed_dict(5)
    inner = _keyed_dict(6)
    d.set_item(COSName.get_pdf_name("A"), inner)
    seen: set[COSObjectKey] = {COSObjectKey(5, 0)}

    result = d.reset_object_keys(seen)

    assert result is seen
    # Early return: nothing was cleared.
    assert d.get_key() == COSObjectKey(5, 0)
    assert inner.get_key() == COSObjectKey(6, 0)


def test_reset_skips_already_cleared_wrapper_without_dereferencing() -> None:
    """A reference whose declared object number is 0 mirrors upstream's
    null-key wrapper: skipped without resolving the referent."""
    loaded = []

    def loader(ref: COSObject) -> None:
        loaded.append(ref)
        return None

    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("X"), COSObject(0, 0, loader=loader))
    d.reset_imported_object_keys()
    assert loaded == []


def test_reset_records_visited_keys_and_returns_collection() -> None:
    d = COSDictionary()
    prefs = _keyed_dict(50)
    d.set_item(COSName.get_pdf_name("V"), COSObject(50, 0, resolved=prefs))
    seen: set[COSObjectKey] = set()

    result = d.reset_object_keys(seen)

    assert result is seen
    assert COSObjectKey(50, 0) in seen


# ---------- COSArray.reset_object_keys ----------


def test_array_reset_clears_self_key_and_elements() -> None:
    arr = COSArray()
    arr.set_key(COSObjectKey(20, 0))
    leaf_ref = COSObject(21, 0, resolved=None)
    arr.add(leaf_ref)
    seen: set[COSObjectKey] = set()

    result = arr.reset_object_keys(seen)

    assert result is seen
    assert arr.get_key() is None
    assert leaf_ref.object_number == 0
    assert COSObjectKey(21, 0) in seen


def test_array_reset_short_circuits_on_seen_self_key() -> None:
    arr = COSArray()
    arr.set_key(COSObjectKey(20, 0))
    leaf_ref = COSObject(21, 0, resolved=None)
    arr.add(leaf_ref)

    result = arr.reset_object_keys({COSObjectKey(20, 0)})

    assert result == {COSObjectKey(20, 0)}
    assert arr.get_key() == COSObjectKey(20, 0)
    assert leaf_ref.object_number == 21
