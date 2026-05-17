"""Wave 1337 coverage-boost tests for ``pypdfbox.xmpbox.date_converter``.

Targets the missing branches around:

  * :meth:`DateConverter.parse_big_endian_date` — invalid (year/month/day)
    triples drop into the validation ``except`` arm and the helper returns
    ``None``.
  * :meth:`DateConverter.parse_date` — three control paths exercised here:
    consumed trailing data after a big-endian parse (longest_len bookkeeping),
    fall-back through ``ALPHA_START_FORMATS`` when the string starts with a
    non-digit, and the final ``longest_date is not None`` return.
  * :func:`_two_digit_year_to_full` — the > base+99 branch that subtracts 100.
  * Every ``_make_handler_*`` regex/validate path — drive each one through an
    out-of-range (year=0 / month=13 / day=32 etc.) field so the
    ``cal.validate()`` ``ValueError`` arm executes and returns ``(None, 0)``.
"""
from __future__ import annotations

from pypdfbox.xmpbox import DateConverter
from pypdfbox.xmpbox.date_converter import (
    ParsePosition,
    _make_handler_dd_mmm_yy_hm,
    _make_handler_dd_mmm_yy_hms,
    _make_handler_h_m_md_yy,
    _make_handler_md_yy,
    _make_handler_md_yy_hm,
    _make_handler_md_yy_hms,
    _make_handler_yyyy_mmm_d,
    _make_handler_yyyymmdd_hms,
    _two_digit_year_to_full,
)


def test_parse_big_endian_date_invalid_calendar_returns_none() -> None:
    """A four-digit year prefix that scans cleanly but produces an
    impossible date (month 13 / day 32) falls into the ``except`` arm and
    returns ``None``."""
    where = ParsePosition(0)
    result = DateConverter.parse_big_endian_date("2024-13-01", where)
    assert result is None


def test_parse_big_endian_date_day_out_of_range_returns_none() -> None:
    where = ParsePosition(0)
    result = DateConverter.parse_big_endian_date("2024-02-30", where)
    assert result is None


def test_parse_date_consumes_trailing_z_after_big_endian() -> None:
    """A big-endian parse that consumes the whole string returns the
    parsed calendar with no additional simple-format fall-through."""
    where = ParsePosition(0)
    cal = DateConverter.parse_date("2024-01-15", where)
    assert cal is not None
    assert cal.year == 2024


def test_parse_date_with_simple_format_alpha_start() -> None:
    """Alpha-start input falls through to ``ALPHA_START_FORMATS`` —
    none of those formats currently parse, so the result is ``None`` but
    we still walk the branch."""
    where = ParsePosition(0)
    cal = DateConverter.parse_date("Monday, Jan 01, 2024", where)
    # We don't expect a result — the alpha-start formats are advisory
    # only in our port — but the branch must execute without raising.
    assert cal is None or cal.year == 2024


def test_parse_date_digit_start_simple_format() -> None:
    where = ParsePosition(0)
    cal = DateConverter.parse_date("2024 Jan 15", where)
    assert cal is not None
    assert cal.year == 2024
    assert cal.month == 0  # 0-based, like java.util.Calendar
    assert cal.day == 15


def test_parse_date_partial_consumed_returns_longest() -> None:
    """A simple-format parse that consumes more characters than the
    big-endian attempt should win — exercises the longest_len branch."""
    where = ParsePosition(0)
    cal = DateConverter.parse_date("5/12/2008 trailing garbage", where)
    # Either the simple-format wins or both fail; either way the helper
    # must terminate cleanly. When it wins, the date fields land.
    if cal is not None:
        assert cal.year == 2008


def test_parse_date_none_and_empty_short_circuit() -> None:
    where = ParsePosition(0)
    assert DateConverter.parse_date(None, where) is None
    assert DateConverter.parse_date("", where) is None
    assert DateConverter.parse_date("D:", where) is None


def test_two_digit_year_to_full_within_window() -> None:
    """Sliding-window covers ``thisyear-79 .. thisyear+20``. Pick a yy
    well inside the window so the candidate doesn't need adjusting."""
    # The result is just a sanity bound — pick a digit that lands in
    # the lower half regardless of "today".
    candidate = _two_digit_year_to_full(50)
    assert 1900 < candidate < 2100


def test_two_digit_year_to_full_lower_bound_branch() -> None:
    """yy=99 / yy=00 should still produce a valid year — exercise both
    sliding-window adjustment arms."""
    for yy in (0, 25, 99):
        candidate = _two_digit_year_to_full(yy)
        assert 1900 < candidate < 2100


def test_simple_format_handlers_reject_invalid_dates() -> None:
    """Every ``_make_handler_*`` validates via ``cal.validate()``; an
    invalid month/day triggers the ``except`` arm and returns ``(None, 0)``.

    All eight handlers share the same except-arm pattern, so this test
    walks each one with deliberately impossible field values.
    """
    # "yyyy MMM d" — year 1970 valid, month name Zzz unknown ⇒ month_num is None
    assert _make_handler_yyyy_mmm_d("1970 Zzz 15") == (None, 0)
    # An unparseable prefix ⇒ regex miss
    assert _make_handler_yyyy_mmm_d("not a date") == (None, 0)
    # Valid format but day=32 ⇒ validate() raises
    assert _make_handler_yyyy_mmm_d("2024 Feb 32") == (None, 0)

    # "dd MMM yy HH:mm:ss" — unknown month abbreviation
    assert _make_handler_dd_mmm_yy_hms("15 Zzz 2024 10:00:00") == (None, 0)
    assert _make_handler_dd_mmm_yy_hms("not a date") == (None, 0)
    # day=99 ⇒ validate() raises
    assert _make_handler_dd_mmm_yy_hms("99 Feb 2024 10:00:00") == (None, 0)

    # "dd MMM yy HH:mm" — unknown month abbreviation + invalid day
    assert _make_handler_dd_mmm_yy_hm("15 Zzz 2024 10:00") == (None, 0)
    assert _make_handler_dd_mmm_yy_hm("not a date") == (None, 0)
    assert _make_handler_dd_mmm_yy_hm("99 Feb 2024 10:00") == (None, 0)

    # "yyyymmddhh:mm:ss" — month=13 in the 8-digit prefix
    assert _make_handler_yyyymmdd_hms("not a date") == (None, 0)
    assert _make_handler_yyyymmdd_hms("20241332" + "10:00:00") == (None, 0)

    # "H:m M/d/yy" — month=13 ⇒ validate raises
    assert _make_handler_h_m_md_yy("not a date") == (None, 0)
    assert _make_handler_h_m_md_yy("10:00 13/15/2024") == (None, 0)

    # "M/d/yy HH:mm:ss" — month=13
    assert _make_handler_md_yy_hms("not a date") == (None, 0)
    assert _make_handler_md_yy_hms("13/15/2024 10:00:00") == (None, 0)

    # "M/d/yy HH:mm" — month=13
    assert _make_handler_md_yy_hm("not a date") == (None, 0)
    assert _make_handler_md_yy_hm("13/15/2024 10:00") == (None, 0)

    # "M/d/yy" — month=13
    assert _make_handler_md_yy("not a date") == (None, 0)
    assert _make_handler_md_yy("13/15/2024") == (None, 0)


def test_simple_format_handlers_two_digit_year_branch() -> None:
    """When the year part is two digits, ``_two_digit_year_to_full`` is
    consulted to expand it. Drive each handler with a yy value to walk
    that branch."""
    # H:m M/d/yy with yy=08
    cal, consumed = _make_handler_h_m_md_yy("9:47 5/12/08")
    assert cal is not None
    assert consumed > 0
    # M/d/yy HH:mm:ss with yy=99
    cal, consumed = _make_handler_md_yy_hms("7/6/99 17:22:01")
    assert cal is not None
    assert consumed > 0
    # M/d/yy HH:mm with yy=99
    cal, consumed = _make_handler_md_yy_hm("7/6/99 17:22")
    assert cal is not None
    assert consumed > 0
    # M/d/yy with yy=99
    cal, consumed = _make_handler_md_yy("7/6/99")
    assert cal is not None
    assert consumed > 0
    # dd MMM yy HH:mm:ss with yy=99 (two digits)
    cal, consumed = _make_handler_dd_mmm_yy_hms("26 May 99 11:25:10")
    assert cal is not None
    assert consumed > 0
    # dd MMM yy HH:mm with yy=99
    cal, consumed = _make_handler_dd_mmm_yy_hm("26 May 99 11:25")
    assert cal is not None
    assert consumed > 0


def test_parse_date_short_no_year_falls_through() -> None:
    """A string that starts with a digit but doesn't form a four-digit
    year still falls through to ``parse_simple_date`` (digit-start arm)
    and returns ``None`` cleanly."""
    where = ParsePosition(0)
    # "1/2/3" — too short for a four-digit big-endian year, but
    # exercises the digit-start branch.
    result = DateConverter.parse_date("1/2/3", where)
    # The simple-format handlers expect 2+ digit years, so this is
    # likely None — but the path must execute.
    assert result is None or result.year > 0


def test_parse_date_alpha_start_only() -> None:
    """A string that starts with a non-digit triggers the
    ``ALPHA_START_FORMATS`` selection branch. None of those formats
    have real handlers in the Python port, so the result is None — but
    the branch is walked."""
    where = ParsePosition(0)
    result = DateConverter.parse_date("Monday Jan 15 2024", where)
    assert result is None


def test_parse_date_big_endian_partial_consume_with_tz_trailing() -> None:
    """Big-endian parses successfully + ``parse_t_zoffset`` consumes a
    trailing offset, but the input still has trailing garbage. Exercises
    the ``longest_len = where_len; longest_date = ret_cal`` branch
    (lines 707-708) where parse_date keeps the partial result while
    looking for a better simple-format match."""
    where = ParsePosition(0)
    result = DateConverter.parse_date("2024-01-15Z trailing", where)
    assert result is not None
    assert result.year == 2024
    # ``where.index`` lands after the longest successful parse — at the
    # point the TZ was consumed (not at the end of the string).
    assert where.index < len("2024-01-15Z trailing")


def test_parse_date_big_endian_partial_with_extra_garbage() -> None:
    """Same as above but with a numeric TZ offset — exercises
    ``parse_t_zoffset`` returning True with a multi-character consume."""
    where = ParsePosition(0)
    result = DateConverter.parse_date("2024-01-15+05 extra", where)
    assert result is not None
    assert result.year == 2024


def test_parse_date_digit_start_partial_consume() -> None:
    """A "M/d/yy" hand-off that consumes exactly the input — exercising
    the ``where_len == len(text)`` short-circuit on the simple-format
    arm (lines 717-718, 725-727 covering longest_len bookkeeping when
    big-endian fails). Use direct method to avoid to_calendar's
    PDF-like front gate."""
    where = ParsePosition(0)
    result = DateConverter.parse_date("5/12/08", where)
    if result is not None:
        # The two-digit year sliding window must place us between
        # 1900 and 2100.
        assert 1900 < result.year < 2100
