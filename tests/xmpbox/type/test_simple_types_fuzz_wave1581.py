"""Fuzz / characterization tests for xmpbox simple value types (wave 1581).

Hammers the parse/format/validation contract of RealType, IntegerType,
BooleanType and DateType against the behaviour of their upstream Java
counterparts (``org.apache.xmpbox.type.*`` in PDFBox 3.0.7). The expected
values in the RealType / IntegerType acceptance tables were produced by running
``Float.parseFloat`` / ``Float.toString`` and ``Integer.parseInt`` /
``Integer.toString`` on the bundled ``xmpbox-3.0.7`` reference and asserting the
Python port reproduces them byte-for-byte (lower-case ``inf``/``nan`` rejected,
``Infinity``/``NaN``/``1.5f``/hex-float accepted, int32 bounds enforced, etc.).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from pypdfbox.xmpbox import (
    BooleanType,
    DateType,
    IntegerType,
    RealType,
    XMPMetadata,
)
from pypdfbox.xmpbox.type.abstract_simple_property import AbstractSimpleProperty


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def _real(metadata: XMPMetadata, value: object) -> RealType:
    return RealType(metadata, "ns", "p", "x", value)


def _integer(metadata: XMPMetadata, value: object) -> IntegerType:
    return IntegerType(metadata, "ns", "p", "x", value)


def _boolean(metadata: XMPMetadata, value: object) -> BooleanType:
    return BooleanType(metadata, "ns", "p", "x", value)


def _date(metadata: XMPMetadata, value: object) -> DateType:
    return DateType(metadata, "ns", "p", "x", value)


# --------------------------------------------------------------------------- #
# RealType: accepted string grammar (Float.parseFloat) + Float.toString render #
# --------------------------------------------------------------------------- #

# (input string, expected float value, expected get_string_value()).
_REAL_ACCEPT = [
    ("1.5", 1.5, "1.5"),
    ("-2.25", -2.25, "-2.25"),
    ("0", 0.0, "0.0"),
    ("1e3", 1000.0, "1000.0"),
    ("1E3", 1000.0, "1000.0"),
    (".5", 0.5, "0.5"),
    ("5.", 5.0, "5.0"),
    ("Infinity", float("inf"), "Infinity"),
    ("-Infinity", float("-inf"), "-Infinity"),
    ("+Infinity", float("inf"), "Infinity"),
    ("1.5f", 1.5, "1.5"),
    ("1.5F", 1.5, "1.5"),
    ("1.5d", 1.5, "1.5"),
    ("1.5D", 1.5, "1.5"),
    ("0x1.8p1", 3.0, "3.0"),
    ("0X1.8P1", 3.0, "3.0"),
    ("  1.5  ", 1.5, "1.5"),
]


@pytest.mark.parametrize(
    ("text", "expected", "rendered"),
    _REAL_ACCEPT,
    ids=[c[0].strip() or "blank" for c in _REAL_ACCEPT],
)
def test_real_accepts_java_float_grammar(
    metadata: XMPMetadata, text: str, expected: float, rendered: str
) -> None:
    field = _real(metadata, text)
    assert field.get_value() == expected
    assert field.get_string_value() == rendered


def test_real_accepts_hex_float_with_type_suffix(metadata: XMPMetadata) -> None:
    # Exercises the hex branch of _parse_java_float where a trailing d/D after
    # the mandatory binary exponent is the Java type suffix, not a hex digit.
    field = _real(metadata, "0x1.8p1d")
    assert field.get_value() == 3.0


def test_real_nan_round_trips(metadata: XMPMetadata) -> None:
    field = _real(metadata, "NaN")
    value = field.get_value()
    assert value != value  # NaN is the only value not equal to itself.
    assert field.get_string_value() == "NaN"


# Strings Float.parseFloat rejects (NumberFormatException) -> ValueError.
_REAL_REJECT = [
    "inf",
    "nan",
    "infinity",
    "Inf",
    "1_000.0",
    "1,5",
    "",
    "   ",
    "abc",
    "1.5.5",
    "0x1.8",  # hex float missing the mandatory binary exponent
    "++1",
    "1f5",
]


@pytest.mark.parametrize("text", _REAL_REJECT, ids=[t or "blank" for t in _REAL_REJECT])
def test_real_rejects_non_java_float(metadata: XMPMetadata, text: str) -> None:
    with pytest.raises(ValueError):
        _real(metadata, text)


def test_real_rejects_bool(metadata: XMPMetadata) -> None:
    # bool is a subclass of int in Python; upstream Boolean is not Float.
    with pytest.raises(ValueError):
        _real(metadata, True)


def test_real_rejects_non_numeric_object(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        _real(metadata, object())


def test_real_from_float_and_int(metadata: XMPMetadata) -> None:
    assert _real(metadata, 2.5).get_value() == 2.5
    # int is accepted as a numeric source (documented port divergence).
    assert _real(metadata, 3).get_value() == 3.0


def test_real_get_value_is_float(metadata: XMPMetadata) -> None:
    assert isinstance(_real(metadata, "1.5").get_value(), float)
    assert isinstance(_real(metadata, 7).get_value(), float)


def test_real_narrows_to_single_precision(metadata: XMPMetadata) -> None:
    # Upstream stores a Java float; Float.toString(3.14159265358979f) -> 3.1415927.
    field = _real(metadata, 3.14159265358979)
    assert field.get_string_value() == "3.1415927"


def test_real_overflows_to_infinity(metadata: XMPMetadata) -> None:
    # 1e40 exceeds float32 max -> single-precision Infinity, like Java.
    field = _real(metadata, 1.0e40)
    assert field.get_value() == float("inf")
    assert field.get_string_value() == "Infinity"


def test_real_set_value_replaces(metadata: XMPMetadata) -> None:
    field = _real(metadata, "1.5")
    field.set_value("-2.0")
    assert field.get_value() == -2.0
    assert field.get_string_value() == "-2.0"


# --------------------------------------------------------------------------- #
# IntegerType: Integer.parseInt grammar + int32 bounds                         #
# --------------------------------------------------------------------------- #

_INT_ACCEPT = [
    ("12", 12),
    ("+12", 12),
    ("-12", -12),
    ("0", 0),
    ("007", 7),
    ("2147483647", 2147483647),
    ("-2147483648", -2147483648),
]


@pytest.mark.parametrize(("text", "expected"), _INT_ACCEPT, ids=[c[0] for c in _INT_ACCEPT])
def test_integer_accepts_decimal(metadata: XMPMetadata, text: str, expected: int) -> None:
    field = _integer(metadata, text)
    assert field.get_value() == expected
    assert field.get_string_value() == str(expected)


_INT_REJECT = [
    "2147483648",  # Integer.MAX_VALUE + 1 overflow
    "-2147483649",  # Integer.MIN_VALUE - 1 overflow
    " 12",  # Integer.parseInt rejects whitespace
    "12 ",
    "0x10",  # no radix prefix support
    "1.0",
    "",
    "+",
    "-",
    "abc",
    "1_000",
    "12L",
]


@pytest.mark.parametrize("text", _INT_REJECT, ids=[t or "blank" for t in _INT_REJECT])
def test_integer_rejects_non_decimal_or_overflow(metadata: XMPMetadata, text: str) -> None:
    with pytest.raises(ValueError):
        _integer(metadata, text)


def test_integer_direct_int_bounds(metadata: XMPMetadata) -> None:
    assert _integer(metadata, 2**31 - 1).get_value() == 2**31 - 1
    assert _integer(metadata, -(2**31)).get_value() == -(2**31)
    with pytest.raises(ValueError):
        _integer(metadata, 2**31)
    with pytest.raises(ValueError):
        _integer(metadata, -(2**31) - 1)


def test_integer_rejects_bool(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        _integer(metadata, True)


def test_integer_rejects_float_and_object(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        _integer(metadata, 1.5)
    with pytest.raises(ValueError):
        _integer(metadata, object())


def test_integer_get_value_is_int(metadata: XMPMetadata) -> None:
    assert isinstance(_integer(metadata, "42").get_value(), int)


# --------------------------------------------------------------------------- #
# BooleanType: trim().toUpperCase() match, exact "True"/"False" serialization  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", ["True", "TRUE", "true", "  TrUe  ", "tRuE"])
def test_boolean_truthy_strings(metadata: XMPMetadata, text: str) -> None:
    # Upstream BooleanType.setValue does value.trim().toUpperCase() then
    # equals "TRUE" — case-insensitive with trimming.
    field = _boolean(metadata, text)
    assert field.get_value() is True
    assert field.get_string_value() == "True"


@pytest.mark.parametrize("text", ["False", "FALSE", "false", "  fAlSe  ", "FaLsE"])
def test_boolean_falsey_strings(metadata: XMPMetadata, text: str) -> None:
    field = _boolean(metadata, text)
    assert field.get_value() is False
    assert field.get_string_value() == "False"


def test_boolean_from_bool(metadata: XMPMetadata) -> None:
    assert _boolean(metadata, True).get_value() is True
    assert _boolean(metadata, False).get_value() is False
    assert _boolean(metadata, True).get_string_value() == "True"
    assert _boolean(metadata, False).get_string_value() == "False"


@pytest.mark.parametrize("text", ["yes", "no", "1", "0", "T", "F", "", "truee"])
def test_boolean_rejects_invalid_string(metadata: XMPMetadata, text: str) -> None:
    with pytest.raises(ValueError):
        _boolean(metadata, text)


def test_boolean_rejects_non_string_non_bool(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        _boolean(metadata, 12)
    with pytest.raises(ValueError):
        _boolean(metadata, object())


def test_boolean_get_value_is_bool(metadata: XMPMetadata) -> None:
    assert isinstance(_boolean(metadata, "true").get_value(), bool)


# --------------------------------------------------------------------------- #
# DateType: ISO-8601 / partial / PDF-dict parse + toISO8601 round-trip         #
# --------------------------------------------------------------------------- #


def test_date_full_iso8601_round_trip(metadata: XMPMetadata) -> None:
    field = _date(metadata, "2024-06-16T12:30:00Z")
    value = field.get_value()
    assert value == datetime(2024, 6, 16, 12, 30, 0, tzinfo=UTC)
    assert field.get_string_value() == "2024-06-16T12:30:00+00:00"


def test_date_with_explicit_offset(metadata: XMPMetadata) -> None:
    field = _date(metadata, "2024-06-16T12:30:00+02:00")
    value = field.get_value()
    assert value.utcoffset() == timedelta(hours=2)
    assert field.get_string_value() == "2024-06-16T12:30:00+02:00"


@pytest.mark.parametrize(
    ("text", "year", "month", "day"),
    [
        ("2024", 2024, 1, 1),
        ("2024-06", 2024, 6, 1),
        ("2024-06-16", 2024, 6, 16),
    ],
)
def test_date_partial_iso8601(
    metadata: XMPMetadata, text: str, year: int, month: int, day: int
) -> None:
    field = _date(metadata, text)
    value = field.get_value()
    assert (value.year, value.month, value.day) == (year, month, day)


def test_date_pdf_dictionary_form(metadata: XMPMetadata) -> None:
    field = _date(metadata, "D:20240616123000")
    value = field.get_value()
    assert (value.year, value.month, value.day) == (2024, 6, 16)
    assert (value.hour, value.minute, value.second) == (12, 30, 0)


def test_date_from_datetime(metadata: XMPMetadata) -> None:
    moment = datetime(2020, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=-5)))
    field = _date(metadata, moment)
    assert field.get_value() == moment


def test_date_from_plain_date_is_utc_midnight(metadata: XMPMetadata) -> None:
    field = _date(metadata, date(2020, 1, 2))
    value = field.get_value()
    assert value == datetime(2020, 1, 2, 0, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize("text", ["not-a-date", "garbage", "2024-99-XX"])
def test_date_rejects_malformed(metadata: XMPMetadata, text: str) -> None:
    # Genuinely unparseable strings (DateConverter.toCalendar throws IOException
    # -> ValueError). Out-of-range-but-numeric fields like "2024-13-01" are NOT
    # rejected: java.util.Calendar is lenient by default and rolls them over.
    with pytest.raises(ValueError):
        _date(metadata, text)


def test_date_lenient_month_rollover(metadata: XMPMetadata) -> None:
    # Upstream Calendar is lenient: month 13 rolls into the next January.
    # DateConverter.toCalendar("2024-13-01") -> 2025-01-01 (verified against
    # xmpbox-3.0.7). Only the year/month/day are asserted; the stored zone is
    # the machine default, which differs across CI hosts.
    value = _date(metadata, "2024-13-01").get_value()
    assert (value.year, value.month, value.day) == (2025, 1, 1)


def test_date_rejects_none_and_wrong_type(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        _date(metadata, None)
    with pytest.raises(ValueError):
        _date(metadata, 12345)


def test_date_is_good_type(metadata: XMPMetadata) -> None:
    field = _date(metadata, "2024-06-16T12:30:00Z")
    assert field.is_good_type("2020-01-01") is True
    assert field.is_good_type(datetime(2020, 1, 1, tzinfo=UTC)) is True
    assert field.is_good_type(date(2020, 1, 1)) is True
    assert field.is_good_type("garbage") is False
    assert field.is_good_type(42) is False


# --------------------------------------------------------------------------- #
# AbstractSimpleProperty contract: raw value, namespace/prefix, to_string      #
# --------------------------------------------------------------------------- #


def test_all_simple_types_subclass_abstract() -> None:
    for cls in (RealType, IntegerType, BooleanType, DateType):
        assert issubclass(cls, AbstractSimpleProperty)


def test_raw_value_is_retained(metadata: XMPMetadata) -> None:
    # get_raw_value returns the *original* constructor argument verbatim,
    # before any parsing/narrowing.
    assert _real(metadata, "1.5").get_raw_value() == "1.5"
    assert _integer(metadata, "007").get_raw_value() == "007"
    assert _boolean(metadata, "true").get_raw_value() == "true"


def test_namespace_prefix_property_name(metadata: XMPMetadata) -> None:
    field = RealType(metadata, "http://ns/", "pre", "ratio", 2.5)
    assert field.get_namespace() == "http://ns/"
    assert field.get_prefix() == "pre"
    assert field.get_property_name() == "ratio"


def test_to_string_format(metadata: XMPMetadata) -> None:
    # Upstream: "[" + name + "=" + simpleClassName + ":" + stringValue + "]".
    field = _boolean(metadata, True)
    assert str(field) == "[x=BooleanType:True]"
    assert repr(field) == "[x=BooleanType:True]"
    assert _integer(metadata, "5").to_string() == "[x=IntegerType:5]"
