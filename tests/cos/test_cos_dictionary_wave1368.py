"""Wave 1368 — COSDictionary typed-accessor edge cases.

Round-out tests for accessor paths not yet exercised:

* ``get_int`` / ``get_long`` / ``get_float`` / ``get_boolean`` with a
  ``COSObject`` indirect reference value (must dereference).
* ``get_int`` with a ``COSFloat`` value (must truncate via ``int(value)``)
  and ``get_float`` with a ``COSInteger`` value (must widen via ``float``).
* ``get_int`` / ``get_long`` fallback parameter when both keys are absent
  (``default`` is the second key, ``fallback`` is the scalar default).
* ``get_date`` returning ``default`` for a non-COSString entry.
* ``get_embedded_date`` returning ``default`` when the embedded dictionary
  is absent.
* ``get_string`` returning the ``COSName`` text when the value is a name
  (PDFBox parity — ``Name`` values are accepted by string accessors).
* ``get_name_as_string`` mirroring ``get_string`` for both name and string
  values.
"""

from __future__ import annotations

import datetime as dt

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSString,
)


def test_get_int_dereferences_indirect_cosinteger() -> None:
    target = COSInteger.get(42)
    ref = COSObject(7, 0, resolved=target)
    d = COSDictionary([("Count", ref)])
    assert d.get_int("Count") == 42


def test_get_int_truncates_float_value() -> None:
    d = COSDictionary([("Page", COSFloat(3.9))])
    assert d.get_int("Page") == 3


def test_get_float_widens_integer_value() -> None:
    d = COSDictionary([("Page", COSInteger.get(7))])
    assert d.get_float("Page") == 7.0


def test_get_long_uses_fallback_when_both_keys_missing() -> None:
    d = COSDictionary()
    # First key missing, second key also missing — return fallback.
    assert d.get_long("Length", "L", fallback=99) == 99


def test_get_long_returns_first_key_when_present() -> None:
    d = COSDictionary([("Length", COSInteger.get(123))])
    assert d.get_long("Length", "L", fallback=99) == 123


def test_get_long_returns_second_key_when_first_missing() -> None:
    d = COSDictionary([("L", COSInteger.get(55))])
    assert d.get_long("Length", "L", fallback=99) == 55


def test_get_int_returns_explicit_default_when_absent() -> None:
    d = COSDictionary()
    assert d.get_int("Count", 17) == 17


def test_get_int_default_minus_one_when_unmapped() -> None:
    d = COSDictionary([("Count", COSString("not-a-number"))])
    # Non-numeric value falls back to default (-1).
    assert d.get_int("Count") == -1


def test_get_float_with_second_key_and_fallback() -> None:
    d = COSDictionary([("R", COSFloat(1.5))])
    assert d.get_float("Radius", "R", fallback=-9.0) == 1.5


def test_get_float_second_key_falls_back_when_neither_present() -> None:
    d = COSDictionary()
    assert d.get_float("Radius", "R", fallback=-9.0) == -9.0


def test_get_boolean_second_key_path() -> None:
    d = COSDictionary([("F", COSBoolean.TRUE)])
    assert d.get_boolean("Flag", "F", fallback=False) is True


def test_get_boolean_returns_fallback_for_non_bool_value() -> None:
    d = COSDictionary([("Flag", COSInteger.get(1))])
    # Mirrors PDFBox: ``getBoolean`` only honours ``COSBoolean`` — an
    # integer ``1`` falls back to the default.
    assert d.get_boolean("Flag", default=False) is False


def test_get_string_returns_name_text() -> None:
    d = COSDictionary([("Type", COSName.get_pdf_name("Page"))])
    assert d.get_string("Type") == "Page"


def test_get_name_as_string_matches_get_string() -> None:
    d = COSDictionary(
        [
            ("Sub", COSName.get_pdf_name("Form")),
            ("Title", COSString("hello")),
        ]
    )
    assert d.get_name_as_string("Sub") == "Form"
    assert d.get_name_as_string("Title") == "hello"
    assert d.get_name_as_string("Missing", "default") == "default"


def test_get_date_returns_default_for_non_cosstring_entry() -> None:
    d = COSDictionary([("Date", COSInteger.get(20240101))])
    assert d.get_date("Date") is None
    assert d.get_date("Date", default=dt.datetime(1999, 1, 1, tzinfo=dt.UTC)) == dt.datetime(
        1999, 1, 1, tzinfo=dt.UTC
    )


def test_get_date_returns_parsed_datetime() -> None:
    d = COSDictionary([("Date", COSString("D:20240315120000Z"))])
    parsed = d.get_date("Date")
    assert parsed == dt.datetime(2024, 3, 15, 12, 0, 0, tzinfo=dt.UTC)


def test_get_date_returns_default_for_unparseable_string() -> None:
    d = COSDictionary([("Date", COSString("notadate"))])
    assert d.get_date("Date") is None


def test_get_embedded_date_returns_default_when_outer_missing() -> None:
    d = COSDictionary()
    fallback = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
    assert d.get_embedded_date("Outer", "Inner", default=fallback) == fallback


def test_get_embedded_int_falls_back_when_outer_missing() -> None:
    d = COSDictionary()
    assert d.get_embedded_int("Outer", "Inner", default=-77) == -77


def test_get_embedded_string_falls_back_when_outer_present_but_key_missing() -> None:
    inner = COSDictionary([("Y", COSString("yes"))])
    d = COSDictionary([("Outer", inner)])
    assert d.get_embedded_string("Outer", "Missing", "fallback") == "fallback"
    assert d.get_embedded_string("Outer", "Y") == "yes"


def test_get_cos_name_default_returned_when_absent() -> None:
    sentinel = COSName.get_pdf_name("Default")
    d = COSDictionary()
    assert d.get_cos_name("Sub", sentinel) is sentinel


def test_get_cos_name_default_returned_for_non_name_value() -> None:
    sentinel = COSName.get_pdf_name("Default")
    d = COSDictionary([("Sub", COSString("text"))])
    assert d.get_cos_name("Sub", sentinel) is sentinel


def test_get_cos_name_returns_name_when_present() -> None:
    pages = COSName.get_pdf_name("Pages")
    d = COSDictionary([("Type", pages)])
    assert d.get_cos_name("Type") is pages


def test_get_cos_dictionary_returns_none_for_non_dict_value() -> None:
    d = COSDictionary([("X", COSInteger.get(5))])
    assert d.get_cos_dictionary("X") is None


def test_get_cos_array_returns_none_for_non_array_value() -> None:
    d = COSDictionary([("X", COSInteger.get(5))])
    assert d.get_cos_array("X") is None


def test_get_cos_array_returns_array_when_present() -> None:
    arr = COSArray([COSInteger.get(1)])
    d = COSDictionary([("Kids", arr)])
    assert d.get_cos_array("Kids") is arr


def test_get_flag_reads_bitmask() -> None:
    d = COSDictionary([("Flags", COSInteger.get(0b1010))])
    assert d.get_flag("Flags", 0b1000) is True
    assert d.get_flag("Flags", 0b0100) is False
    assert d.get_flag("Flags", 0b0010) is True


def test_set_flag_toggles_bit_via_set_int() -> None:
    d = COSDictionary([("Flags", COSInteger.get(0b0001))])
    d.set_flag("Flags", 0b1000, True)
    assert d.get_int("Flags") == 0b1001
    d.set_flag("Flags", 0b0001, False)
    assert d.get_int("Flags") == 0b1000


def test_get_int_resolves_cosobject_to_null_falls_back_to_default() -> None:
    d = COSDictionary([("X", COSObject(9, 0, resolved=COSNull.NULL))])
    assert d.get_int("X", default=33) == 33


def test_get_string_falls_back_for_indirect_null_object() -> None:
    d = COSDictionary([("Title", COSObject(2, 0, resolved=COSNull.NULL))])
    assert d.get_string("Title", default="fallback") == "fallback"


def test_set_string_with_none_removes_entry() -> None:
    d = COSDictionary([("Title", COSString("old"))])
    d.set_string("Title", None)
    assert "Title" not in d


def test_set_name_with_none_removes_entry() -> None:
    d = COSDictionary([("Type", COSName.get_pdf_name("Page"))])
    d.set_name("Type", None)
    assert "Type" not in d


def test_set_date_with_none_removes_entry() -> None:
    d = COSDictionary([("CreationDate", COSString("D:20240101000000Z"))])
    d.set_date("CreationDate", None)
    assert "CreationDate" not in d


def test_set_int_overwrites_existing_value() -> None:
    d = COSDictionary([("Count", COSInteger.get(1))])
    d.set_int("Count", 99)
    assert d.get_int("Count") == 99


def test_has_int_distinguishes_numeric_and_non_numeric() -> None:
    d = COSDictionary(
        [
            ("I", COSInteger.get(7)),
            ("F", COSFloat(7.5)),
            ("S", COSString("nope")),
        ]
    )
    assert d.has_int("I") is True
    assert d.has_int("F") is True  # COSFloat coerced via get_int
    assert d.has_int("S") is False
    assert d.has_int("Missing") is False


def test_has_string_true_for_both_name_and_string() -> None:
    d = COSDictionary(
        [
            ("S", COSString("hello")),
            ("N", COSName.get_pdf_name("Hi")),
        ]
    )
    assert d.has_string("S") is True
    assert d.has_string("N") is True


def test_clear_int_removes_entry() -> None:
    d = COSDictionary([("Count", COSInteger.get(5))])
    d.clear_int("Count")
    assert "Count" not in d


@pytest.mark.parametrize(
    "method,value",
    [
        ("clear_int", COSInteger.get(1)),
        ("clear_long", COSInteger.get(1)),
        ("clear_float", COSFloat(1.0)),
        ("clear_boolean", COSBoolean.TRUE),
        ("clear_string", COSString("x")),
        ("clear_name", COSName.get_pdf_name("X")),
        ("clear_cos_dictionary", COSDictionary()),
        ("clear_cos_array", COSArray()),
    ],
    ids=[
        "int",
        "long",
        "float",
        "boolean",
        "string",
        "name",
        "dict",
        "array",
    ],
)
def test_typed_clear_helpers_remove_entry(method: str, value: object) -> None:
    d = COSDictionary([("K", value)])
    getattr(d, method)("K")
    assert "K" not in d
