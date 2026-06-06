"""Wave 1495 — behaviour-anchored coverage for ``FreeXReference``'s column
accessors and string forms on the concrete class (the existing xref-entry
coverage suite overrides these in subclasses, so the real implementations of
``get_third_column_value`` / ``to_string`` / ``__repr__`` stay unexercised).

Mirrors ``org.apache.pdfbox.pdfparser.xref.FreeXReference``.
"""

from __future__ import annotations

from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.pdfparser.xref.free_x_reference import FreeXReference
from pypdfbox.pdfparser.xref.x_reference_type import XReferenceType


def test_referenced_key_round_trips() -> None:
    key = COSObjectKey(7, 3)
    ref = FreeXReference(key, 12)
    assert ref.get_referenced_key() is key


def test_second_column_is_next_free_object() -> None:
    ref = FreeXReference(COSObjectKey(7, 0), 42)
    assert ref.get_second_column_value() == 42


def test_third_column_is_generation_of_referenced_key() -> None:
    # Column-3 of a free entry is the generation of *its own* key, not the
    # next-free object number.
    ref = FreeXReference(COSObjectKey(7, 5), 42)
    assert ref.get_third_column_value() == 5


def test_type_is_free() -> None:
    ref = FreeXReference(COSObjectKey(1, 0), 0)
    assert ref.get_type() is XReferenceType.FREE


def test_repr_and_to_string_agree_and_carry_fields() -> None:
    ref = FreeXReference(COSObjectKey(7, 5), 42)
    text = ref.to_string()
    assert text == repr(ref)
    assert text == str(ref)
    assert text.startswith("FreeReference{")
    assert "nextFreeObject=42" in text
    assert f"type={XReferenceType.FREE.get_numeric_value()}" in text


def test_null_entry_sentinel_is_object_zero_generation_65535() -> None:
    sentinel = FreeXReference.NULL_ENTRY
    assert sentinel.get_referenced_key().get_number() == 0
    assert sentinel.get_third_column_value() == 65535
    assert sentinel.get_second_column_value() == 0
