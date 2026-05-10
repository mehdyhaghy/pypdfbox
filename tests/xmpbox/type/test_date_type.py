from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from pypdfbox.xmpbox import DateType, XMPMetadata
from pypdfbox.xmpbox.date_converter import to_iso8601
from pypdfbox.xmpbox.type import TypeMapping
from pypdfbox.xmpbox.type.abstract_simple_property import AbstractSimpleProperty


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_date_is_simple_property() -> None:
    # Upstream DateType extends AbstractSimpleProperty; the port preserves it.
    assert issubclass(DateType, AbstractSimpleProperty)


def test_date_from_datetime_aware(metadata: XMPMetadata) -> None:
    dt = datetime(2010, 3, 22, 14, 33, 11, tzinfo=timezone(timedelta(hours=1)))
    field = DateType(metadata, "ns", "p", "when", dt)
    assert field.get_value() == dt
    # ISO 8601 round-trip via DateConverter.toISO8601.
    assert field.get_string_value() == "2010-03-22T14:33:11+01:00"


def test_date_from_naive_datetime_treated_as_utc(metadata: XMPMetadata) -> None:
    # Upstream Calendar always carries a zone; the port preserves whatever
    # tzinfo it gets and DateConverter.toISO8601 attaches UTC for naive
    # values when serializing.
    naive = datetime(2024, 1, 2, 3, 4, 5)
    field = DateType(metadata, "ns", "p", "when", naive)
    assert field.get_value() is naive
    assert field.get_string_value() == "2024-01-02T03:04:05+00:00"


def test_date_from_plain_date_promotes_to_midnight_utc(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", date(2010, 3, 22))
    value = field.get_value()
    assert value == datetime(2010, 3, 22, tzinfo=UTC)
    assert field.get_string_value() == "2010-03-22T00:00:00+00:00"


def test_date_from_iso_string_with_offset(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", "2010-03-22T14:33:11+01:00")
    assert field.get_string_value() == "2010-03-22T14:33:11+01:00"


def test_date_from_iso_string_with_z(metadata: XMPMetadata) -> None:
    # The 'Z' designator must round-trip to '+00:00' (UTC).
    field = DateType(metadata, "ns", "p", "when", "2010-03-22T14:33:11Z")
    assert field.get_value().tzinfo is not None
    assert field.get_string_value() == "2010-03-22T14:33:11+00:00"


def test_date_from_partial_iso_year_only(metadata: XMPMetadata) -> None:
    # Upstream DateConverter accepts year-only partial dates; the port now
    # delegates to DateConverter so DateType matches that surface.
    field = DateType(metadata, "ns", "p", "when", "2010")
    assert field.get_value().year == 2010
    assert field.get_value().month == 1
    assert field.get_value().day == 1


def test_date_from_partial_iso_year_month(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", "2010-03")
    val = field.get_value()
    assert (val.year, val.month, val.day) == (2010, 3, 1)


def test_date_from_partial_iso_date_only(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", "2010-03-22")
    val = field.get_value()
    assert (val.year, val.month, val.day) == (2010, 3, 22)
    assert (val.hour, val.minute, val.second) == (0, 0, 0)


def test_date_from_pdf_dictionary_form(metadata: XMPMetadata) -> None:
    # PDF dictionary date form 'D:YYYYMMDDhhmmss' is the input shape used by
    # PDFBox's PDDocumentInformation; upstream DateConverter parses it, so
    # DateType must accept it too.
    field = DateType(metadata, "ns", "p", "when", "D:20100322143311Z")
    val = field.get_value()
    assert (val.year, val.month, val.day) == (2010, 3, 22)
    assert (val.hour, val.minute, val.second) == (14, 33, 11)


def test_wave324_date_type_accepts_pdf_apostrophe_offset(
    metadata: XMPMetadata,
) -> None:
    field = DateType(metadata, "ns", "p", "when", "D:20100322143311-05'30'")
    assert field.get_string_value() == "2010-03-22T14:33:11-05:30"


def test_date_rejects_garbage_string(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        DateType(metadata, "ns", "p", "when", "not a date")


def test_date_rejects_empty_string(metadata: XMPMetadata) -> None:
    # DateConverter returns None for empty / whitespace strings; DateType
    # must surface that as a ValueError (mirrors upstream isGoodType).
    with pytest.raises(ValueError):
        DateType(metadata, "ns", "p", "when", "")


def test_date_rejects_whitespace_only_string(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        DateType(metadata, "ns", "p", "when", "   ")


def test_date_rejects_none(metadata: XMPMetadata) -> None:
    # Upstream throws IllegalArgumentException with a None-specific message.
    with pytest.raises(ValueError, match="null"):
        DateType(metadata, "ns", "p", "when", None)


def test_date_rejects_non_datetime_object(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        DateType(metadata, "ns", "p", "when", 12345)


def test_date_set_value_replaces(metadata: XMPMetadata) -> None:
    field = DateType(
        metadata, "ns", "p", "when", datetime(2010, 1, 1, tzinfo=UTC)
    )
    field.set_value(datetime(2020, 12, 31, 23, 59, 59, tzinfo=UTC))
    assert field.get_value().year == 2020
    assert field.get_string_value() == "2020-12-31T23:59:59+00:00"


def test_date_namespace_and_prefix(metadata: XMPMetadata) -> None:
    field = DateType(
        metadata, "http://ns/", "pre", "when", "2010-03-22T14:33:11Z"
    )
    assert field.get_namespace() == "http://ns/"
    assert field.get_prefix() == "pre"
    assert field.get_property_name() == "when"


def test_date_raw_value_preserved(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", "2010-03-22T14:33:11Z")
    assert field.get_raw_value() == "2010-03-22T14:33:11Z"


def test_date_repr_matches_upstream_to_string(metadata: XMPMetadata) -> None:
    # Upstream AbstractSimpleProperty#toString:
    # "[" + propertyName + "=" + simpleClassName + ":" + stringValue + "]"
    field = DateType(metadata, "ns", "p", "when", "2010-03-22T14:33:11Z")
    assert repr(field) == f"[when=DateType:{field.get_string_value()}]"


def test_date_get_string_value_uses_date_converter(metadata: XMPMetadata) -> None:
    # The string serialization must agree byte-for-byte with the standalone
    # DateConverter helper, since upstream DateType.getStringValue forwards to it.
    dt = datetime(2010, 3, 22, 14, 33, 11, tzinfo=timezone(timedelta(hours=-5)))
    field = DateType(metadata, "ns", "p", "when", dt)
    assert field.get_string_value() == to_iso8601(dt)


def test_date_round_trip_via_string(metadata: XMPMetadata) -> None:
    # Constructing from a string and re-serializing should be idempotent for
    # canonical full ISO 8601 strings.
    canonical = "2010-03-22T14:33:11+01:00"
    field = DateType(metadata, "ns", "p", "when", canonical)
    assert field.get_string_value() == canonical


def test_date_registry_returns_date_type(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.instanciate_simple_property(
        "ns", "p", "when", "2010-03-22T14:33:11Z", "Date"
    )
    assert isinstance(instance, DateType)


def test_date_set_value_replaces_with_string(metadata: XMPMetadata) -> None:
    field = DateType(
        metadata, "ns", "p", "when", datetime(2010, 1, 1, tzinfo=UTC)
    )
    field.set_value("2024-06-15T08:30:00Z")
    val = field.get_value()
    assert (val.year, val.month, val.day) == (2024, 6, 15)
    assert (val.hour, val.minute) == (8, 30)


def test_is_good_type_accepts_datetime(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", datetime(2010, 1, 1, tzinfo=UTC))
    assert field.is_good_type(datetime(2024, 1, 1, tzinfo=UTC)) is True


def test_is_good_type_accepts_date(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", datetime(2010, 1, 1, tzinfo=UTC))
    assert field.is_good_type(date(2024, 1, 1)) is True


def test_is_good_type_accepts_parseable_string(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", datetime(2010, 1, 1, tzinfo=UTC))
    assert field.is_good_type("2010-03-22T14:33:11+01:00") is True


def test_is_good_type_rejects_unparseable_string(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", datetime(2010, 1, 1, tzinfo=UTC))
    assert field.is_good_type("not a date") is False


def test_is_good_type_rejects_empty_string(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", datetime(2010, 1, 1, tzinfo=UTC))
    # to_calendar returns None for empty/whitespace; isGoodType therefore False.
    assert field.is_good_type("") is False


def test_is_good_type_rejects_other_types(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", datetime(2010, 1, 1, tzinfo=UTC))
    assert field.is_good_type(12345) is False
    assert field.is_good_type(None) is False
    assert field.is_good_type([]) is False


def test_set_value_from_calendar_with_datetime(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", datetime(2010, 1, 1, tzinfo=UTC))
    new_val = datetime(2030, 6, 15, 12, 0, 0, tzinfo=UTC)
    field.set_value_from_calendar(new_val)
    assert field.get_value() == new_val


def test_set_value_from_calendar_with_date_promotes_to_midnight_utc(
    metadata: XMPMetadata,
) -> None:
    field = DateType(metadata, "ns", "p", "when", datetime(2010, 1, 1, tzinfo=UTC))
    field.set_value_from_calendar(date(2030, 6, 15))
    assert field.get_value() == datetime(2030, 6, 15, tzinfo=UTC)


def test_set_value_from_string_parses_iso(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", datetime(2010, 1, 1, tzinfo=UTC))
    field.set_value_from_string("2024-06-15T08:30:00Z")
    val = field.get_value()
    assert (val.year, val.month, val.day) == (2024, 6, 15)


def test_set_value_from_string_rejects_garbage(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", datetime(2010, 1, 1, tzinfo=UTC))
    with pytest.raises(ValueError):
        field.set_value_from_string("not a date")


def test_set_value_from_string_rejects_empty(metadata: XMPMetadata) -> None:
    field = DateType(metadata, "ns", "p", "when", datetime(2010, 1, 1, tzinfo=UTC))
    with pytest.raises(ValueError):
        field.set_value_from_string("")
