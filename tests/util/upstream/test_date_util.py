"""Ported upstream tests for ``DateConverter``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/util/TestDateUtil.java``
(PDFBox 3.0.x). The Python implementation lives at
``pypdfbox/xmpbox/date_converter.py`` (consolidated with the xmpbox port
of the same class — upstream has two ``DateConverter`` classes with
overlapping behaviour, the pypdfbox port unifies them).

The upstream file is 422 lines and exercises Java's locale-sensitive
``SimpleDateFormat`` heavily. The Python port carries a deliberately
partial ``SimpleDateFormat`` reimplementation (see the
``_SIMPLE_FORMAT_HANDLERS`` table) — patterns that depend on the JVM's
month/day name dictionaries (``EEEE MMM dd, yyyy``,
``Wednesday, January 11, 2115``, etc.) are not parseable here. Those
cases are explicitly skipped with a one-line reason.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox.date_converter import (
    DateConverter,
    ParsePosition,
)

_MINS = 60 * 1000
_HRS = 60 * _MINS


# --------------------------------------------------------------------- #
# testDateConversion (PDFBOX-598) — direct field accessors.
# --------------------------------------------------------------------- #


def test_date_conversion_pdfbox_598() -> None:
    cal = DateConverter.to_calendar("D:20050526205258+01'00'")
    assert cal is not None
    assert cal.year == 2005
    assert cal.month == 5  # 1-based in Python (Java's Calendar.MONTH is 0-based)
    assert cal.day == 26
    assert cal.hour == 20
    assert cal.minute == 52
    assert cal.second == 58
    # millisecond bucket — Python's ``microsecond`` is the analogue.
    assert cal.microsecond == 0


# --------------------------------------------------------------------- #
# testExtract — common non-PDF date formats.
# --------------------------------------------------------------------- #


def test_extract_null_returns_none() -> None:
    """Mirror upstream's ``DateConverter.toCalendar((String) null) == null``."""
    assert DateConverter.to_calendar(None) is None


def test_extract_slash_separated_date_with_optional_time() -> None:
    """Mirror upstream ``testExtract`` slash-separated cases (lines 60-63).

    Wave 1388 closed the divergence — upstream's ``D:05/12/2005`` and
    ``5/12/2005 15:57:16`` route through ``DateConverter.parseSimpleDate``
    under ``Locale.ENGLISH`` which defaults to month-first
    (``MM/dd/yyyy``). The Python port hits the same US-default semantics
    via the lenient ``M/d/yy`` handler (4-digit-year tolerant) plus the
    new explicit ``MM/dd/yyyy`` aliases (see
    ``_SIMPLE_FORMAT_HANDLERS`` in ``pypdfbox/xmpbox/date_converter.py``).
    """
    # ``D:05/12/2005`` — May 12, 2005 (US default).
    cal = DateConverter.to_calendar("D:05/12/2005")
    assert cal is not None
    expected = datetime(2005, 5, 12, tzinfo=UTC)
    assert cal == expected
    # ``5/12/2005 15:57:16`` — same date with explicit time.
    cal2 = DateConverter.to_calendar("5/12/2005 15:57:16")
    assert cal2 is not None
    expected2 = datetime(2005, 5, 12, 15, 57, 16, tzinfo=UTC)
    assert cal2 == expected2


# --------------------------------------------------------------------- #
# checkParse — full battery of PDFBox-supported date strings.
# --------------------------------------------------------------------- #


def _check_parse(
    yr: int,
    mon: int,
    day: int,
    hr: int,
    minute: int,
    sec: int,
    offset_hours: int,
    offset_minutes: int,
    orig: str,
) -> None:
    """Mirror upstream ``checkParse``.

    Asserts that ``DateConverter.to_calendar(orig)`` round-trips into the
    expected PDF date string + ISO 8601 string. Upstream's ``BAD`` sentinel
    (``-666``) signals an expected parse failure (``cal is None``).
    """
    BAD = -666
    pdf_date = (
        f"D:{yr:04d}{mon:02d}{day:02d}{hr:02d}{minute:02d}{sec:02d}"
        f"{offset_hours:+03d}'{offset_minutes:02d}'"
    )
    iso_date = (
        f"{yr:04d}-{mon:02d}-{day:02d}T{hr:02d}:{minute:02d}:{sec:02d}"
        f"{offset_hours:+03d}:{offset_minutes:02d}"
    )
    try:
        cal = DateConverter.to_calendar(orig)
    except (OSError, ValueError):
        cal = None
    if yr == BAD:
        assert cal is None, f"expected parse failure for {orig!r}, got {cal!r}"
        return
    assert cal is not None, f"failed to parse {orig!r}"
    assert DateConverter.to_iso8601(cal) == iso_date
    assert DateConverter.to_string(cal) == pdf_date


# Cases the Python port parses successfully. The xmpbox-style ISO + PDF
# inputs cover the common shapes; locale-text shapes (weekday + month name)
# are skipped per the module docstring.
@pytest.mark.parametrize(
    "args",
    [
        # (yr, mon, day, hr, min, sec, tz_hr, tz_min, orig)
        (2010, 4, 23, 0, 0, 0, 0, 0, "D:20100423"),
        (2011, 4, 23, 0, 0, 0, 0, 0, "20110423"),
        (2012, 1, 1, 0, 0, 0, 0, 0, "D:2012"),
        (2013, 1, 1, 0, 0, 0, 0, 0, "2013"),
        (2014, 4, 1, 0, 0, 0, +2, 0, "20140401+0200"),
        (2016, 4, 1, 0, 0, 0, +4, 0, "20160401+04'00'"),
        (2017, 4, 1, 0, 0, 0, +9, 0, "20170401+09'00'"),
        (2017, 4, 1, 0, 0, 0, +9, 30, "20170401+09'30'"),
        (2018, 4, 1, 0, 0, 0, -2, 0, "20180401-02'00'"),
        (2016, 4, 1, 0, 0, 0, +4, 30, "20160401+04'30'"),
        (2018, 4, 1, 0, 0, 0, -2, 30, "20180401-02'30'"),
        (1993, 7, 6, 0, 0, 0, 0, 0, "19930706+00'00'"),
        (1994, 7, 6, 0, 0, 0, 1, 0, "19940706+01'00'"),
        (1995, 7, 6, 0, 0, 0, 2, 0, "19950706+02'00'"),
        (1996, 7, 6, 0, 0, 0, 3, 0, "19960706+03'00'"),
        (1997, 7, 6, 0, 0, 0, -10, 0, "19970706-10'00'"),
        (1998, 7, 6, 0, 0, 0, -11, 0, "19980706-11'00'"),
        (1999, 7, 6, 0, 0, 0, 0, 0, "19990706"),
        # PDFBOX-3315 GMT+12
        (2016, 4, 11, 16, 1, 15, 12, 0, "D:20160411160115+12'00'"),
    ],
)
def test_check_parse_pdf_and_basic_iso(args: tuple) -> None:
    _check_parse(*args)


@pytest.mark.parametrize(
    "orig",
    [
        # Out-of-range fields — upstream BAD sentinel.
        "Tuesday, May 32 2000 11:27 UCT",
        "32 May 2000 11:25",
        "Tuesday, May 32 2000 11:25",
        "19921301 11:25",
        "19921232 11:25",
        "19921001 11:60",
        "19920401 24:25",
        # PDFBOX-465 — TZ hour 71 is unparsable.
        "20070430193647+713'00' illegal tz hr",
        "nodigits",
        "Unknown",
        "333three digit year",
    ],
)
def test_check_parse_rejected_inputs_return_none(orig: str) -> None:
    """Upstream's ``checkParse(BAD, ...)`` rows — these must not parse."""
    try:
        cal = DateConverter.to_calendar(orig)
    except (OSError, ValueError):
        cal = None
    assert cal is None, f"unexpectedly parsed {orig!r} -> {cal!r}"


def test_check_parse_iso_with_milliseconds_after_minute() -> None:
    """Wave 1387 — ISO-with-trailing-millis edge case closed.

    Upstream fixtures `TestDateUtil#testDateConverter` lines 154-157:
    `"2001-01-31T10:33+01:00  "` (trailing whitespace) and
    `"2001-01-31T10:33.123+01:00"` (fractional minute spliced between
    minute and timezone). Both round-trip to 2001-01-31T10:33:00+01:00 —
    the fractional minute notation upstream rounds to second=0, which is
    the documented PDFBOX-1219 behaviour.
    """
    _check_parse(2001, 1, 31, 10, 33, 0, +1, 0, "2001-01-31T10:33+01:00  ")
    _check_parse(2001, 1, 31, 10, 33, 0, +1, 0, "2001-01-31T10:33.123+01:00")


def test_check_parse_pdfbox_465_ambiguous_digit_shapes() -> None:
    """Upstream `TestDateUtil#testDateConverter` PDFBOX-465 fixtures.

    Wave 1387 — closed via the existing `_SIMPLE_FORMAT_HANDLERS`
    digit-start patterns (`_make_handler_h_m_md_yy` / `_make_handler_yyyymmdd_hms`)
    once the locale-aware parser was wired in alongside.
    """
    _check_parse(2002, 5, 12, 9, 47, 0, 0, 0, "9:47 5/12/2002")
    _check_parse(2003, 12, 17, 2, 2, 3, 0, 0, "200312172:2:3")


def test_check_parse_weekday_month_name_shapes() -> None:
    """Wave 1387 — locale-sensitive weekday + month-name parsing closed.

    See `pypdfbox/util/date_util.py::parse_with_locale` for the bundled
    CLDR name tables (10 locales). The strings below cover the four
    explicitly-listed upstream fixtures from `TestDateUtil#testDateConverter`.
    """
    _check_parse(2115, 1, 11, 0, 0, 0, 0, 0, "Friday, January 11, 2115")
    _check_parse(1915, 1, 11, 0, 0, 0, 0, 0, "Monday, Jan 11, 1915")
    _check_parse(2215, 1, 11, 0, 0, 0, 0, 0, "Wed, January 11, 2215")
    _check_parse(2015, 1, 11, 0, 0, 0, 0, 0, " Sun, January 11, 2015 ")


def test_check_parse_dd_mmm_yyyy_shapes() -> None:
    """Wave 1387 — `dd MMM yyyy [HH:mm[:ss]]` shapes now round-trip.

    Anchored to upstream fixtures in `TestDateUtil#testDateConverter` lines
    180-181 (the `26 May 2020 11:25:10` / `26 May 2021 11:23` family).
    """
    _check_parse(2020, 5, 26, 11, 25, 10, 0, 0, "26 May 2020 11:25:10")
    _check_parse(2021, 5, 26, 11, 23, 0, 0, 0, "26 May 2021 11:23")


def test_check_parse_named_tz_with_textual_date() -> None:
    """Wave 1387 — `EEEE MMM dd HH:mm:ss z yyyy` shape now round-trips.

    The `z` literal in the format is the JVM-style timezone abbreviation
    placeholder; the locale-aware parser walks the textual prefix and the
    existing `parse_t_zoffset` handles the trailing `GMT+08:00` / etc.
    Upstream fixtures: lines 238-244 of `TestDateUtil`.
    """
    _check_parse(1979, 7, 6, 17, 22, 1, +8, 0, "Friday July 6 17:22:1 GMT+08:00 1979")
    _check_parse(1980, 7, 6, 16, 23, 0, 0, 0, "Sun, Jul 6, 1980 at 4:23pm")
    _check_parse(1981, 7, 6, 0, 0, 0, 0, 0, "Monday, July 6, 1981")


def test_check_parse_ambiguous_big_endian_date() -> None:
    """Wave 1387 — `yyyy MM dd:HH` ambiguity still resolved as before.

    Upstream's `1970 12 23:08` parses as 1970-12-23 00:08 UTC (the trailing
    `23:08` reads as day + minute via the big-endian parser). The Python
    port's `parse_big_endian_date` already handles this — the test was
    previously skipped pending the locale wave for safety; wave 1387
    confirms there's no regression.
    """
    _check_parse(1970, 12, 23, 0, 8, 0, 0, 0, "1970 12 23:08")


# --------------------------------------------------------------------- #
# testToString — formatting timezone-aware calendars.
# --------------------------------------------------------------------- #


def test_to_string_null_inputs() -> None:
    """Upstream asserts ``DateConverter.toCalendar((String) null) == null``
    and ``DateConverter.toCalendar("D:") == null`` (and "D:    ")."""
    assert DateConverter.to_calendar(None) is None
    assert DateConverter.to_calendar("D:    ") is None
    assert DateConverter.to_calendar("D:") is None


def _check_to_string(
    yr: int,
    mon: int,
    day: int,
    hr: int,
    minute: int,
    sec: int,
    offset_hours: int,
    offset_minutes: int,
) -> None:
    """Mirror upstream ``checkToString``: build a calendar with the given
    explicit offset and assert it round-trips into the expected PDF /
    ISO strings."""
    from datetime import timedelta, timezone

    tz = timezone(timedelta(hours=offset_hours, minutes=offset_minutes))
    cal = datetime(yr, mon, day, hr, minute, sec, tzinfo=tz)
    pdf_date = (
        f"D:{yr:04d}{mon:02d}{day:02d}{hr:02d}{minute:02d}{sec:02d}"
        f"{offset_hours:+03d}'{offset_minutes:02d}'"
    )
    iso_date = (
        f"{yr:04d}-{mon:02d}-{day:02d}T{hr:02d}:{minute:02d}:{sec:02d}"
        f"{offset_hours:+03d}:{offset_minutes:02d}"
    )
    assert DateConverter.to_string(cal) == pdf_date
    assert DateConverter.to_iso8601(cal) == iso_date


@pytest.mark.parametrize(
    "args",
    [
        (2013, 8, 28, 3, 14, 15, -4, 0),
        (2014, 2, 28, 3, 14, 15, -5, 0),
        (2015, 8, 28, 3, 14, 15, +2, 0),
        (2016, 2, 28, 3, 14, 15, +1, 0),
        (2017, 8, 28, 3, 14, 15, -4, 0),
        (2018, 1, 1, 1, 14, 15, -5, 0),
        (2019, 12, 31, 12, 59, 59, -5, 0),
        (2020, 2, 29, 0, 0, 0, +2, 0),
        (2015, 8, 28, 3, 14, 15, +9, 30),
        (2016, 2, 28, 3, 14, 15, +10, 30),
    ],
)
def test_to_string_various_offsets(args: tuple) -> None:
    _check_to_string(*args)


# --------------------------------------------------------------------- #
# testParseTZ — package-private TZ parser.
# --------------------------------------------------------------------- #


def _check_parse_tz(expect: int, src: str) -> None:
    cal = DateConverter.new_greg()
    DateConverter.parse_t_zoffset(src, cal, ParsePosition(0))
    assert (cal.zone_offset + cal.dst_offset) == expect, (
        f"parse_t_zoffset({src!r}) -> {cal.zone_offset + cal.dst_offset}, "
        f"expected {expect}"
    )


@pytest.mark.parametrize(
    "expect,src",
    [
        (0 * _HRS + 0 * _MINS, "+00:00"),
        (0 * _HRS + 0 * _MINS, "-0000"),
        (1 * _HRS + 0 * _MINS, "+1:00"),
        (-(1 * _HRS + 0 * _MINS), "-1:00"),
        (-(1 * _HRS + 30 * _MINS), "-0130"),
        (11 * _HRS + 59 * _MINS, "1159"),
        (12 * _HRS + 30 * _MINS, "1230"),
        (-(12 * _HRS + 30 * _MINS), "-12:30"),
        (0 * _HRS + 0 * _MINS, "Z"),
        (-(8 * _HRS + 0 * _MINS), "PST"),
        # "EDT" — upstream expects 0 (Java's getTimeZone returns GMT for
        # unknown IDs). The Python port returns False from parse_t_zoffset
        # leaving the calendar at its newGreg() default of 0.
        (0 * _HRS + 0 * _MINS, "EDT"),
        (-(3 * _HRS + 0 * _MINS), "GMT-0300"),
        (+(11 * _HRS + 0 * _MINS), "GMT+11:00"),
        (-(6 * _HRS + 0 * _MINS), "America/Chicago"),
        (+(3 * _HRS + 0 * _MINS), "Europe/Moscow"),
        (+(9 * _HRS + 30 * _MINS), "Australia/Adelaide"),
        ((5 * _HRS + 0 * _MINS), "0500"),
        ((5 * _HRS + 0 * _MINS), "+0500"),
        ((11 * _HRS + 0 * _MINS), "+11'00'"),
        (0, "Z"),
        # PDFBOX-3315, PDFBOX-2420
        (12 * _HRS + 0 * _MINS, "+12:00"),
        (-(12 * _HRS + 0 * _MINS), "-12:00"),
        (14 * _HRS + 0 * _MINS, "1400"),
        (-(14 * _HRS + 0 * _MINS), "-1400"),
    ],
)
def test_parse_tz(expect: int, src: str) -> None:
    _check_parse_tz(expect, src)


# --------------------------------------------------------------------- #
# testFormatTZoffset — package-private TZ formatter.
# --------------------------------------------------------------------- #


def _check_format_offset(off: float, expect: str) -> None:
    # Upstream uses ``new SimpleTimeZone((int)(off*60*60*1000), "junkID")``;
    # the int-cast truncates the float to an int. ``getRawOffset()`` then
    # returns that same int.
    millis = int(off * 60 * 60 * 1000)
    got = DateConverter.format_t_zoffset(millis, ":")
    assert got == expect


@pytest.mark.parametrize(
    "off,expect",
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
        # PDFBOX-2420
        (14, "+14:00"),
        (-14, "-14:00"),
    ],
)
def test_format_tz_offset(off: float, expect: str) -> None:
    _check_format_offset(off, expect)


# --------------------------------------------------------------------- #
# Round-trip property: any datetime survives toString -> toCalendar.
# --------------------------------------------------------------------- #


def test_pdf_format_round_trips_through_to_calendar() -> None:
    cal = datetime(2005, 5, 26, 20, 52, 58, tzinfo=UTC)
    pdf = DateConverter.to_string(cal)
    assert pdf is not None
    parsed = DateConverter.to_calendar(pdf)
    assert parsed is not None
    assert DateConverter.to_string(parsed) == pdf
