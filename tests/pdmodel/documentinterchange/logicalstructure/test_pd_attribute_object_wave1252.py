"""Wave 1252 round-out: parity tests for ``PDDictionaryWrapper``-style
``__eq__`` / ``__hash__`` on :class:`PDAttributeObject`.

Mirrors upstream ``PDDictionaryWrapper.equals(Object)`` and
``PDDictionaryWrapper.hashCode()``
(``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/common/
PDDictionaryWrapper.java`` L60-L77) which ``PDAttributeObject`` inherits:
identity short-circuit, dictionary-based equality when both sides are
``PDDictionaryWrapper`` instances, otherwise unequal.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
    PDAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_default_attribute_object import (
    PDDefaultAttributeObject,
)

_O = COSName.get_pdf_name("O")


def test_eq_identity_same_instance_wave1252() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    assert attr == attr


def test_eq_same_underlying_dictionary_wave1252() -> None:
    cos = COSDictionary()
    cos.set_name(_O, "Layout")
    a = PDAttributeObject(cos)
    b = PDAttributeObject(cos)
    # Two wrappers around the same COSDictionary compare equal — mirrors
    # upstream ``PDDictionaryWrapper.equals`` which delegates to
    # ``this.dictionary.equals(other.dictionary)``.
    assert a == b
    assert hash(a) == hash(b)


def test_eq_distinct_dictionaries_unequal_wave1252() -> None:
    a = PDAttributeObject()
    a.set_owner("Layout")
    b = PDAttributeObject()
    b.set_owner("Layout")
    # COSDictionary uses identity equality, so distinct dicts even with
    # identical entries compare unequal — same as upstream Java since
    # COSDictionary.equals is identity-based.
    assert a != b


def test_eq_with_non_attribute_object_returns_not_equal_wave1252() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    assert attr != object()
    assert attr != "Layout"
    assert attr != 42
    assert attr is not None


def test_eq_subclass_with_same_dictionary_compares_equal_wave1252() -> None:
    cos = COSDictionary()
    cos.set_name(_O, "MyOwner")
    base = PDAttributeObject(cos)
    sub = PDDefaultAttributeObject(cos)
    # Both wrap the same COSDictionary -> wrapper equality holds across
    # the PDAttributeObject hierarchy (mirrors PDDictionaryWrapper.equals).
    assert base == sub
    assert sub == base


def test_hash_is_stable_across_attribute_mutations_wave1252() -> None:
    cos = COSDictionary()
    attr = PDAttributeObject(cos)
    h0 = hash(attr)
    attr.set_owner("Layout")
    attr.set_revision_number(3)
    # The wrapper hashes off the underlying dictionary's identity, so
    # mutating entries does not change the hash — required for use in
    # sets/dicts mid-mutation.
    assert hash(attr) == h0


def test_attribute_object_usable_in_set_wave1252() -> None:
    cos = COSDictionary()
    a = PDAttributeObject(cos)
    b = PDAttributeObject(cos)
    c = PDAttributeObject()
    pool = {a, b, c}
    # ``a`` and ``b`` wrap the same dict -> dedupe to one entry.
    assert len(pool) == 2
