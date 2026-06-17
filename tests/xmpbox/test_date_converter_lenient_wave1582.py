"""Wave 1582 — lenient date-field rollover parity for ``_build_lenient``.

``org.apache.xmpbox.DateConverter.toCalendar`` (and the pdfbox.util sibling)
builds a ``java.util.Calendar`` that is **lenient** by default: out-of-range
numeric date fields roll over instead of raising. The pypdfbox port routes the
``D:YYYYMMDD…`` numeric form (and the partial / full numeric forms) through
:func:`pypdfbox.xmpbox.date_converter._build_lenient`.

The wave-1581 audit (DEFERRED.md) found two divergences, both rooted in the
**field-resolution ORDER**: the old code anchored at the year/January/day-1
base and added ``day - 1`` BEFORE applying the month offset — the inverse of
``Calendar``, which resolves ``year`` + ``month`` to the 1st of the resolved
month FIRST, then adds the day-of-month delta. That produced:

* ``"2024-06-99"`` → 2024-09-08 (one day late vs Java's 2024-09-07).
* ``"2024-00-00"`` → ``ValueError`` (Java rolls to 2023-11-30).

Wave 1582 reorders ``_build_lenient`` to match ``Calendar`` exactly. These
cases pin the Java-documented values (``java.util.GregorianCalendar`` lenient
field resolution, verified against the live ``xmpbox-3.0.7.jar`` in the
DEFERRED.md analysis).

The values here are zone-independent (date/time fields only), so they hold
regardless of the host's default zone — the strict xmpbox parser attaches the
default zone but the wall-clock fields are what these assertions check.
"""

from __future__ import annotations

from datetime import UTC

import pytest

from pypdfbox.xmpbox.date_converter import _build_lenient, to_calendar_strict


def _fields(dt) -> tuple[int, int, int, int, int, int]:
    return (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


# (D: numeric input, expected (year, month, day, hour, minute, second))
# Every input routes through the strict parser's fixed-substring path, which
# calls ``_build_lenient`` (the ``D:`` form has no ``T`` so it never hits the
# ISO fast path).
_ROLLOVER_CASES: list[tuple[str, tuple[int, int, int, int, int, int]]] = [
    # ---- the two regression cases from DEFERRED.md (wave 1581) -------------
    # Day overflow across months: June 1 + (99-1) days = Sep 7 (NOT Sep 8).
    ("D:20240699", (2024, 9, 7, 0, 0, 0)),
    # Zero month + zero day: month 0 → previous Dec, day 0 → last day of prev
    # month → 2023-11-30.
    ("D:20240000", (2023, 11, 30, 0, 0, 0)),
    # ---- month rollover ----------------------------------------------------
    # month 13 → next year's January.
    ("D:20241301", (2025, 1, 1, 0, 0, 0)),
    # month 24 → two years forward, December (month0 = 23 → +1yr, month 11).
    ("D:20242401", (2025, 12, 1, 0, 0, 0)),
    # month 00 with a valid day rolls the month back to the prior December.
    ("D:20240015", (2023, 12, 15, 0, 0, 0)),
    # ---- day rollover within / across months -------------------------------
    # Jan 32 → Feb 1.
    ("D:20240132", (2024, 2, 1, 0, 0, 0)),
    # day 0 in March → last day of February (2024 is a leap year → Feb 29).
    ("D:20240300", (2024, 2, 29, 0, 0, 0)),
    # Dec 32 → next year's Jan 1 (day overflow rolls the year).
    ("D:20241232", (2025, 1, 1, 0, 0, 0)),
    # April 0 → one day before April 1 → March 31.
    ("D:20240400", (2024, 3, 31, 0, 0, 0)),
    # ---- hour / minute / second overflow -----------------------------------
    # hour 25 → next day 01:00.
    ("D:20240101250000", (2024, 1, 2, 1, 0, 0)),
    # second 60 → +1 minute.
    ("D:20240101000060", (2024, 1, 1, 0, 1, 0)),
    # minute 90 → +1 hour 30 min.
    ("D:20240101009000", (2024, 1, 1, 1, 30, 0)),
    # hour 48 → +2 days.
    ("D:20240101480000", (2024, 1, 3, 0, 0, 0)),
    # ---- valid (in-range) dates unchanged ----------------------------------
    ("D:20240615", (2024, 6, 15, 0, 0, 0)),
    ("D:20240630000000", (2024, 6, 30, 0, 0, 0)),
    ("D:20241231235959", (2024, 12, 31, 23, 59, 59)),
    ("D:20240229", (2024, 2, 29, 0, 0, 0)),  # leap day, valid
]


@pytest.mark.parametrize(
    ("date_string", "expected"),
    _ROLLOVER_CASES,
    ids=[c[0] for c in _ROLLOVER_CASES],
)
def test_lenient_rollover_matches_java_calendar(
    date_string: str, expected: tuple[int, int, int, int, int, int]
) -> None:
    result = to_calendar_strict(date_string)
    assert result is not None
    assert _fields(result) == expected


def test_regression_2024_06_99_off_by_one_fixed() -> None:
    """DEFERRED wave-1581 case (1): day overflow was one day late."""
    result = to_calendar_strict("D:20240699")
    assert result is not None
    # Java Calendar.set(2024, 5/*June*/, 99) → 2024-09-07 (June 1 + 98 days).
    assert (result.year, result.month, result.day) == (2024, 9, 7)


def test_regression_2024_00_00_rolls_back_instead_of_raising() -> None:
    """DEFERRED wave-1581 case (2): zero month + zero day used to raise."""
    result = to_calendar_strict("D:20240000")
    assert result is not None
    # month 0 → previous December, day 0 → last day of the prior month.
    assert (result.year, result.month, result.day) == (2023, 11, 30)


def test_build_lenient_resolves_month_before_day() -> None:
    """Unit-level check of the field-resolution order on ``_build_lenient``.

    month0 = 5 (June, 0-based), day = 99: base is June 1, then +(99-1) days
    lands on Sep 7 — NOT the January-anchored Sep 8 the old order produced.
    """

    dt = _build_lenient(2024, 5, 99, 0, 0, 0, UTC)
    assert (dt.year, dt.month, dt.day) == (2024, 9, 7)


def test_build_lenient_negative_month_and_day() -> None:
    """month0 = -1, day = 0 rolls back across the year boundary."""

    dt = _build_lenient(2024, -1, 0, 0, 0, 0, UTC)
    # month0=-1 → December of the prior year, day 0 → one day before Dec 1.
    assert (dt.year, dt.month, dt.day) == (2023, 11, 30)


def test_build_lenient_valid_fields_unchanged() -> None:

    dt = _build_lenient(2024, 5, 15, 13, 30, 45, UTC)
    assert _fields(dt) == (2024, 6, 15, 13, 30, 45)
