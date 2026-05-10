"""Upstream-derived tests for ``DateConverter``.

Ported from:

* ``xmpbox/src/test/java/org/apache/xmpbox/DateConverterTest.java``
  (PDFBox 3.0.x).
* Selected scenarios from
  ``pdfbox/src/test/java/org/apache/pdfbox/util/TestDateUtil.java`` that
  exercise the package-private helpers (``parseTZoffset``,
  ``formatTZoffset``, ``newGreg``) the parity report flagged as missing.

Some scenarios are deliberately skipped — they depend on Java's
locale-sensitive ``SimpleDateFormat`` (full month/day name dictionaries) or
the JVM's TimeZone database. Those are documented inline next to the
xfail/skip marker.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from pypdfbox.xmpbox.date_converter import (
    DateConverter,
    ParsePosition,
    to_calendar,
    to_iso8601,
)

# --------------------------------------------------------------------- #
# DateConverterTest#testDateConversion (xmpbox)
# --------------------------------------------------------------------- #


def test_date_conversion_partial_year() -> None:
    cal = DateConverter.to_calendar("2015")
    assert cal is not None
    assert cal.year == 2015


def test_date_conversion_partial_year_month() -> None:
    cal = DateConverter.to_calendar("2015-05")
    assert cal is not None
    # In Python the month is 1-based; upstream's Calendar.MONTH is 0-based,
    # so upstream asserts ``4`` here.
    assert cal.month == 5


def test_date_conversion_partial_year_month_day() -> None:
    cal = DateConverter.to_calendar("2015-05-02")
    assert cal is not None
    assert cal.year == 2015
    assert cal.month == 5
    assert cal.day == 2


def test_date_conversion_pdf_prefixed_date_only() -> None:
    cal = DateConverter.to_calendar("D:2015-02-02")
    assert cal is not None
    assert cal.year == 2015


def test_date_conversion_pdf_prefixed_with_time() -> None:
    cal = DateConverter.to_calendar("D:2015-02-03T10:11:12")
    assert cal is not None
    assert cal.year == 2015
    assert cal.month == 2
    assert cal.day == 3
    assert cal.hour == 10
    assert cal.minute == 11
    assert cal.second == 12


def test_date_conversion_pdf_prefixed_with_z() -> None:
    cal = DateConverter.to_calendar("D:2015-02-03T10:11:12Z")
    assert cal is not None
    assert cal.year == 2015
    assert cal.month == 2
    assert cal.day == 3
    assert cal.hour == 10
    assert cal.minute == 11
    assert cal.second == 12


def test_date_conversion_milliseconds_truncation() -> None:
    cal = DateConverter.to_calendar("2025-09-03T15:43:47.989082+00:00")
    assert cal is not None
    # Upstream stores millis (3 digits); Python keeps microseconds. Both
    # truncate to 989 ms.
    assert cal.microsecond // 1000 == 989


@pytest.mark.parametrize(
    "bad",
    [
        "123",
        "2008-12-02T21:04:0Z",
        "0-01-01T00:00:00Z",
        "2009-03-16T01:15:19-0-4:00",
        "0-00-00T00:00:00-04:00",
    ],
)
def test_date_conversion_bad_strings_raise(bad: str) -> None:
    with pytest.raises(OSError):
        DateConverter.to_calendar(bad)


def test_date_conversion_missing_seconds_iso() -> None:
    a = DateConverter.to_calendar("2015-12-08T12:07:00-05:00")
    b = DateConverter.to_calendar("2015-12-08T12:07-05:00")
    assert a == b


def test_date_conversion_missing_seconds_z() -> None:
    a = DateConverter.to_calendar("2011-11-20T10:09:00Z")
    b = DateConverter.to_calendar("2011-11-20T10:09Z")
    assert a == b


def test_date_conversion_offset_round_trip_z() -> None:
    cal = DateConverter.to_calendar("2015-02-02T16:37:19.192Z")
    assert cal is not None
    assert cal.utcoffset() == timedelta(0)


def test_date_conversion_half_hour_offset_pdfbox_4902() -> None:
    cal = DateConverter.to_calendar("2015-02-02T16:37:19.192+05:30")
    assert cal is not None
    assert cal.utcoffset() == timedelta(hours=5, minutes=30)

    cal = DateConverter.to_calendar("2015-02-02T16:37:19.192-05:30")
    assert cal is not None
    assert cal.utcoffset() == -timedelta(hours=5, minutes=30)


def test_date_conversion_naive_falls_back_to_utc() -> None:
    cal = DateConverter.to_calendar("2024-04-09T14:41:38")
    assert cal is not None
    assert cal.utcoffset() == timedelta(0)


def test_date_conversion_none_and_empty() -> None:
    assert DateConverter.to_calendar(None) is None
    assert DateConverter.to_calendar("") is None


# --------------------------------------------------------------------- #
# DateConverterTest#testDateFormatting (xmpbox)
# --------------------------------------------------------------------- #


def test_date_formatting_round_trip_z() -> None:
    cal = DateConverter.to_calendar("2015-02-02T16:37:19.192Z")
    assert cal is not None
    formatted = DateConverter.to_iso8601(cal, True)
    parsed = DateConverter.to_calendar(formatted)
    assert parsed == cal


def test_date_formatting_round_trip_offset() -> None:
    cal = DateConverter.to_calendar("2015-02-02T16:37:19.192+09:09")
    assert cal is not None
    formatted = DateConverter.to_iso8601(cal, True)
    parsed = DateConverter.to_calendar(formatted)
    assert parsed == cal


def test_date_formatting_round_trip_offset_10_10() -> None:
    cal = DateConverter.to_calendar("2015-02-02T16:37:19.192+10:10")
    assert cal is not None
    formatted = DateConverter.to_iso8601(cal, True)
    parsed = DateConverter.to_calendar(formatted)
    assert parsed == cal


# --------------------------------------------------------------------- #
# pdfbox.util TestDateUtil#testParseTZ — package-private helper coverage
# --------------------------------------------------------------------- #


HRS = 60 * 60 * 1000
MINS = 60 * 1000


@pytest.mark.parametrize(
    ("expected_millis", "src"),
    [
        (0 * HRS + 0 * MINS, "+00:00"),
        (0 * HRS + 0 * MINS, "-0000"),
        (1 * HRS + 0 * MINS, "+1:00"),
        (-(1 * HRS + 0 * MINS), "-1:00"),
        (-(1 * HRS + 30 * MINS), "-0130"),
        (11 * HRS + 59 * MINS, "1159"),
        (12 * HRS + 30 * MINS, "1230"),
        (-(12 * HRS + 30 * MINS), "-12:30"),
        (0 * HRS + 0 * MINS, "Z"),
        (-(8 * HRS + 0 * MINS), "PST"),
        (0 * HRS + 0 * MINS, "EDT"),  # unknown name → no offset, parser leaves zero
        (-(3 * HRS + 0 * MINS), "GMT-0300"),
        (+(11 * HRS + 0 * MINS), "GMT+11:00"),
        (5 * HRS + 0 * MINS, "0500"),
        (5 * HRS + 0 * MINS, "+0500"),
        (11 * HRS + 0 * MINS, "+11'00'"),
        (12 * HRS + 0 * MINS, "+12:00"),
        (-(12 * HRS + 0 * MINS), "-12:00"),
        (14 * HRS + 0 * MINS, "1400"),
        (-(14 * HRS + 0 * MINS), "-1400"),
    ],
)
def test_parse_t_zoffset(expected_millis: int, src: str) -> None:
    cal = DateConverter.new_greg()
    DateConverter.parse_t_zoffset(src, cal, ParsePosition(0))
    assert cal.zone_offset == expected_millis


# --------------------------------------------------------------------- #
# pdfbox.util TestDateUtil#testFormatTZoffset
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("offset_hours", "expected"),
    [
        (-12.1, "-12:06"),
        (12.1, "+12:06"),
        (0, "+00:00"),
        (-1, "-01:00"),
        (0.5, "+00:30"),
        (-0.5, "-00:30"),
        (0.1, "+00:06"),
        (-0.1, "-00:06"),
        (-12, "-12:00"),
        (12, "+12:00"),
        (-11.5, "-11:30"),
        (11.5, "+11:30"),
        (11.9, "+11:54"),
        (11.1, "+11:06"),
        (-11.9, "-11:54"),
        (-11.1, "-11:06"),
        (14, "+14:00"),
        (-14, "-14:00"),
    ],
)
def test_format_t_zoffset(offset_hours: float, expected: str) -> None:
    millis = int(offset_hours * 60 * 60 * 1000)
    assert DateConverter.format_t_zoffset(millis, ":") == expected


# --------------------------------------------------------------------- #
# Coverage of the smaller helpers
# --------------------------------------------------------------------- #


def test_skip_optionals_advances_past_chars() -> None:
    where = ParsePosition(0)
    last = DateConverter.skip_optionals("   abc", where, " ")
    assert where.index == 3
    assert last == " "


def test_skip_optionals_returns_last_non_space() -> None:
    where = ParsePosition(0)
    last = DateConverter.skip_optionals("Z+ abc", where, "Z+ ")
    assert last == "+"
    assert where.index == 3


def test_skip_string_match() -> None:
    where = ParsePosition(0)
    assert DateConverter.skip_string("D:2015", "D:", where) is True
    assert where.index == 2


def test_skip_string_no_match() -> None:
    where = ParsePosition(0)
    assert DateConverter.skip_string("2015", "D:", where) is False
    assert where.index == 0


def test_parse_time_field_two_digit() -> None:
    where = ParsePosition(0)
    val = DateConverter.parse_time_field("12abc", where, 2, -1)
    assert val == 12
    assert where.index == 2


def test_parse_time_field_no_digits_returns_remedy() -> None:
    where = ParsePosition(0)
    val = DateConverter.parse_time_field("abc", where, 2, -999)
    assert val == -999
    assert where.index == 0


def test_new_greg_defaults_to_utc_non_lenient() -> None:
    cal = DateConverter.new_greg()
    assert cal.zone_offset == 0
    assert cal.tz_id == "UTC"
    assert cal.lenient is False
    assert cal.millisecond == 0


def test_restrain_t_zoffset_within_range_passthrough() -> None:
    assert DateConverter.restrain_t_zoffset(5 * HRS) == 5 * HRS
    assert DateConverter.restrain_t_zoffset(-14 * HRS) == -14 * HRS
    assert DateConverter.restrain_t_zoffset(14 * HRS) == 14 * HRS


def test_update_zone_id_gmt_for_zero_offset() -> None:
    cal = DateConverter.new_greg()
    cal.zone_offset = 0
    DateConverter.update_zone_id(cal)
    assert cal.tz_id == "GMT"


def test_update_zone_id_positive_offset() -> None:
    cal = DateConverter.new_greg()
    cal.zone_offset = 5 * HRS
    DateConverter.update_zone_id(cal)
    assert cal.tz_id == "GMT+05:00"


def test_update_zone_id_negative_offset() -> None:
    cal = DateConverter.new_greg()
    cal.zone_offset = -3 * HRS
    DateConverter.update_zone_id(cal)
    assert cal.tz_id == "GMT-03:00"


def test_update_zone_id_unknown_for_out_of_range() -> None:
    cal = DateConverter.new_greg()
    cal.zone_offset = 15 * HRS
    DateConverter.update_zone_id(cal)
    assert cal.tz_id == "unknown"


# --------------------------------------------------------------------- #
# parse_big_endian_date
# --------------------------------------------------------------------- #


def test_parse_big_endian_date_full() -> None:
    where = ParsePosition(0)
    cal = DateConverter.parse_big_endian_date("20100423000000", where)
    assert cal is not None
    assert cal.year == 2010
    assert cal.month == 4 - 1  # 0-based, parity with Calendar
    assert cal.day == 23


def test_parse_big_endian_date_year_only() -> None:
    where = ParsePosition(0)
    cal = DateConverter.parse_big_endian_date("2013", where)
    assert cal is not None
    assert cal.year == 2013


def test_parse_big_endian_date_returns_none_for_short_year() -> None:
    where = ParsePosition(0)
    cal = DateConverter.parse_big_endian_date("333", where)
    assert cal is None


# --------------------------------------------------------------------- #
# from_iso8601 helper exposed for parity
# --------------------------------------------------------------------- #


def test_from_iso8601_zoned() -> None:
    parsed = DateConverter.from_iso8601("2015-02-03T10:11:12+02:00")
    assert parsed == datetime(2015, 2, 3, 10, 11, 12, tzinfo=timezone(timedelta(hours=2)))


def test_from_iso8601_naive_falls_back_to_utc() -> None:
    parsed = DateConverter.from_iso8601("2024-04-09T14:41:38")
    assert parsed == datetime(2024, 4, 9, 14, 41, 38, tzinfo=UTC)


# --------------------------------------------------------------------- #
# to_string (PDF date format)
# --------------------------------------------------------------------- #


def test_to_string_none_returns_none() -> None:
    assert DateConverter.to_string(None) is None


def test_to_string_pdfbox_598() -> None:
    # Round-trip an upstream-style "D:20050526205258+01'00'" through to_calendar
    # and back. (Mirrors PDFBOX-598 from upstream TestDateUtil.testDateConversion.)
    cal = DateConverter.to_calendar("D:20050526205258+01'00'")
    assert cal is not None
    assert DateConverter.to_string(cal) == "D:20050526205258+01'00'"


def test_to_string_naive_assumes_utc() -> None:
    dt = datetime(2024, 1, 15, 12, 30, 45)
    assert DateConverter.to_string(dt) == "D:20240115123045+00'00'"


def test_to_string_negative_offset() -> None:
    tz = timezone(timedelta(hours=-5))
    dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=tz)
    assert DateConverter.to_string(dt) == "D:20240115123045-05'00'"


# --------------------------------------------------------------------- #
# Module-level stable surface
# --------------------------------------------------------------------- #


def test_module_level_to_calendar_matches_classmethod() -> None:
    a = to_calendar("2015-05-02")
    b = DateConverter.to_calendar("2015-05-02")
    assert a == b


def test_module_level_to_iso8601_matches_classmethod() -> None:
    dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=UTC)
    assert to_iso8601(dt) == DateConverter.to_iso8601(dt)


def test_cannot_instantiate() -> None:
    with pytest.raises(TypeError):
        DateConverter()


# --------------------------------------------------------------------- #
# parse_date dispatch
# --------------------------------------------------------------------- #


def test_parse_date_returns_none_for_empty_marker() -> None:
    assert DateConverter.parse_date("D:", ParsePosition(0)) is None
    assert DateConverter.parse_date("", ParsePosition(0)) is None
    assert DateConverter.parse_date(None, ParsePosition(0)) is None


def test_parse_date_full_pdf_with_offset() -> None:
    # PDFBOX-3315 — GMT+12 acceptance.
    cal = DateConverter.parse_date("20160411160115+12'00'", ParsePosition(0))
    assert cal is not None
    assert cal.year == 2016
    assert cal.month == 4 - 1
    assert cal.day == 11
    assert cal.hour == 16 - 12  # adjust_time_zone_nicely shifts wall clock back
    assert cal.zone_offset == 12 * HRS
