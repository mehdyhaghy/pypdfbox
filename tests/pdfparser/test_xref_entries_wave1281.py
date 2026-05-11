"""Wave 1281: xref entry hierarchy (AbstractXReference + concrete types)."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSObjectKey, COSStream
from pypdfbox.pdfparser.xref import (
    AbstractXReference,
    FreeXReference,
    NormalXReference,
    ObjectStreamXReference,
    XReferenceEntry,
    XReferenceType,
)


def test_xreference_type_numeric_values() -> None:
    assert XReferenceType.FREE.get_numeric_value() == 0
    assert XReferenceType.NORMAL.get_numeric_value() == 1
    assert XReferenceType.OBJECT_STREAM_ENTRY.get_numeric_value() == 2


def test_abstract_x_reference_cannot_instantiate() -> None:
    with pytest.raises(TypeError):
        AbstractXReference(XReferenceType.NORMAL)  # type: ignore[abstract]


def test_free_x_reference_columns() -> None:
    key = COSObjectKey(5, 0)
    ref = FreeXReference(key, 7)
    assert ref.get_type() is XReferenceType.FREE
    assert ref.get_referenced_key() is key
    assert ref.get_first_column_value() == 0
    assert ref.get_second_column_value() == 7
    assert ref.get_third_column_value() == 0


def test_null_entry_sentinel() -> None:
    null = FreeXReference.NULL_ENTRY
    assert null.get_referenced_key().get_number() == 0
    assert null.get_referenced_key().get_generation() == 65535
    assert null.get_second_column_value() == 0


def test_normal_x_reference_byte_offset() -> None:
    key = COSObjectKey(3, 0)
    stream = COSStream()
    ref = NormalXReference(123, key, stream)
    assert ref.get_byte_offset() == 123
    assert ref.get_first_column_value() == 1
    assert ref.get_second_column_value() == 123
    assert ref.get_third_column_value() == 0
    assert ref.get_object() is stream


def test_normal_x_reference_detects_object_stream() -> None:
    key = COSObjectKey(3, 0)
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.OBJ_STM)
    ref = NormalXReference(123, key, stream)
    assert ref.is_object_stream()


def test_object_stream_x_reference_columns() -> None:
    parent = COSObjectKey(5, 0)
    key = COSObjectKey(8, 0)
    stream = COSStream()
    ref = ObjectStreamXReference(2, key, stream, parent)
    assert ref.get_first_column_value() == 2
    assert ref.get_second_column_value() == 5  # parent object number
    assert ref.get_third_column_value() == 2
    assert ref.get_parent_key() is parent
    assert ref.get_object_stream_index() == 2


def test_compare_to_orders_by_referenced_key() -> None:
    a = FreeXReference(COSObjectKey(1, 0), 0)
    b = FreeXReference(COSObjectKey(2, 0), 0)
    assert a.compare_to(b) < 0
    assert sorted([b, a]) == [a, b]


def test_x_reference_entry_is_abstract() -> None:
    with pytest.raises(TypeError):
        XReferenceEntry()  # type: ignore[abstract]
