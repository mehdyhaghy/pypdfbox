"""Wave 1391 — coverage round-out for :mod:`pypdfbox.util.date_util`.

Targets the residual missing branches in the SimpleDateFormat-style
locale-aware parser ported in wave 1387.
"""

from __future__ import annotations

from datetime import datetime

from pypdfbox.util.date_util import parse_with_locale


def test_literal_double_single_quote_yields_literal_quote() -> None:
    result = parse_with_locale("12'34", "HH''mm", locale="en")
    assert result == datetime(1970, 1, 1, 12, 34, 0)


def test_unterminated_quote_treats_rest_as_quoted_literal() -> None:
    result = parse_with_locale("12:34 leftover", "HH:mm 'leftover", locale="en")
    assert result == datetime(1970, 1, 1, 12, 34, 0)


def test_token_run_collapses_long_M_letters() -> None:
    result = parse_with_locale("January 2020", "MMMMM yyyy", locale="en")
    assert result is not None
    assert result.year == 2020
    assert result.month == 1


def test_token_run_collapses_long_E_letters() -> None:
    result = parse_with_locale(
        "Monday January 2020", "EEEEEEEEEE MMMM yyyy", locale="en"
    )
    assert result is not None
    assert result.year == 2020
    assert result.month == 1


def test_quoted_literal_case_insensitive_match() -> None:
    result = parse_with_locale("12:30 AT 2020", "HH:mm 'at' yyyy", locale="en")
    assert result == datetime(2020, 1, 1, 12, 30, 0)


def test_quoted_literal_mismatch_returns_none() -> None:
    assert parse_with_locale("12:30 xx 2020", "HH:mm 'at' yyyy", locale="en") is None


def test_yy_four_digit_passthrough() -> None:
    result = parse_with_locale("2020-01-15", "yy-MM-dd", locale="en")
    assert result == datetime(2020, 1, 15, 0, 0, 0)


def test_yy_two_digit_sliding_window() -> None:
    result = parse_with_locale("25-01-15", "yy-MM-dd", locale="en")
    assert result is not None
    assert result.year == 2025


def test_single_letter_d_token() -> None:
    result = parse_with_locale("2020-01-5", "yyyy-MM-d", locale="en")
    assert result == datetime(2020, 1, 5, 0, 0, 0)


def test_single_letter_d_token_failure_when_no_digit() -> None:
    assert parse_with_locale("2020-01-x", "yyyy-MM-d", locale="en") is None


def test_single_letter_m_minute() -> None:
    result = parse_with_locale("12:5", "HH:m", locale="en")
    assert result == datetime(1970, 1, 1, 12, 5, 0)


def test_single_letter_s_second() -> None:
    result = parse_with_locale("12:30:5", "HH:mm:s", locale="en")
    assert result == datetime(1970, 1, 1, 12, 30, 5)


def test_single_letter_h_hour() -> None:
    result = parse_with_locale("9:30", "H:mm", locale="en")
    assert result == datetime(1970, 1, 1, 9, 30, 0)


def test_hh_with_am_marker_at_12_rolls_to_midnight() -> None:
    result = parse_with_locale("12:30 AM", "hh:mm a", locale="en")
    assert result == datetime(1970, 1, 1, 0, 30, 0)


def test_hh_with_pm_marker_at_12_stays_noon() -> None:
    result = parse_with_locale("12:30 PM", "hh:mm a", locale="en")
    assert result == datetime(1970, 1, 1, 12, 30, 0)


def test_hh_with_pm_marker_below_12_adds_12() -> None:
    result = parse_with_locale("3:30 PM", "hh:mm a", locale="en")
    assert result == datetime(1970, 1, 1, 15, 30, 0)


def test_hh_out_of_range_with_am_marker_returns_none() -> None:
    assert parse_with_locale("13:30 AM", "hh:mm a", locale="en") is None


def test_hh_zero_with_am_marker_returns_none() -> None:
    assert parse_with_locale("00:30 AM", "hh:mm a", locale="en") is None


def test_am_marker_at_string_end_returns_none() -> None:
    assert parse_with_locale("12:30 A", "hh:mm a", locale="en") is None


def test_invalid_am_pm_marker_returns_none() -> None:
    assert parse_with_locale("12:30 XX", "hh:mm a", locale="en") is None


def test_a_token_tolerates_leading_whitespace() -> None:
    result = parse_with_locale("12:30    AM", "hh:mm a", locale="en")
    assert result == datetime(1970, 1, 1, 0, 30, 0)


def test_z_token_consumes_named_timezone() -> None:
    result = parse_with_locale("12:30 PST 2020", "HH:mm z yyyy", locale="en")
    assert result == datetime(2020, 1, 1, 12, 30, 0)


def test_z_token_with_explicit_offset() -> None:
    result = parse_with_locale("12:30 GMT+08:00 2020", "HH:mm z yyyy", locale="en")
    assert result == datetime(2020, 1, 1, 12, 30, 0)


def test_z_token_at_eos_returns_none() -> None:
    assert parse_with_locale("12:30 ", "HH:mm z", locale="en") is None


def test_z_token_zero_length_run_returns_none() -> None:
    assert parse_with_locale("12:30   ", "HH:mm z", locale="en") is None


def test_yyyy_with_short_input_returns_none() -> None:
    assert parse_with_locale("202", "yyyy", locale="en") is None


def test_yy_with_no_digits_returns_none() -> None:
    assert parse_with_locale("xx", "yy", locale="en") is None


def test_mm_with_no_digits_returns_none() -> None:
    assert parse_with_locale("xx", "MM", locale="en") is None


def test_dd_with_no_digits_returns_none() -> None:
    assert parse_with_locale("2020-01-xx", "yyyy-MM-dd", locale="en") is None


def test_d_with_no_digits_returns_none() -> None:
    assert parse_with_locale("2020-01-x", "yyyy-MM-d", locale="en") is None


def test_h_with_no_digits_returns_none() -> None:
    assert parse_with_locale("xx:30", "H:mm", locale="en") is None


def test_hh_with_no_digits_returns_none() -> None:
    assert parse_with_locale("xx:30 AM", "hh:mm a", locale="en") is None


def test_mm_minute_with_no_digits_returns_none() -> None:
    assert parse_with_locale("12:xx", "HH:mm", locale="en") is None


def test_s_second_with_no_digits_returns_none() -> None:
    assert parse_with_locale("12:30:xx", "HH:mm:s", locale="en") is None


def test_mmmm_unknown_month_name_returns_none() -> None:
    assert parse_with_locale("Foo 2020", "MMMM yyyy", locale="en") is None


def test_mmm_unknown_month_name_returns_none() -> None:
    assert parse_with_locale("Foo 2020", "MMM yyyy", locale="en") is None


def test_eeee_unknown_weekday_returns_none() -> None:
    assert (
        parse_with_locale("Foosday January 1, 2020", "EEEE MMMM d, yyyy", locale="en")
        is None
    )


def test_eee_unknown_weekday_returns_none() -> None:
    assert (
        parse_with_locale("Foo January 1, 2020", "EEE MMMM d, yyyy", locale="en")
        is None
    )


def test_invalid_month_caught_by_datetime() -> None:
    assert parse_with_locale("2020-13-01", "yyyy-MM-dd", locale="en") is None


def test_invalid_day_caught_by_datetime() -> None:
    assert parse_with_locale("2020-02-30", "yyyy-MM-dd", locale="en") is None


def test_literal_space_allows_collapse_to_following_punct() -> None:
    result = parse_with_locale("2020 01-15", "yyyy MM-dd", locale="en")
    assert result == datetime(2020, 1, 15)


def test_literal_space_absent_at_end_of_input_returns_none() -> None:
    assert parse_with_locale("2020", "yyyy ", locale="en") is None


def test_literal_mismatched_char_returns_none() -> None:
    assert parse_with_locale("2020X01", "yyyy-MM", locale="en") is None


def test_trailing_input_residue_returns_none() -> None:
    assert parse_with_locale("2020 extra", "yyyy", locale="en") is None


def test_trailing_whitespace_in_input_is_accepted() -> None:
    result = parse_with_locale("2020  ", "yyyy", locale="en")
    assert result == datetime(2020, 1, 1, 0, 0, 0)


def test_empty_input_returns_none() -> None:
    assert parse_with_locale("", "yyyy", locale="en") is None


def test_whitespace_only_input_returns_none() -> None:
    assert parse_with_locale("   ", "yyyy", locale="en") is None


def test_unknown_locale_falls_back_to_english() -> None:
    result = parse_with_locale("January 2020", "MMMM yyyy", locale="xx-unknown")
    assert result is not None
    assert result.year == 2020
    assert result.month == 1


def test_french_full_month_name() -> None:
    result = parse_with_locale("janvier 2020", "MMMM yyyy", locale="fr")
    assert result is not None
    assert result.month == 1
    assert result.year == 2020


def test_french_diacritic_tolerance() -> None:
    result = parse_with_locale("fevrier 2020", "MMMM yyyy", locale="fr")
    assert result is not None
    assert result.month == 2


def test_french_full_month_case_insensitive() -> None:
    result = parse_with_locale("JANVIER 2020", "MMMM yyyy", locale="fr")
    assert result is not None
    assert result.month == 1


def test_german_full_weekday() -> None:
    result = parse_with_locale("Montag 15.01.2020", "EEEE dd.MM.yyyy", locale="de")
    assert result is not None
    assert result.day == 15


def test_lookup_picks_longest_match() -> None:
    result = parse_with_locale("January 15, 2020", "MMM d, yyyy", locale="en")
    assert result is not None
    assert result.month == 1
    assert result.day == 15


def test_lookup_position_past_end_returns_none() -> None:
    # When _lookup_locale_index is called with position >= len(text), it
    # short-circuits to None — exercised when input ends right where a
    # month/weekday name should start.
    # Pattern: yyyy MMMM, input: 2020 (no trailing month). Parse should fail.
    assert parse_with_locale("2020 ", "yyyy MMMM", locale="en") is None


def test_pos_overshoots_text_length_returns_none() -> None:
    # When pos > len(text) at the top of the token loop, parse fails.
    # Trigger this by having a pattern token after the input ends.
    assert parse_with_locale("12", "HH:mm", locale="en") is None


def test_literal_space_substitute_when_next_pattern_char_matches() -> None:
    # When the pattern says "yyyy MM-dd" but the input is "2020MM-dd" with
    # no space (and pattern's next char 'M' isn't in input), parse fails.
    # When pattern has "yyyy-MM" and input has "2020 -MM", the literal-space
    # collapse mechanism applies: if input pos is at '-', the pattern was a
    # literal space then '-', input is '-' (no space), we allow skipping.
    # Actually this needs the "j + 1 < len(value) and text[pos] == value[j+1]"
    # — pattern " -" against input "-": the absence-tolerance triggers.
    result = parse_with_locale("2020-01", "yyyy -MM", locale="en")
    assert result == datetime(2020, 1, 1, 0, 0, 0)


def test_eee_advance_position_after_weekday_match() -> None:
    # Already covered indirectly via test_eee_unknown_weekday_returns_none
    # but explicitly assert the advance happens when match succeeds.
    result = parse_with_locale("Mon 2020", "EEE yyyy", locale="en")
    assert result is not None
    assert result.year == 2020


def test_a_token_with_only_whitespace_before_eos_returns_none() -> None:
    # When the ``a`` token skips whitespace and reaches EOS, fail.
    assert parse_with_locale("12:30 ", "HH:mm a", locale="en") is None


def test_z_token_skips_extended_whitespace_before_tz() -> None:
    # Pattern z preceded by literal space; input has extra whitespace
    # which the z-token's own whitespace skip handles.
    result = parse_with_locale("12:30  PST", "HH:mm z", locale="en")
    assert result == datetime(1970, 1, 1, 12, 30, 0)


def test_z_token_at_eos_after_whitespace_returns_none() -> None:
    # ``HH:mm  z`` with trailing whitespace and no tz designator
    # — the whitespace skip eats everything, then z finds nothing.
    assert parse_with_locale("12:30      ", "HH:mm z", locale="en") is None


def test_a_token_eats_leading_whitespace_without_literal_separator() -> None:
    # Pattern has no separator before 'a' so the a-token's own whitespace
    # skip (line 447) fires.
    result = parse_with_locale("12:30 AM", "hh:mma", locale="en")
    assert result == datetime(1970, 1, 1, 0, 30, 0)


def test_z_token_eats_leading_whitespace_without_literal_separator() -> None:
    # Pattern has no separator before 'z' so the z-token whitespace skip
    # (line 466) fires.
    result = parse_with_locale("12:30 PST", "HH:mmz", locale="en")
    assert result == datetime(1970, 1, 1, 12, 30, 0)


def test_z_token_with_quoted_separator_eos_returns_none() -> None:
    # Use a quoted-literal separator (no trailing literal space) so we reach
    # the z token. Input ends exactly at the quoted literal so z hits EOS.
    assert parse_with_locale("12:30 sep", "HH:mm 'sep'z", locale="en") is None
