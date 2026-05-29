from __future__ import annotations

from pypdfbox.cos import COSArray, COSBoolean, COSFloat, COSInteger, COSName, COSNull, COSObject
from pypdfbox.cos.cos_string import COSString


def test_typed_getters_match_upstream_raw_entry_semantics() -> None:
    # Upstream COSArray.getName / getInt / getString read the *raw* entry
    # (objects.get(index)), NOT getObject — they do not dereference an indirect
    # COSObject, so an indirect element falls through to the default. Verified
    # against PDFBox 3.0.7 by tests/cos/oracle/test_cos_array_accessor_oracle.py.
    # (get_float / get_boolean are pypdfbox additions with no upstream
    # equivalent and intentionally still dereference.)
    name = COSName.get_pdf_name("DeviceRGB")
    array = COSArray(
        [
            COSObject(1, 0, resolved=name),
            COSObject(2, 0, resolved=COSInteger.get(7)),
            COSObject(3, 0, resolved=COSFloat(2.5)),
            COSObject(4, 0, resolved=COSBoolean.TRUE),
            COSObject(5, 0, resolved=COSString("hello")),
        ]
    )

    assert isinstance(array.get(0), COSObject)
    assert array.get_name(0) is None
    assert array.get_name(0, "fallback") == "fallback"
    assert array.get_int(1) == -1
    assert array.get_int(1, 99) == 99
    assert array.get_string(4) is None
    assert array.get_string(4, "fallback") == "fallback"
    # pypdfbox-only accessors still dereference.
    assert array.get_float(2) == 2.5
    assert array.get_boolean(3) is True


def test_typed_getters_treat_indirect_null_as_absent() -> None:
    array = COSArray(
        [
            COSObject(1, 0, resolved=COSNull.NULL),
            COSObject(2, 0),
        ]
    )

    assert array.get_name(0, "fallback") == "fallback"
    assert array.get_int(0, 42) == 42
    assert array.get_float(0, 4.25) == 4.25
    assert array.get_boolean(0, True) is True
    assert array.get_string(0, "fallback") == "fallback"
    assert array.get_int(1, 99) == 99


def test_typed_list_conversions_resolve_indirect_entries() -> None:
    array = COSArray(
        [
            COSObject(1, 0, resolved=COSName.get_pdf_name("Pattern")),
            COSObject(2, 0, resolved=COSString("text")),
            COSObject(3, 0, resolved=COSInteger.get(3)),
            COSObject(4, 0, resolved=COSFloat(4.5)),
            COSObject(5, 0, resolved=COSNull.NULL),
        ]
    )

    assert array.to_cos_name_string_list() == ["Pattern", None, None, None, None]
    assert array.to_cos_string_string_list() == [None, "text", None, None, None]
    assert array.to_cos_number_integer_list() == [None, None, 3, 4, None]
    assert array.to_cos_number_float_list() == [None, None, 3.0, 4.5, None]
    assert array.to_float_array() == [0.0, 0.0, 3.0, 4.5, 0.0]
