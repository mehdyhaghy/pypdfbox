"""Coverage-boost tests for ``pypdfbox.xmpbox.date_converter``.

Targets the private ``DateConverter`` helpers (``parse_t_zoffset``,
``parse_time_field``, ``skip_optionals``, ``skip_string``, ``new_greg``,
``parse_big_endian_date``, ``parse_simple_date``, ``parse_date``,
``restrain_t_zoffset``, ``format_t_zoffset``, ``update_zone_id``,
``adjust_time_zone_nicely``, ``from_iso8601``) and the small ``ParsePosition``
/ ``_GregLike`` shims. These mirror upstream ``DateConverter`` internals so
having them under test future-proofs porting of code that calls into the
package-private surface.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pypdfbox.xmpbox import DateConverter
from pypdfbox.xmpbox.date_converter import (
    ParsePosition,
    _from_iso8601,
    _GregLike,
    _lookup_named_tz_offset,
    _two_digit_year_to_full,
)


# ---------- ParsePosition --------------------------------------------------


def test_parse_position_get_set_index() -> None:
    p = ParsePosition()
    assert p.get_index() == 0
    p.set_index(7)
    assert p.get_index() == 7
    assert p.index == 7


def test_parse_position_get_set_error_index() -> None:
    p = ParsePosition()
    assert p.get_error_index() == -1
    p.set_error_index(3)
    assert p.get_error_index() == 3


# ---------- _GregLike ------------------------------------------------------


def test_greg_like_set_fields_assigns_all() -> None:
    g = _GregLike()
    g.set_fields(2020, 5, 4, 10, 11, 12)
    assert (g.year, g.month, g.day, g.hour, g.minute, g.second) == (
        2020,
        5,
        4,
        10,
        11,
        12,
    )


def test_greg_like_add_minutes_wraps_across_day_boundary() -> None:
    g = _GregLike()
    g.set_fields(2020, 0, 1, 23, 50, 0)
    g.add_minutes(20)
    assert g.year == 2020
    assert g.month == 0
    assert g.day == 2
    assert g.hour == 0
    assert g.minute == 10


def test_greg_like_to_datetime_uses_zone_offset() -> None:
    g = _GregLike()
    g.set_fields(2020, 4, 5, 6, 7, 8)
    g.zone_offset = 60 * 60 * 1000  # +1h
    g.millisecond = 250
    dt = g.to_datetime()
    assert dt.year == 2020
    assert dt.utcoffset() == timedelta(hours=1)
    assert dt.microsecond == 250 * 1000


def test_greg_like_validate_lenient_does_not_raise_for_invalid() -> None:
    g = _GregLike()
    # lenient defaults True — invalid month must not raise.
    g.set_fields(2020, 13, 99, 0, 0, 0)
    g.validate()


def test_greg_like_validate_non_lenient_raises_for_invalid() -> None:
    g = _GregLike()
    g.lenient = False
    g.set_fields(2020, 13, 99, 0, 0, 0)
    with pytest.raises(ValueError):
        g.validate()


# ---------- restrain_t_zoffset -------------------------------------------


def test_restrain_t_zoffset_in_range_returns_unchanged() -> None:
    in_range = 5 * DateConverter.MILLIS_PER_HOUR
    assert DateConverter.restrain_t_zoffset(in_range) == in_range


def test_restrain_t_zoffset_zero_returns_zero() -> None:
    assert DateConverter.restrain_t_zoffset(0) == 0


def test_restrain_t_zoffset_exact_plus_fourteen_unchanged() -> None:
    val = 14 * DateConverter.MILLIS_PER_HOUR
    assert DateConverter.restrain_t_zoffset(val) == val


def test_restrain_t_zoffset_out_of_range_is_clamped() -> None:
    # 36h is a multiple of HALF_DAY → folds to exactly HALF_DAY per the
    # upstream guard at lines 222-224 of DateConverter.java.
    out = DateConverter.restrain_t_zoffset(36 * DateConverter.MILLIS_PER_HOUR)
    assert -DateConverter.HALF_DAY <= out <= DateConverter.HALF_DAY


def test_restrain_t_zoffset_offset_eighteen_hours_is_clamped() -> None:
    # 18h > 14h ceiling: enters the folding branch and ends in
    # (-HALF_DAY, HALF_DAY).
    out = DateConverter.restrain_t_zoffset(18 * DateConverter.MILLIS_PER_HOUR)
    assert -DateConverter.HALF_DAY < out < DateConverter.HALF_DAY


# ---------- format_t_zoffset ----------------------------------------------


def test_format_t_zoffset_positive_apostrophe_separator() -> None:
    millis = (5 * 60 + 30) * 60 * 1000  # +05:30
    assert DateConverter.format_t_zoffset(millis, "'") == "+05'30"


def test_format_t_zoffset_negative_colon_separator() -> None:
    millis = -(8 * 60) * 60 * 1000  # -08:00
    assert DateConverter.format_t_zoffset(millis, ":") == "-08:00"


def test_format_t_zoffset_zero_is_plus_zero() -> None:
    assert DateConverter.format_t_zoffset(0, ":") == "+00:00"


# ---------- update_zone_id ------------------------------------------------


def test_update_zone_id_zero_is_gmt() -> None:
    g = _GregLike()
    g.zone_offset = 0
    DateConverter.update_zone_id(g)
    assert g.tz_id == "GMT"


def test_update_zone_id_positive_within_twelve_hours() -> None:
    g = _GregLike()
    g.zone_offset = (5 * 60 + 30) * 60 * 1000
    DateConverter.update_zone_id(g)
    assert g.tz_id == "GMT+05:30"


def test_update_zone_id_negative_within_fourteen_hours() -> None:
    g = _GregLike()
    g.zone_offset = -8 * 60 * 60 * 1000
    DateConverter.update_zone_id(g)
    assert g.tz_id == "GMT-08:00"


def test_update_zone_id_positive_above_twelve_hours_is_unknown() -> None:
    g = _GregLike()
    g.zone_offset = 15 * 60 * 60 * 1000
    DateConverter.update_zone_id(g)
    assert g.tz_id == "unknown"


def test_update_zone_id_negative_above_fourteen_hours_is_unknown() -> None:
    g = _GregLike()
    g.zone_offset = -15 * 60 * 60 * 1000
    DateConverter.update_zone_id(g)
    assert g.tz_id == "unknown"


# ---------- parse_time_field ----------------------------------------------


def test_parse_time_field_none_returns_remedy() -> None:
    p = ParsePosition()
    assert DateConverter.parse_time_field(None, p, 4, -1) == -1


def test_parse_time_field_no_digits_returns_remedy() -> None:
    p = ParsePosition(0)
    assert DateConverter.parse_time_field("abc", p, 4, -77) == -77
    # index unchanged when nothing was consumed
    assert p.index == 0


def test_parse_time_field_consumes_only_digits_and_advances() -> None:
    p = ParsePosition(2)
    # text: "xx12ab" — read 2 digits starting at index 2
    assert DateConverter.parse_time_field("xx12ab", p, 4, 0) == 12
    assert p.index == 4


def test_parse_time_field_respects_max_length() -> None:
    p = ParsePosition(0)
    # 4 digits available, max=2 → only 12 consumed
    assert DateConverter.parse_time_field("1234", p, 2, 0) == 12
    assert p.index == 2


# ---------- skip_optionals / skip_string ----------------------------------


def test_skip_optionals_skips_known_chars_and_returns_last() -> None:
    p = ParsePosition(0)
    # the trailing space resets retval to ' ' only when non-space is absent.
    assert DateConverter.skip_optionals("+-x", p, "+- ") == "-"
    assert p.index == 2


def test_skip_optionals_only_spaces_returns_space() -> None:
    p = ParsePosition(0)
    assert DateConverter.skip_optionals("   x", p, " ") == " "
    assert p.index == 3


def test_skip_string_match_advances_and_returns_true() -> None:
    p = ParsePosition(0)
    assert DateConverter.skip_string("GMT+05", "GMT", p) is True
    assert p.index == 3


def test_skip_string_no_match_returns_false() -> None:
    p = ParsePosition(0)
    assert DateConverter.skip_string("UTC", "GMT", p) is False
    assert p.index == 0


# ---------- new_greg ------------------------------------------------------


def test_new_greg_defaults_to_utc_non_lenient() -> None:
    g = DateConverter.new_greg()
    assert g.zone_offset == 0
    assert g.dst_offset == 0
    assert g.tz_id == "UTC"
    assert g.lenient is False
    assert g.millisecond == 0


# ---------- adjust_time_zone_nicely ---------------------------------------


def test_adjust_time_zone_nicely_shifts_wall_clock_backward() -> None:
    g = DateConverter.new_greg()
    g.set_fields(2020, 0, 1, 12, 0, 0)
    # +60 minute zone — must subtract 60 minutes from wall clock.
    DateConverter.adjust_time_zone_nicely(g, 60 * 60 * 1000)
    assert g.zone_offset == 60 * 60 * 1000
    assert g.hour == 11


# ---------- parse_t_zoffset -----------------------------------------------


def test_parse_t_zoffset_z_marker_returns_true_and_offset_zero() -> None:
    cal = DateConverter.new_greg()
    cal.set_fields(2020, 0, 1, 12, 0, 0)
    p = ParsePosition(0)
    assert DateConverter.parse_t_zoffset("Z", cal, p) is True
    # Wall clock unaffected for offset-0 zone:
    assert cal.hour == 12


def test_parse_t_zoffset_signed_hours_minutes_updates_calendar() -> None:
    cal = DateConverter.new_greg()
    cal.set_fields(2020, 0, 1, 12, 0, 0)
    p = ParsePosition(0)
    assert DateConverter.parse_t_zoffset("+05:30", cal, p) is True
    assert cal.zone_offset == (5 * 60 + 30) * 60 * 1000


def test_parse_t_zoffset_named_tz_known() -> None:
    cal = DateConverter.new_greg()
    cal.set_fields(2020, 0, 1, 12, 0, 0)
    p = ParsePosition(0)
    assert DateConverter.parse_t_zoffset("PST", cal, p) is True
    assert cal.zone_offset == -8 * 60 * 60 * 1000


def test_parse_t_zoffset_named_tz_unknown_returns_false() -> None:
    cal = DateConverter.new_greg()
    cal.set_fields(2020, 0, 1, 12, 0, 0)
    p = ParsePosition(0)
    assert DateConverter.parse_t_zoffset("BOGUSXYZ", cal, p) is False


# ---------- parse_big_endian_date -----------------------------------------


def test_parse_big_endian_date_full_ymdhms() -> None:
    p = ParsePosition(0)
    cal = DateConverter.parse_big_endian_date("2020-05-04 10:11:12", p)
    assert cal is not None
    assert cal.year == 2020
    assert cal.month == 4  # 0-based
    assert cal.day == 4
    assert cal.hour == 10


def test_parse_big_endian_date_year_only_succeeds() -> None:
    p = ParsePosition(0)
    cal = DateConverter.parse_big_endian_date("2020", p)
    assert cal is not None
    assert cal.year == 2020


def test_parse_big_endian_date_no_four_digit_year_returns_none() -> None:
    p = ParsePosition(0)
    assert DateConverter.parse_big_endian_date("xx", p) is None


def test_parse_big_endian_date_with_fractional_second_consumed() -> None:
    p = ParsePosition(0)
    cal = DateConverter.parse_big_endian_date("2020-05-04 10:11:12.345", p)
    assert cal is not None


# ---------- parse_simple_date ---------------------------------------------


def test_parse_simple_date_handles_yyyy_mmm_d() -> None:
    p = ParsePosition(0)
    cal = DateConverter.parse_simple_date(
        "2000 Feb 29", ("yyyy MMM d",), p
    )
    assert cal is not None
    assert cal.year == 2000
    assert cal.month == 1  # 0-based


def test_parse_simple_date_handles_md_yy() -> None:
    p = ParsePosition(0)
    cal = DateConverter.parse_simple_date("7/6/1973", ("M/d/yy",), p)
    assert cal is not None
    assert cal.year == 1973


def test_parse_simple_date_unknown_format_returns_none() -> None:
    p = ParsePosition(0)
    assert DateConverter.parse_simple_date(
        "blah", ("EEEE MMM dd HH:mm:ss yy",), p
    ) is None


def test_parse_simple_date_md_yy_hms() -> None:
    p = ParsePosition(0)
    cal = DateConverter.parse_simple_date(
        "7/6/1973 17:22:1", ("M/d/yy HH:mm:ss",), p
    )
    assert cal is not None
    assert cal.hour == 17


def test_parse_simple_date_md_yy_hm() -> None:
    p = ParsePosition(0)
    cal = DateConverter.parse_simple_date(
        "7/6/1973 17:22", ("M/d/yy HH:mm",), p
    )
    assert cal is not None
    assert cal.minute == 22


def test_parse_simple_date_dd_mmm_yy_hms() -> None:
    p = ParsePosition(0)
    cal = DateConverter.parse_simple_date(
        "26 May 2000 11:25:10", ("dd MMM yy HH:mm:ss",), p
    )
    assert cal is not None
    assert cal.day == 26
    assert cal.hour == 11


def test_parse_simple_date_dd_mmm_yy_hm() -> None:
    p = ParsePosition(0)
    cal = DateConverter.parse_simple_date(
        "26 May 2000 11:25", ("dd MMM yy HH:mm",), p
    )
    assert cal is not None
    assert cal.minute == 25


def test_parse_simple_date_yyyymmddhhmmss_compact() -> None:
    p = ParsePosition(0)
    cal = DateConverter.parse_simple_date(
        "200712172:2:3", ("yyyymmddhh:mm:ss",), p
    )
    assert cal is not None
    assert cal.year == 2007


def test_parse_simple_date_h_m_md_yy() -> None:
    p = ParsePosition(0)
    cal = DateConverter.parse_simple_date(
        "9:47 5/12/2008", ("H:m M/d/yy",), p
    )
    assert cal is not None
    assert cal.hour == 9


def test_parse_simple_date_two_digit_year_md() -> None:
    # Exercise the two-digit year → century conversion.
    p = ParsePosition(0)
    cal = DateConverter.parse_simple_date(
        "1/2/05", ("M/d/yy",), p
    )
    assert cal is not None
    assert cal.year >= 2000


# ---------- parse_date dispatch -------------------------------------------


def test_parse_date_none_returns_none() -> None:
    p = ParsePosition(0)
    assert DateConverter.parse_date(None, p) is None


def test_parse_date_empty_string_returns_none() -> None:
    p = ParsePosition(0)
    assert DateConverter.parse_date("", p) is None


def test_parse_date_pdf_prefix_only_returns_none() -> None:
    p = ParsePosition(0)
    assert DateConverter.parse_date("D:", p) is None


def test_parse_date_dispatches_to_big_endian() -> None:
    p = ParsePosition(0)
    cal = DateConverter.parse_date("2020-05-04 10:11:12", p)
    assert cal is not None
    assert cal.year == 2020


def test_parse_date_dispatches_to_simple_format() -> None:
    p = ParsePosition(0)
    cal = DateConverter.parse_date("7/6/1973 17:22:1", p)
    assert cal is not None
    assert cal.year == 1973


# ---------- from_iso8601 (private helper, exposed for parity) -------------


def test_from_iso8601_naive_attaches_utc() -> None:
    dt = _from_iso8601("2020-05-04T10:11:12")
    assert dt.tzinfo is not None
    assert dt.utcoffset() == timedelta(0)


def test_from_iso8601_with_z_marker() -> None:
    dt = DateConverter.from_iso8601("2020-05-04T10:11:12Z")
    assert dt.utcoffset() == timedelta(0)


def test_from_iso8601_invalid_raises_oserror() -> None:
    with pytest.raises(OSError):
        _from_iso8601("not-a-date")


# ---------- to_string / to_iso8601 round-trip via DateConverter -----------


def test_to_string_none_input_returns_none() -> None:
    assert DateConverter.to_string(None) is None


def test_to_string_naive_treated_as_utc() -> None:
    s = DateConverter.to_string(datetime(2020, 5, 4, 10, 11, 12))
    assert s is not None
    assert s.startswith("D:20200504101112+00'00'")


def test_to_string_tz_aware_formats_offset() -> None:
    tz = timedelta(hours=5, minutes=30)
    dt = datetime(2020, 5, 4, 10, 11, 12, tzinfo=UTC).astimezone(
        tz=__import__("datetime").timezone(tz)
    )
    s = DateConverter.to_string(dt)
    assert s is not None
    assert "+05'30'" in s


def test_to_iso8601_naive_attaches_utc() -> None:
    out = DateConverter.to_iso8601(datetime(2020, 5, 4, 10, 11, 12))
    assert out.endswith("+00:00")


def test_to_iso8601_with_millis_flag_writes_milliseconds() -> None:
    out = DateConverter.to_iso8601(
        datetime(2020, 5, 4, 10, 11, 12, 250_000, tzinfo=UTC), print_millis=True
    )
    assert ".250" in out


# ---------- DateConverter construction is forbidden -----------------------


def test_date_converter_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        DateConverter()


# ---------- named tz lookup ----------------------------------------------


def test_lookup_named_tz_offset_known() -> None:
    assert _lookup_named_tz_offset("PST") == -8 * 60 * 60 * 1000


def test_lookup_named_tz_offset_unknown_returns_none() -> None:
    assert _lookup_named_tz_offset("not-a-zone") is None


def test_lookup_named_tz_offset_empty_returns_none() -> None:
    assert _lookup_named_tz_offset("") is None


# ---------- two-digit year sliding window --------------------------------


def test_two_digit_year_resolves_into_century_window() -> None:
    # Should pick a year close to today's year; just sanity-check the
    # output stays a positive int in a plausible century.
    y = _two_digit_year_to_full(5)
    assert 1900 <= y <= 2100
