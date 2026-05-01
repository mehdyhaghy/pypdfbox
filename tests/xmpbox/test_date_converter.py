from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from pypdfbox.xmpbox import DateConverter
from pypdfbox.xmpbox.date_converter import to_calendar, to_iso8601


def test_none_and_empty_return_none() -> None:
    assert DateConverter.to_calendar(None) is None
    assert DateConverter.to_calendar("") is None
    assert DateConverter.to_calendar("   ") is None


def test_partial_year_only() -> None:
    cal = DateConverter.to_calendar("2015")
    assert cal is not None
    assert cal.year == 2015


def test_partial_year_month() -> None:
    cal = DateConverter.to_calendar("2015-05")
    assert cal is not None
    assert cal.month == 5


def test_partial_year_month_day() -> None:
    cal = DateConverter.to_calendar("2015-05-02")
    assert cal is not None
    assert cal.year == 2015
    assert cal.month == 5
    assert cal.day == 2


def test_pdf_prefixed_date_only() -> None:
    cal = DateConverter.to_calendar("D:2015-02-02")
    assert cal is not None
    assert cal.year == 2015


def test_pdf_prefixed_full_no_zone() -> None:
    cal = DateConverter.to_calendar("D:2015-02-03T10:11:12")
    assert cal is not None
    assert cal.year == 2015
    assert cal.month == 2
    assert cal.day == 3
    assert cal.hour == 10
    assert cal.minute == 11
    assert cal.second == 12


def test_pdf_prefixed_full_with_z() -> None:
    cal = DateConverter.to_calendar("D:2015-02-03T10:11:12Z")
    assert cal is not None
    assert cal.year == 2015
    assert cal.month == 2
    assert cal.day == 3
    assert cal.utcoffset() == timedelta(0)


def test_iso8601_with_milliseconds() -> None:
    cal = DateConverter.to_calendar("2025-09-03T15:43:47.989082+00:00")
    assert cal is not None
    # 989 milliseconds = 989000 microseconds (the test asserts millisecond precision)
    assert cal.microsecond // 1000 == 989


def test_iso8601_with_z_suffix() -> None:
    cal = DateConverter.to_calendar("2015-02-02T16:37:19.192Z")
    assert cal is not None
    assert cal.utcoffset() == timedelta(0)


def test_iso8601_with_offset() -> None:
    cal = DateConverter.to_calendar("2015-02-02T16:37:19.192+02:00")
    assert cal is not None
    assert cal.utcoffset() == timedelta(hours=2)


def test_iso8601_half_hour_offset() -> None:
    # PDFBOX-4902 — half-hour TZ
    cal = DateConverter.to_calendar("2015-02-02T16:37:19.192+05:30")
    assert cal is not None
    assert cal.utcoffset() == timedelta(hours=5, minutes=30)


def test_iso8601_naive_falls_back_to_utc() -> None:
    cal = DateConverter.to_calendar("2024-04-09T14:41:38")
    assert cal is not None
    assert cal.utcoffset() == timedelta(0)


def test_invalid_short_string_raises() -> None:
    with pytest.raises(OSError):
        DateConverter.to_calendar("123")


def test_invalid_t_position_raises() -> None:
    with pytest.raises(OSError):
        DateConverter.to_calendar("D:1234T567")


def test_to_iso8601_round_trip_z() -> None:
    cal = DateConverter.to_calendar("2015-02-02T16:37:19.192Z")
    formatted = DateConverter.to_iso8601(cal, True)
    again = DateConverter.to_calendar(formatted)
    assert cal == again


def test_to_iso8601_format_no_millis() -> None:
    dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=UTC)
    assert DateConverter.to_iso8601(dt) == "2024-01-15T12:30:45+00:00"


def test_to_iso8601_format_with_millis() -> None:
    dt = datetime(2024, 1, 15, 12, 30, 45, 987000, tzinfo=UTC)
    assert DateConverter.to_iso8601(dt, True) == "2024-01-15T12:30:45.987+00:00"


def test_to_iso8601_negative_offset() -> None:
    tz = timezone(timedelta(hours=-5))
    dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=tz)
    assert DateConverter.to_iso8601(dt) == "2024-01-15T12:30:45-05:00"


def test_to_iso8601_naive_assumes_utc() -> None:
    dt = datetime(2024, 1, 15, 12, 30, 45)
    assert DateConverter.to_iso8601(dt) == "2024-01-15T12:30:45+00:00"


def test_module_level_functions_match_classmethods() -> None:
    cal_a = to_calendar("2015-05-02")
    cal_b = DateConverter.to_calendar("2015-05-02")
    assert cal_a == cal_b
    dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=UTC)
    assert to_iso8601(dt) == DateConverter.to_iso8601(dt)


def test_cannot_instantiate() -> None:
    with pytest.raises(TypeError):
        DateConverter()


def test_missing_seconds_iso() -> None:
    a = DateConverter.to_calendar("2015-12-08T12:07:00-05:00")
    b = DateConverter.to_calendar("2015-12-08T12:07-05:00")
    assert a == b


def test_missing_seconds_with_z() -> None:
    a = DateConverter.to_calendar("2011-11-20T10:09:00Z")
    b = DateConverter.to_calendar("2011-11-20T10:09Z")
    assert a == b
