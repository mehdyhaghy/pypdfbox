"""Fuzz / parity tests for COSDictionary typed accessors, setters, and the
bit-field flag helpers (``set_flag`` / ``get_flag``).

Compared against Apache PDFBox 3.0.7 ``COSDictionary`` behavior:

* ``getInt(key, default)`` returns ``default`` for an absent key, the int
  value for a ``COSNumber`` entry, and ``default`` for a non-numeric entry.
* ``setFlag(field, bitFlag, value)`` takes a **bit MASK** (not a 1-based bit
  number): it ORs ``bitFlag`` in (creating the entry as 0 if absent) or
  ANDs ``~bitFlag`` out. ``getFlag`` tests ``(getInt(field, 0) & bitFlag) ==
  bitFlag``.
* ``getInt(key, secondKey, default)`` — the two-key overload — tries the
  first key, then the second, then the default.
* ``setItem(key, null)`` removes the key.
* ``getEmbeddedInt`` / ``getEmbeddedString`` walk into the nested dictionary
  stored under the first key.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)

# ---------- get_int ----------


def test_get_int_missing_returns_default() -> None:
    d = COSDictionary()
    assert d.get_int("Foo", 7) == 7


def test_get_int_missing_no_default_is_minus_one() -> None:
    d = COSDictionary()
    assert d.get_int("Foo") == -1


def test_get_int_present_returns_value() -> None:
    d = COSDictionary()
    d.set_int("Foo", 42)
    assert d.get_int("Foo", 7) == 42


def test_get_int_non_numeric_returns_default() -> None:
    """A string entry is not a COSNumber → default (matches upstream:
    ``getInt`` only unwraps ``COSNumber``)."""
    d = COSDictionary()
    d.set_string("Foo", "hello")
    assert d.get_int("Foo", 99) == 99


def test_get_int_name_value_returns_default() -> None:
    d = COSDictionary()
    d.set_name("Foo", "Bar")
    assert d.get_int("Foo", 5) == 5


def test_get_int_from_float_truncates() -> None:
    """A COSFloat entry returns its narrowing intValue (upstream
    ``COSNumber.intValue``)."""
    d = COSDictionary()
    d.set_item("Foo", COSFloat(3.9))
    assert d.get_int("Foo", 0) == 3


def test_get_int_negative_round_trip() -> None:
    d = COSDictionary()
    d.set_int("Foo", -12345)
    assert d.get_int("Foo") == -12345


@pytest.mark.parametrize("value", [0, 1, -1, 255, 65535, 2**31 - 1, -(2**31)])
def test_set_int_round_trip(value: int) -> None:
    d = COSDictionary()
    d.set_int("N", value)
    assert d.get_int("N") == value


def test_get_int_two_key_fallback_first_present() -> None:
    d = COSDictionary()
    d.set_int("A", 10)
    d.set_int("B", 20)
    # First key present wins.
    assert d.get_int("A", "B", 0) == 10


def test_get_int_two_key_fallback_first_missing() -> None:
    d = COSDictionary()
    d.set_int("B", 20)
    # First key absent → second key.
    assert d.get_int("A", "B", 0) == 20


def test_get_int_two_key_fallback_both_missing() -> None:
    d = COSDictionary()
    assert d.get_int("A", "B", 77) == 77


# ---------- get_long / get_float ----------


def test_get_long_missing_default() -> None:
    d = COSDictionary()
    assert d.get_long("X", 123) == 123


def test_get_long_from_float() -> None:
    d = COSDictionary()
    d.set_item("X", COSFloat(7.8))
    assert d.get_long("X") == 7


def test_get_float_missing_default() -> None:
    d = COSDictionary()
    assert d.get_float("X", 2.5) == 2.5


def test_get_float_from_int() -> None:
    d = COSDictionary()
    d.set_int("X", 4)
    assert d.get_float("X") == 4.0


def test_get_float_non_numeric_default() -> None:
    d = COSDictionary()
    d.set_string("X", "nope")
    assert d.get_float("X", -3.0) == -3.0


# ---------- get_boolean / set_boolean ----------


def test_get_boolean_missing_default_false() -> None:
    d = COSDictionary()
    assert d.get_boolean("B") is False


def test_get_boolean_missing_explicit_default() -> None:
    d = COSDictionary()
    assert d.get_boolean("B", True) is True


def test_set_boolean_round_trip_true() -> None:
    d = COSDictionary()
    d.set_boolean("B", True)
    assert d.get_boolean("B") is True
    assert d.get_item("B") is COSBoolean.TRUE


def test_set_boolean_round_trip_false() -> None:
    d = COSDictionary()
    d.set_boolean("B", False)
    assert d.get_boolean("B", True) is False


def test_get_boolean_non_boolean_default() -> None:
    d = COSDictionary()
    d.set_int("B", 1)
    # An integer 1 is NOT a COSBoolean → default returned (upstream parity).
    assert d.get_boolean("B", True) is True


# ---------- set_flag / get_flag (bit-MASK semantics) ----------


def test_set_flag_creates_entry_as_zero_then_sets_bit() -> None:
    """``set_flag`` on an absent key starts from 0 and ORs the mask in."""
    d = COSDictionary()
    d.set_flag("Ff", 1 << 2, True)
    assert d.get_int("Ff") == (1 << 2)
    assert d.get_flag("Ff", 1 << 2) is True


def test_set_flag_clear_bit() -> None:
    d = COSDictionary()
    d.set_int("Ff", 0b1111)
    d.set_flag("Ff", 0b0100, False)
    assert d.get_int("Ff") == 0b1011
    assert d.get_flag("Ff", 0b0100) is False


def test_get_flag_absent_key_is_false() -> None:
    d = COSDictionary()
    assert d.get_flag("Ff", 1 << 3) is False


def test_set_flag_idempotent_set() -> None:
    d = COSDictionary()
    d.set_flag("Ff", 1 << 5, True)
    d.set_flag("Ff", 1 << 5, True)
    assert d.get_int("Ff") == (1 << 5)


def test_set_flag_clear_already_clear_is_noop() -> None:
    d = COSDictionary()
    d.set_int("Ff", 0b0001)
    d.set_flag("Ff", 0b1000, False)
    assert d.get_int("Ff") == 0b0001


def test_multiple_flags_on_same_key() -> None:
    d = COSDictionary()
    d.set_flag("Ff", 1 << 0, True)
    d.set_flag("Ff", 1 << 2, True)
    d.set_flag("Ff", 1 << 4, True)
    assert d.get_int("Ff") == (1 | (1 << 2) | (1 << 4))
    assert d.get_flag("Ff", 1 << 0) is True
    assert d.get_flag("Ff", 1 << 2) is True
    assert d.get_flag("Ff", 1 << 4) is True
    assert d.get_flag("Ff", 1 << 1) is False
    # Clear the middle one only.
    d.set_flag("Ff", 1 << 2, False)
    assert d.get_flag("Ff", 1 << 2) is False
    assert d.get_flag("Ff", 1 << 0) is True
    assert d.get_flag("Ff", 1 << 4) is True


def test_get_flag_multi_bit_mask_requires_all_bits() -> None:
    """``get_flag`` checks ``(value & mask) == mask`` → all mask bits must
    be set, not just any (upstream semantics)."""
    d = COSDictionary()
    d.set_int("Ff", 0b0100)  # only one of the two mask bits set
    assert d.get_flag("Ff", 0b0110) is False
    d.set_int("Ff", 0b0110)
    assert d.get_flag("Ff", 0b0110) is True


def test_set_flag_with_cosname_key() -> None:
    d = COSDictionary()
    d.set_flag(COSName.get_pdf_name("Ff"), 1 << 7, True)
    assert d.get_flag("Ff", 1 << 7) is True


# ---------- set_item(key, None) removal ----------


def test_set_item_none_removes_key() -> None:
    d = COSDictionary()
    d.set_int("Foo", 1)
    assert d.contains_key("Foo")
    d.set_item("Foo", None)
    assert not d.contains_key("Foo")


def test_set_item_none_on_absent_key_is_noop() -> None:
    d = COSDictionary()
    d.set_item("Nope", None)
    assert d.size() == 0


def test_set_name_none_removes() -> None:
    d = COSDictionary()
    d.set_name("Foo", "Bar")
    d.set_name("Foo", None)
    assert not d.contains_key("Foo")


def test_set_string_none_removes() -> None:
    d = COSDictionary()
    d.set_string("Foo", "x")
    d.set_string("Foo", None)
    assert not d.contains_key("Foo")


# ---------- get_dictionary_object two-key fallback ----------


def test_get_dictionary_object_two_key_first_missing() -> None:
    d = COSDictionary()
    arr = COSArray()
    d.set_item("Second", arr)
    assert d.get_dictionary_object("First", "Second") is arr


def test_get_dictionary_object_two_key_first_present() -> None:
    d = COSDictionary()
    first = COSInteger.get(1)
    second = COSInteger.get(2)
    d.set_item("First", first)
    d.set_item("Second", second)
    assert d.get_dictionary_object("First", "Second") is first


def test_get_dictionary_object_default_non_name() -> None:
    d = COSDictionary()
    sentinel = COSInteger.get(9)
    assert d.get_dictionary_object("Missing", sentinel) is sentinel


# ---------- get_cos_array ----------


def test_get_cos_array_present() -> None:
    d = COSDictionary()
    arr = COSArray()
    d.set_item("A", arr)
    assert d.get_cos_array("A") is arr


def test_get_cos_array_wrong_type_none() -> None:
    d = COSDictionary()
    d.set_int("A", 1)
    assert d.get_cos_array("A") is None


def test_get_cos_array_missing_none() -> None:
    d = COSDictionary()
    assert d.get_cos_array("A") is None


# ---------- embedded int / string ----------


def test_get_embedded_int_nested() -> None:
    d = COSDictionary()
    inner = COSDictionary()
    inner.set_int("K", 33)
    d.set_item("Outer", inner)
    assert d.get_embedded_int("Outer", "K") == 33


def test_get_embedded_int_missing_outer_default() -> None:
    d = COSDictionary()
    assert d.get_embedded_int("Outer", "K", 5) == 5


def test_get_embedded_int_missing_inner_key_default() -> None:
    d = COSDictionary()
    d.set_item("Outer", COSDictionary())
    assert d.get_embedded_int("Outer", "K", 8) == 8


def test_set_embedded_int_creates_nested_dict() -> None:
    d = COSDictionary()
    d.set_embedded_int("Outer", "K", 12)
    inner = d.get_cos_dictionary("Outer")
    assert inner is not None
    assert inner.get_int("K") == 12


def test_get_embedded_string_nested() -> None:
    d = COSDictionary()
    inner = COSDictionary()
    inner.set_string("K", "value")
    d.set_item("Outer", inner)
    assert d.get_embedded_string("Outer", "K") == "value"


def test_get_embedded_string_missing_outer_default() -> None:
    d = COSDictionary()
    assert d.get_embedded_string("Outer", "K", "def") == "def"


# ---------- get_date ----------


def test_get_date_parses_pdf_date() -> None:
    d = COSDictionary()
    d.set_string("CreationDate", "D:20240315120000Z")
    parsed = d.get_date("CreationDate")
    assert parsed is not None
    assert parsed.year == 2024
    assert parsed.month == 3
    assert parsed.day == 15


def test_get_date_missing_default() -> None:
    d = COSDictionary()
    fallback = _dt.datetime(2000, 1, 1)
    assert d.get_date("CreationDate", fallback) is fallback


def test_get_date_non_string_default() -> None:
    d = COSDictionary()
    d.set_int("CreationDate", 5)
    assert d.get_date("CreationDate") is None


def test_set_date_round_trip() -> None:
    d = COSDictionary()
    dt = _dt.datetime(2021, 6, 7, 8, 9, 10)
    d.set_date("M", dt)
    back = d.get_date("M")
    assert back is not None
    assert (back.year, back.month, back.day) == (2021, 6, 7)
    assert (back.hour, back.minute, back.second) == (8, 9, 10)


# ---------- set_string with a name key ----------


def test_set_string_with_name_key_stores_cosstring() -> None:
    """The value is stored as a COSString even when the key is a COSName."""
    d = COSDictionary()
    d.set_string(COSName.TYPE, "Catalog")
    stored = d.get_item(COSName.TYPE)
    assert isinstance(stored, COSString)
    assert d.get_string(COSName.TYPE) == "Catalog"
    # get_name must NOT coerce a COSString into a name.
    assert d.get_name(COSName.TYPE) is None


def test_set_name_then_get_string_returns_default() -> None:
    """A COSName value is not decoded by get_string (upstream parity)."""
    d = COSDictionary()
    d.set_name("Foo", "Bar")
    assert d.get_string("Foo", "fallback") == "fallback"
    assert d.get_name("Foo") == "Bar"


def test_set_string_with_bytes() -> None:
    d = COSDictionary()
    d.set_string("S", b"\x01\x02hi")
    assert isinstance(d.get_item("S"), COSString)


# ---------- get_int 32-bit wrap parity (Java int overflow) ----------


def test_get_int_wraps_like_java_int() -> None:
    """A value stored above 2**31 round-trips through getInt as the signed
    32-bit wrap, matching Java ``COSInteger.intValue`` narrowing."""
    d = COSDictionary()
    d.set_item("N", COSInteger.get(2**31))
    # 2**31 as signed 32-bit → -2**31
    assert d.get_int("N") == -(2**31)
