from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSNull,
    COSString,
)


def test_array_contains_float_int_branch_and_boolean_default() -> None:
    array = COSArray([COSInteger.get(1), COSFloat(2.9)])

    assert array.contains(COSInteger.get(1))
    assert array.get_int(1) == 2
    assert array.get_boolean(10, True) is True


def test_dictionary_delitem_missing_key_raises_key_error() -> None:
    dictionary = COSDictionary()

    with pytest.raises(KeyError) as exc_info:
        del dictionary["Missing"]

    assert exc_info.value.args == ("Missing",)


def test_document_id_without_trailer_is_none() -> None:
    document = COSDocument()
    try:
        assert document.get_document_id() is None
    finally:
        document.close()


def test_null_repr_is_upstream_singleton_name() -> None:
    assert repr(COSNull.NULL) == "COSNull.NULL"


def test_cos_string_bytes_property_returns_raw_bytes() -> None:
    cos_string = COSString(b"\xffraw")

    assert cos_string.bytes_ == b"\xffraw"
