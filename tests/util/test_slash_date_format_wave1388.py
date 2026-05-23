"""Wave 1388 — close the slash-separated ``MM/dd/yyyy`` divergence.

Pre-1388 ``tests/util/upstream/test_date_util.py`` skipped the upstream
``testExtract`` slash-separated cases on the assumption that the Python
port's ``_SIMPLE_FORMAT_HANDLERS`` table didn't carry an entry for the
ambiguous ``MM/dd/yyyy`` shape. In fact the lenient ``M/d/yy`` handler
already accepts 4-digit years (``\\d{2,4}``) and routes them
month-first per upstream's ``Locale.ENGLISH`` default, so the cases
parsed correctly all along. Wave 1388:

1. Removes the now-stale skip and ports the upstream assertions.
2. Adds explicit ``MM/dd/yyyy [HH:mm[:ss]]`` aliases to the dispatch
   table so the format-table read matches upstream's commented-out
   format list (``DateConverter.java`` lines 136-142) code-by-code.
3. Pins behaviour in this file with end-to-end fixtures covering the
   shapes the task brief calls out: bare slash, ``D:``-prefixed slash,
   slash + time, and the out-of-range guards.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox.date_converter import DateConverter

# --------------------------------------------------------------------- #
# Valid US-default slash parses.
# --------------------------------------------------------------------- #


def test_slash_one_digit_month_one_digit_day_parses_us_default() -> None:
    """``5/12/2005`` -> May 12, 2005 (Locale.ENGLISH = US month-first)."""
    cal = DateConverter.to_calendar("5/12/2005")
    assert cal is not None
    assert cal == datetime(2005, 5, 12, tzinfo=UTC)


def test_slash_two_digit_month_two_digit_day_parses_us_default() -> None:
    """``05/12/2005`` -> May 12, 2005."""
    cal = DateConverter.to_calendar("05/12/2005")
    assert cal is not None
    assert cal == datetime(2005, 5, 12, tzinfo=UTC)


def test_slash_with_optional_time_hms() -> None:
    """``5/12/2005 15:57:16`` -> May 12, 2005, 15:57:16."""
    cal = DateConverter.to_calendar("5/12/2005 15:57:16")
    assert cal is not None
    assert cal == datetime(2005, 5, 12, 15, 57, 16, tzinfo=UTC)


def test_slash_with_optional_time_hm_only() -> None:
    """``5/12/2005 15:57`` -> May 12, 2005, 15:57:00."""
    cal = DateConverter.to_calendar("5/12/2005 15:57")
    assert cal is not None
    assert cal == datetime(2005, 5, 12, 15, 57, 0, tzinfo=UTC)


def test_slash_d_prefix_strip() -> None:
    """``D:05/12/2005`` -> ``D:`` is stripped, then slash-parses as above."""
    cal = DateConverter.to_calendar("D:05/12/2005")
    assert cal is not None
    assert cal == datetime(2005, 5, 12, tzinfo=UTC)


def test_slash_d_prefix_with_time() -> None:
    """``D:05/12/2005 15:57:16`` -> ``D:`` strip + slash + time."""
    cal = DateConverter.to_calendar("D:05/12/2005 15:57:16")
    assert cal is not None
    assert cal == datetime(2005, 5, 12, 15, 57, 16, tzinfo=UTC)


# --------------------------------------------------------------------- #
# Out-of-range — Java's ``SimpleDateFormat`` with
# ``Calendar.setLenient(false)`` rejects 13-month / 32-day values; the
# Python port mirrors that via ``cal.validate()`` and surfaces the
# upstream-equivalent ``OSError`` ("Invalid date format") at the
# ``to_calendar`` boundary (the same ``IOException -> OSError`` mapping
# used elsewhere in the port).
# --------------------------------------------------------------------- #


def test_slash_out_of_range_month_rejected() -> None:
    """``13/01/2005`` is out of range — upstream raises IOException."""
    with pytest.raises(OSError, match="Invalid date format"):
        DateConverter.to_calendar("13/01/2005")


def test_slash_out_of_range_day_rejected() -> None:
    """``1/32/2005`` is out of range — upstream raises IOException."""
    with pytest.raises(OSError, match="Invalid date format"):
        DateConverter.to_calendar("1/32/2005")


def test_slash_zero_month_rejected() -> None:
    """``0/15/2005`` — month 0 has no valid mapping (Java is 1-based)."""
    with pytest.raises(OSError, match="Invalid date format"):
        DateConverter.to_calendar("0/15/2005")


def test_slash_zero_day_rejected() -> None:
    """``5/0/2005`` — day 0 invalid."""
    with pytest.raises(OSError, match="Invalid date format"):
        DateConverter.to_calendar("5/0/2005")


def test_slash_february_29_non_leap_rejected() -> None:
    """``2/29/2005`` — 2005 was not a leap year, so Feb 29 is invalid."""
    with pytest.raises(OSError, match="Invalid date format"):
        DateConverter.to_calendar("2/29/2005")


def test_slash_february_29_leap_year_accepted() -> None:
    """``2/29/2000`` — 2000 was a leap year, Feb 29 valid."""
    cal = DateConverter.to_calendar("2/29/2000")
    assert cal is not None
    assert cal == datetime(2000, 2, 29, tzinfo=UTC)


# --------------------------------------------------------------------- #
# Explicit MM/dd/yyyy handler aliases — verify each registered entry
# parses end-to-end via the dispatcher (rather than the lenient M/d/yy
# fallback above it in the table).
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("12/25/2005", datetime(2005, 12, 25, tzinfo=UTC)),
        ("01/01/2000", datetime(2000, 1, 1, tzinfo=UTC)),
        ("06/15/1999", datetime(1999, 6, 15, tzinfo=UTC)),
        ("12/31/2099", datetime(2099, 12, 31, tzinfo=UTC)),
    ],
    ids=["dec25", "jan1", "jun15", "dec31"],
)
def test_mm_dd_yyyy_alias_parses_canonical_us_dates(
    text: str, expected: datetime
) -> None:
    cal = DateConverter.to_calendar(text)
    assert cal is not None
    assert cal == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "12/25/2005 23:59:59",
            datetime(2005, 12, 25, 23, 59, 59, tzinfo=UTC),
        ),
        (
            "06/15/1999 09:30:00",
            datetime(1999, 6, 15, 9, 30, 0, tzinfo=UTC),
        ),
        (
            "01/01/2000 00:00:01",
            datetime(2000, 1, 1, 0, 0, 1, tzinfo=UTC),
        ),
    ],
    ids=["dec25_late", "jun15_morning", "y2k_one_second_after"],
)
def test_mm_dd_yyyy_with_hms_alias(text: str, expected: datetime) -> None:
    cal = DateConverter.to_calendar(text)
    assert cal is not None
    assert cal == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("12/25/2005 23:59", datetime(2005, 12, 25, 23, 59, 0, tzinfo=UTC)),
        ("06/15/1999 09:30", datetime(1999, 6, 15, 9, 30, 0, tzinfo=UTC)),
    ],
    ids=["dec25_hm", "jun15_hm"],
)
def test_mm_dd_yyyy_with_hm_alias(text: str, expected: datetime) -> None:
    cal = DateConverter.to_calendar(text)
    assert cal is not None
    assert cal == expected
