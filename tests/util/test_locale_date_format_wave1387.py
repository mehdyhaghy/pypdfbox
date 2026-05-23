"""Wave 1387 — locale-sensitive SimpleDateFormat parsing.

Closes the documented divergence ``"SimpleDateFormat locale-sensitive
parsing not ported"`` (see ``CHANGES.md``). The implementation lives at
``pypdfbox/util/locale_data.py`` (CLDR-derived month + weekday name
tables for 10 locales) + ``pypdfbox/util/date_util.py``
(``parse_with_locale`` tokeniser).
"""

from __future__ import annotations

import pytest

from pypdfbox.util.date_util import parse_with_locale
from pypdfbox.util.locale_data import (
    SUPPORTED_LOCALES,
    get_month_names_abbrev,
    get_month_names_full,
    get_weekday_names_abbrev,
    get_weekday_names_full,
)

_TEN_LOCALES = ("en", "fr", "de", "es", "it", "pt", "ja", "zh", "ko", "ru")


# --------------------------------------------------------------------- #
# Locale-table integrity
# --------------------------------------------------------------------- #


def test_supported_locales_lists_the_ten_target_locales() -> None:
    """Wave 1387 — exactly the 10 locales listed in the brief ship by default."""
    assert set(SUPPORTED_LOCALES) == set(_TEN_LOCALES)


@pytest.mark.parametrize("locale", _TEN_LOCALES, ids=list(_TEN_LOCALES))
def test_month_names_full_have_twelve_entries(locale: str) -> None:
    names = get_month_names_full(locale)
    assert len(names) == 12
    assert all(isinstance(name, str) and name for name in names)


@pytest.mark.parametrize("locale", _TEN_LOCALES, ids=list(_TEN_LOCALES))
def test_month_names_abbrev_have_twelve_entries(locale: str) -> None:
    names = get_month_names_abbrev(locale)
    assert len(names) == 12
    assert all(isinstance(name, str) and name for name in names)


@pytest.mark.parametrize("locale", _TEN_LOCALES, ids=list(_TEN_LOCALES))
def test_weekday_names_full_have_seven_entries(locale: str) -> None:
    names = get_weekday_names_full(locale)
    assert len(names) == 7
    assert all(isinstance(name, str) and name for name in names)


@pytest.mark.parametrize("locale", _TEN_LOCALES, ids=list(_TEN_LOCALES))
def test_weekday_names_abbrev_have_seven_entries(locale: str) -> None:
    names = get_weekday_names_abbrev(locale)
    assert len(names) == 7
    assert all(isinstance(name, str) and name for name in names)


# --------------------------------------------------------------------- #
# Full-month-name round-trips: 10 locales x 12 months
# --------------------------------------------------------------------- #


_MONTH_FULL_PARAMS = [
    (locale, month_idx)
    for locale in _TEN_LOCALES
    for month_idx in range(1, 13)
]


@pytest.mark.parametrize(
    "locale,month",
    _MONTH_FULL_PARAMS,
    ids=[f"{loc}-m{m:02d}" for loc, m in _MONTH_FULL_PARAMS],
)
def test_full_month_name_round_trip(locale: str, month: int) -> None:
    """Every full month name in every locale parses against ``MMMM yyyy``."""
    name = get_month_names_full(locale)[month - 1]
    text = f"{name} 2025"
    parsed = parse_with_locale(text, "MMMM yyyy", locale=locale)
    assert parsed is not None, f"failed to parse {text!r} for locale {locale}"
    assert parsed.month == month
    assert parsed.year == 2025


@pytest.mark.parametrize(
    "locale,month",
    _MONTH_FULL_PARAMS,
    ids=[f"{loc}-m{m:02d}" for loc, m in _MONTH_FULL_PARAMS],
)
def test_abbrev_month_name_round_trip(locale: str, month: int) -> None:
    """Every abbreviated month name in every locale parses against ``MMM yyyy``."""
    name = get_month_names_abbrev(locale)[month - 1]
    text = f"{name} 2025"
    parsed = parse_with_locale(text, "MMM yyyy", locale=locale)
    assert parsed is not None, f"failed to parse {text!r} for locale {locale}"
    assert parsed.month == month
    assert parsed.year == 2025


# --------------------------------------------------------------------- #
# Weekday-name round-trips: 10 locales x 7 weekdays
# --------------------------------------------------------------------- #


_WEEKDAY_PARAMS = [
    (locale, weekday)
    for locale in _TEN_LOCALES
    for weekday in range(7)
]


@pytest.mark.parametrize(
    "locale,weekday",
    _WEEKDAY_PARAMS,
    ids=[f"{loc}-d{d}" for loc, d in _WEEKDAY_PARAMS],
)
def test_full_weekday_name_round_trip(locale: str, weekday: int) -> None:
    """Every full weekday name in every locale parses against ``EEEE, yyyy``."""
    name = get_weekday_names_full(locale)[weekday]
    text = f"{name}, 2025"
    parsed = parse_with_locale(text, "EEEE, yyyy", locale=locale)
    assert parsed is not None, f"failed to parse {text!r} for locale {locale}"
    assert parsed.year == 2025


@pytest.mark.parametrize(
    "locale,weekday",
    _WEEKDAY_PARAMS,
    ids=[f"{loc}-d{d}" for loc, d in _WEEKDAY_PARAMS],
)
def test_abbrev_weekday_name_round_trip(locale: str, weekday: int) -> None:
    """Every abbreviated weekday name in every locale parses against ``EEE, yyyy``."""
    name = get_weekday_names_abbrev(locale)[weekday]
    text = f"{name}, 2025"
    parsed = parse_with_locale(text, "EEE, yyyy", locale=locale)
    assert parsed is not None, f"failed to parse {text!r} for locale {locale}"
    assert parsed.year == 2025


# --------------------------------------------------------------------- #
# Case-insensitive matching (mixed-case input)
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "input_text,expected_month",
    [
        ("JANUARY 2025", 1),
        ("january 2025", 1),
        ("January 2025", 1),
        ("jAnUaRy 2025", 1),
        ("DECEMBER 2025", 12),
        ("december 2025", 12),
    ],
)
def test_case_insensitive_full_month_match(
    input_text: str, expected_month: int
) -> None:
    """Mixed-case month names match against the canonical English table."""
    parsed = parse_with_locale(input_text, "MMMM yyyy", locale="en")
    assert parsed is not None, f"failed: {input_text!r}"
    assert parsed.month == expected_month


@pytest.mark.parametrize(
    "input_text,expected_weekday_present",
    [
        ("MONDAY, 2025", True),
        ("monday, 2025", True),
        ("Monday, 2025", True),
        ("MoNdAy, 2025", True),
    ],
)
def test_case_insensitive_full_weekday_match(
    input_text: str, expected_weekday_present: bool
) -> None:
    parsed = parse_with_locale(input_text, "EEEE, yyyy", locale="en")
    assert (parsed is not None) == expected_weekday_present


# --------------------------------------------------------------------- #
# Diacritic-folding matching (input without accents)
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "input_text,locale,expected_month",
    [
        # French "février" matches both with-accent and without-accent input.
        ("fevrier 2025", "fr", 2),
        ("février 2025", "fr", 2),
        ("FEVRIER 2025", "fr", 2),
        # German "März" matches both spellings.
        ("Marz 2025", "de", 3),
        ("März 2025", "de", 3),
        # Spanish "miércoles" weekday (test diacritic stripping on weekdays too).
        # This one uses EEEE in a date-shaped context.
    ],
)
def test_diacritic_insensitive_month_match(
    input_text: str, locale: str, expected_month: int
) -> None:
    """Diacritic-stripped input matches the canonical accented entry."""
    parsed = parse_with_locale(input_text, "MMMM yyyy", locale=locale)
    assert parsed is not None, f"failed: {input_text!r} for {locale}"
    assert parsed.month == expected_month


@pytest.mark.parametrize(
    "input_text,locale",
    [
        ("miercoles, 2025", "es"),
        ("miércoles, 2025", "es"),
        ("MIERCOLES, 2025", "es"),
    ],
)
def test_diacritic_insensitive_weekday_match(
    input_text: str, locale: str
) -> None:
    parsed = parse_with_locale(input_text, "EEEE, yyyy", locale=locale)
    assert parsed is not None, f"failed: {input_text!r}"


# --------------------------------------------------------------------- #
# Unknown locale fallback (Java behaviour: unknown Locale -> default)
# --------------------------------------------------------------------- #


def test_unknown_locale_falls_back_to_english() -> None:
    """Unknown locale codes fall back to English (no spurious None)."""
    parsed = parse_with_locale("January 2025", "MMMM yyyy", locale="xx-not-a-locale")
    assert parsed is not None
    assert parsed.month == 1


# --------------------------------------------------------------------- #
# Reject malformed inputs
# --------------------------------------------------------------------- #


def test_empty_input_returns_none() -> None:
    assert parse_with_locale("", "MMMM yyyy", locale="en") is None
    assert parse_with_locale("   ", "MMMM yyyy", locale="en") is None


def test_unparseable_month_name_returns_none() -> None:
    assert parse_with_locale("Smarch 2025", "MMMM yyyy", locale="en") is None


def test_missing_year_returns_none() -> None:
    assert parse_with_locale("January", "MMMM yyyy", locale="en") is None


def test_trailing_residue_returns_none() -> None:
    """Pattern must consume the entire input (after stripping outer whitespace)."""
    parsed = parse_with_locale(
        "January 2025 extra-trailing-junk", "MMMM yyyy", locale="en"
    )
    assert parsed is None


# --------------------------------------------------------------------- #
# Upstream-shape fixtures (from TestDateUtil.java)
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "input_text,pattern,expected",
    [
        # The four shapes from TestDateUtil "EEEE, MMM dd, yy" rows.
        ("Friday, January 11, 2115", "EEEE, MMM dd, yy", (2115, 1, 11)),
        ("Monday, Jan 11, 1915", "EEEE, MMM dd, yy", (1915, 1, 11)),
        ("Wed, January 11, 2215", "EEEE, MMM dd, yy", (2215, 1, 11)),
        ("Sun, January 11, 2015", "EEEE, MMM dd, yy", (2015, 1, 11)),
        # 'at' literal between date and time.
        (
            "Sun, Jul 6, 1980 at 4:23pm",
            "EEEE, MMM dd, yy 'at' hh:mma",
            (1980, 7, 6),
        ),
        # Full weekday + month + time.
        ("Monday, July 6, 1981", "EEEE, MMM dd, yy", (1981, 7, 6)),
    ],
)
def test_upstream_fixture_shapes(
    input_text: str, pattern: str, expected: tuple[int, int, int]
) -> None:
    parsed = parse_with_locale(input_text, pattern, locale="en")
    assert parsed is not None, f"failed: {input_text!r}"
    assert (parsed.year, parsed.month, parsed.day) == expected


# --------------------------------------------------------------------- #
# AM/PM handling
# --------------------------------------------------------------------- #


def test_am_pm_marker_pm_adds_twelve() -> None:
    parsed = parse_with_locale(
        "Sun, Jul 6, 1980 at 4:23pm",
        "EEEE, MMM dd, yy 'at' hh:mma",
        locale="en",
    )
    assert parsed is not None
    assert parsed.hour == 16
    assert parsed.minute == 23


def test_am_pm_marker_am_leaves_hour() -> None:
    parsed = parse_with_locale(
        "Sun, Jul 6, 1980 at 4:23am",
        "EEEE, MMM dd, yy 'at' hh:mma",
        locale="en",
    )
    assert parsed is not None
    assert parsed.hour == 4


def test_am_marker_at_noon_normalises_to_zero() -> None:
    parsed = parse_with_locale(
        "Sun, Jul 6, 1980 at 12:00am",
        "EEEE, MMM dd, yy 'at' hh:mma",
        locale="en",
    )
    assert parsed is not None
    assert parsed.hour == 0
